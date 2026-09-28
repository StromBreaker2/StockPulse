from abc import ABC, abstractmethod
import logging
from typing import NamedTuple
from app import models
from app.config import settings
from app.ai import AIAdvisorClient

logger = logging.getLogger(__name__)

# Trigger condition helpers
def should_trigger_inventory_low(product: models.Product) -> bool:
    """Check if inventory is below reorder threshold."""
    return product.stock_level < product.reorder_threshold

def should_trigger_demand_spike(product: models.Product, category_avg_velocity: float, multiplier: float = 3.0) -> bool:
    """Check if demand velocity is significantly higher than category average."""
    return category_avg_velocity > 0 and product.demand_velocity > (category_avg_velocity * multiplier)

# Recommendation data structures
class PricingRecommendation:
    def __init__(
        self,
        recommended_price: float,
        direction: models.PricingDirection,
        confidence: float,
        reasoning: str
    ):
        self.recommended_price = recommended_price
        self.direction = direction
        self.confidence = confidence
        self.reasoning = reasoning

class ReorderRecommendation:
    def __init__(
        self,
        recommended_quantity: int,
        suggested_lead_time_days: int,
        confidence: float,
        reasoning: str
    ):
        self.recommended_quantity = recommended_quantity
        self.suggested_lead_time_days = suggested_lead_time_days
        self.confidence = confidence
        self.reasoning = reasoning

class RecommendationResult(NamedTuple):
    pricing: PricingRecommendation
    reorder: ReorderRecommendation

# Base Strategy Interface
class CommerceAdvisor(ABC):
    @abstractmethod
    def get_recommendations(
        self,
        product: models.Product,
        category_avg_velocity: float,
        trigger_reason: models.TriggerReason
    ) -> RecommendationResult:
        """Generate both pricing and reorder recommendations."""
        pass

    def get_pricing_recommendation(
        self,
        product: models.Product,
        category_avg_velocity: float,
        trigger_reason: models.TriggerReason
    ) -> PricingRecommendation:
        return self.get_recommendations(product, category_avg_velocity, trigger_reason).pricing

    def get_reorder_recommendation(
        self,
        product: models.Product,
        category_avg_velocity: float,
        trigger_reason: models.TriggerReason
    ) -> ReorderRecommendation:
        return self.get_recommendations(product, category_avg_velocity, trigger_reason).reorder

# 1. Deterministic Rule-Based Advisor
class RuleBasedAdvisor(CommerceAdvisor):
    def get_recommendations(
        self,
        product: models.Product,
        category_avg_velocity: float,
        trigger_reason: models.TriggerReason
    ) -> RecommendationResult:
        # Rule-based pricing logic
        current_price = product.current_price
        if product.stock_level < product.reorder_threshold:
            recommended_price = round(current_price * 1.10, 2)
            direction = models.PricingDirection.INCREASE
            price_reasoning = (
                f"Stock ({product.stock_level}) is below threshold ({product.reorder_threshold}). "
                "Rule-based advisor recommends a 10% price increase to throttle demand and protect inventory."
            )
        elif category_avg_velocity > 0 and product.demand_velocity > (2 * category_avg_velocity):
            recommended_price = round(current_price * 1.05, 2)
            direction = models.PricingDirection.INCREASE
            price_reasoning = (
                f"Demand velocity ({product.demand_velocity:.1f}) exceeds 2x category average ({category_avg_velocity:.1f}). "
                "Rule-based advisor recommends a 5% price increase to capture revenue upside."
            )
        else:
            recommended_price = round(current_price, 2)
            direction = models.PricingDirection.HOLD
            price_reasoning = "Normal inventory and demand conditions. Maintaining current price."

        pricing_rec = PricingRecommendation(
            recommended_price=recommended_price,
            direction=direction,
            confidence=0.90,
            reasoning=price_reasoning
        )

        # Rule-based reorder logic: (threshold * 3) - current_stock, minimum 1
        target_buffer = product.reorder_threshold * 3
        recommended_quantity = max(1, target_buffer - product.stock_level)
        reorder_reasoning = (
            f"Current stock ({product.stock_level}) is below target buffer ({target_buffer}). "
            f"Rule-based advisor recommends reordering {recommended_quantity} units."
        )

        reorder_rec = ReorderRecommendation(
            recommended_quantity=recommended_quantity,
            suggested_lead_time_days=7,
            confidence=0.90,
            reasoning=reorder_reasoning
        )

        return RecommendationResult(pricing=pricing_rec, reorder=reorder_rec)

# 2. AI Advisor with Automatic Rule-Based Fallback
class AIAdvisor(CommerceAdvisor):
    def __init__(self):
        self._ai_client = AIAdvisorClient()
        self._rule_fallback = RuleBasedAdvisor()

    def get_recommendations(
        self,
        product: models.Product,
        category_avg_velocity: float,
        trigger_reason: models.TriggerReason
    ) -> RecommendationResult:
        try:
            data = self._ai_client.get_recommendations_sync(product, category_avg_velocity, trigger_reason)
            pricing_rec = PricingRecommendation(
                recommended_price=data["recommended_price"],
                direction=data["direction"],
                confidence=data["price_confidence"],
                reasoning=data["price_reasoning"]
            )
            reorder_rec = ReorderRecommendation(
                recommended_quantity=data["recommended_quantity"],
                suggested_lead_time_days=data.get("suggested_lead_time_days", 7),
                confidence=data["reorder_confidence"],
                reasoning=data["reorder_reasoning"]
            )
            return RecommendationResult(pricing=pricing_rec, reorder=reorder_rec)
        except Exception as e:
            # Fallback path strictly required by business requirements
            logger.warning("AI advisor failed; using rule-based fallback.")
            return self._rule_fallback.get_recommendations(product, category_avg_velocity, trigger_reason)

# Strategy Manager
class CommerceAdvisorManager:
    def __init__(self):
        self._strategies = {
            models.StrategyType.RULE_BASED: RuleBasedAdvisor(),
            models.StrategyType.AI: AIAdvisor(),
        }
        raw_default = settings.default_strategy.upper()
        if raw_default == "RULE_BASED":
            self._current_strategy = models.StrategyType.RULE_BASED
        else:
            self._current_strategy = models.StrategyType.AI

    def set_strategy(self, strategy: models.StrategyType):
        """Switch active strategy at runtime."""
        if strategy in self._strategies:
            self._current_strategy = strategy
            logger.info(f"Commerce advisor strategy switched to {strategy.value}")
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

    def get_current_strategy(self) -> models.StrategyType:
        return self._current_strategy

    def get_advisor(self) -> CommerceAdvisor:
        return self._strategies[self._current_strategy]