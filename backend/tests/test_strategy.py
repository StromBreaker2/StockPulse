import pytest
from app import models
from app.models import Category, ProductStatus, TriggerReason, PricingDirection, StrategyType
from app.strategies import RuleBasedAdvisor, AIAdvisor, CommerceAdvisorManager
from app.ai import AIAdvisorClient, AIAdvisorError

def test_rule_based_pricing_inventory_low():
    advisor = RuleBasedAdvisor()
    product = models.Product(
        id="TEST-LOW",
        sku="SKU-LOW",
        name="Test Low Stock",
        category=Category.ELECTRONICS,
        current_price=100.0,
        stock_level=5,
        reorder_threshold=10,
        demand_velocity=2.0,
        status=ProductStatus.ACTIVE
    )
    rec = advisor.get_pricing_recommendation(product, 5.0, TriggerReason.INVENTORY_LOW)
    assert rec.direction == PricingDirection.INCREASE
    assert rec.recommended_price == 110.0  # 100 * 1.10
    assert rec.confidence == 0.90
    assert "protect inventory" in rec.reasoning.lower()

def test_rule_based_pricing_high_demand():
    advisor = RuleBasedAdvisor()
    product = models.Product(
        id="TEST-HIGH-D",
        sku="SKU-HIGH-D",
        name="High Demand Product",
        category=Category.ELECTRONICS,
        current_price=50.0,
        stock_level=40,
        reorder_threshold=10,
        demand_velocity=12.0,  # > 2 * 4.0
        status=ProductStatus.ACTIVE
    )
    rec = advisor.get_pricing_recommendation(product, 4.0, TriggerReason.DEMAND_SPIKE)
    assert rec.direction == PricingDirection.INCREASE
    assert rec.recommended_price == 52.5  # 50 * 1.05
    assert rec.confidence == 0.90

def test_rule_based_pricing_normal():
    advisor = RuleBasedAdvisor()
    product = models.Product(
        id="TEST-NORM",
        sku="SKU-NORM",
        name="Normal Product",
        category=Category.HOME,
        current_price=30.0,
        stock_level=20,
        reorder_threshold=10,
        demand_velocity=3.0,
        status=ProductStatus.ACTIVE
    )
    rec = advisor.get_pricing_recommendation(product, 3.0, TriggerReason.INITIAL)
    assert rec.direction == PricingDirection.HOLD
    assert rec.recommended_price == 30.0
    assert rec.confidence == 0.90

def test_rule_based_reorder():
    advisor = RuleBasedAdvisor()
    product = models.Product(
        id="TEST-REORDER",
        sku="SKU-REORDER",
        name="Reorder Product",
        category=Category.APPAREL,
        current_price=25.0,
        stock_level=4,
        reorder_threshold=10,
        demand_velocity=2.0,
        status=ProductStatus.ACTIVE
    )
    rec = advisor.get_reorder_recommendation(product, 2.0, TriggerReason.INVENTORY_LOW)
    # (10 * 3) - 4 = 26
    assert rec.recommended_quantity == 26
    assert rec.confidence == 0.90
    assert rec.suggested_lead_time_days == 7

def test_ai_validation_success():
    client = AIAdvisorClient()
    raw_payload = {
        "recommendedPrice": 105.0,
        "direction": "INCREASE",
        "priceConfidence": 0.88,
        "priceReasoning": "Low inventory requires temporary price hike.",
        "recommendedQuantity": 25,
        "reorderConfidence": 0.82,
        "reorderReasoning": "Replenish to maintain standard buffer."
    }
    validated = client._validate_response(raw_payload, current_price=100.0)
    assert validated["recommended_price"] == 105.0
    assert validated["direction"] == PricingDirection.INCREASE
    assert validated["price_confidence"] == 0.88
    assert validated["recommended_quantity"] == 25

def test_ai_validation_failures():
    client = AIAdvisorClient()

    # Case 1: Price exceeds 2x current price
    with pytest.raises(AIAdvisorError):
        client._validate_response({
            "recommendedPrice": 300.0,  # > 2 * 100
            "direction": "INCREASE",
            "priceConfidence": 0.8,
            "priceReasoning": "Too high",
            "recommendedQuantity": 10,
            "reorderConfidence": 0.8,
            "reorderReasoning": "Ok"
        }, current_price=100.0)

    # Case 2: Invalid direction
    with pytest.raises(AIAdvisorError):
        client._validate_response({
            "recommendedPrice": 110.0,
            "direction": "SKYROCKET",
            "priceConfidence": 0.8,
            "priceReasoning": "Invalid dir",
            "recommendedQuantity": 10,
            "reorderConfidence": 0.8,
            "reorderReasoning": "Ok"
        }, current_price=100.0)

    # Case 3: Recommended quantity < 1
    with pytest.raises(AIAdvisorError):
        client._validate_response({
            "recommendedPrice": 105.0,
            "direction": "INCREASE",
            "priceConfidence": 0.8,
            "priceReasoning": "Ok",
            "recommendedQuantity": 0,
            "reorderConfidence": 0.8,
            "reorderReasoning": "Bad qty"
        }, current_price=100.0)

def test_ai_advisor_fallback_on_failure():
    """Verify that when AI fails (e.g. unconfigured key or network error), it cleanly falls back to rule-based."""
    ai_advisor = AIAdvisor()
    product = models.Product(
        id="TEST-FALLBACK",
        sku="SKU-FALLBACK",
        name="Fallback Product",
        category=Category.ELECTRONICS,
        current_price=100.0,
        stock_level=5,
        reorder_threshold=10,
        demand_velocity=2.0,
        status=ProductStatus.ACTIVE
    )
    # Even without API key / mocked failure, get_recommendations must return a valid recommendation via RuleBased fallback
    result = ai_advisor.get_recommendations(product, 2.0, TriggerReason.INVENTORY_LOW)
    assert result.pricing.direction == PricingDirection.INCREASE
    assert result.pricing.recommended_price == 110.0
    assert result.reorder.recommended_quantity == 25  # (10 * 3) - 5
    assert result.pricing.confidence == 0.90

def test_strategy_manager_switching():
    manager = CommerceAdvisorManager()
    # Test setting RULE_BASED
    manager.set_strategy(StrategyType.RULE_BASED)
    assert manager.get_current_strategy() == StrategyType.RULE_BASED
    assert isinstance(manager.get_advisor(), RuleBasedAdvisor)

    # Test setting AI
    manager.set_strategy(StrategyType.AI)
    assert manager.get_current_strategy() == StrategyType.AI
    assert isinstance(manager.get_advisor(), AIAdvisor)