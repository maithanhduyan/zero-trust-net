# control-plane/api/v1/admin.py
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import List

from database.session import get_db
from database.models import Node, AccessPolicy
import schemas
from config import settings

router = APIRouter()

# Middleware check token đơn giản
def verify_admin(x_admin_token: str = Header(...)):
    if x_admin_token != settings.ADMIN_SECRET:
        raise HTTPException(status_code=401, detail="Invalid Admin Token")

@router.get("/nodes", response_model=List[schemas.NodeResponse])
def list_nodes(db: Session = Depends(get_db), authorized: bool = Depends(verify_admin)):
    return db.query(Node).all()

@router.post("/nodes/{node_id}/approve")
def approve_node(node_id: int, db: Session = Depends(get_db), authorized: bool = Depends(verify_admin)):
    node = db.query(Node).filter(Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    node.is_approved = True
    db.commit()
    return {"message": f"Node {node.hostname} approved"}

@router.post("/policies")
def create_policy(policy: schemas.PolicyCreate, db: Session = Depends(get_db), authorized: bool = Depends(verify_admin)):
    new_policy = AccessPolicy(**policy.model_dump())
    db.add(new_policy)
    db.commit()
    return {"message": "Policy created", "id": new_policy.id}