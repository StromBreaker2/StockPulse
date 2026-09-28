import logging
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, Depends, BackgroundTasks, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app import models, schemas, database, services, strategies
from app.seed import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Strategy Manager singleton
advisor_manager = strategies.CommerceAdvisorManager()

# Background task worker for reactive recommendation loop
def generate_recommendations_task(product_id: str, trigger_reason: models.TriggerReason):
    """
    Run recommendations in the background so the order or stock request
    does not wait for the LLM.
    """
    db = database.SessionLocal()
    try:
        product = services.get_product(db, product_id)
        if not product:
            logger.warning(f"Product {product_id} not found in background task.")
            return

        cat_avg = services.get_category_average_demand_velocity(db, product.category)
        advisor = advisor_manager.get_advisor()

        logger.info(f"Generating recommendations for {product.id} via {advisor_manager.get_current_strategy().value} [Trigger: {trigger_reason.value}]")
        rec_result = advisor.get_recommendations(product, cat_avg, trigger_reason)

        # Persist pricing suggestion
        services.create_pricing_suggestion(
            db,
            schemas.PricingSuggestionCreate(
                product_id=product.id,
                current_price=product.current_price,
                recommended_price=rec_result.pricing.recommended_price,
                direction=rec_result.pricing.direction,
                confidence=rec_result.pricing.confidence,
                reasoning=rec_result.pricing.reasoning,
                trigger_reason=trigger_reason
            )
        )

        # Persist reorder suggestion
        services.create_reorder_suggestion(
            db,
            schemas.ReorderSuggestionCreate(
                product_id=product.id,
                current_stock=product.stock_level,
                recommended_quantity=rec_result.reorder.recommended_quantity,
                suggested_lead_time_days=rec_result.reorder.suggested_lead_time_days,
                confidence=rec_result.reorder.confidence,
                reasoning=rec_result.reorder.reasoning,
                trigger_reason=trigger_reason
            )
        )
        logger.info(f"Background recommendations persisted for product {product.id}")
    except Exception as e:
        logger.error(f"Error executing background recommendation task for product {product_id}: {e}")
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB and seed products on startup
    try:
        init_db()
    except Exception as e:
        logger.error(f"Failed to initialize database on startup: {e}")
    yield

app = FastAPI(
    title="StockPulse — AI Inventory & Dynamic Pricing Engine",
    description="Reactive commerce advisor for inventory management and dynamic pricing",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health Check
@app.get("/health", response_model=schemas.HealthCheck)
def health_check():
    return {"status": "healthy"}

# Product Endpoints
@app.post("/products", response_model=schemas.Product, status_code=status.HTTP_201_CREATED)
def create_product(product_in: schemas.ProductCreate, db: Session = Depends(database.get_db)):
    existing = services.get_product(db, product_in.id)
    if existing:
        raise HTTPException(status_code=400, detail="Product with this ID already exists")
    return services.create_product(db, product_in)

@app.get("/products", response_model=List[schemas.Product])
def list_products(
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(database.get_db)
):
    return services.get_products(db, skip=skip, limit=limit, category=category, status=status)

@app.get("/products/{product_id}", response_model=schemas.Product)
def get_product(product_id: str, db: Session = Depends(database.get_db)):
    product = services.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@app.patch("/products/{product_id}/stock", response_model=schemas.Product)
def update_product_stock(
    product_id: str,
    stock_update: schemas.ProductUpdateStock,
    background_tasks: BackgroundTasks,
    db: Session = Depends(database.get_db)
):
    product = services.update_product_stock(db, product_id, stock_update.stock)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # If stock is below threshold, trigger INVENTORY_LOW in the background
    if product.stock_level < product.reorder_threshold:
        background_tasks.add_task(
            generate_recommendations_task,
            product_id=product.id,
            trigger_reason=models.TriggerReason.INVENTORY_LOW
        )

    return product

@app.post("/products/{product_id}/orders", response_model=schemas.Product)
def process_order(
    product_id: str,
    order: schemas.ProductOrder,
    background_tasks: BackgroundTasks,
    db: Session = Depends(database.get_db)
):
    product = services.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    if product.stock_level < order.quantity:
        raise HTTPException(status_code=400, detail="Insufficient stock for order")

    # Process order (decrease stock, increase velocity)
    updated_product = services.process_order(db, product_id, order.quantity)

    # Detect signals for reactive recommendations
    triggers = services.check_triggers(db, product_id)
    for trigger in triggers:
        # Run recommendations in the background so the order request returns immediately
        background_tasks.add_task(
            generate_recommendations_task,
            product_id=product_id,
            trigger_reason=trigger
        )

    return updated_product

# Manual Suggestion Generation Endpoints
@app.post("/products/{product_id}/suggest-pricing", response_model=schemas.PricingSuggestion)
def suggest_pricing(product_id: str, db: Session = Depends(database.get_db)):
    product = services.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    cat_avg = services.get_category_average_demand_velocity(db, product.category)
    advisor = advisor_manager.get_advisor()
    pricing_rec = advisor.get_pricing_recommendation(product, cat_avg, models.TriggerReason.MANUAL)

    return services.create_pricing_suggestion(
        db,
        schemas.PricingSuggestionCreate(
            product_id=product.id,
            current_price=product.current_price,
            recommended_price=pricing_rec.recommended_price,
            direction=pricing_rec.direction,
            confidence=pricing_rec.confidence,
            reasoning=pricing_rec.reasoning,
            trigger_reason=models.TriggerReason.MANUAL
        )
    )

@app.post("/products/{product_id}/suggest-reorder", response_model=schemas.ReorderSuggestion)
def suggest_reorder(product_id: str, db: Session = Depends(database.get_db)):
    product = services.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    cat_avg = services.get_category_average_demand_velocity(db, product.category)
    advisor = advisor_manager.get_advisor()
    reorder_rec = advisor.get_reorder_recommendation(product, cat_avg, models.TriggerReason.MANUAL)

    return services.create_reorder_suggestion(
        db,
        schemas.ReorderSuggestionCreate(
            product_id=product.id,
            current_stock=product.stock_level,
            recommended_quantity=reorder_rec.recommended_quantity,
            suggested_lead_time_days=reorder_rec.suggested_lead_time_days,
            confidence=reorder_rec.confidence,
            reasoning=reorder_rec.reasoning,
            trigger_reason=models.TriggerReason.MANUAL
        )
    )

# Suggestions & Human Approval Endpoints
@app.get("/suggestions/pending", response_model=schemas.PendingSuggestionsResponse)
def get_pending_suggestions(db: Session = Depends(database.get_db)):
    return services.get_pending_suggestions(db)

@app.patch("/pricing-suggestions/{suggestion_id}", response_model=schemas.PricingSuggestion)
def update_pricing_suggestion(
    suggestion_id: int,
    action_in: schemas.SuggestionAction,
    db: Session = Depends(database.get_db)
):
    try:
        suggestion = services.update_pricing_suggestion_status(db, suggestion_id, action_in.action)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not suggestion:
        raise HTTPException(status_code=404, detail="Pricing suggestion not found")
    return suggestion

@app.patch("/reorder-suggestions/{suggestion_id}", response_model=schemas.ReorderSuggestion)
def update_reorder_suggestion(
    suggestion_id: int,
    action_in: schemas.SuggestionAction,
    db: Session = Depends(database.get_db)
):
    try:
        suggestion = services.update_reorder_suggestion_status(db, suggestion_id, action_in.action)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not suggestion:
        raise HTTPException(status_code=404, detail="Reorder suggestion not found")
    return suggestion

# Strategy Management Endpoints
@app.get("/settings/strategy", response_model=schemas.StrategyResponse)
def get_strategy():
    return {"strategy": advisor_manager.get_current_strategy()}

@app.patch("/settings/strategy", response_model=schemas.StrategyResponse)
def update_strategy(strategy_update: schemas.StrategyUpdate):
    advisor_manager.set_strategy(strategy_update.strategy)
    return {"strategy": advisor_manager.get_current_strategy()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)