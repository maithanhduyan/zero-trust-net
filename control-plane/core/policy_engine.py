# control-plane/core/policy_engine.py
from typing import List
from schemas import FirewallRule

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