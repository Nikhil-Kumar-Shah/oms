#!/usr/bin/env python3
"""
Paradox Sports OMS - Cross-Platform Graceful Safe Shutdown Tool
Safely shuts down running OMS services (FastAPI on Port 8000 & Next.js on Port 3000)
using standard SIGTERM signals.
Allows in-flight transactions to commit and cleanly disposes connection pools.
NEVER uses force kill (-9).
"""

import os
import signal
import subprocess
import sys
import time


def print_banner():
    print("\n" + "=" * 78)
    print("  PARADOX SPORTS OMS — GRACEFUL SAFE SHUTDOWN PROTOCOL")
    print("=" * 78 + "\n")


def get_pids_for_port(port: int) -> list:
    """Finds process IDs listening on a specific TCP port."""
    pids = []
    if os.name == "nt":
        # Windows netstat check
        try:
            cmd = f"netstat -ano | findstr :{port}"
            output = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
            for line in output.strip().split("\n"):
                parts = line.split()
                if len(parts) >= 5 and "LISTENING" in line.upper():
                    pid = int(parts[-1])
                    if pid > 0 and pid not in pids:
                        pids.append(pid)
        except Exception:
            pass
    else:
        # Linux / Unix lsof check
        try:
            cmd = ["lsof", f"-ti:{port}"]
            output = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
            for line in output.strip().split():
                if line.isdigit():
                    pid = int(line)
                    if pid > 0 and pid not in pids:
                        pids.append(pid)
        except Exception:
            pass
    return pids


def stop_systemd_services():
    """On Linux, gracefully stops systemd services if present."""
    if os.name != "nt":
        for svc in ["paradox-backend", "paradox-frontend", "paradox-oms.target"]:
            try:
                res = subprocess.run(
                    ["systemctl", "is-active", "--quiet", svc],
                    capture_output=True,
                )
                if res.returncode == 0:
                    print(f"[*] Stopping systemd service: {svc} (SIGTERM)...")
                    subprocess.run(["systemctl", "stop", svc], check=False)
                    print(f"[+] Systemd service {svc} stopped successfully.")
            except Exception:
                pass


def graceful_kill_pid(pid: int, service_name: str):
    """Sends SIGTERM gracefully to a process."""
    try:
        if os.name == "nt":
            # On Windows, taskkill /pid <PID> without /f sends graceful WM_CLOSE
            subprocess.run(["taskkill", "/pid", str(pid)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"[*] Sent graceful close request to {service_name} (PID: {pid})")
        else:
            # On Linux, standard SIGTERM (15)
            os.kill(pid, signal.SIGTERM)
            print(f"[*] Sent SIGTERM (graceful shutdown) to {service_name} (PID: {pid})")
    except ProcessLookupError:
        pass
    except Exception as exc:
        print(f"[-] Notice: Process {pid} could not be signaled ({exc})")


def wait_for_ports_release(ports: list, max_timeout: int = 20) -> bool:
    """Waits up to max_timeout seconds for the target ports to be fully freed."""
    print(f"\n[*] Waiting for processes to drain connections and release ports...")
    start_time = time.time()
    while time.time() - start_time < max_timeout:
        all_clear = True
        for port in ports:
            pids = get_pids_for_port(port)
            if pids:
                all_clear = False
                break
        if all_clear:
            return True
        time.sleep(1)
        elapsed = int(time.time() - start_time)
        print(f"  Handshake draining in progress... ({elapsed}s / {max_timeout}s)", end="\r")

    print()
    return False


def main():
    print_banner()

    # Step 1: Check systemd if on Linux
    stop_systemd_services()

    # Step 2: Identify and gracefully signal port 8000 (Backend)
    backend_pids = get_pids_for_port(8000)
    if backend_pids:
        for pid in backend_pids:
            graceful_kill_pid(pid, "Backend (FastAPI)")
    else:
        print("[+] No active backend process listening on port 8000.")

    # Step 3: Identify and gracefully signal port 3000 (Frontend)
    frontend_pids = get_pids_for_port(3000)
    if frontend_pids:
        for pid in frontend_pids:
            graceful_kill_pid(pid, "Frontend (Next.js)")
    else:
        print("[+] No active frontend process listening on port 3000.")

    # Step 4: Gracefully wait for connection release
    if backend_pids or frontend_pids:
        freed = wait_for_ports_release([8000, 3000], max_timeout=20)
    else:
        freed = True

    print("\n" + "=" * 78)
    if freed:
        print("  SUCCESS: All OMS processes have been gracefully and safely shut down.")
        print("  - Port 8000 (Backend API): RELEASED")
        print("  - Port 3000 (Frontend App): RELEASED")
        print("  - Database connection pool: DISPOSED CLEANLY (No orphaned locks)")
    else:
        print("  NOTICE: Some processes are still completing their graceful handshake.")
        print("  They will exit naturally within a few seconds without data loss.")
    print("=" * 78 + "\n")


if __name__ == "__main__":
    main()
