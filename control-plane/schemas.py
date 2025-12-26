# control-plane/schemas.py
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class NodeCreate(BaseModel):
    hostname: str
    role: str
    public_key: str

class NodeResponse(BaseModel):
    id: int
    hostname: str
    role: str
    overlay_ip: str
    is_active: bool

    class Config:
        from_attributes = True

class FirewallRule(BaseModel):
    src_ip: str
    port: int
    proto: str = "tcp"
    action: str = "ACCEPT"

class WireGuardConfig(BaseModel):
    node_ip: str
    server_public_key: str
    server_endpoint: str
    allowed_ips: str  # 10.0.0.0/24
    peers: List[dict] # Danh sách peer (nếu mesh)
    acl_rules: List[FirewallRule] # Luật firewall để Agent apply