# control-plane/core/policy_engine.py
from typing import List
from schemas import FirewallRule
from database.models import AccessPolicy, Node
from sqlalchemy.orm import Session

# Định nghĩa luật truy cập (Intent-based)
# Ai (Source Role) -> Được làm gì (Port) -> Với ai (Target Role)
POLICIES = [
    # Odoo (App) được gọi Postgres (DB) qua port 5432
    {"src": "app", "dst": "db", "port": 5432, "proto": "tcp"},

    # Ops được SSH vào tất cả mọi nơi
    {"src": "ops", "dst": "*", "port": 22, "proto": "tcp"},

    # Ops được truy cập monitoring
    {"src": "ops", "dst": "*", "port": 9100, "proto": "tcp"},
]

def generate_acl(target_role: str, all_nodes: list) -> List[FirewallRule]:
    """
    Tính toán danh sách IP được phép kết nối vào Node hiện tại
    """
    rules = []

    for policy in POLICIES:
        # Nếu rule áp dụng cho role của node hiện tại (hoặc wildcard *)
        if policy["dst"] == target_role or policy["dst"] == "*":

            # Tìm tất cả node có role là nguồn (src)
            authorized_nodes = [
                n for n in all_nodes
                if n.role == policy["src"] and n.is_active
            ]

            # Tạo rule cho từng IP
            for node in authorized_nodes:
                rules.append(FirewallRule(
                    src_ip=node.overlay_ip,
                    port=policy["port"],
                    proto=policy["proto"]
                ))

    return rules

def build_config_for_node(db: Session, node: Node) -> dict:
    """Tính toán Peers và ACLs cho một Node cụ thể"""

    # 1. Lấy danh sách tất cả các Nodes đã active
    all_nodes = db.query(Node).filter(Node.is_approved == True).all()

    # 2. Xây dựng danh sách Peers (WireGuard)
    # Trong mô hình Hub-Spoke:
    # - Nếu là Hub: Cần biết tất cả Peers
    # - Nếu là Spoke: Chỉ cần biết Hub (đã hardcode trong settings)
    # Nhưng để các node nói chuyện qua Hub, Hub phải routing.
    # Ở đây ta trả về danh sách IP để Agent biết
    peers = []
    # (Logic mở rộng: Nếu muốn Mesh, trả về full list peers tại đây)

    # 3. Xây dựng Firewall Rules (ACL)
    # Tìm các policy mà node này là ĐÍCH (Destination)
    # Ví dụ: Node là DB, tìm rule nào cho phép truy cập vào DB
    acl_rules = []

    # Lấy policy từ DB
    policies = db.query(AccessPolicy).filter(
        (AccessPolicy.dst_role == node.role) | (AccessPolicy.dst_role == "*")
    ).all()

    for policy in policies:
        # Tìm các node có role là nguồn (Source)
        src_nodes = [n for n in all_nodes if n.role == policy.src_role]

        for src in src_nodes:
            if src.overlay_ip:
                acl_rules.append(FirewallRule(
                    src_ip=src.overlay_ip,
                    port=policy.port,
                    proto=policy.protocol,
                    action=policy.action
                ))

    return {
        "peers": peers,
        "acl_rules": acl_rules
    }