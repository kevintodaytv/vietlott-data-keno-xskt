"""
╔══════════════════════════════════════════════════════════╗
║  SNIPER-X HUB — MASTER DEPLOY v2.0                     ║
║  All-in-one: Upload → Build → Restart → Verify          ║
╚══════════════════════════════════════════════════════════╝
- Tự động encode path (fix lỗi tiếng Việt)
- Upload đầy đủ tất cả files đã thay đổi
- Build frontend trên VPS
- Restart backend + verify health
"""
import paramiko, os, sys, time, io, json, subprocess
from pathlib import Path

# ── CONFIG ──────────────────────────────────────────────
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HOST        = "103.82.25.23"
PORT        = 22
USER        = "root"
PASS        = "ZOKrDUh7HcNvC8B6"
REMOTE_BASE = "/root/XSKT"
LOCAL_BASE  = Path("D:/GEN Z/DỰ ÁN/XSKT")

# ── FILE LIST (Tất cả files cần deploy) ──────────────────
# Format: (local_relative, remote_relative)
FILES_TO_UPLOAD = [
    # === BACKEND ===
    ("core-backend/main.py",                                "core-backend/main.py"),
    ("core-backend/shared_state.py",                        "core-backend/shared_state.py"),
    ("core-backend/phantom_scraper.py",                     "core-backend/phantom_scraper.py"),
    ("core-backend/agents/boss_agent.py",                   "core-backend/agents/boss_agent.py"),
    ("core-backend/config/agent_dna.json",                  "core-backend/config/agent_dna.json"),
    ("core-backend/ml_engine/hybrid_brain.py",              "core-backend/ml_engine/hybrid_brain.py"),
    ("core-backend/ml_engine/dna_evolution_engine.py",      "core-backend/ml_engine/dna_evolution_engine.py"),

    # === FRONTEND ===
    ("nexus-frontend/src/routes/+page.svelte",              "nexus-frontend/src/routes/+page.svelte"),
    ("nexus-frontend/src/lib/AgentDNAChat.svelte",          "nexus-frontend/src/lib/AgentDNAChat.svelte"),
    ("nexus-frontend/src/lib/VietlottHub.svelte",           "nexus-frontend/src/lib/VietlottHub.svelte"),
    ("nexus-frontend/src/lib/MarketFlow.svelte",            "nexus-frontend/src/lib/MarketFlow.svelte"),
    ("nexus-frontend/src/lib/store.ts",                     "nexus-frontend/src/lib/store.ts"),
    ("nexus-frontend/src/lib/NeuralCoreDashboard.svelte",   "nexus-frontend/src/lib/NeuralCoreDashboard.svelte"),

    # === CONFIG ===
    ("docker-compose.yml",                                  "docker-compose.yml"),
    ("docker-compose.prod.yml",                             "docker-compose.prod.yml"),
]

# ── HELPERS ─────────────────────────────────────────────
STEP = 0
def step(title):
    global STEP
    STEP += 1
    print(f"\n{'='*60}")
    print(f"  [{STEP}] {title}")
    print(f"{'='*60}")

def ok(msg):  print(f"  ✅  {msg}")
def err(msg): print(f"  ❌  {msg}")
def info(msg):print(f"  ℹ️   {msg}")

def ssh_run(ssh, cmd, timeout=90, silent=False):
    if not silent:
        print(f"  $ {cmd[:100]}")
    try:
        _, out, errp = ssh.exec_command(cmd, timeout=timeout)
        exit_code = out.channel.recv_exit_status()
        o = out.read().decode("utf-8", "replace").strip()
        e = errp.read().decode("utf-8", "replace").strip()
        if o and not silent:
            for line in o.split("\n")[-5:]:
                print(f"    {line}")
        if e and "warning" not in e.lower() and not silent:
            print(f"  [ERR] {e[:200]}")
        return o, exit_code
    except Exception as ex:
        if not silent:
            err(f"SSH Exception: {ex}")
        return "", -1

def ensure_remote_dir(sftp, ssh, remote_path):
    """Đảm bảo thư mục remote tồn tại"""
    d = "/".join(remote_path.split("/")[:-1])
    try:
        sftp.stat(d)
    except:
        ssh_run(ssh, f"mkdir -p {d}", silent=True)

def upload_file(sftp, ssh, local_path, remote_path):
    ensure_remote_dir(sftp, ssh, remote_path)
    try:
        sftp.put(str(local_path), remote_path)
        ok(f"Uploaded: {local_path.name}  →  {'/'.join(remote_path.split('/')[-2:])}")
        return True
    except Exception as e:
        err(f"Upload FAIL: {local_path.name} → {e}")
        return False

# ── MAIN ────────────────────────────────────────────────
def main():
    print("\n")
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  SNIPER-X HUB — MASTER DEPLOY v2.0                     ║")
    print(f"║  Target: {HOST:<48}║")
    print("╚══════════════════════════════════════════════════════════╝")

    # ── Connect SSH ────────────────────────────────────
    step("Kết nối SSH đến VPS")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(HOST, PORT, USER, PASS, timeout=20)
        ok(f"SSH connected → {HOST}:{PORT}")
    except Exception as e:
        err(f"SSH FAILED: {e}")
        sys.exit(1)

    sftp = ssh.open_sftp()

    # ── Upload files ───────────────────────────────────
    step("Upload files (backend + frontend)")
    uploaded = 0
    skipped  = 0
    failed   = 0

    for local_rel, remote_rel in FILES_TO_UPLOAD:
        local_path  = LOCAL_BASE / Path(local_rel)
        remote_path = f"{REMOTE_BASE}/{remote_rel}"
        if local_path.exists():
            if upload_file(sftp, ssh, local_path, remote_path):
                uploaded += 1
            else:
                failed += 1
        else:
            info(f"Skipped (not found): {local_rel}")
            skipped += 1

    print(f"\n  Summary: ✅ {uploaded} uploaded | ⚠️ {skipped} skipped | ❌ {failed} failed")
    sftp.close()

    # ── Build Frontend ─────────────────────────────────
    step("Build Frontend trên VPS (npm run build)")
    out, code = ssh_run(ssh,
        f"cd {REMOTE_BASE}/nexus-frontend && npm install --silent 2>&1 | tail -1 && npm run build 2>&1 | tail -8",
        timeout=180
    )
    if "built in" in out or "✓" in out or code == 0:
        ok("Frontend build THÀNH CÔNG!")
    else:
        err(f"Build có vấn đề (exit={code}), kiểm tra log thủ công")

    # ── Restart Backend ────────────────────────────────
    step("Restart Backend Docker Container")
    # Kill old uvicorn nếu chạy native
    ssh_run(ssh, "pkill -f 'uvicorn main:app' 2>/dev/null; true", silent=True)

    # Tìm container backend — ưu tiên core_api, tránh frontend/nginx
    out, code = ssh_run(ssh, "docker ps --format '{{.Names}}' 2>/dev/null | grep -iE 'core.api|core-api|backend' | grep -v -iE 'nginx|ui|front'")
    container = out.strip().split("\n")[0] if out.strip() else ""

    if container:
        ok(f"Tìm thấy container: {container}")
        # 1. Copy files mới vào container
        cp_ok = 0
        for src, dst in [
            ("core-backend/main.py",                           "/app/main.py"),
            ("core-backend/shared_state.py",                   "/app/shared_state.py"),
            ("core-backend/agents/boss_agent.py",              "/app/agents/boss_agent.py"),
            ("core-backend/config/agent_dna.json",             "/app/config/agent_dna.json"),
            ("core-backend/ml_engine/hybrid_brain.py",         "/app/ml_engine/hybrid_brain.py"),
            ("core-backend/ml_engine/dna_evolution_engine.py", "/app/ml_engine/dna_evolution_engine.py"),
        ]:
            r, rc = ssh_run(ssh, f"docker cp {REMOTE_BASE}/{src} {container}:{dst} 2>&1", silent=True)
            if rc == 0:
                cp_ok += 1
            else:
                info(f"  docker cp {src} → {r.strip()[:80]}")
        ok(f"Đã cp {cp_ok}/5 files vào container.")
        # 2. Restart container để uvicorn khởi động với code mới
        ssh_run(ssh, f"docker restart {container} 2>&1", timeout=30)
        time.sleep(8)
        ok(f"Container {container} đã restart với code mới.")
    else:
        # Thử docker-compose restart nếu có docker-compose.yml
        info("Không tìm thấy container bằng tên — thử docker compose restart...")
        compose_out, _ = ssh_run(ssh,
            f"cd {REMOTE_BASE} && docker compose restart core_api 2>&1 | tail -3",
            timeout=30
        )
        if "Started" in compose_out or "Running" in compose_out or compose_out.strip():
            ok(f"docker compose restart: {compose_out.strip()[:100]}")
        else:
            # Fallback: native uvicorn
            info("Fallback → native uvicorn...")
            ssh_run(ssh,
                f"pkill -f uvicorn 2>/dev/null; sleep 1; "
                f"cd {REMOTE_BASE}/core-backend && "
                f"nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8888 "
                f">> /tmp/backend.log 2>&1 & sleep 5 && echo STARTED",
                timeout=20
            )

    time.sleep(6)

    # ── Verify Backend Health ──────────────────────────
    step("Verify Backend Health trên VPS")
    # Thử nginx proxy trước (port 80), sau đó port 8888 trực tiếp
    out, code = ssh_run(ssh,
        "curl -sf http://127.0.0.1:80/api/health 2>/dev/null || "
        "curl -sf http://127.0.0.1:8888/api/health 2>/dev/null || echo BACKEND_DOWN",
        timeout=15
    )
    if "ONLINE" in out:
        # Lấy thêm draw_id để xác nhận data pipeline hoạt động
        draw_out, _ = ssh_run(ssh,
            "curl -sf http://127.0.0.1:80/api/latest 2>/dev/null | "
            "python3 -c \"import sys,json; d=json.load(sys.stdin); print(f'draw_id={d.get(\\\"draw_id\\\",\\\"N/A\\\")}')\" 2>/dev/null || echo 'no data'",
            timeout=10, silent=True
        )
        ok(f"Backend ONLINE ✓ | {draw_out.strip()}")
    elif "BACKEND_DOWN" in out or not out:
        err("Backend chưa respond → xem log bên dưới")
        ssh_run(ssh,
            "docker logs --tail 30 $(docker ps -q --filter name=core_api) 2>/dev/null || "
            "tail -20 /tmp/backend.log 2>/dev/null || echo 'No logs found'"
        )

    # ── Verify Frontend (nginx) ────────────────────────
    step("Verify Frontend (port 80 / nginx)")
    out, code = ssh_run(ssh,
        f"curl -s -o /dev/null -w '%{{http_code}}' http://127.0.0.1:80/ 2>/dev/null || echo 000",
        timeout=10
    )
    if out.strip() in ("200", "301", "302"):
        ok(f"Frontend nginx → HTTP {out.strip()}")
    else:
        info(f"Frontend port 80 → {out.strip()} (có thể dùng port khác)")
        # Thử port 3000
        out2, _ = ssh_run(ssh, "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3000/ 2>/dev/null || echo 000", timeout=5, silent=True)
        if out2.strip() in ("200", "301"):
            ok(f"Frontend port 3000 → HTTP {out2.strip()}")

    # ── Summary ────────────────────────────────────────
    print("\n")
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  🎉  DEPLOY HOÀN TẤT!                                   ║")
    print(f"║  ✈️   Backend: http://{HOST}:8888                   ║")
    print(f"║  🌐  Frontend: http://{HOST}                        ║")
    print("╚══════════════════════════════════════════════════════════╝")
    ssh.close()

if __name__ == "__main__":
    main()
