"""
Inspect MZ systemexport and find exact workflows containing aggregation or duplicate filters.
"""

import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')

HOST = "10.4.15.134"
PORT = 22
USER = "mzadmin"
PASS = "Security#1"

try:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=10)
    print("Connected to QAS MZ server.")

    # 1. Test systemexport syntax
    print("\n--- 1. TESTING systemexport COMMAND ---")
    stdin, stdout, stderr = c.exec_command("/mz8/bin/mzsh mzadmin/dr systemexport /tmp/mz_systemexport_dir 2>&1")
    out = stdout.read().decode('utf-8', errors='replace').strip()
    print(out[:1000] if out else "Done")

    # 2. Check exported directory files
    print("\n--- 2. EXPORTED FILES ---")
    stdin, stdout, stderr = c.exec_command("find /tmp/mz_systemexport_dir -type f | head -30")
    files = stdout.read().decode('utf-8', errors='replace').strip()
    print(files or "No files in export dir")

    # 3. Search exported files for aggregation and duplicate keywords
    print("\n--- 3. GREP FOR AGGREGATION & DUPLICATE IN EXPORTED FILES ---")
    cmd_grep = "grep -rn -i 'aggr\\|duplicate\\|dedup\\|agg_map\\|Batch Aggregation\\|Duplicate Batch' /tmp/mz_systemexport_dir 2>/dev/null | head -40"
    stdin, stdout, stderr = c.exec_command(cmd_grep)
    res_grep = stdout.read().decode('utf-8', errors='replace').strip()
    print(res_grep or "No matches found in systemexport")

    c.close()
except Exception as e:
    print(f"Error: {e}")
