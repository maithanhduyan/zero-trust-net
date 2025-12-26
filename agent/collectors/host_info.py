# agent/collectors/host_info.py
"""
Host Information Collector
Collects system information for registration and monitoring
"""

import os
import platform
import socket
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger('zt-agent.collector')


def collect_host_info() -> Dict[str, Any]:
    """
    Collect basic host information

    Returns:
        Dict with os_info, hostname, platform details
    """
    info = {
        "hostname": socket.gethostname(),
        "platform": platform.system(),
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
    }

    # Build OS info string
    info["os_info"] = f"{info['platform']} {info['platform_release']} ({info['architecture']})"

    # Get Linux distribution info
    try:
        import distro
        info["distro_name"] = distro.name()
        info["distro_version"] = distro.version()
        info["distro_id"] = distro.id()
        info["os_info"] = f"{distro.name()} {distro.version()} ({info['architecture']})"
    except ImportError:
        # Fall back to platform.freedesktop_os_release() on Python 3.10+
        try:
            os_release = platform.freedesktop_os_release()
            info["distro_name"] = os_release.get("NAME", "")
            info["distro_version"] = os_release.get("VERSION_ID", "")
            info["distro_id"] = os_release.get("ID", "")
            info["os_info"] = f"{info['distro_name']} {info['distro_version']} ({info['architecture']})"
        except (AttributeError, OSError):
            pass

    return info


def collect_network_info() -> Dict[str, Any]:
    """
    Collect network interface information

    Returns:
        Dict with network interfaces and IPs
    """
    info = {
        "interfaces": {},
        "public_ip": None
    }

    try:
        import subprocess

        # Get interface info
        result = subprocess.run(
            ["ip", "-j", "addr", "show"],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            import json
            interfaces = json.loads(result.stdout)

            for iface in interfaces:
                name = iface.get("ifname", "")
                if name in ("lo",):
                    continue

                addrs = []
                for addr_info in iface.get("addr_info", []):
                    addrs.append({
                        "family": addr_info.get("family"),
                        "address": addr_info.get("local"),
                        "prefixlen": addr_info.get("prefixlen")
                    })

                info["interfaces"][name] = {
                    "state": iface.get("operstate", "unknown"),
                    "mac": iface.get("address"),
                    "addresses": addrs
                }

        # Get public IP
        info["public_ip"] = get_public_ip()

    except Exception as e:
        logger.debug(f"Failed to collect network info: {e}")

    return info


def get_public_ip() -> Optional[str]:
    """Get public IP address using external service"""
    import urllib.request

    services = [
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://icanhazip.com"
    ]

    for url in services:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                return response.read().decode('utf-8').strip()
        except Exception:
            continue

    return None


def collect_resource_usage() -> Dict[str, Any]:
    """
    Collect current resource usage (for heartbeat)

    Returns:
        Dict with CPU, memory, disk usage
    """
    info = {
        "cpu_percent": None,
        "memory_percent": None,
        "disk_percent": None,
        "uptime_seconds": None,
        "load_average": None
    }

    try:
        # CPU usage (simple method without psutil)
        with open('/proc/stat', 'r') as f:
            cpu_line = f.readline()
            cpu_times = list(map(int, cpu_line.split()[1:]))
            idle = cpu_times[3]
            total = sum(cpu_times)
            # This is instantaneous, not accurate without sampling
            # For accurate CPU%, use psutil or sample over time
    except Exception:
        pass

    # Memory usage
    try:
        with open('/proc/meminfo', 'r') as f:
            mem_total = 0
            mem_available = 0

            for line in f:
                if line.startswith('MemTotal:'):
                    mem_total = int(line.split()[1])
                elif line.startswith('MemAvailable:'):
                    mem_available = int(line.split()[1])

            if mem_total > 0:
                info["memory_percent"] = round((1 - mem_available / mem_total) * 100, 1)
                info["memory_total_mb"] = mem_total // 1024
                info["memory_available_mb"] = mem_available // 1024
    except Exception:
        pass

    # Disk usage
    try:
        statvfs = os.statvfs('/')
        total = statvfs.f_frsize * statvfs.f_blocks
        free = statvfs.f_frsize * statvfs.f_bfree
        if total > 0:
            info["disk_percent"] = round((1 - free / total) * 100, 1)
            info["disk_total_gb"] = round(total / 1024 / 1024 / 1024, 1)
            info["disk_free_gb"] = round(free / 1024 / 1024 / 1024, 1)
    except Exception:
        pass

    # Uptime
    try:
        with open('/proc/uptime', 'r') as f:
            uptime = float(f.readline().split()[0])
            info["uptime_seconds"] = int(uptime)
    except Exception:
        pass

    # Load average
    try:
        with open('/proc/loadavg', 'r') as f:
            load = f.readline().split()[:3]
            info["load_average"] = [float(x) for x in load]
    except Exception:
        pass

    return info


def collect_all() -> Dict[str, Any]:
    """Collect all host information"""
    return {
        "host": collect_host_info(),
        "network": collect_network_info(),
        "resources": collect_resource_usage()
    }
