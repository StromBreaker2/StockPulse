import pytest
from app import models, schemas, services
from app.models import Category, ProductStatus
from app.strategies import should_trigger_inventory_low, should_trigger_demand_spike

def test_health_endpoint(client):
    """Test GET /health returns 200 and healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_create_product(db_session, client):
    """Test product creation via service and API."""
    payload = {
        "id": "TEST-001",
        "sku": "SKU-TEST-001",
        "name": "Test Wireless Earbuds",
        "category": "ELECTRONICS",
        "current_price": 49.99,
        "stock_level": 50,
        "reorder_threshold": 15,
        "demand_velocity": 4.0
    }
    response = client.post("/products", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == "TEST-001"
    assert data["name"] == "Test Wireless Earbuds"
    assert data["stock_level"] == 50
    assert data["status"] == "ACTIVE"

def test_list_products(db_session, client):
    """Test product listing and filtering."""
    p1 = schemas.ProductCreate(
        id="P-01",
        sku="SKU-01",
        name="T-Shirt",
        category=Category.APPAREL,
        current_price=20.0,
        stock_level=10,
        reorder_threshold=5,
        demand_velocity=2.0
    )
    p2 = schemas.ProductCreate(
        id="P-02",
        sku="SKU-02",
        name="Coffee Maker",
        category=Category.HOME,
        current_price=60.0,
        stock_level=5,
        reorder_threshold=5,
        demand_velocity=1.0
    )
    services.create_product(db_session, p1)
    services.create_product(db_session, p2)

    response = client.get("/products")
    assert response.status_code == 200
    products = response.json()
    assert len(products) >= 2
    product_ids = [p["id"] for p in products]
    assert "P-01" in product_ids
    assert "P-02" in product_ids

    # Filter by category
    apparel_resp = client.get("/products?category=APPAREL")
    assert apparel_resp.status_code == 200
    apparel_ids = [p["id"] for p in apparel_resp.json()]
    assert "P-01" in apparel_ids
    assert "P-02" not in apparel_ids

def test_simulated_order_decreases_stock(db_session, client):
    """Test that placing an order decreases stock and increases demand velocity."""
    p = schemas.ProductCreate(
        id="P-ORDER",
        sku="SKU-ORD",
        name="Water Bottle",
        category=Category.HOME,
        current_price=15.0,
        stock_level=10,
        reorder_threshold=5,
        demand_velocity=2.0
    )
    services.create_product(db_session, p)

    # Place order for 3 items
    response = client.post("/products/P-ORDER/orders", json={"quantity": 3})
    assert response.status_code == 200
    data = response.json()
    assert data["stock_level"] == 7
    assert data["demand_velocity"] == 3.5  # 2.0 + (0.5 * 3)

def test_inventory_low_detection():
    """Test inventory low condition."""
    low_stock_prod = models.Product(
        id="LOW",
        sku="SKU-LOW",
        name="Low Item",
        category=Category.ELECTRONICS,
        current_price=10.0,
        stock_level=4,
        reorder_threshold=10,
        demand_velocity=2.0,
        status=ProductStatus.ACTIVE
    )
    assert should_trigger_inventory_low(low_stock_prod) is True

    normal_stock_prod = models.Product(
        id="NORM",
        sku="SKU-NORM",
        name="Normal Item",
        category=Category.ELECTRONICS,
        current_price=10.0,
        stock_level=15,
        reorder_threshold=10,
        demand_velocity=2.0,
        status=ProductStatus.ACTIVE
    )
    assert should_trigger_inventory_low(normal_stock_prod) is False

def test_demand_spike_detection():
    """Test demand spike condition."""
    spike_prod = models.Product(
        id="SPIKE",
        sku="SKU-SPIKE",
        name="Spike Item",
        category=Category.APPAREL,
        current_price=20.0,
        stock_level=50,
        reorder_threshold=10,
        demand_velocity=15.0,
        status=ProductStatus.ACTIVE
    )
    category_avg = 3.0
    multiplier = 3.0
    # 15.0 > (3.0 * 3.0 = 9.0) -> True
    assert should_trigger_demand_spike(spike_prod, category_avg, multiplier) is True

    normal_prod = models.Product(
        id="NO-SPIKE",
        sku="SKU-NO-SPIKE",
        name="Regular Item",
        category=Category.APPAREL,
        current_price=20.0,
        stock_level=50,
        reorder_threshold=10,
        demand_velocity=6.0,
        status=ProductStatus.ACTIVE
    )
    # 6.0 <= 9.0 -> False
    assert should_trigger_demand_spike(normal_prod, category_avg, multiplier) is False