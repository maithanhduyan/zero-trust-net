# control-plane/schemas.py
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# --- Node Schemas ---
class NodeCreate(BaseModel):
    hostname: str
    role: str
    public_key: str

class NodeResponse(BaseModel):
    id: int
    hostname: str
    role: str
    overlay_ip: Optional[str]
    is_approved: bool
    last_seen: datetime

    class Config:
        from_attributes = True

# --- Config Response cho Agent ---
class PeerConfig(BaseModel):
    public_key: str
    allowed_ips: str
    endpoint: Optional[str] = None

class FirewallRule(BaseModel):
    src_ip: str
    port: int
    proto: str = "tcp"
    action: str = "ACCEPT"

class AgentConfig(BaseModel):
    # Cấu hình Interface cho Agent
    overlay_ip: str
    hub_public_key: str
    hub_endpoint: str

    # Danh sách Peers (để Agent biết các node khác)
    peers: List[PeerConfig]

    # Danh sách ACL (để Agent cấu hình iptables)
    acl_rules: List[FirewallRule]

# --- Policy Schemas ---
class PolicyCreate(BaseModel):
    name: str
    src_role: str
    dst_role: str
    port: int
    protocol: str = "tcp"


class WireGuardConfig(BaseModel):
    node_ip: str
    server_public_key: str
    server_endpoint: str
    allowed_ips: str  # 10.0.0.0/24
    peers: List[dict] # Danh sách peer (nếu mesh)
    acl_rules: List[FirewallRule] # Luật firewall để Agent apply