import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from app import models, schemas
from app.config import settings
from app.strategies import should_trigger_inventory_low, should_trigger_demand_spike

logger = logging.getLogger(__name__)

# Product Operations
def get_product(db: Session, product_id: str) -> Optional[models.Product]:
    return db.query(models.Product).filter(models.Product.id == product_id).first()

def get_products(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = None,
    status: Optional[str] = None
) -> List[models.Product]:
    query = db.query(models.Product)
    if category:
        query = query.filter(models.Product.category == category)
    if status:
        query = query.filter(models.Product.status == status)
    return query.order_by(models.Product.id).offset(skip).limit(limit).all()

def create_product(db: Session, product_in: schemas.ProductCreate) -> models.Product:
    # Set initial status according to inventory rules
    initial_status = models.ProductStatus.OUT_OF_STOCK if product_in.stock_level == 0 else models.ProductStatus.ACTIVE
    
    db_product = models.Product(
        id=product_in.id,
        sku=product_in.sku,
        name=product_in.name,
        category=product_in.category,
        current_price=product_in.current_price,
        stock_level=product_in.stock_level,
        reorder_threshold=product_in.reorder_threshold,
        demand_velocity=product_in.demand_velocity,
        status=initial_status,
        cost_price=product_in.cost_price,
        supplier_id=product_in.supplier_id,
    )
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

def update_product_stock(db: Session, product_id: str, stock: int) -> Optional[models.Product]:
    db_product = get_product(db, product_id)
    if not db_product:
        return None

    db_product.stock_level = stock
    if stock == 0:
        db_product.status = models.ProductStatus.OUT_OF_STOCK
    else:
        db_product.status = models.ProductStatus.ACTIVE

    db.commit()
    db.refresh(db_product)
    return db_product

def process_order(db: Session, product_id: str, quantity: int) -> Optional[models.Product]:
    """Validate sufficient stock, decrease inventory, increase demand velocity."""
    db_product = get_product(db, product_id)
    if not db_product:
        return None

    if db_product.stock_level < quantity:
        return None

    db_product.stock_level -= quantity
    db_product.demand_velocity += 0.5 * quantity

    if db_product.stock_level == 0:
        db_product.status = models.ProductStatus.OUT_OF_STOCK
    else:
        db_product.status = models.ProductStatus.ACTIVE

    db.commit()
    db.refresh(db_product)
    return db_product

# Category Analytics
def get_category_average_demand_velocity(db: Session, category: models.Category) -> float:
    avg_velocity = db.query(func.avg(models.Product.demand_velocity)).filter(
        models.Product.category == category
    ).scalar()
    return float(avg_velocity) if avg_velocity is not None else 0.0

# Trigger Detection
def check_triggers(db: Session, product_id: str) -> List[models.TriggerReason]:
    product = get_product(db, product_id)
    if not product:
        return []

    triggers: List[models.TriggerReason] = []
    
    # 1. Check Inventory Low
    if should_trigger_inventory_low(product):
        triggers.append(models.TriggerReason.INVENTORY_LOW)

    # 2. Check Demand Spike
    cat_avg = get_category_average_demand_velocity(db, product.category)
    if should_trigger_demand_spike(product, cat_avg, settings.demand_spike_multiplier):
        triggers.append(models.TriggerReason.DEMAND_SPIKE)

    return triggers

# Suggestion Operations & Duplicate Prevention
def create_pricing_suggestion(
    db: Session,
    suggestion_in: schemas.PricingSuggestionCreate
) -> models.PricingSuggestion:
    # Duplicate prevention: same product + same trigger + PENDING
    existing = db.query(models.PricingSuggestion).filter(
        models.PricingSuggestion.product_id == suggestion_in.product_id,
        models.PricingSuggestion.trigger_reason == suggestion_in.trigger_reason,
        models.PricingSuggestion.status == models.SuggestionStatus.PENDING
    ).first()

    if existing:
        logger.info(f"Duplicate PENDING pricing suggestion detected for product {suggestion_in.product_id}. Skipping insert.")
        return existing

    db_suggestion = models.PricingSuggestion(
        product_id=suggestion_in.product_id,
        current_price=suggestion_in.current_price,
        recommended_price=suggestion_in.recommended_price,
        direction=suggestion_in.direction,
        confidence=suggestion_in.confidence,
        reasoning=suggestion_in.reasoning,
        trigger_reason=suggestion_in.trigger_reason,
        status=models.SuggestionStatus.PENDING
    )
    db.add(db_suggestion)
    db.commit()
    db.refresh(db_suggestion)
    return db_suggestion

def create_reorder_suggestion(
    db: Session,
    suggestion_in: schemas.ReorderSuggestionCreate
) -> models.ReorderSuggestion:
    # Duplicate prevention: same product + same trigger + PENDING
    existing = db.query(models.ReorderSuggestion).filter(
        models.ReorderSuggestion.product_id == suggestion_in.product_id,
        models.ReorderSuggestion.trigger_reason == suggestion_in.trigger_reason,
        models.ReorderSuggestion.status == models.SuggestionStatus.PENDING
    ).first()

    if existing:
        logger.info(f"Duplicate PENDING reorder suggestion detected for product {suggestion_in.product_id}. Skipping insert.")
        return existing

    db_suggestion = models.ReorderSuggestion(
        product_id=suggestion_in.product_id,
        current_stock=suggestion_in.current_stock,
        recommended_quantity=suggestion_in.recommended_quantity,
        suggested_lead_time_days=suggestion_in.suggested_lead_time_days,
        confidence=suggestion_in.confidence,
        reasoning=suggestion_in.reasoning,
        trigger_reason=suggestion_in.trigger_reason,
        status=models.SuggestionStatus.PENDING
    )
    db.add(db_suggestion)
    db.commit()
    db.refresh(db_suggestion)
    return db_suggestion

def get_pending_pricing_suggestions(db: Session) -> List[models.PricingSuggestion]:
    return db.query(models.PricingSuggestion).filter(
        models.PricingSuggestion.status == models.SuggestionStatus.PENDING
    ).order_by(models.PricingSuggestion.created_at.desc()).all()

def get_pending_reorder_suggestions(db: Session) -> List[models.ReorderSuggestion]:
    return db.query(models.ReorderSuggestion).filter(
        models.ReorderSuggestion.status == models.SuggestionStatus.PENDING
    ).order_by(models.ReorderSuggestion.created_at.desc()).all()

def get_pending_suggestions(db: Session) -> Dict[str, Any]:
    return {
        "pricing": get_pending_pricing_suggestions(db),
        "reorder": get_pending_reorder_suggestions(db)
    }

# Human Approval Handlers
def update_pricing_suggestion_status(
    db: Session,
    suggestion_id: int,
    action: str
) -> Optional[models.PricingSuggestion]:
    suggestion = db.query(models.PricingSuggestion).filter(
        models.PricingSuggestion.id == suggestion_id
    ).first()
    if not suggestion:
        return None

    # Prevent re-accepting or re-rejecting
    if suggestion.status != models.SuggestionStatus.PENDING:
        raise ValueError(f"Suggestion has already been {suggestion.status.value}")

    norm_action = models.SuggestionStatus(action)
    suggestion.status = norm_action

    if norm_action == models.SuggestionStatus.ACCEPTED:
        product = get_product(db, suggestion.product_id)
        if product:
            product.current_price = suggestion.recommended_price

    db.commit()
    db.refresh(suggestion)
    return suggestion

def update_reorder_suggestion_status(
    db: Session,
    suggestion_id: int,
    action: str
) -> Optional[models.ReorderSuggestion]:
    suggestion = db.query(models.ReorderSuggestion).filter(
        models.ReorderSuggestion.id == suggestion_id
    ).first()
    if not suggestion:
        return None

    # Prevent re-accepting or re-rejecting
    if suggestion.status != models.SuggestionStatus.PENDING:
        raise ValueError(f"Suggestion has already been {suggestion.status.value}")

    norm_action = models.SuggestionStatus(action)
    suggestion.status = norm_action

    if norm_action == models.SuggestionStatus.ACCEPTED:
        product = get_product(db, suggestion.product_id)
        if product:
            product.stock_level += suggestion.recommended_quantity
            if product.stock_level > 0 and product.status == models.ProductStatus.OUT_OF_STOCK:
                product.status = models.ProductStatus.ACTIVE

    db.commit()
    db.refresh(suggestion)
    return suggestion