import logging
from app.models import Product, Category, ProductStatus
from app.database import SessionLocal, engine, Base

logger = logging.getLogger(__name__)

def init_db():
    """Initialize database tables and insert seed data if empty."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized.")

    db = SessionLocal()
    try:
        count = db.query(Product).count()
        if count == 0:
            logger.info("Database is empty. Seeding initial products...")
            products = [
                Product(
                    id="PRD-001",
                    sku="SKU-ELEC-001",
                    name="Wireless Earbuds Pro",
                    category=Category.ELECTRONICS,
                    current_price=79.99,
                    stock_level=45,
                    reorder_threshold=20,
                    demand_velocity=3.0,
                    status=ProductStatus.ACTIVE
                ),
                Product(
                    id="PRD-002",
                    sku="SKU-ELEC-002",
                    name="USB-C Hub 7-Port",
                    category=Category.ELECTRONICS,
                    current_price=34.99,
                    stock_level=120,
                    reorder_threshold=30,
                    demand_velocity=1.0,
                    status=ProductStatus.ACTIVE
                ),
                Product(
                    id="PRD-003",
                    sku="SKU-APP-001",
                    name="Organic Cotton T-Shirt",
                    category=Category.APPAREL,
                    current_price=24.99,
                    stock_level=8,
                    reorder_threshold=15,
                    demand_velocity=12.0,
                    status=ProductStatus.ACTIVE
                ),
                Product(
                    id="PRD-004",
                    sku="SKU-APP-002",
                    name="Running Shorts - Navy",
                    category=Category.APPAREL,
                    current_price=39.99,
                    stock_level=55,
                    reorder_threshold=20,
                    demand_velocity=2.0,
                    status=ProductStatus.ACTIVE
                ),
                Product(
                    id="PRD-005",
                    sku="SKU-HOME-001",
                    name="Ceramic Pour-Over Set",
                    category=Category.HOME,
                    current_price=49.99,
                    stock_level=22,
                    reorder_threshold=10,
                    demand_velocity=4.0,
                    status=ProductStatus.ACTIVE
                ),
                Product(
                    id="PRD-006",
                    sku="SKU-HOME-002",
                    name="LED Desk Lamp - Dimmable",
                    category=Category.HOME,
                    current_price=59.99,
                    stock_level=0,
                    reorder_threshold=15,
                    demand_velocity=0.0,
                    status=ProductStatus.OUT_OF_STOCK
                ),
                Product(
                    id="PRD-007",
                    sku="SKU-ELEC-003",
                    name="Portable Charger 20K",
                    category=Category.ELECTRONICS,
                    current_price=44.99,
                    stock_level=18,
                    reorder_threshold=25,
                    demand_velocity=8.0,
                    status=ProductStatus.ACTIVE
                ),
                Product(
                    id="PRD-008",
                    sku="SKU-APP-003",
                    name="Hoodie - Heather Grey",
                    category=Category.APPAREL,
                    current_price=54.99,
                    stock_level=11,
                    reorder_threshold=12,
                    demand_velocity=15.0,
                    status=ProductStatus.ACTIVE
                )
            ]
            for p in products:
                db.add(p)
            db.commit()
            logger.info("Successfully seeded 8 initial products.")
        else:
            logger.info(f"Database already contains {count} products. Skipping seeding.")
    except Exception as e:
        logger.error(f"Error during database initialization/seeding: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_db()