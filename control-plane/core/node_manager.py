# control-plane/core/node_manager.py
from sqlalchemy.orm import Session
from database.models import Node
import schemas
import ipaddress

# Cấu hình mạng Overlay
NETWORK_CIDR = "10.0.0.0/24"
SERVER_IP = "10.0.0.1"
SERVER_PUBLIC_KEY = "SERVER_WG_PUBLIC_KEY_PLACEHOLDER" # Thay bằng key thật của VPS-1
SERVER_ENDPOINT = "vps1.domain.com:51820" # Thay bằng IP/Domain thật

def get_next_ip(db: Session):
    """Cấp phát IP tiếp theo chưa sử dụng"""
    used_ips = [n.overlay_ip for n in db.query(Node).all()]
    network = ipaddress.IPv4Network(NETWORK_CIDR)

    # Bỏ qua .0 (network), .1 (gateway/hub), .255 (broadcast)
    for ip in network.hosts():
        ip_str = str(ip)
        if ip_str == SERVER_IP: continue
        if ip_str not in used_ips:
            return ip_str
    raise Exception("Network exhausted")

def register_node(db: Session, node_in: schemas.NodeCreate):
    # Kiểm tra xem hostname hoặc key đã tồn tại chưa
    existing = db.query(Node).filter(
        (Node.hostname == node_in.hostname) | (Node.public_key == node_in.public_key)
    ).first()

    if existing:
        return existing

    # Cấp IP mới
    new_ip = get_next_ip(db)

    # Mặc định auto-approve cho Ops, các role khác phải đợi (hoặc auto cho demo)
    is_active = True

    db_node = Node(
        hostname=node_in.hostname,
        role=node_in.role,
        public_key=node_in.public_key,
        overlay_ip=new_ip,
        is_active=is_active
    )
    db.add(db_node)
    db.commit()
    db.refresh(db_node)
    return db_node