"""
Inspect MZ servers (QAS 10.4.15.134 and DEV 10.4.4.128)
Find all workflows, export configs, search for APL files & aggregation logic.
"""

import paramiko
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

SERVERS = [
    {"name": "QAS", "host": "10.4.15.134", "user": "mzadmin", "pass": "Security#1"},
    {"name": "DEV", "host": "10.4.4.128",  "user": "mzadmin", "pass": "Security#1"}
]

def inspect_server(srv):
    print(f"\n{'='*80}")
    print(f" CONNECTING TO {srv['name']} ({srv['host']}) ")
    print(f"{'='*80}")
    
    try:
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(srv["host"], port=22, username=srv["user"], password=srv["pass"], timeout=10)
        print(f"✅ Connected to {srv['name']}")
        
        # Determine mzsh path
        mzsh_cmd = "/mz8/bin/mzsh"
        stdin, stdout, stderr = c.exec_command("test -f /mz9/bin/mzsh && echo /mz9/bin/mzsh || echo /mz8/bin/mzsh")
        mzsh_path = stdout.read().decode('utf-8', errors='replace').strip()
        print(f"MZSH Path: {mzsh_path}")
        
        # Check running workflows via mzsh
        print("\n--- 1. ACTIVE WORKFLOWS (`wflist -active`) ---")
        stdin, stdout, stderr = c.exec_command(f"{mzsh_path} mzadmin/dr wflist -active 2>&1")
        wfl_active = stdout.read().decode('utf-8', errors='replace').strip()
        print(wfl_active[:2000] if wfl_active else "No response")
        
        print("\n--- 2. ALL WORKFLOWS (`wflist -long`) ---")
        stdin, stdout, stderr = c.exec_command(f"{mzsh_path} mzadmin/dr wflist -long 2>&1")
        wfl_all = stdout.read().decode('utf-8', errors='replace').strip()
        print(wfl_all[:2000] if wfl_all else "No response")
        
        print("\n--- 3. SEARCH FOR AGGREGATION / DEDUPLICATION / WFL FILES ---")
        cmd_find = "find /mz8 /mz9 /opt /home -name '*aggre*' -o -name '*dedup*' -o -name '*duplicate*' -o -name '*.apl' -o -name '*.wfl' 2>/dev/null | head -50"
        stdin, stdout, stderr = c.exec_command(cmd_find)
        found_files = stdout.read().decode('utf-8', errors='replace').strip()
        print(found_files or "No matching files found via search")
        
        # Export workflows to /tmp/mz_export_inspect
        print("\n--- 4. EXPORTING ALL CONFIGS TO /tmp/mz_export_inspect ---")
        export_cmd = f"{mzsh_path} mzadmin/dr export /tmp/mz_export_inspect 2>&1"
        stdin, stdout, stderr = c.exec_command(export_cmd, timeout=60)
        export_out = stdout.read().decode('utf-8', errors='replace').strip()
        print(export_out[:300] if export_out else "Export completed.")
        
        print("\n--- 5. GREP IN EXPORT FOR AGGREGATION / DUPLICATE / MAP / DRAIN ---")
        grep_cmd = "grep -rn -i 'aggregation\\|aggregate\\|deduplicat\\|duplicate\\|drain\\|agg_map' /tmp/mz_export_inspect 2>/dev/null | head -50"
        stdin, stdout, stderr = c.exec_command(grep_cmd, timeout=30)
        grep_res = stdout.read().decode('utf-8', errors='replace').strip()
        print(grep_res or "No direct matches found for aggregation/duplicate terms in export.")
        
        c.close()
    except Exception as e:
        print(f"❌ Error connecting to {srv['name']}: {e}")

for srv in SERVERS:
    inspect_server(srv)
