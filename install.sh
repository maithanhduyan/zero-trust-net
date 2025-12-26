#!/bin/bash

# ==============================================================================
#  ZERO TRUST PROJECT SCAFFOLDING (UV EDITION)
# ==============================================================================

set -e
PROJECT_NAME="zero-trust-networking"

# ... (Giữ nguyên các phần tạo thư mục cũ) ...

log "0. Cài đặt uv..."
if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.cargo/env
fi

mkdir -p "$PROJECT_NAME"
cd "$PROJECT_NAME"

# --- TẠO FILE PYPROJECT.TOML ---
log "1. Khởi tạo Workspace..."
cat > pyproject.toml <<EOF
[project]
name = "zero-trust-networking"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = []

[tool.uv]
members = ["control-plane", "agent"]
EOF

# --- CONTROL PLANE SETUP ---
log "2. Setup Control Plane..."
mkdir -p control-plane
cat > control-plane/pyproject.toml <<EOF
[project]
name = "control-plane"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "fastapi",
    "uvicorn",
    "sqlalchemy",
    "pydantic",
    "psycopg2-binary"
]
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
EOF

# --- AGENT SETUP ---
log "3. Setup Agent..."
mkdir -p agent
cat > agent/pyproject.toml <<EOF
[project]
name = "zt-agent"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "requests",
    "schedule"
]
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
EOF

# --- CÀI ĐẶT ---
log "4. Installing dependencies with uv..."
uv sync

success "Hoàn tất! Môi trường ảo đã được tạo tại .venv"
echo "Để kích hoạt: source .venv/bin/activate"