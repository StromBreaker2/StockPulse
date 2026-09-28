from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.models import (
    Category,
    ProductStatus,
    SuggestionStatus,
    TriggerReason,
    PricingDirection,
    StrategyType,
)

# Product Schemas
class ProductBase(BaseModel):
    sku: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    category: Category
    current_price: float = Field(..., gt=0, description="Price must be positive")
    stock_level: int = Field(..., ge=0, description="Stock cannot be negative")
    reorder_threshold: int = Field(..., gt=0, description="Threshold must be positive")
    demand_velocity: float = Field(default=0.0, ge=0)
    cost_price: Optional[float] = None
    supplier_id: Optional[str] = None

class ProductCreate(ProductBase):
    id: str = Field(..., min_length=1)

class ProductUpdateStock(BaseModel):
    stock: int = Field(..., ge=0)

class ProductOrder(BaseModel):
    quantity: int = Field(..., gt=0)

class Product(ProductBase):
    id: str
    status: ProductStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

# Pricing Suggestion Schemas
class PricingSuggestionBase(BaseModel):
    product_id: str
    current_price: float
    recommended_price: float
    direction: PricingDirection
    confidence: float
    reasoning: str
    trigger_reason: TriggerReason

class PricingSuggestionCreate(PricingSuggestionBase):
    pass

class PricingSuggestion(PricingSuggestionBase):
    id: int
    status: SuggestionStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# Reorder Suggestion Schemas
class ReorderSuggestionBase(BaseModel):
    product_id: str
    current_stock: int
    recommended_quantity: int
    suggested_lead_time_days: int = 7
    confidence: float
    reasoning: str
    trigger_reason: TriggerReason

class ReorderSuggestionCreate(ReorderSuggestionBase):
    pass

class ReorderSuggestion(ReorderSuggestionBase):
    id: int
    status: SuggestionStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class PendingSuggestionsResponse(BaseModel):
    pricing: List[PricingSuggestion]
    reorder: List[ReorderSuggestion]

    model_config = ConfigDict(from_attributes=True)

# Strategy Schemas
class StrategyResponse(BaseModel):
    strategy: StrategyType

class StrategyUpdate(BaseModel):
    strategy: StrategyType

# Suggestion Action Schema (Supports ACCEPT/REJECT or ACCEPTED/REJECTED)
class SuggestionAction(BaseModel):
    action: str

    @field_validator("action")
    @classmethod
    def normalize_action(cls, v: str) -> str:
        v_upper = v.strip().upper()
        if v_upper in ["ACCEPT", "ACCEPTED"]:
            return "ACCEPTED"
        if v_upper in ["REJECT", "REJECTED"]:
            return "REJECTED"
        raise ValueError("Action must be ACCEPT or REJECT")

# Health Check
class HealthCheck(BaseModel):
    status: str