import pytest
from app import models, schemas, services
from app.models import Category, ProductStatus, SuggestionStatus, TriggerReason, PricingDirection

def test_duplicate_prevention(db_session):
    """Test that creating a duplicate PENDING suggestion for the same product and trigger returns the existing one."""
    product_in = schemas.ProductCreate(
        id="P-DUP",
        sku="SKU-DUP",
        name="Dup Test Product",
        category=Category.ELECTRONICS,
        current_price=50.0,
        stock_level=5,
        reorder_threshold=10,
        demand_velocity=1.0
    )
    services.create_product(db_session, product_in)

    sug1_in = schemas.PricingSuggestionCreate(
        product_id="P-DUP",
        current_price=50.0,
        recommended_price=55.0,
        direction=PricingDirection.INCREASE,
        confidence=0.90,
        reasoning="First suggestion",
        trigger_reason=TriggerReason.INVENTORY_LOW
    )
    sug1 = services.create_pricing_suggestion(db_session, sug1_in)

    sug2_in = schemas.PricingSuggestionCreate(
        product_id="P-DUP",
        current_price=50.0,
        recommended_price=60.0,
        direction=PricingDirection.INCREASE,
        confidence=0.95,
        reasoning="Second suggestion attempt",
        trigger_reason=TriggerReason.INVENTORY_LOW
    )
    sug2 = services.create_pricing_suggestion(db_session, sug2_in)

    # Must return the existing suggestion
    assert sug1.id == sug2.id
    assert sug2.recommended_price == 55.0  # Original kept

def test_pricing_accept_updates_product_price(db_session, client):
    """Test that accepting a pricing suggestion updates the product price."""
    product_in = schemas.ProductCreate(
        id="P-PRC-ACC",
        sku="SKU-PRC-ACC",
        name="Price Accept Item",
        category=Category.ELECTRONICS,
        current_price=100.0,
        stock_level=10,
        reorder_threshold=15,
        demand_velocity=2.0
    )
    services.create_product(db_session, product_in)

    sug_in = schemas.PricingSuggestionCreate(
        product_id="P-PRC-ACC",
        current_price=100.0,
        recommended_price=110.0,
        direction=PricingDirection.INCREASE,
        confidence=0.90,
        reasoning="10% hike",
        trigger_reason=TriggerReason.INVENTORY_LOW
    )
    sug = services.create_pricing_suggestion(db_session, sug_in)

    resp = client.patch(f"/pricing-suggestions/{sug.id}", json={"action": "ACCEPT"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ACCEPTED"

    # Verify product price was updated
    prod = services.get_product(db_session, "P-PRC-ACC")
    assert prod.current_price == 110.0

def test_pricing_reject_leaves_product_price_unchanged(db_session, client):
    """Test that rejecting a pricing suggestion leaves product price unchanged."""
    product_in = schemas.ProductCreate(
        id="P-PRC-REJ",
        sku="SKU-PRC-REJ",
        name="Price Reject Item",
        category=Category.APPAREL,
        current_price=40.0,
        stock_level=10,
        reorder_threshold=15,
        demand_velocity=2.0
    )
    services.create_product(db_session, product_in)

    sug_in = schemas.PricingSuggestionCreate(
        product_id="P-PRC-REJ",
        current_price=40.0,
        recommended_price=45.0,
        direction=PricingDirection.INCREASE,
        confidence=0.90,
        reasoning="Proposed hike",
        trigger_reason=TriggerReason.INVENTORY_LOW
    )
    sug = services.create_pricing_suggestion(db_session, sug_in)

    resp = client.patch(f"/pricing-suggestions/{sug.id}", json={"action": "REJECT"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "REJECTED"

    prod = services.get_product(db_session, "P-PRC-REJ")
    assert prod.current_price == 40.0

def test_reorder_accept_updates_product_stock(db_session, client):
    """Test that accepting a reorder suggestion increases product stock level."""
    product_in = schemas.ProductCreate(
        id="P-REO-ACC",
        sku="SKU-REO-ACC",
        name="Reorder Accept Item",
        category=Category.HOME,
        current_price=25.0,
        stock_level=5,
        reorder_threshold=15,
        demand_velocity=1.0
    )
    services.create_product(db_session, product_in)

    sug_in = schemas.ReorderSuggestionCreate(
        product_id="P-REO-ACC",
        current_stock=5,
        recommended_quantity=40,
        suggested_lead_time_days=7,
        confidence=0.90,
        reasoning="Replenish stock",
        trigger_reason=TriggerReason.INVENTORY_LOW
    )
    sug = services.create_reorder_suggestion(db_session, sug_in)

    resp = client.patch(f"/reorder-suggestions/{sug.id}", json={"action": "ACCEPT"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ACCEPTED"

    prod = services.get_product(db_session, "P-REO-ACC")
    assert prod.stock_level == 45  # 5 + 40

def test_reorder_reject_leaves_stock_unchanged(db_session, client):
    """Test that rejecting a reorder suggestion leaves product stock unchanged."""
    product_in = schemas.ProductCreate(
        id="P-REO-REJ",
        sku="SKU-REO-REJ",
        name="Reorder Reject Item",
        category=Category.HOME,
        current_price=25.0,
        stock_level=8,
        reorder_threshold=15,
        demand_velocity=1.0
    )
    services.create_product(db_session, product_in)

    sug_in = schemas.ReorderSuggestionCreate(
        product_id="P-REO-REJ",
        current_stock=8,
        recommended_quantity=37,
        suggested_lead_time_days=7,
        confidence=0.90,
        reasoning="Replenish stock",
        trigger_reason=TriggerReason.INVENTORY_LOW
    )
    sug = services.create_reorder_suggestion(db_session, sug_in)

    resp = client.patch(f"/reorder-suggestions/{sug.id}", json={"action": "REJECT"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "REJECTED"

    prod = services.get_product(db_session, "P-REO-REJ")
    assert prod.stock_level == 8

def test_cannot_re_decide_suggestion(db_session, client):
    """Test that once accepted or rejected, a suggestion cannot be modified again."""
    product_in = schemas.ProductCreate(
        id="P-LOCK",
        sku="SKU-LOCK",
        name="Lock Test Item",
        category=Category.HOME,
        current_price=25.0,
        stock_level=8,
        reorder_threshold=15,
        demand_velocity=1.0
    )
    services.create_product(db_session, product_in)

    sug_in = schemas.PricingSuggestionCreate(
        product_id="P-LOCK",
        current_price=25.0,
        recommended_price=30.0,
        direction=PricingDirection.INCREASE,
        confidence=0.90,
        reasoning="Test",
        trigger_reason=TriggerReason.MANUAL
    )
    sug = services.create_pricing_suggestion(db_session, sug_in)

    # First accept
    resp1 = client.patch(f"/pricing-suggestions/{sug.id}", json={"action": "ACCEPT"})
    assert resp1.status_code == 200

    # Second accept/reject should fail
    resp2 = client.patch(f"/pricing-suggestions/{sug.id}", json={"action": "REJECT"})
    assert resp2.status_code == 400