# Agent Integrity Verification - Test Cases

## Overview

Test suite cho Agent Hash Verification để ngăn chặn agent giả mạo.

## Cấu trúc Test

```
tests/agent/
├── conftest.py                    # Pytest fixtures
├── pytest.ini                     # Pytest config
├── run_integrity_tests.sh         # Test runner script
├── test_agent_integrity.py        # Unit tests - Agent side
├── test_integrity_service.py      # Unit tests - Server side
└── test_integrity_integration.py  # Integration tests
```

## Cách chạy tests

### Quick Start

```bash
cd /home/zero-trust-net

# Chạy tất cả unit tests
pytest tests/agent/test_agent_integrity.py tests/agent/test_integrity_service.py -v

# Chạy với script runner
chmod +x tests/agent/run_integrity_tests.sh
./tests/agent/run_integrity_tests.sh
```

### Chạy từng loại test

```bash
# Unit tests - Agent hash calculation
pytest tests/agent/test_agent_integrity.py -v

# Unit tests - Server verification logic
pytest tests/agent/test_integrity_service.py -v

# Integration tests (cần server chạy)
CONTROL_PLANE_URL=http://localhost:8000 \
ADMIN_TOKEN=your-token \
pytest tests/agent/test_integrity_integration.py -v -s
```

### Chạy test cụ thể

```bash
# Chạy tests có tên chứa "mismatch"
pytest tests/agent/ -v -k "mismatch"

# Chạy tests trong class TestVerifyIntegrity
pytest tests/agent/test_integrity_service.py::TestVerifyIntegrity -v

# Chạy 1 test cụ thể
pytest tests/agent/test_agent_integrity.py::TestCalculateFileHash::test_hash_existing_file -v
```

### Debug & Development

```bash
# Dừng ngay khi fail
pytest tests/agent/ -v -x

# Chạy lại tests đã fail
pytest tests/agent/ -v --lf

# Xem output chi tiết
pytest tests/agent/ -v -s --tb=long

# Coverage report
pytest tests/agent/ --cov=agent/collectors --cov=control-plane/core --cov-report=term-missing
```

## Test Cases

### 1. Agent Integrity Module (test_agent_integrity.py)

| Test Case | Mô tả | Status |
|-----------|-------|--------|
| `test_hash_existing_file` | Hash file tồn tại | ✅ |
| `test_hash_nonexistent_file` | File không tồn tại trả về None | ✅ |
| `test_hash_consistency` | Hash cùng file cho kết quả giống nhau | ✅ |
| `test_different_files_different_hashes` | File khác nhau có hash khác nhau | ✅ |
| `test_hash_detects_modification` | Phát hiện file bị sửa | ✅ |
| `test_detect_file_addition` | Phát hiện thêm code độc | ✅ |
| `test_detect_file_deletion` | Phát hiện xóa file | ✅ |

### 2. Integrity Service (test_integrity_service.py)

| Test Case | Mô tả | Status |
|-----------|-------|--------|
| `test_no_expected_hash_first_report` | Lần đầu report, chưa có expected | ✅ |
| `test_hash_matches` | Hash khớp → verified | ✅ |
| `test_hash_mismatch_warning` | Mismatch lần 1 → warning | ✅ |
| `test_hash_mismatch_suspends` | Mismatch 3 lần → suspend | ✅ |
| `test_hash_mismatch_revokes` | Mismatch 5 lần → revoke | ✅ |
| `test_progressive_penalty` | Trust penalty tăng theo số lần mismatch | ✅ |
| `test_scenario_agent_tampered` | Kịch bản agent bị hack | ✅ |
| `test_scenario_agent_update` | Kịch bản update agent hợp lệ | ✅ |

### 3. Integration Tests (test_integrity_integration.py)

| Test Case | Mô tả | Requires |
|-----------|-------|----------|
| `test_heartbeat_with_integrity_hash` | Heartbeat gửi kèm hash | Server |
| `test_approve_agent_hash` | Admin approve hash | Server + Admin API |
| `test_set_expected_hash` | Admin set expected hash | Server + Admin API |
| `test_integrity_mismatch_reduces_trust` | Mismatch giảm trust score | Server |
| `test_full_registration_to_verification_flow` | Flow hoàn chỉnh | Server |

## Scenarios được test

### Scenario 1: Agent mới đăng ký
```
1. Agent register → Server tạo node (pending)
2. Agent gửi heartbeat với hash → Server lưu reported_hash
3. Admin approve hash → expected_hash = reported_hash
4. Heartbeat tiếp theo → verified ✓
```

### Scenario 2: Agent bị hack
```
1. Agent đang hoạt động bình thường (verified)
2. Attacker modify agent code
3. Heartbeat với hash mới (mismatch)
   - Lần 1: warning
   - Lần 2: warning
   - Lần 3: SUSPENDED
   - Lần 5: REVOKED
```

### Scenario 3: Update agent hợp lệ
```
1. Agent v1.0 đang chạy (verified)
2. Deploy agent v1.1 → hash thay đổi
3. Admin register hash mới cho version 1.1
4. Agent restart → verified với hash mới ✓
```

## Environment Variables

| Variable | Default | Mô tả |
|----------|---------|-------|
| `CONTROL_PLANE_URL` | `http://localhost:8000` | URL của Control Plane |
| `ADMIN_TOKEN` | `test-admin-token` | Token để gọi Admin API |
| `VERBOSE` | `0` | Set `1` để xem output chi tiết |

## Troubleshooting

### Test fail vì import error

```bash
# Set PYTHONPATH
export PYTHONPATH="/home/zero-trust-net/agent:/home/zero-trust-net/control-plane:$PYTHONPATH"
```

### Integration tests bị skip

```bash
# Kiểm tra server có chạy không
curl http://localhost:8000/health

# Start server
cd /home/zero-trust-net/control-plane
uv run uvicorn main:app --port 8000
```

### Coverage report

```bash
# Tạo HTML report
pytest tests/agent/ \
    --cov=agent/collectors/agent_integrity \
    --cov=control-plane/core/agent_integrity \
    --cov-report=html

# Mở report
open htmlcov/index.html
```
