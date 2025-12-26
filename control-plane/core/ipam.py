# control-plane/core/ipam.py
import ipaddress
from sqlalchemy.orm import Session
from database.models import Node
from config import settings

def allocate_ip(db: Session) -> str:
    """Tìm IP rảnh tiếp theo trong dải 10.0.0.0/24"""
    network = ipaddress.IPv4Network(settings.OVERLAY_NETWORK)
    used_ips = {n.overlay_ip for n in db.query(Node).filter(Node.overlay_ip != None).all()}

    # Bỏ qua .0 (network), .1 (gateway/hub), .255 (broadcast)
    # Giả sử Hub dùng 10.0.0.1
    reserved = {str(network.network_address), str(network.network_address + 1), str(network.broadcast_address)}

    for ip in network.hosts():
        ip_str = str(ip)
        if ip_str not in used_ips and ip_str not in reserved:
            return ip_str

    raise Exception("Hết địa chỉ IP trong pool!")