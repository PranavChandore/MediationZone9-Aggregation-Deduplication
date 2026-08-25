"""
MediationZone 9 (InfoZone) — Aggregation & Deduplication Engine Simulation
==========================================================================
Demonstrates how MediationZone handles raw incoming event streams to:
1. Detect and BLOCK duplicate payment requests (preventing double charging).
2. AGGREGATE multi-part valid requests for the same invoice into 1 consolidated output.
3. ROUTE invalid requests to ECS Quarantined Error Queue for operator review.
4. PRODUCE clean output ready for downstream SAP HANA / Billing posting.
"""

import os
import sys
import time
from datetime import datetime

# Force UTF-8 output formatting for terminal compatibility
sys.stdout.reconfigure(encoding='utf-8')


# ==============================================================================
# 1. INPUT STREAM (Raw UDRs coming from Gateway / Webhooks / Network switches)
# ==============================================================================
RAW_UDR_STREAM = [
    # Normal Payment #1
    {
        "transaction_id": "TXN_1001",
        "preliminary_inv_no": "INV_2026_001",
        "customer_id": "CUST_8801",
        "amount": 25000.0,
        "channel": "MOBILE_APP",
        "timestamp": "2026-08-26 10:00:00"
    },
    # DUPLICATE of Payment #1 (e.g. Network retry or user double-clicking pay)
    {
        "transaction_id": "TXN_1001",  # Same Txn ID
        "preliminary_inv_no": "INV_2026_001",
        "customer_id": "CUST_8801",
        "amount": 25000.0,
        "channel": "MOBILE_APP_RETRY",
        "timestamp": "2026-08-26 10:00:03"
    },
    # Multi-Part Payment for Invoice INV_2026_002 (Part A)
    {
        "transaction_id": "TXN_1002",
        "preliminary_inv_no": "INV_2026_002",
        "customer_id": "CUST_8802",
        "amount": 15000.0,
        "channel": "POS_KIOSK",
        "timestamp": "2026-08-26 10:01:15"
    },
    # Multi-Part Payment for Invoice INV_2026_002 (Part B - Addon purchase)
    {
        "transaction_id": "TXN_1003",
        "preliminary_inv_no": "INV_2026_002",
        "customer_id": "CUST_8802",
        "amount": 5000.0,
        "channel": "WEB_PORTAL",
        "timestamp": "2026-08-26 10:02:10"
    },
    # INVALID Payment (Zero / Negative amount)
    {
        "transaction_id": "TXN_1004",
        "preliminary_inv_no": "INV_2026_003",
        "customer_id": "CUST_8803",
        "amount": -500.0,
        "channel": "API_GATEWAY",
        "timestamp": "2026-08-26 10:03:00"
    },
    # DUPLICATE of Payment #1 AGAIN (Delayed HTTP retry)
    {
        "transaction_id": "TXN_1001",  # Same Txn ID again
        "preliminary_inv_no": "INV_2026_001",
        "customer_id": "CUST_8801",
        "amount": 25000.0,
        "channel": "WEBHOOK_RETRY",
        "timestamp": "2026-08-26 10:05:00"
    },
    # Normal Payment #2
    {
        "transaction_id": "TXN_1005",
        "preliminary_inv_no": "INV_2026_004",
        "customer_id": "CUST_8804",
        "amount": 42000.0,
        "channel": "BANK_TRANSFER",
        "timestamp": "2026-08-26 10:06:00"
    }
]


# ==============================================================================
# 2. MEDIATIONZONE 9 APL ENGINE SIMULATOR
# ==============================================================================
class MZ9AggregationEngine:
    """
    Simulates the execution of WFL_Payment_Deduplication_Aggregation.apl inside an
    Execution Context (EC) in MediationZone 9.
    """
    def __init__(self):
        # In-Memory State Maps (APL Globals)
        self.agg_map = {}                      # map<string, record>
        self.processed_requests_cache = set()  # set of seen dedupe keys
        
        # Output Buffers (Simulating MZ Router / Output Agents)
        self.sap_hana_output = []
        self.duplicate_audit_output = []
        self.ecs_error_queue = []
        
        # Statistics
        self.stats = {
            "received": 0,
            "aggregated_records": 0,
            "duplicates_blocked": 0,
            "quarantined_ecs": 0
        }

    def initialize(self):
        """APL initialize() lifecycle method"""
        print("⚡ [MZ9 Engine] Initializing Workflow: WFL_Payment_Deduplication_Aggregation")
        print("⚡ [MZ9 Engine] Allocating APL In-Memory State Maps & Cache Containers...")
        self.stats["received"] = 0
        self.stats["aggregated_records"] = 0
        self.stats["duplicates_blocked"] = 0
        self.stats["quarantined_ecs"] = 0
        time.sleep(0.3)

    def consume(self, udr):
        """APL consume(udr) lifecycle method — Called for every raw record"""
        self.stats["received"] += 1
        
        tx_id   = udr["transaction_id"]
        inv_no  = udr["preliminary_inv_no"]
        cust_id = udr["customer_id"]
        amt     = udr["amount"]
        channel = udr["channel"]

        print(f"\n📥 [consume()] UDR #{self.stats['received']}: Txn={tx_id} | Inv={inv_no} | Cust={cust_id} | Amt={amt:,.2f} IQD | via {channel}")

        # STEP 1: VALIDATION (Amount > 0)
        if amt <= 0:
            err_udr = udr.copy()
            err_udr["error_code"] = "ERR_INV_AMOUNT"
            err_udr["error_msg"] = f"Invalid payment amount ({amt:,.2f} IQD)"
            self.ecs_error_queue.append(err_udr)
            self.stats["quarantined_ecs"] += 1
            print(f"   ❌ -> REJECTED & QUARANTINED TO ECS: {err_udr['error_msg']}")
            return

        # STEP 2: DEDUPLICATION CHECK (Unique Key: inv_no + "_" + tx_id)
        dedupe_key = f"{inv_no}_{tx_id}"

        if dedupe_key in self.processed_requests_cache:
            dup_udr = udr.copy()
            dup_udr["rejection_reason"] = "DUPLICATE_REQUEST_ID_BLOCKED"
            dup_udr["action"] = "BLOCKED_FROM_SAP_POSTING"
            self.duplicate_audit_output.append(dup_udr)
            self.stats["duplicates_blocked"] += 1
            print(f"   🚫 -> DUPLICATE REQUEST DETECTED! Key '{dedupe_key}' already processed. Blocked & sent to Audit Queue.")
            return

        # Register key in deduplication cache to block future retries
        self.processed_requests_cache.add(dedupe_key)

        # STEP 3: AGGREGATION (Grouping by preliminary invoice & customer)
        agg_key = f"{inv_no}_{cust_id}"

        if agg_key in self.agg_map:
            # Key already exists in batch -> Accumulate totals
            existing = self.agg_map[agg_key]
            existing["total_amount"] += amt
            existing["transaction_count"] += 1
            existing["transaction_ids"].append(tx_id)
            existing["last_updated"] = udr["timestamp"]
            print(f"   🔄 -> AGGREGATED into existing session '{agg_key}': New Total = {existing['total_amount']:,.2f} IQD (Count: {existing['transaction_count']})")
        else:
            # Create new aggregated entry
            self.agg_map[agg_key] = {
                "preliminary_inv_no": inv_no,
                "customer_id": cust_id,
                "total_amount": amt,
                "transaction_count": 1,
                "transaction_ids": [tx_id],
                "status": "AGGREGATED",
                "creation_time": udr["timestamp"]
            }
            print(f"   ✅ -> CREATED new aggregation entry '{agg_key}' with initial amount = {amt:,.2f} IQD")

    def drain(self):
        """APL drain() lifecycle method — Executed at end of batch to emit output"""
        print("\n" + "=" * 80)
        print("⚙️ [drain()] Batch Stream Completed. Draining In-Memory Aggregation Map...")
        print("=" * 80)

        for agg_key, consolidated_record in self.agg_map.items():
            self.sap_hana_output.append(consolidated_record)
            self.stats["aggregated_records"] += 1
            print(f"  📤 [SAP Output Agent] Dispatched Consolidated Record: Inv={consolidated_record['preliminary_inv_no']} | Cust={consolidated_record['customer_id']} | Total={consolidated_record['total_amount']:,.2f} IQD | Included Txns={consolidated_record['transaction_ids']}")

        time.sleep(0.3)


# ==============================================================================
# 3. RUNNER & REPORT DISPLAY
# ==============================================================================
def main():
    print("=" * 80)
    print("         MEDIATIONZONE 9 (INFOZONE) — AGGREGATION & DEDUPLICATION DEMO")
    print("=" * 80)
    print("Scenario: Processing raw UDR stream with retries, duplicates, and multi-part payments.")
    print("Goal    : Avoid duplicate requests to SAP HANA and produce consolidated invoices.")
    print("=" * 80)

    # Initialize Engine
    engine = MZ9AggregationEngine()
    engine.initialize()

    # Consume Stream
    print("\n--- PHASE 1: CONSUMING RAW UDR STREAM ---")
    for udr in RAW_UDR_STREAM:
        engine.consume(udr)

    # Drain Engine
    engine.drain()

    # Final Summary Report
    print("\n" + "=" * 80)
    print("                       FINAL WORKFLOW SUMMARY REPORT")
    print("=" * 80)
    print(f"  Raw Events Received       : {engine.stats['received']}")
    print(f"  Clean SAP Aggregated Output: {engine.stats['aggregated_records']} invoice(s)")
    print(f"  Duplicate Requests Blocked : {engine.stats['duplicates_blocked']}")
    print(f"  Quarantined to ECS Queue   : {engine.stats['quarantined_ecs']}")
    print("=" * 80)

    # Output Breakdown Tables
    print("\n📋 1. CLEAN CONSOLIDATED OUTPUT (Sent to SAP HANA / Billing System):")
    print("-" * 80)
    print(f"{'INVOICE NO':<16} {'CUSTOMER ID':<14} {'TOTAL AMOUNT (IQD)':<20} {'TXN COUNT':<10} {'TXN IDS'}")
    print("-" * 80)
    for rec in engine.sap_hana_output:
        txns_str = ", ".join(rec["transaction_ids"])
        print(f"{rec['preliminary_inv_no']:<16} {rec['customer_id']:<14} {rec['total_amount']:<20,.2f} {rec['transaction_count']:<10} {txns_str}")

    print("\n🚫 2. BLOCKED DUPLICATE REQUESTS (Prevented Double Billing):")
    print("-" * 80)
    print(f"{'TXN ID':<12} {'INVOICE NO':<16} {'CUSTOMER ID':<14} {'CHANNEL':<20} {'REASON'}")
    print("-" * 80)
    for dup in engine.duplicate_audit_output:
        print(f"{dup['transaction_id']:<12} {dup['preliminary_inv_no']:<16} {dup['customer_id']:<14} {dup['channel']:<20} {dup['rejection_reason']}")

    print("\n❌ 3. QUARANTINED ECS RECORDS (Requiring Operator Review):")
    print("-" * 80)
    print(f"{'TXN ID':<12} {'INVOICE NO':<16} {'CUSTOMER ID':<14} {'AMOUNT':<12} {'ERROR MSG'}")
    print("-" * 80)
    for err in engine.ecs_error_queue:
        print(f"{err['transaction_id']:<12} {err['preliminary_inv_no']:<16} {err['customer_id']:<14} {err['amount']:<12,.2f} {err['error_msg']}")

    print("=" * 80)
    print("✅ Aggregation & Deduplication Demo executed successfully!")
    print("=" * 80)

if __name__ == "__main__":
    main()
