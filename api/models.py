# api/models.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float, Text
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class AdminUser(Base):
    __tablename__ = "admin_users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255))
    password_hash = Column(String(256))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tokens = relationship("AdminToken", back_populates="user", cascade="all, delete-orphan")
    measurements = relationship("Measurement", back_populates="user", cascade="all, delete-orphan")
    account_id = Column(String(64), unique=True, index=True, nullable=True)


class AdminToken(Base):
    __tablename__ = "admin_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("admin_users.id"), nullable=False)
    token = Column(String(512), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    ip_address = Column(String(45))
    user_agent = Column(String(512))
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("AdminUser", back_populates="tokens")


class AnalysisHistory(Base):
    __tablename__ = "analysis_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    color_type = Column(String(50), nullable=False)
    michelson_contrast = Column(Float, nullable=True)
    contrast_level = Column(String(50), nullable=True)
    original_photo_path = Column(String(500), nullable=False)
    legend_path = Column(String(500), nullable=True)
    visual_path = Column(String(500), nullable=True)
    palette_html_path = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Measurement(Base):
    """Измерения для анализа фигуры"""
    __tablename__ = "measurements"
    
    id = Column(String, primary_key=True)
    user_id = Column(Integer, ForeignKey("admin_users.id"), nullable=False)
    body_type = Column(String(100))
    chest_cm = Column(Float)
    waist_cm = Column(Float)
    hips_cm = Column(Float)
    height_cm = Column(Float)
    source = Column(String(50), nullable=False)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("AdminUser", back_populates="measurements")