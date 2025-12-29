#!bin/bash
pkill -f "hub_agent.py" 2>/dev/null || true

# Create Service
cat > /etc/systemd/system/hub-agent.service << 'EOF'
[Unit]
Description=Zero Trust Hub Agent
Documentation=https://github.com/zero-trust-net
After=network-online.target docker.service
Wants=network-online.target
Requires=docker.service

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/home/zero-trust-net/agent/hub

# Environment
EnvironmentFile=/home/zero-trust-net/.env
Environment=PYTHONUNBUFFERED=1
Environment=HUB_API_KEY=${HUB_AGENT_API_KEY}

# Virtual environment activation and execution
ExecStart=/home/zero-trust-net/.venv/bin/python /home/zero-trust-net/agent/hub/hub_agent.py \
    --control-plane-url ws://localhost:8000/api/v1/ws/hub \
    --api-key ${HUB_AGENT_API_KEY} \
    --log-level INFO

# Restart policy
Restart=always
RestartSec=5

# Security hardening
NoNewPrivileges=no
ProtectSystem=false
ProtectHome=false
PrivateTmp=true

# Logging
StandardOutput=append:/var/log/hub-agent.log
StandardError=append:/var/log/hub-agent.log

# Capabilities for WireGuard and iptables
AmbientCapabilities=CAP_NET_ADMIN CAP_NET_RAW

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
echo "Service file created"

# View the created service file
cat /etc/systemd/system/hub-agent.service

#  Reload systemd to recognize the new service
systemctl start hub-agent && sleep 3 && systemctl status hub-agent --no-pager

# Show recent log entries
tail -10 /var/log/hub-agent.log