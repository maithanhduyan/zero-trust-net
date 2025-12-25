#!/bin/bash
# =============================================================================
# ZERO TRUST NETWORK - HEALTH CHECK SCRIPT
# =============================================================================
# 
# Kiểm tra trạng thái toàn bộ mesh network
#
# Sử dụng:
#   ./scripts/health-check.sh           # Full check
#   ./scripts/health-check.sh --quick   # Quick check (ping only)
#   ./scripts/health-check.sh --json    # JSON output
#
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
WIREGUARD_INTERFACE="wg0"
WIREGUARD_NETWORK="10.10.0.0/24"

# Nodes to check (WireGuard IPs)
declare -A NODES=(
    ["hub-1"]="10.10.0.1"
    ["hub-2"]="10.10.0.2"
    ["db-primary"]="10.10.0.10"
    ["db-replica"]="10.10.0.11"
)

# Parse arguments
QUICK_MODE=false
JSON_OUTPUT=false
for arg in "$@"; do
    case $arg in
        --quick) QUICK_MODE=true ;;
        --json) JSON_OUTPUT=true ;;
    esac
done

# Functions
print_header() {
    if [ "$JSON_OUTPUT" = false ]; then
        echo -e "\n${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${CYAN}║${NC}           ${BLUE}ZERO TRUST NETWORK - HEALTH CHECK${NC}               ${CYAN}║${NC}"
        echo -e "${CYAN}║${NC}           $(date '+%Y-%m-%d %H:%M:%S')                           ${CYAN}║${NC}"
        echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
    fi
}

print_section() {
    if [ "$JSON_OUTPUT" = false ]; then
        echo -e "\n${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${YELLOW}  $1${NC}"
        echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    fi
}

check_pass() {
    if [ "$JSON_OUTPUT" = false ]; then
        echo -e "  ${GREEN}✓${NC} $1"
    fi
}

check_fail() {
    if [ "$JSON_OUTPUT" = false ]; then
        echo -e "  ${RED}✗${NC} $1"
    fi
}

check_warn() {
    if [ "$JSON_OUTPUT" = false ]; then
        echo -e "  ${YELLOW}⚠${NC} $1"
    fi
}

check_info() {
    if [ "$JSON_OUTPUT" = false ]; then
        echo -e "  ${BLUE}ℹ${NC} $1"
    fi
}

# JSON output array
declare -a JSON_RESULTS=()

# =============================================================================
# CHECK 1: Local WireGuard Status
# =============================================================================
check_local_wireguard() {
    print_section "1. LOCAL WIREGUARD STATUS"
    
    # Check if WireGuard interface exists
    if ip link show "$WIREGUARD_INTERFACE" &>/dev/null; then
        check_pass "WireGuard interface '$WIREGUARD_INTERFACE' exists"
        
        # Get local WireGuard IP
        local_ip=$(ip addr show "$WIREGUARD_INTERFACE" | grep -oP '(?<=inet\s)\d+\.\d+\.\d+\.\d+')
        check_info "Local WireGuard IP: $local_ip"
        
        # Check if interface is UP
        if ip link show "$WIREGUARD_INTERFACE" | grep -q "state UNKNOWN"; then
            check_pass "Interface is UP (state UNKNOWN is normal for WireGuard)"
        else
            check_warn "Interface state may not be active"
        fi
        
        # Show connected peers
        peer_count=$(wg show "$WIREGUARD_INTERFACE" peers | wc -l)
        check_info "Connected peers: $peer_count"
        
        JSON_RESULTS+=("{\"check\":\"wireguard_local\",\"status\":\"pass\",\"local_ip\":\"$local_ip\",\"peers\":$peer_count}")
        return 0
    else
        check_fail "WireGuard interface '$WIREGUARD_INTERFACE' not found"
        JSON_RESULTS+=("{\"check\":\"wireguard_local\",\"status\":\"fail\"}")
        return 1
    fi
}

# =============================================================================
# CHECK 2: Node Connectivity
# =============================================================================
check_node_connectivity() {
    print_section "2. NODE CONNECTIVITY (PING)"
    
    local all_reachable=true
    
    for node_name in "${!NODES[@]}"; do
        node_ip="${NODES[$node_name]}"
        
        if ping -c 1 -W 2 "$node_ip" &>/dev/null; then
            # Get latency
            latency=$(ping -c 1 -W 2 "$node_ip" | grep -oP 'time=\K[\d.]+')
            check_pass "$node_name ($node_ip) - ${latency}ms"
            JSON_RESULTS+=("{\"check\":\"ping\",\"node\":\"$node_name\",\"ip\":\"$node_ip\",\"status\":\"pass\",\"latency\":$latency}")
        else
            check_fail "$node_name ($node_ip) - UNREACHABLE"
            JSON_RESULTS+=("{\"check\":\"ping\",\"node\":\"$node_name\",\"ip\":\"$node_ip\",\"status\":\"fail\"}")
            all_reachable=false
        fi
    done
    
    return $([ "$all_reachable" = true ] && echo 0 || echo 1)
}

# =============================================================================
# CHECK 3: WireGuard Peer Status
# =============================================================================
check_wireguard_peers() {
    print_section "3. WIREGUARD PEER STATUS"
    
    # Get current timestamp
    current_time=$(date +%s)
    
    # Parse wg show output
    while IFS= read -r line; do
        if [[ $line =~ ^peer ]]; then
            peer_key=$(echo "$line" | awk '{print $2}')
        elif [[ $line =~ "latest handshake" ]]; then
            handshake_ago=$(echo "$line" | grep -oP '\d+(?=\s*(second|minute|hour))' | head -1)
            handshake_unit=$(echo "$line" | grep -oP '(second|minute|hour)' | head -1)
            
            # Find peer IP
            peer_ip=$(wg show "$WIREGUARD_INTERFACE" allowed-ips | grep "$peer_key" | awk '{print $2}' | cut -d'/' -f1)
            
            # Calculate handshake age in seconds
            case $handshake_unit in
                second*) age_seconds=${handshake_ago:-0} ;;
                minute*) age_seconds=$((${handshake_ago:-0} * 60)) ;;
                hour*) age_seconds=$((${handshake_ago:-0} * 3600)) ;;
                *) age_seconds=0 ;;
            esac
            
            # Find node name
            node_name="unknown"
            for name in "${!NODES[@]}"; do
                if [ "${NODES[$name]}" = "$peer_ip" ]; then
                    node_name=$name
                    break
                fi
            done
            
            # Check handshake freshness (warn if > 3 minutes)
            if [ "${age_seconds:-0}" -lt 180 ]; then
                check_pass "$node_name ($peer_ip) - Last handshake: ${handshake_ago:-?} ${handshake_unit:-second}s ago"
            elif [ "${age_seconds:-0}" -lt 300 ]; then
                check_warn "$node_name ($peer_ip) - Last handshake: ${handshake_ago:-?} ${handshake_unit:-second}s ago (slightly stale)"
            else
                check_fail "$node_name ($peer_ip) - Last handshake: ${handshake_ago:-?} ${handshake_unit:-second}s ago (STALE)"
            fi
        fi
    done < <(wg show "$WIREGUARD_INTERFACE" 2>/dev/null)
}

# =============================================================================
# CHECK 4: SSH Connectivity (via WireGuard)
# =============================================================================
check_ssh_connectivity() {
    if [ "$QUICK_MODE" = true ]; then
        return 0
    fi
    
    print_section "4. SSH CONNECTIVITY (via WireGuard)"
    
    for node_name in "${!NODES[@]}"; do
        node_ip="${NODES[$node_name]}"
        
        # Skip localhost
        if [ "$node_name" = "hub-1" ]; then
            check_info "$node_name ($node_ip) - localhost (skipped)"
            continue
        fi
        
        # Test SSH connection with timeout
        if ssh -o ConnectTimeout=5 -o BatchMode=yes -o StrictHostKeyChecking=no "root@$node_ip" 'echo ok' &>/dev/null; then
            check_pass "$node_name ($node_ip) - SSH accessible"
            JSON_RESULTS+=("{\"check\":\"ssh\",\"node\":\"$node_name\",\"ip\":\"$node_ip\",\"status\":\"pass\"}")
        else
            check_fail "$node_name ($node_ip) - SSH not accessible"
            JSON_RESULTS+=("{\"check\":\"ssh\",\"node\":\"$node_name\",\"ip\":\"$node_ip\",\"status\":\"fail\"}")
        fi
    done
}

# =============================================================================
# CHECK 5: Security Status
# =============================================================================
check_security_status() {
    if [ "$QUICK_MODE" = true ]; then
        return 0
    fi
    
    print_section "5. LOCAL SECURITY STATUS"
    
    # Check UFW
    if command -v ufw &>/dev/null; then
        if ufw status | grep -q "Status: active"; then
            check_pass "UFW Firewall: ACTIVE"
        else
            check_warn "UFW Firewall: INACTIVE"
        fi
    else
        check_info "UFW not installed"
    fi
    
    # Check Fail2ban
    if systemctl is-active --quiet fail2ban 2>/dev/null; then
        banned_count=$(fail2ban-client status sshd 2>/dev/null | grep "Currently banned" | awk '{print $NF}' || echo "0")
        check_pass "Fail2ban: ACTIVE (Banned IPs: $banned_count)"
    else
        check_warn "Fail2ban: INACTIVE or not installed"
    fi
    
    # Check auditd
    if systemctl is-active --quiet auditd 2>/dev/null; then
        check_pass "Audit logging: ACTIVE"
    else
        check_warn "Audit logging: INACTIVE"
    fi
    
    # Check unattended-upgrades
    if dpkg -l | grep -q unattended-upgrades; then
        check_pass "Automatic security updates: INSTALLED"
    else
        check_warn "Automatic security updates: NOT INSTALLED"
    fi
}

# =============================================================================
# CHECK 6: Docker Status
# =============================================================================
check_docker_status() {
    if [ "$QUICK_MODE" = true ]; then
        return 0
    fi
    
    print_section "6. DOCKER STATUS"
    
    if command -v docker &>/dev/null; then
        if systemctl is-active --quiet docker; then
            docker_version=$(docker --version | awk '{print $3}' | tr -d ',')
            container_count=$(docker ps -q 2>/dev/null | wc -l)
            check_pass "Docker: RUNNING (v$docker_version, $container_count containers)"
        else
            check_warn "Docker installed but not running"
        fi
    else
        check_info "Docker not installed"
    fi
}

# =============================================================================
# CHECK 7: Resource Usage
# =============================================================================
check_resources() {
    if [ "$QUICK_MODE" = true ]; then
        return 0
    fi
    
    print_section "7. RESOURCE USAGE"
    
    # CPU load
    load=$(cat /proc/loadavg | awk '{print $1}')
    cpu_cores=$(nproc)
    load_per_core=$(echo "scale=2; $load / $cpu_cores" | bc)
    
    if (( $(echo "$load_per_core < 0.7" | bc -l) )); then
        check_pass "CPU Load: $load ($cpu_cores cores) - OK"
    elif (( $(echo "$load_per_core < 0.9" | bc -l) )); then
        check_warn "CPU Load: $load ($cpu_cores cores) - HIGH"
    else
        check_fail "CPU Load: $load ($cpu_cores cores) - CRITICAL"
    fi
    
    # Memory usage
    mem_total=$(free -m | awk 'NR==2{print $2}')
    mem_used=$(free -m | awk 'NR==2{print $3}')
    mem_percent=$((mem_used * 100 / mem_total))
    
    if [ "$mem_percent" -lt 70 ]; then
        check_pass "Memory: ${mem_used}MB / ${mem_total}MB (${mem_percent}%) - OK"
    elif [ "$mem_percent" -lt 90 ]; then
        check_warn "Memory: ${mem_used}MB / ${mem_total}MB (${mem_percent}%) - HIGH"
    else
        check_fail "Memory: ${mem_used}MB / ${mem_total}MB (${mem_percent}%) - CRITICAL"
    fi
    
    # Disk usage
    disk_percent=$(df -h / | awk 'NR==2{print $5}' | tr -d '%')
    disk_used=$(df -h / | awk 'NR==2{print $3}')
    disk_total=$(df -h / | awk 'NR==2{print $2}')
    
    if [ "$disk_percent" -lt 70 ]; then
        check_pass "Disk: ${disk_used} / ${disk_total} (${disk_percent}%) - OK"
    elif [ "$disk_percent" -lt 90 ]; then
        check_warn "Disk: ${disk_used} / ${disk_total} (${disk_percent}%) - HIGH"
    else
        check_fail "Disk: ${disk_used} / ${disk_total} (${disk_percent}%) - CRITICAL"
    fi
}

# =============================================================================
# SUMMARY
# =============================================================================
print_summary() {
    if [ "$JSON_OUTPUT" = false ]; then
        echo -e "\n${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${CYAN}║${NC}                    ${GREEN}HEALTH CHECK COMPLETE${NC}                    ${CYAN}║${NC}"
        echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
        echo ""
        echo -e "  Run ${BLUE}./scripts/health-check.sh --quick${NC} for fast ping-only check"
        echo -e "  Run ${BLUE}./scripts/health-check.sh --json${NC} for JSON output"
        echo ""
    else
        # Output JSON
        echo "{"
        echo "  \"timestamp\": \"$(date -Iseconds)\","
        echo "  \"checks\": ["
        for i in "${!JSON_RESULTS[@]}"; do
            if [ $i -eq $((${#JSON_RESULTS[@]} - 1)) ]; then
                echo "    ${JSON_RESULTS[$i]}"
            else
                echo "    ${JSON_RESULTS[$i]},"
            fi
        done
        echo "  ]"
        echo "}"
    fi
}

# =============================================================================
# MAIN
# =============================================================================
main() {
    print_header
    
    check_local_wireguard
    check_node_connectivity
    check_wireguard_peers
    check_ssh_connectivity
    check_security_status
    check_docker_status
    check_resources
    
    print_summary
}

main
