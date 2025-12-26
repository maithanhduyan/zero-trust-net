# control-plane/database/models.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base
from datetime import datetime
from pydantic import BaseModel

Base = declarative_base()

class Node(Base):
    __tablename__ = "nodes"

    id = Column(Integer, primary_key=True, index=True)
    hostname = Column(String, unique=True, index=True) # VD: vps-2-odoo
    role = Column(String)       # VD: app, db, ops
    public_key = Column(String, unique=True)
    overlay_ip = Column(String, unique=True) # IP VPN: 10.0.0.x
    real_ip = Column(String, nullable=True)  # IP Public hiện tại
    is_approved = Column(Boolean, default=False) # Admin phải duyệt mới được kết nối
    last_seen = Column(DateTime, default=datetime.utcnow)

class AccessPolicy(Base):
    # Thay vì code cứng, ta lưu policy vào DB để Admin thêm sửa xóa được
    __tablename__ = "policies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    src_role = Column(String) # Ai được gọi
    dst_role = Column(String) # Gọi tới ai
    port = Column(Integer)    # Port nào (VD: 5432)
    protocol = Column(String, default="tcp") # tcp/udp
    action = Column(String, default="ACCEPT") # ACCEPT/DENY