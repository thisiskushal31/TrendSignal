# Deploy on a VM

Run TrendSignal on a Linux VM (e.g. EC2, GCE, Azure VM, or any box with Docker or Python).

---

## Option A: Docker on VM

1. **SSH into the VM.**

2. **Install Docker** (if not already):
   ```bash
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker $USER
   # log out and back in, or: newgrp docker
   ```

3. **Copy the project** (or clone from git):
   ```bash
   scp -r TrendSignal user@vm:/home/user/
   ```

4. **On the VM, create `.env`** with your OpenAI key:
   ```bash
   cd /home/user/TrendSignal
   echo "OPENAI_API_KEY=sk-your-key" > .env
   ```

5. **Build and run** (from repo root; copy deploy ignore first so Docker uses it):
   ```bash
   cp deploy/.dockerignore .
   docker build -f deploy/Dockerfile -t trend-signal .
   docker run -d --name trend-signal -p 8001:8001 --env-file .env trend-signal
   ```

6. **Open** `http://<VM-IP>:8001` (ensure firewall allows port 8001).

7. **Optional — restart on reboot:** use the `deploy/vm/run-docker.sh` script with systemd (see below).

---

## Option B: Python on VM (no Docker)

1. **SSH into the VM.**

2. **Install Python 3.11+** and create a venv:
   ```bash
   sudo apt update && sudo apt install -y python3 python3-venv python3-pip
   cd /home/user/TrendSignal
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r app/requirements.txt
   ```

3. **Create `.env`** (e.g. `cp app/.env.example .env`) with `OPENAI_API_KEY=sk-your-key`.

4. **Run the API:**
   ```bash
   python -m app.api
   ```
   Or run in background: `nohup python -m app.api &` or use the systemd unit below.

5. **Open** `http://<VM-IP>:8001`.

---

## Optional: systemd unit (Docker)

Save as `/etc/systemd/system/trend-signal.service` (adjust paths and user):

```ini
[Unit]
Description=TrendSignal API
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/user/TrendSignal
ExecStartPre=-/usr/bin/docker stop trend-signal
ExecStartPre=-/usr/bin/docker rm trend-signal
ExecStart=/usr/bin/docker run --name trend-signal -p 8001:8001 --env-file .env trend-signal
ExecStop=/usr/bin/docker stop trend-signal
User=user

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable trend-signal
sudo systemctl start trend-signal
```
