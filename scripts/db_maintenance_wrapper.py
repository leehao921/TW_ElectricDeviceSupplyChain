#!/usr/bin/env python3
"""launchd TCC wrapper — bash 直接被 launchd spawn 讀 ~/Documents 會 EPERM
(2026-08-25 db-backup exit 126 實災;platform binary 無法持有 TCC 授權)。
以已授權的 venv python 為 top process, 子行程繼承其 TCC session。

Usage: db_maintenance_wrapper.py {backup|drill}
"""
import subprocess
import sys

SCRIPTS = {
    "backup": "/Users/lulala/Documents/coding/database/scripts/db_maintenance/selective_backup.sh",
    "drill": "/Users/lulala/Documents/coding/database/scripts/db_maintenance/restore_drill.sh",
}

if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "backup"
    sys.exit(subprocess.call(["/bin/bash", SCRIPTS[which]]))
