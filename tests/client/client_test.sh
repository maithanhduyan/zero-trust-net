#!bin/bash
# tests/install/new_install_test.sh

# Event Bus and Domain Events Test Script
cd /home/zero-trust-netwoking/control-plane && python -c "
from core.events import event_bus, publish, Event
from core.domain_events import EventTypes
from core.event_handlers import register_event_handlers

# Test event bus
print('Testing Event Bus...')

# Track if handler was called
handler_called = []

def test_handler(event):
    handler_called.append(event.event_type)
    print(f'  Handler received: {event.event_type}')

# Subscribe
event_bus.subscribe('TestEvent', test_handler)

# Publish
publish('TestEvent', {'message': 'Hello World'}, source='Test')

# Verify
assert len(handler_called) == 1, 'Handler was not called!'
print('✓ Event Bus works correctly')

# Test domain events
print('Testing Domain Events...')
from core.domain_events import node_registered_payload, client_device_created_payload
payload = node_registered_payload(1, 'test-node', '10.10.0.5', 'pubkey123', 'app')
assert 'node_id' in payload
print('✓ Domain Events defined correctly')

print('\\nAll tests passed!')
"

# deploy lên production:
rsync -av --exclude='__pycache__' --exclude='.venv' --exclude='*.pyc' /home/zero-trust-netwoking/control-plane/ /opt/zero-trust/control-plane/ && echo "Files synced successfully"


#
systemctl restart zero-trust-control-plane && sleep 3 && systemctl status zero-trust-control-plane --no-pager

journalctl -u zero-trust-control-plane -n 30 --no-pager | grep -E "(Event|handler|WebSocket|register)" || echo "Checking startup logs..."

journalctl -u zero-trust-control-plane -n 50 --no-pager

# Test tạo client device mới để verify events được publish:
cd /opt/zero-trust && ./scripts/ztctl client add Pixel-Event-Test --type=mobile --user=events@test.com --tunnel=full --expires=30

# websocket status check:
curl -s http://localhost:8000/api/v1/ws/status | python3 -m json.tool

# Test revoke để verify event được publish:
cd /opt/zero-trust && ./scripts/ztctl client revoke 5