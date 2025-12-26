# control-plane/database/models.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class Node(Base):
    __tablename__ = "nodes"

    id = Column(Integer, primary_key=True, index=True)
    hostname = Column(String, unique=True, index=True)
    role = Column(String)  # 'hub', 'app', 'db', 'ops'
    public_key = Column(String, unique=True)
    overlay_ip = Column(String, unique=True) # IP trong mạng VPN (VD: 10.0.0.2)
    real_ip = Column(String, nullable=True)  # IP Public của VPS
    is_active = Column(Boolean, default=False) # Phải được approve mới chạy
    last_seen = Column(DateTime, default=datetime.utcnow)