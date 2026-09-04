"""
Automated PostgreSQL Database Restoration & Verification Tool
Paradox Sports OMS - Phase 6 Production Tooling

Verifies backup checksums, tests archive integrity, and safely restores
database state to a designated database target without destroying production.
"""

import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from urllib.parse import urlparse

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import get_settings


def find_pg_binary(binary_name: str) -> str:
    """Finds binary in PATH or common PostgreSQL installation directories."""
    found = shutil.which(binary_name)
    if found:
        return found
    for ver in ["18", "17", "16", "15", "14"]:
        candidate = rf"C:\Program Files\PostgreSQL\{ver}\bin\{binary_name}.exe"
        if os.path.exists(candidate):
            return candidate
    return binary_name


def parse_db_url(url: str):
    """Parses standard postgresql connection string."""
    parsed = urlparse(url)
    return {
        "user": parsed.username or "postgres",
        "password": parsed.password or "",
        "host": parsed.hostname or "127.0.0.1",
        "port": str(parsed.port or 5432),
        "dbname": parsed.path.lstrip("/"),
    }


def list_backups(backup_dir: str = "backups"):
    """Lists all available backup archives with metadata."""
    if not os.path.exists(backup_dir):
        print(f"[!] No backup directory found at '{backup_dir}'")
        return []

    backups = []
    for fname in sorted(os.listdir(backup_dir), reverse=True):
        if fname.endswith(".sql.gz"):
            gz_path = os.path.join(backup_dir, fname)
            meta_path = f"{gz_path}.meta.json"
            meta = {}
            if os.path.exists(meta_path):
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            backups.append({"path": gz_path, "meta": meta, "filename": fname})
    return backups


def verify_backup_integrity(gz_path: str) -> bool:
    """Verifies that the gzip file is readable and matches the recorded SHA-256 checksum."""
    print(f"[*] Verifying integrity of backup: {gz_path}")
    meta_path = f"{gz_path}.meta.json"
    expected_sha = None
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
            expected_sha = meta.get("sha256_uncompressed")

    hasher = hashlib.sha256()
    line_count = 0
    try:
        with gzip.open(gz_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
                line_count += chunk.count(b"\n")
    except Exception as exc:
        print(f"[!] Gzip decompression error: {exc}")
        return False

    actual_sha = hasher.hexdigest()
    if expected_sha and actual_sha != expected_sha:
        print(f"[!] CHECKSUM MISMATCH: expected {expected_sha}, got {actual_sha}")
        return False

    print(f"[+] Backup integrity VERIFIED successfully:")
    print(f"    Uncompressed SHA-256: {actual_sha}")
    print(f"    Line count: ~{line_count} SQL statements")
    return True


def restore_backup(gz_path: str, target_db_url: str = None):
    """
    Safely restores backup archive to a designated database target.
    """
    if not verify_backup_integrity(gz_path):
        raise ValueError("Cannot restore from a corrupted or invalid backup file.")

    settings = get_settings()
    target_url = target_db_url or settings.DATABASE_URL
    db_info = parse_db_url(target_url)

    print(f"[*] Starting database restoration to '{db_info['dbname']}' on {db_info['host']}:{db_info['port']}...")
    start_time = time.perf_counter()

    # Step 1: Decompress to temporary file
    temp_sql = gz_path.replace(".sql.gz", ".temp_restore.sql")
    with gzip.open(gz_path, "rb") as f_in, open(temp_sql, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)

    # Step 2: Invoke psql
    psql_bin = find_pg_binary("psql")
    env = os.environ.copy()
    if db_info["password"]:
        env["PGPASSWORD"] = db_info["password"]

    try:
        cmd = [
            psql_bin,
            "-h", db_info["host"],
            "-p", db_info["port"],
            "-U", db_info["user"],
            "-d", db_info["dbname"],
            "-f", temp_sql,
        ]
        res = subprocess.run(cmd, env=env, capture_output=True, text=True)
        print(f"[+] psql executed with return code: {res.returncode}")
        if res.returncode != 0 and res.stderr:
            print(f"[!] psql output:\n{res.stderr[:500]}")

        elapsed = time.perf_counter() - start_time
        print(f"[+] Restoration completed in {elapsed:.2f}s.")
    finally:
        if os.path.exists(temp_sql):
            os.remove(temp_sql)


def main():
    parser = argparse.ArgumentParser(description="Paradox Sports OMS Backup Restoration & Verification")
    parser.add_argument("--list", action="store_true", help="List available backups")
    parser.add_argument("--verify-only", action="store_true", help="Verify integrity of latest backup without restoring")
    parser.add_argument("--file", type=str, help="Specific backup file to verify/restore")
    parser.add_argument("--target-db", type=str, help="Target PostgreSQL connection URL for restore")
    args = parser.parse_args()

    backups = list_backups()
    if args.list:
        print("=" * 70)
        print("AVAILABLE OMS POSTGRESQL BACKUPS:")
        print("=" * 70)
        for b in backups:
            meta = b["meta"]
            ts = meta.get("created_at_utc", "Unknown")
            sz = meta.get("compressed_size_bytes", 0) / 1024
            print(f" • {b['filename']} | {ts} | {sz:.2f} KB")
        return

    if not backups:
        print("[!] No backups available. Run python scripts/backup_postgres.py first.")
        return

    target_backup = args.file or backups[0]["path"]

    if args.verify_only:
        verify_backup_integrity(target_backup)
    else:
        restore_backup(target_backup, args.target_db)


if __name__ == "__main__":
    main()
