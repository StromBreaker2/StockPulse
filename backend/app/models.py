from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, func
from sqlalchemy.orm import relationship
from app.database import Base

# Enums
class Category(str, PyEnum):
    ELECTRONICS = "ELECTRONICS"
    APPAREL = "APPAREL"
    HOME = "HOME"

class ProductStatus(str, PyEnum):
    ACTIVE = "ACTIVE"
    PRICE_REVIEW_PENDING = "PRICE_REVIEW_PENDING"
    OUT_OF_STOCK = "OUT_OF_STOCK"

class SuggestionStatus(str, PyEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"

class TriggerReason(str, PyEnum):
    INITIAL = "INITIAL"
    INVENTORY_LOW = "INVENTORY_LOW"
    DEMAND_SPIKE = "DEMAND_SPIKE"
    MANUAL = "MANUAL"

class PricingDirection(str, PyEnum):
    INCREASE = "INCREASE"
    DECREASE = "DECREASE"
    HOLD = "HOLD"

class StrategyType(str, PyEnum):
    AI = "AI"
    RULE_BASED = "RULE_BASED"

# Models
class Product(Base):
    __tablename__ = "products"
    
    id = Column(String, primary_key=True, index=True)
    sku = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    category = Column(Enum(Category, native_enum=False), nullable=False)
    current_price = Column(Float, nullable=False)
    stock_level = Column(Integer, nullable=False)
    reorder_threshold = Column(Integer, nullable=False)
    demand_velocity = Column(Float, nullable=False)
    status = Column(Enum(ProductStatus, native_enum=False), default=ProductStatus.ACTIVE, nullable=False)
    cost_price = Column(Float, nullable=True)
    supplier_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    pricing_suggestions = relationship("PricingSuggestion", back_populates="product", cascade="all, delete-orphan")
    reorder_suggestions = relationship("ReorderSuggestion", back_populates="product", cascade="all, delete-orphan")

class PricingSuggestion(Base):
    __tablename__ = "pricing_suggestions"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    current_price = Column(Float, nullable=False)
    recommended_price = Column(Float, nullable=False)
    direction = Column(Enum(PricingDirection, native_enum=False), nullable=False)
    confidence = Column(Float, nullable=False)
    reasoning = Column(String, nullable=False)
    status = Column(Enum(SuggestionStatus, native_enum=False), default=SuggestionStatus.PENDING, nullable=False)
    trigger_reason = Column(Enum(TriggerReason, native_enum=False), nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Relationship
    product = relationship("Product", back_populates="pricing_suggestions")

class ReorderSuggestion(Base):
    __tablename__ = "reorder_suggestions"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    current_stock = Column(Integer, nullable=False)
    recommended_quantity = Column(Integer, nullable=False)
    suggested_lead_time_days = Column(Integer, default=7, nullable=False)
    confidence = Column(Float, nullable=False)
    reasoning = Column(String, nullable=False)
    status = Column(Enum(SuggestionStatus, native_enum=False), default=SuggestionStatus.PENDING, nullable=False)
    trigger_reason = Column(Enum(TriggerReason, native_enum=False), nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Relationship
    product = relationship("Product", back_populates="reorder_suggestions")