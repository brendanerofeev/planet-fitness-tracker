"""
SQLAlchemy models for Planet Fitness Tracker
Maps to existing SQLite schema for backward compatibility
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Float, ForeignKey, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Gym(Base):
    """Gym/Club location model"""
    __tablename__ = 'gyms'

    id = Column(Integer, primary_key=True, autoincrement=True)
    club_name = Column(Text, unique=True, nullable=False)
    club_address = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship to capacity logs
    capacity_logs = relationship('CapacityLog', back_populates='gym', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Gym(id={self.id}, name='{self.club_name}')>"


class CapacityLog(Base):
    """Capacity log entry for a gym"""
    __tablename__ = 'capacity_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    gym_id = Column(Integer, ForeignKey('gyms.id'), nullable=False)
    users_count = Column(Integer, nullable=False)
    users_limit = Column(Integer, nullable=True)
    timestamp = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship to gym
    gym = relationship('Gym', back_populates='capacity_logs')

    # Indexes
    __table_args__ = (
        Index('idx_capacity_logs_timestamp', 'timestamp'),
        Index('idx_capacity_logs_gym_id', 'gym_id'),
    )

    def __repr__(self):
        return f"<CapacityLog(id={self.id}, gym_id={self.gym_id}, count={self.users_count}, timestamp={self.timestamp})>"


class Credential(Base):
    """User credentials for Planet Fitness login"""
    __tablename__ = 'credentials'

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(Text, nullable=False)
    password = Column(Text, nullable=False)  # TODO: Should be encrypted
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Credential(id={self.id}, email='{self.email}')>"


class SyncHistory(Base):
    """History of data synchronization operations"""
    __tablename__ = 'sync_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    status = Column(Text, nullable=False)  # 'success', 'failed', 'in_progress'
    gyms_fetched = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    triggered_by = Column(Text, default='scheduler')  # 'scheduler' or 'manual'

    # Index
    __table_args__ = (
        Index('idx_sync_history_started_at', 'started_at'),
    )

    def __repr__(self):
        return f"<SyncHistory(id={self.id}, status='{self.status}', started_at={self.started_at})>"
