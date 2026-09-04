"""
Paradox Sports OMS - Single Command Development Runtime Runner
Starts FastAPI backend (Port 8000) and Next.js frontend (Port 3000) concurrently
with database pre-flight checks and hot reload.
"""

import os
import signal
import subprocess
import sys
import time

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

def check_database():
    print("[*] 1. Pre-flight Check: Verifying PostgreSQL connection...")
    try:
        from app.core.database import verify_database_connection
        health = verify_database_connection()
        print(f"  [+] PostgreSQL connected successfully (latency: {health.get('latency_ms')}ms)")
    except Exception as exc:
        print(f"  [-] WARNING: Database check failed: {exc}")
        print("  [-] Ensure PostgreSQL is running and DATABASE_URL is set in .env")

def run_dev():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    frontend_dir = os.path.join(root_dir, "frontend")

    print("=" * 80)
    print("PARADOX SPORTS OMS - DEVELOPMENT RUNTIME")
    print("=" * 80)
    print(f"Root Directory:     {root_dir}")
    print(f"Frontend Directory: {frontend_dir}")
    print("=" * 80)

    check_database()

    # Launch FastAPI Backend
    print("\n[*] 2. Launching FastAPI Backend on http://127.0.0.1:8000 ...")
    backend_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
        "--reload",
    ]
    backend_proc = subprocess.Popen(backend_cmd, cwd=root_dir)

    # Wait for FastAPI Backend to be healthy before launching Next.js frontend
    print("  [*] Waiting for FastAPI backend to complete startup (http://127.0.0.1:8000/health)...")
    import urllib.request
    backend_ready = False
    for _ in range(20):
        time.sleep(0.5)
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=1.0) as resp:
                if resp.status == 200:
                    backend_ready = True
                    print("  [+] FastAPI backend is ready and responding.")
                    break
        except Exception:
            pass
    if not backend_ready:
        print("  [!] Backend taking longer than expected to report healthy, proceeding with frontend launch.")

    # Launch Next.js Frontend
    print("\n[*] 3. Launching Next.js Frontend on http://localhost:3000 ...")
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    frontend_cmd = [npm_cmd, "run", "dev"]
    frontend_proc = subprocess.Popen(frontend_cmd, cwd=frontend_dir)

    print("\n" + "=" * 80)
    print("DEVELOPMENT SERVERS ACTIVE:")
    print("  - Backend API:    http://127.0.0.1:8000 (API: /api/v1, Health: /health)")
    print("  - Frontend App:   http://localhost:3000")
    print("  - Press Ctrl+C to terminate both servers safely.")
    print("=" * 80 + "\n")

    def handle_signal(sig, frame):
        print("\n[*] Shutting down development servers...")
        try:
            backend_proc.terminate()
        except Exception:
            pass
        try:
            frontend_proc.terminate()
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        while True:
            time.sleep(1)
            # Monitor process health
            if backend_proc.poll() is not None:
                print(f"[-] Backend process terminated with code {backend_proc.returncode}")
                break
            if frontend_proc.poll() is not None:
                print(f"[-] Frontend process terminated with code {frontend_proc.returncode}")
                break
    except KeyboardInterrupt:
        handle_signal(None, None)

if __name__ == "__main__":
    run_dev()
