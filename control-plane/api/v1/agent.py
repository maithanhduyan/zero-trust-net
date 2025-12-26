# control-plane/api/v1/agent.py
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime

from database.session import get_db
from database.models import Node
import schemas
from core import ipam, policy_engine
from config import settings

router = APIRouter()

@router.post("/register", response_model=schemas.NodeResponse)
def register_agent(node_in: schemas.NodeCreate, db: Session = Depends(get_db)):
    """Agent gọi API này lần đầu để xin tham gia mạng"""

    # Check trùng
    existing = db.query(Node).filter(Node.public_key == node_in.public_key).first()
    if existing:
        return existing

    # Cấp IP mới
    try:
        new_ip = ipam.allocate_ip(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    new_node = Node(
        hostname=node_in.hostname,
        role=node_in.role,
        public_key=node_in.public_key,
        overlay_ip=new_ip,
        is_approved=False # Mặc định chờ duyệt
    )
    db.add(new_node)
    db.commit()
    db.refresh(new_node)
    return new_node

@router.get("/config", response_model=schemas.AgentConfig)
def get_agent_config(public_key: str, request: Request, db: Session = Depends(get_db)):
    """Agent poll API này để lấy cấu hình mới nhất"""
    node = db.query(Node).filter(Node.public_key == public_key).first()

    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    if not node.is_approved:
        raise HTTPException(status_code=403, detail="Node not approved yet")

    # Update Heartbeat
    node.last_seen = datetime.utcnow()
    node.real_ip = request.client.host
    db.commit()

    # Tính toán config
    config_data = policy_engine.build_config_for_node(db, node)

    return schemas.AgentConfig(
        overlay_ip=node.overlay_ip,
        hub_public_key=settings.HUB_PUBLIC_KEY,
        hub_endpoint=settings.HUB_ENDPOINT,
        peers=config_data["peers"],
        acl_rules=config_data["acl_rules"]
    )