#!bin/bash
chmod +x /home/zero-trust-netwoking/scripts/install-agent.sh && echo "=== Hub Info for Agent Installation ===" && echo "HUB_PUBLIC_KEY=$(cat /etc/wireguard/public.key)" && echo "HUB_ENDPOINT=$(curl -s ifconfig.me):51820" && echo "HUB_URL=http://$(curl -s ifconfig.me):8000"

#
PUBLIC_IP=$(curl -4 -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}') && echo "=== AGENT INSTALLATION COMMAND ===" && echo "" && echo "# Copy và chạy trên node cần cài Agent:" && echo "" && echo "curl -sL https://raw.githubusercontent.com/maithanhduyan/zero-trust-netwoking/main/scripts/install-agent.sh | \\" && echo "  sudo HUB_URL=\"http://${PUBLIC_IP}:8000\" \\" && echo "       HUB_ENDPOINT=\"${PUBLIC_IP}:51820\" \\" && echo "       HUB_PUBLIC_KEY=\"$(cat /etc/wireguard/public.key)\" \\" && echo "       NODE_ROLE=\"app\" \\" && echo "       bash"


# Ping to agent node to verify connectivity
ssh root@155.133.7.254 'ip addr show wg0; echo "---"; cat /etc/wireguard/wg0.conf; echo "---"; ping -c 2 10.10.0.1'


# restart agent service on agent node to register again
ssh root@155.133.7.254 'systemctl restart zero-trust-agent && sleep 3 && journalctl -u zero-trust-agent -n 15 --no-pager'

# Restart WireGuard và fix endpoint:
ssh root@155.133.7.254 'sed -i "s|Endpoint = 2400:d320:2261:7974::1:51820|Endpoint = 5.104.82.252:51820|" /etc/wireguard/wg0.conf && systemctl restart wg-quick@wg0 && sleep 1 && ip addr show wg0 | grep inet && ping -c 2 10.10.0.1'

# Test từ Hub ping tới Agent qua WireGuard
ping -c 3 10.10.0.2 && echo "✅ BIDIRECTIONAL VPN TUNNEL WORKING!"
