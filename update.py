"""
Incremental update — uploads changed project files and restarts the web container.
Use this for template, CSS, Python, or config changes (no new packages).

If you added packages to requirements.txt, run deploy.py instead (full rebuild).

Usage:
    python update.py
"""
import os, sys, time
import paramiko

SERVER_IP   = "172.16.220.159"
SERVER_USER = "root"
SERVER_PASS = "Bps@it2025"
REMOTE_DIR  = "/opt/parliament-inventory"
LOCAL_DIR   = os.path.dirname(os.path.abspath(__file__))
CONTAINER   = "parliament-inventory-web-1"

SKIP_DIRS  = {".git", "__pycache__", "node_modules", ".pytest_cache",
              "staticfiles", "media", "htmlcov", ".venv", "venv"}
SKIP_EXTS  = {".pyc", ".pyo", ".log", ".sqlite3"}
# Never overwrite production secrets/config on the server
SKIP_FILES = {".env", ".env.local", ".env.production"}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def run(ssh, cmd):
    _, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    rc  = stdout.channel.recv_exit_status()
    if out: print(f"  {out}")
    if err and rc != 0: print(f"  ERR: {err[:300]}")
    return rc

def upload_all(sftp):
    total = 0
    for dirpath, dirnames, filenames in os.walk(LOCAL_DIR):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        rel = os.path.relpath(dirpath, LOCAL_DIR).replace("\\", "/")
        remote_path = REMOTE_DIR if rel == "." else f"{REMOTE_DIR}/{rel}"
        # Ensure remote dir exists
        try:
            sftp.stat(remote_path)
        except FileNotFoundError:
            sftp.mkdir(remote_path)
        for fname in filenames:
            if any(fname.endswith(ext) for ext in SKIP_EXTS):
                continue
            if fname in SKIP_FILES:
                continue
            sftp.put(os.path.join(dirpath, fname), f"{remote_path}/{fname}")
            total += 1
            if total % 50 == 0:
                print(f"  {total} files...")
    return total

def main():
    print(f"\n{'='*55}")
    print(f"  Updating Parliament Inventory → {SERVER_IP}")
    print(f"{'='*55}\n")

    print("[1/3] Connecting...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER_IP, username=SERVER_USER, password=SERVER_PASS, timeout=15)
    print("      Connected.\n")

    print("[2/3] Uploading project files...")
    sftp = ssh.open_sftp()
    n = upload_all(sftp)
    sftp.close()
    print(f"      {n} files uploaded.\n")

    print("[3/3] Copying into container and restarting web...")
    # Copy key dirs directly into the live container (instant, no rebuild needed)
    for src_dir in ("templates", "static", "config"):
        run(ssh, f"docker cp {REMOTE_DIR}/{src_dir} {CONTAINER}:/app/{src_dir}")
    # Copy all app directories (Python files)
    for app in ("assets", "assignees", "assignments", "lifecycle",
                "locations", "qrcodes", "sync_prp", "reports"):
        run(ssh, f"docker cp {REMOTE_DIR}/{app} {CONTAINER}:/app/{app}")
    # Restart gunicorn to reload Python modules and clear template cache
    run(ssh, f"cd {REMOTE_DIR} && docker compose -f docker-compose.yml "
             f"-f docker-compose.prod.yml restart web")
    time.sleep(3)
    # Verify
    _, o, _ = ssh.exec_command(f"cd {REMOTE_DIR} && docker compose ps web --format 'table {{{{.Service}}}}\\t{{{{.Status}}}}'")
    print(f"  {o.read().decode('utf-8', errors='replace').strip()}")

    print(f"""
{'='*55}
  Update complete!  http://{SERVER_IP}
{'='*55}
""")
    ssh.close()

if __name__ == "__main__":
    main()
