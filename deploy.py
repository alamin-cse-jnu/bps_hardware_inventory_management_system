"""
One-shot deployment script — Parliament Intranet Server
Uses paramiko for SSH/SFTP without needing sshpass.
"""
import os
import sys
import stat
import time
import paramiko

# Force UTF-8 output on Windows to handle apt/docker Unicode chars
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SERVER_IP   = "172.16.220.159"
SERVER_USER = "root"
SERVER_PASS = "Bps@it2025"
REMOTE_DIR  = "/opt/parliament-inventory"
LOCAL_DIR   = os.path.dirname(os.path.abspath(__file__))

# Directories and file patterns to skip when uploading
SKIP_DIRS  = {".git", "__pycache__", "node_modules", ".pytest_cache",
              "staticfiles", "media", "htmlcov", ".venv", "venv"}
SKIP_EXTS  = {".pyc", ".pyo", ".log", ".sqlite3"}

PROD_ENV = """\
# Parliament IT Inventory — Production
SECRET_KEY=NAkEQL3(J12Gnij=(1Ti#Yea-2J1^)R+JvtK^xL!5DX5-@4zG!
DEBUG=False
ALLOWED_HOSTS=172.16.220.159,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://172.16.220.159

POSTGRES_DB=parliament_inventory
POSTGRES_USER=parliament
POSTGRES_PASSWORD=8BfOfgksAzmo5TOgBFHb
POSTGRES_HOST=db
POSTGRES_PORT=5432

REDIS_URL=redis://redis:6379/0

PRP_API_BASE_URL=https://prp.parliament.gov.bd
PRP_API_USERNAME=alamin
PRP_API_PASSWORD=Al@min91
"""

# ── helpers ──────────────────────────────────────────────────────────────────

def run(ssh, cmd, check=True):
    print(f"  $ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True)
    out = stdout.read().decode(errors="replace").strip()
    err = stderr.read().decode(errors="replace").strip()
    rc  = stdout.channel.recv_exit_status()
    if out:
        print(f"    {out}")
    if err and rc != 0:
        print(f"    ERR: {err}")
    if check and rc != 0:
        print(f"\n[FAIL] Command exited {rc}: {cmd}")
        sys.exit(1)
    return rc, out

def sftp_mkdir_p(sftp, remote_path):
    parts = remote_path.split("/")
    path = ""
    for part in parts:
        if not part:
            path = "/"
            continue
        path = f"{path}/{part}" if path != "/" else f"/{part}"
        try:
            sftp.stat(path)
        except FileNotFoundError:
            sftp.mkdir(path)

def upload_dir(sftp, local_root, remote_root):
    total = 0
    for dirpath, dirnames, filenames in os.walk(local_root):
        # Prune skip dirs in-place so os.walk doesn't descend into them
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        rel = os.path.relpath(dirpath, local_root).replace("\\", "/")
        remote_path = remote_root if rel == "." else f"{remote_root}/{rel}"
        sftp_mkdir_p(sftp, remote_path)
        for fname in filenames:
            if any(fname.endswith(ext) for ext in SKIP_EXTS):
                continue
            local_file  = os.path.join(dirpath, fname)
            remote_file = f"{remote_path}/{fname}"
            sftp.put(local_file, remote_file)
            total += 1
            if total % 50 == 0:
                print(f"    uploaded {total} files...")
    return total

# ── main ─────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*60}")
    print(f"  Parliament Inventory — Deployment to {SERVER_IP}")
    print(f"{'='*60}\n")

    # 1 ── Connect
    print("[1/6] Connecting to server...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER_IP, username=SERVER_USER, password=SERVER_PASS, timeout=15)
    print("      Connected.\n")

    # 2 ── Check / install Docker
    print("[2/6] Checking Docker...")
    rc, out = run(ssh, "docker compose version 2>/dev/null || docker-compose version 2>/dev/null", check=False)
    if rc != 0:
        print("      Docker not found — installing...")
        run(ssh, "apt-get update -qq")
        run(ssh, "apt-get install -y -qq ca-certificates curl gnupg lsb-release")
        run(ssh, "install -m 0755 -d /etc/apt/keyrings")
        run(ssh, "curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg")
        run(ssh, 'echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] '
                 'https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" '
                 '| tee /etc/apt/sources.list.d/docker.list')
        run(ssh, "apt-get update -qq")
        run(ssh, "apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin")
        run(ssh, "systemctl enable --now docker")
        print("      Docker installed.\n")
    else:
        print(f"      OK — {out.splitlines()[0]}\n")

    # 3 ── Upload project files
    print(f"[3/6] Uploading project files to {REMOTE_DIR}...")
    sftp = ssh.open_sftp()
    try:
        sftp.stat(REMOTE_DIR)
        print(f"      Directory exists — overwriting files...")
    except FileNotFoundError:
        sftp_mkdir_p(sftp, REMOTE_DIR)
    total = upload_dir(sftp, LOCAL_DIR, REMOTE_DIR)
    print(f"      Done — {total} files uploaded.\n")

    # 4 ── Write production .env
    print("[4/6] Writing production .env...")
    with sftp.open(f"{REMOTE_DIR}/.env", "w") as f:
        f.write(PROD_ENV)
    sftp.close()
    print("      Done.\n")

    # 5 ── Build and start containers
    print("[5/6] Building and starting containers (this takes ~2–3 min)...")
    run(ssh, f"cd {REMOTE_DIR} && docker compose -f docker-compose.yml -f docker-compose.prod.yml down --remove-orphans 2>/dev/null; true", check=False)
    run(ssh, f"cd {REMOTE_DIR} && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build", check=True)
    print("      Containers started.\n")

    # 6 ── Wait for web to be healthy then show status
    print("[6/6] Waiting for app to be ready...")
    for i in range(24):  # up to 2 min
        rc, out = run(ssh, f"cd {REMOTE_DIR} && docker compose ps --format 'table {{{{.Service}}}}\\t{{{{.Status}}}}'", check=False)
        if "running" in out.lower() or "healthy" in out.lower():
            break
        time.sleep(5)
    run(ssh, f"cd {REMOTE_DIR} && docker compose -f docker-compose.yml -f docker-compose.prod.yml ps", check=False)

    print(f"""
{'='*60}
  Deployment complete!

  App:    http://{SERVER_IP}
  Admin:  http://{SERVER_IP}/admin/

  Create admin account (run once):
    ssh root@{SERVER_IP}
    cd {REMOTE_DIR}
    docker compose exec web python manage.py createsuperuser

  View logs:
    docker compose logs -f web
{'='*60}
""")
    ssh.close()

if __name__ == "__main__":
    main()
