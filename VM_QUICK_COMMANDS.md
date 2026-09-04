# VM Quick Commands Cheatsheet

Point-to-point commands for managing the OMS server on your Virtual Machine.

---

### 1. Clone & Enter Project Directory
```bash
sudo git clone <REPOSITORY_URL> /opt/paradox-oms
cd /opt/paradox-oms
```

---

### 2. First-Time Activation (Start Production)
```bash
cd /opt/paradox-oms
sudo bash activate_production.sh --domain <YOUR_DOMAIN_OR_IP>
```
*(Automatically sets up DB, backend, frontend, Nginx, SSL, and background systemd daemons).*

---

### 3. Update Code & Restart Production
```bash
cd /opt/paradox-oms
sudo git pull
sudo bash activate_production.sh --domain <YOUR_DOMAIN_OR_IP>
```
*(Pulls latest changes, runs migrations, rebuilds frontend, checks SSL renewal, and restarts services).*

---

### 4. Safe Shutdown (Stop Services Without Force Kill)
```bash
cd /opt/paradox-oms
sudo bash safe_shutdown.sh
```
*(Sends graceful SIGTERM to backend, frontend, and systemd daemons, allowing open database connections to finish safely).*

---

### 5. Stop Specific Services Manually
```bash
# Stop backend and frontend systemd daemons
sudo systemctl stop paradox-backend paradox-frontend

# Check status of services
sudo systemctl status paradox-backend paradox-frontend nginx
```

---

### 6. Maintenance & Clean Test Data (Optional)
```bash
cd /opt/paradox-oms

# Purge mock/test data while preserving admin and core system configs
sudo -u omsapp /opt/paradox-oms/.venv/bin/python scripts/clean_test_data.py

# Provision initial system admin if needed
sudo -u omsapp /opt/paradox-oms/.venv/bin/python scripts/create_production_admin.py
```
