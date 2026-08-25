"""
Unzip /tmp/mz_systemexport_dir.zip on QAS MZ server and inspect PRF_AGG_WALLETAPI and all aggregation workflows.
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

    # 1. Unzip export zip
    print("\n--- 1. UNZIPPING EXPORT ARCHIVE ---")
    cmd_unzip = "rm -rf /tmp/mz_unzipped && unzip -q /tmp/mz_systemexport_dir.zip -d /tmp/mz_unzipped 2>&1"
    stdin, stdout, stderr = c.exec_command(cmd_unzip)
    print("Unzipped into /tmp/mz_unzipped")

    # 2. Find all Aggregation profiles and workflows in unzipped export
    print("\n--- 2. AGGREGATION PROFILES & WORKFLOWS FOUND ---")
    cmd_find_agg = "find /tmp/mz_unzipped -iname '*agg*' -o -iname '*dedup*' -o -iname '*reversal*' 2>/dev/null"
    stdin, stdout, stderr = c.exec_command(cmd_find_agg)
    found_agg = stdout.read().decode('utf-8', errors='replace').strip()
    print(found_agg or "No matching files")

    # 3. Read WalletAPI.PRF_AGG_WALLETAPI content
    print("\n--- 3. CONTENTS OF WalletAPI.PRF_AGG_WALLETAPI ---")
    cmd_cat_prf = "find /tmp/mz_unzipped -name '*PRF_AGG_WALLETAPI*' -exec cat {} \\; 2>/dev/null"
    stdin, stdout, stderr = c.exec_command(cmd_cat_prf)
    prf_content = stdout.read().decode('utf-8', errors='replace').strip()
    print(prf_content[:3000] if prf_content else "Profile file not found or empty")

    # 4. Search for APL code or workflow files containing aggregation / duplicate logic
    print("\n--- 4. GREP FOR AGGREGATION & DEDUPLICATION IN ALL EXPORTED FILES ---")
    cmd_grep = "grep -rn -i 'aggr\\|dedup\\|duplicate\\|mapPut\\|mapGet\\|drain' /tmp/mz_unzipped 2>/dev/null | head -50"
    stdin, stdout, stderr = c.exec_command(cmd_grep)
    grep_res = stdout.read().decode('utf-8', errors='replace').strip()
    print(grep_res or "No direct matches found in unzipped text files")

    c.close()
except Exception as e:
    print(f"Error: {e}")
