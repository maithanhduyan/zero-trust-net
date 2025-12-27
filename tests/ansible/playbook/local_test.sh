#!bin/bash
cd /home/zero-trust-netwoking/infrastructure/ansible && ansible-playbook -i inventory/local.ini playbook/test-local.yml 2>&1

# Syntax check passed!
cd /home/zero-trust-netwoking/infrastructure/ansible && timeout 60 ansible-playbook -i inventory/local.ini playbook/test-local.yml --syntax-check 2>&1

# Kiểm tra syntax của site.yml:
cd /home/zero-trust-netwoking/infrastructure/ansible && ansible-playbook site.yml --syntax-check 2>&1

# Kiểm tra các roles:
cd /home/zero-trust-netwoking/infrastructure/ansible && ansible-playbook -i inventory/local.ini playbook/test-local.yml --list-tasks 2>&1

# Chạy thử test playbook:
cd /home/zero-trust-netwoking/infrastructure/ansible && ansible-playbook -i inventory/local.ini playbook/test-local.yml 2>&1 | head -120

cd /home/zero-trust-netwoking/infrastructure/ansible && ansible-playbook -i inventory/local.ini playbook/test-local.yml 2>&1 | tail -60

# 1. Test locally first
cd infrastructure/ansible && ansible-playbook -i inventory/local.ini playbook/test-local.yml

# 2. Edit inventory với server thật
vim inventory/hosts.ini

# 3. Set admin secret
export ADMIN_SECRET="your-secure-secret"

# 4. Deploy
ansible-playbook -i inventory/hosts.ini site.yml

# Hoặc deploy từng phase:
ansible-playbook -i inventory/hosts.ini site.yml --tags hub
ansible-playbook -i inventory/hosts.ini site.yml --tags agents
ansible-playbook -i inventory/hosts.ini site.yml --tags verify