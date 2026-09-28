import re
import json
import logging
import httpx
from typing import Dict, Any
from app.config import settings
from app import models

logger = logging.getLogger(__name__)

class AIAdvisorError(Exception):
    """Raised when the AI advisor fails to produce a valid recommendation."""
    pass

class AIAdvisorClient:
    def __init__(self):
        self.api_key = settings.llm_api_key
        self.base_url = settings.llm_base_url.rstrip("/")
        self.model = settings.llm_model
        self.product = settings.llm_product
        self.cookie = settings.llm_cookie

    def _build_prompt(
        self,
        product: models.Product,
        category_avg_velocity: float,
        trigger_reason: models.TriggerReason
    ) -> str:
        """Build contextual prompt differentiated by trigger condition."""
        if trigger_reason == models.TriggerReason.INVENTORY_LOW:
            context = (
                "BUSINESS CONTEXT: Inventory scarcity alert. Current stock is below reorder threshold. "
                "Evaluate whether a modest price increase is warranted to throttle demand and protect inventory "
                "while recommending an urgent replenishment order quantity."
            )
        elif trigger_reason == models.TriggerReason.DEMAND_SPIKE:
            context = (
                "BUSINESS CONTEXT: Demand spike alert. Demand velocity significantly exceeds the category average. "
                "Consider a modest dynamic price increase to capture revenue upside while balancing customer price "
                "elasticity, and recommend a higher reorder quantity to prevent stockout."
            )
        else:
            context = (
                "BUSINESS CONTEXT: Routine inventory evaluation. "
                "Analyze velocity and current stock levels to recommend optimal pricing and replenishment."
            )

        return f"""You are a dynamic pricing and inventory commerce advisor for an e-commerce platform.

{context}

Product Details:
- SKU: {product.sku}
- Name: {product.name}
- Category: {product.category.value if hasattr(product.category, 'value') else product.category}
- Current Price: ${product.current_price:.2f}
- Current Stock: {product.stock_level}
- Reorder Threshold: {product.reorder_threshold}
- Demand Velocity: {product.demand_velocity:.2f}
- Category Average Demand Velocity: {category_avg_velocity:.2f}
- Trigger: {trigger_reason.value if hasattr(trigger_reason, 'value') else trigger_reason}

Respond with ONLY a JSON object in this exact shape:
{{
  "recommendedPrice": 29.99,
  "direction": "INCREASE",
  "priceConfidence": 0.85,
  "priceReasoning": "Concise business justification for pricing decision",
  "recommendedQuantity": 30,
  "reorderConfidence": 0.80,
  "reorderReasoning": "Concise business justification for reorder quantity"
}}
"""

    def _extract_json(self, response_text: str) -> Dict[str, Any]:
        """Extract and parse JSON from response text, supporting markdown fences or surrounding text."""
        # Check for ```json ... ``` or ``` ... ```
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
        if fence_match:
            try:
                return json.loads(fence_match.group(1))
            except json.JSONDecodeError:
                pass

        # Check for raw {...}
        brace_match = re.search(r"(\{.*\})", response_text, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(1))
            except json.JSONDecodeError:
                pass

        raise AIAdvisorError("Failed to extract valid JSON from LLM response")

    def _validate_response(
        self,
        data: Dict[str, Any],
        current_price: float
    ) -> Dict[str, Any]:
        """Validate LLM output against required constraints."""
        # Validate recommendedPrice
        rec_price = data.get("recommendedPrice")
        if not isinstance(rec_price, (int, float)) or rec_price <= 0:
            raise AIAdvisorError(f"Invalid recommendedPrice: {rec_price}")
        if rec_price > current_price * 2:
            raise AIAdvisorError(f"recommendedPrice {rec_price} exceeds 2x current price {current_price}")

        # Validate direction
        direction = str(data.get("direction", "")).upper()
        if direction not in ["INCREASE", "DECREASE", "HOLD"]:
            raise AIAdvisorError(f"Invalid direction: {direction}")

        # Validate priceConfidence
        price_conf = data.get("priceConfidence")
        if not isinstance(price_conf, (int, float)) or not (0.0 <= price_conf <= 1.0):
            raise AIAdvisorError(f"Invalid priceConfidence: {price_conf}")

        # Validate priceReasoning
        price_reason = data.get("priceReasoning")
        if not isinstance(price_reason, str) or not price_reason.strip():
            raise AIAdvisorError("Missing or invalid priceReasoning")

        # Validate recommendedQuantity
        rec_qty = data.get("recommendedQuantity")
        if not isinstance(rec_qty, (int, float)) or int(rec_qty) < 1:
            raise AIAdvisorError(f"Invalid recommendedQuantity: {rec_qty}")
        rec_qty = int(rec_qty)

        # Validate reorderConfidence
        reorder_conf = data.get("reorderConfidence")
        if not isinstance(reorder_conf, (int, float)) or not (0.0 <= reorder_conf <= 1.0):
            raise AIAdvisorError(f"Invalid reorderConfidence: {reorder_conf}")

        # Validate reorderReasoning
        reorder_reason = data.get("reorderReasoning")
        if not isinstance(reorder_reason, str) or not reorder_reason.strip():
            raise AIAdvisorError("Missing or invalid reorderReasoning")

        return {
            "recommended_price": round(float(rec_price), 2),
            "direction": models.PricingDirection(direction),
            "price_confidence": float(price_conf),
            "price_reasoning": price_reason.strip(),
            "recommended_quantity": rec_qty,
            "reorder_confidence": float(reorder_conf),
            "reorder_reasoning": reorder_reason.strip(),
            "suggested_lead_time_days": 7
        }

    async def get_recommendations_async(
        self,
        product: models.Product,
        category_avg_velocity: float,
        trigger_reason: models.TriggerReason
    ) -> Dict[str, Any]:
        """Fetch and validate AI recommendations asynchronously."""
        if not self.api_key:
            raise AIAdvisorError("LLM_API_KEY is not configured")

        prompt = self._build_prompt(product, category_avg_velocity, trigger_reason)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "product": self.product,
        }
        if self.cookie:
            headers["Cookie"] = self.cookie

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a professional retail merchandising advisor. Output only strict JSON."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }

        url = f"{self.base_url}/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as e:
            raise AIAdvisorError(f"LLM request timed out: {e}")
        except httpx.HTTPError as e:
            raise AIAdvisorError(f"LLM HTTP error: {e}")
        except Exception as e:
            raise AIAdvisorError(f"LLM communication error: {e}")

        try:
            choices = data.get("choices", [])
            if not choices:
                raise AIAdvisorError("No choices in LLM response")
            raw_text = choices[0]["message"]["content"]
            parsed_json = self._extract_json(raw_text)
            return self._validate_response(parsed_json, product.current_price)
        except AIAdvisorError:
            raise
        except Exception as e:
            raise AIAdvisorError(f"Error parsing LLM response: {e}")

    def get_recommendations_sync(
        self,
        product: models.Product,
        category_avg_velocity: float,
        trigger_reason: models.TriggerReason
    ) -> Dict[str, Any]:
        """Synchronous wrapper for contexts where an event loop is already running or absent."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    return pool.submit(
                        asyncio.run,
                        self.get_recommendations_async(product, category_avg_velocity, trigger_reason)
                    ).result()
            else:
                return loop.run_until_complete(
                    self.get_recommendations_async(product, category_avg_velocity, trigger_reason)
                )
        except Exception as e:
            if isinstance(e, AIAdvisorError):
                raise
            raise AIAdvisorError(f"Synchronous execution failed: {e}")