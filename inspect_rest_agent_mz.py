"""
Inspect REST Agent profiles, Web Service / REST server settings, and REST APL handling in /tmp/mz_unzipped
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

    # 1. Find REST profiles
    print("=" * 80)
    print(" 1. REST PROFILES & WORKFLOW AGENTS IN MZ EXPORT ")
    print("=" * 80)
    cmd_rest_files = "find /tmp/mz_unzipped -iname '*rest*' -o -iname '*http*' -o -iname '*openapi*' 2>/dev/null"
    stdin, stdout, stderr = c.exec_command(cmd_rest_files)
    print(stdout.read().decode('utf-8', errors='replace').strip())

    # 2. Grep for REST request parsing in WFL_Wallet_API
    print("\n" + "=" * 80)
    print(" 2. REST REQUEST HANDLING IN WalletAPI.WFL_Wallet_API ")
    print("=" * 80)
    cmd_rest_wfl = "grep -n -C 15 -i 'RESTreq\\|openapi\\|HTTP\\|web_service\\|rest' '/tmp/mz_unzipped/Configuration/WalletAPI/Workflow/WalletAPI.WFL_Wallet_API' | head -80"
    stdin, stdout, stderr = c.exec_command(cmd_rest_wfl)
    print(stdout.read().decode('utf-8', errors='replace').strip())

    c.close()
except Exception as e:
    print(f"Error: {e}")
