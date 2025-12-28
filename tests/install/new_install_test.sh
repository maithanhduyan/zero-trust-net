#!bin/bash
chmod +x /home/zero-trust-net/scripts/install.sh

# Trước khi chạy, cần stop Control Plane đang chạy trong terminal khác:
pkill -f "uvicorn main:app" 2>/dev/null || true; sleep 1

#
cd /home/zero-trust-net && sudo ./scripts/install.sh 2>&1

# Cài đặt thành công! Giờ verify các services:
echo "=== WireGuard Status ===" && wg show wg0 && echo "" && echo "=== Control Plane Health ===" && curl -s http://localhost:8000/health | jq . && echo "" && echo "=== Services Status ===" && systemctl status zero-trust-control-plane --no-pager -l | head -15 && echo "" && echo "=== WireGuard Service ===" && systemctl status wg-quick@wg0 --no-pager | head -10


# Commands hữu ích:
# Kiểm tra API
curl http://localhost:8000/health

# Xem logs Control Plane
journalctl -u zero-trust-control-plane -f

# Xem WireGuard peers
wg show wg0

# Restart services
systemctl restart zero-trust-control-plane
systemctl restart wg-quick@wg0