"""
Read REST Server Profile and Open API Profile from /tmp/mz_unzipped
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
    print(" 1. REST SERVER PROFILE: WalletAPI.PRF_WalletAPI_Rest_Server ")
    print("=" * 80)
    print(cat("/tmp/mz_unzipped/Configuration/WalletAPI/REST Server Profile/WalletAPI.PRF_WalletAPI_Rest_Server"))

    print("\n" + "=" * 80)
    print(" 2. OPEN API PROFILE: WalletAPI.PRF_WalletAPI_OpenAPI ")
    print("=" * 80)
    print(cat("/tmp/mz_unzipped/Configuration/WalletAPI/Open API Profile/WalletAPI.PRF_WalletAPI_OpenAPI")[:2500])

    c.close()
except Exception as e:
    print(f"Error: {e}")
