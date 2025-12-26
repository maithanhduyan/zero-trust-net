# control-plane/api/v1/endpoints.py
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from database import session, models
from core import node_manager, policy_engine
import schemas
from sqlalchemy.orm import Session

# Khởi tạo DB
session.init_db()

router = APIRouter()

@router.post("/register")
def register(node: schemas.NodeCreate, db: Session = Depends(session.get_db)):
    """Agent gọi endpoint này lần đầu để lấy Overlay IP"""
    return node_manager.register_node(db, node)

@router.get("/config/{hostname}", response_model=schemas.WireGuardConfig)
def get_config(hostname: str, request: Request, db: Session = Depends(session.get_db)):
    """
    Agent gọi endpoint này định kỳ để:
    1. Cập nhật Real IP (Heartbeat)
    2. Lấy danh sách ACL mới nhất
    """
    node = db.query(models.Node).filter(models.Node.hostname == hostname).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    if not node.is_active:
        raise HTTPException(status_code=403, detail="Node pending approval")

    # 1. Update Heartbeat & Real IP
    node.real_ip = request.client.host
    node.last_seen = datetime.utcnow()
    db.commit()

    # 2. Tính toán ACL Rules dựa trên Role
    all_nodes = db.query(models.Node).all()
    acl_rules = policy_engine.generate_acl(node.role, all_nodes)

    # 3. Trả về cấu hình
    return schemas.WireGuardConfig(
        node_ip=node.overlay_ip,
        server_public_key=node_manager.SERVER_PUBLIC_KEY,
        server_endpoint=node_manager.SERVER_ENDPOINT,
        allowed_ips="10.0.0.0/24", # Route toàn bộ VPN traffic qua Hub
        peers=[], # Trong mô hình Hub-and-Spoke, Agent chỉ cần peer với Hub
        acl_rules=acl_rules
    )