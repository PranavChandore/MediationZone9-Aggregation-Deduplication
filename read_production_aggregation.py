"""
Read the exact production MediationZone Aggregation & Deduplication code from /tmp/mz_unzipped
- WalletAPI.WFL_Wallet_API
- WalletAPI.PRF_AGG_WALLETAPI
- WalletAPI.UFL_Int_WalletData
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

    def cat(path):
        stdin, stdout, stderr = c.exec_command(f"cat '{path}' 2>/dev/null")
        return stdout.read().decode('utf-8', errors='replace').strip()

    print("=" * 80)
    print(" 1. AGGREGATION PROFILE: WalletAPI.PRF_AGG_WALLETAPI ")
    print("=" * 80)
    print(cat("/tmp/mz_unzipped/Configuration/WalletAPI/Aggregation Profile/WalletAPI.PRF_AGG_WALLETAPI"))

    print("\n" + "=" * 80)
    print(" 2. ULTRA FORMAT: WalletAPI.UFL_Int_WalletData (DuplicateChecks session) ")
    print("=" * 80)
    print(cat("/tmp/mz_unzipped/Configuration/WalletAPI/Ultra Format/WalletAPI.UFL_Int_WalletData"))

    print("\n" + "=" * 80)
    print(" 3. WORKFLOW AGGREGATION BLOCK: WalletAPI.WFL_Wallet_API ")
    print("=" * 80)
    # Extract lines around Aggregation in WFL_Wallet_API
    cmd_wfl = "grep -n -C 30 'From AGG' '/tmp/mz_unzipped/Configuration/WalletAPI/Workflow/WalletAPI.WFL_Wallet_API'"
    stdin, stdout, stderr = c.exec_command(cmd_wfl)
    wfl_lines = stdout.read().decode('utf-8', errors='replace').strip()
    print(wfl_lines)

    c.close()
except Exception as e:
    print(f"Error: {e}")
