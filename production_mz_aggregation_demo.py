"""
Production MediationZone WalletAPI Aggregation Simulation
==========================================================
Simulates the exact production code extracted from:
  - Workflow: WalletAPI.WFL_Wallet_API
  - Profile : WalletAPI.PRF_AGG_WALLETAPI
  - Ultra   : WalletAPI.UFL_Int_WalletData (DuplicateCheckInt / DuplicateChecks session)
"""

import sys
import time

sys.stdout.reconfigure(encoding='utf-8')


class ProductionMZWalletAggregationEngine:
    def __init__(self, session_timeout_seconds=60):
        # Emulates MediationZone Realtime Aggregation Session Storage (/mz8/Agg_Session/)
        self.active_sessions = {}
        self.session_timeout = session_timeout_seconds
        
        # Route Output Counters
        self.successful_requests = []
        self.duplicate_rejected_requests = []

    def process_incoming_request(self, dup_value, request_id, bp_id, amount):
        """
        Emulates WFL_Wallet_API entry point and Realtime Aggregation Agent:
          1. sessionInit (if session doesn't exist)
          2. consume
        """
        print(f"\n📥 [Incoming Request] TxnKey='{dup_value}' | ReqID={request_id} | BP={bp_id} | Amount={amount:,.2f} IQD")
        
        current_time = time.time()
        
        # Check if session exists and is not expired
        if dup_value in self.active_sessions:
            sess = self.active_sessions[dup_value]
            if current_time - sess["created_at"] > self.session_timeout:
                # Expired -> timeout block: sessionRemove(session)
                print(f"   ⏱️ [Aggregation Engine] Active session for '{dup_value}' timed out. Executing sessionRemove().")
                del self.active_sessions[dup_value]

        # STEP 1: sessionInit block (Runs when session is created)
        if dup_value not in self.active_sessions:
            print(f"   ⚡ [sessionInit] Creating new Aggregation Session for dupValue='{dup_value}'...")
            self.active_sessions[dup_value] = {
                "dupValue": dup_value,
                "count": 0,
                "created_at": current_time
            }

        # STEP 2: consume block (Runs per input record)
        sess = self.active_sessions[dup_value]
        
        if sess["dupValue"] == dup_value:
            sess["count"] += 1
            print(f"   🔍 [consume] From AGG :: Count block | session.count = {sess['count']}")

        # Duplicate Check Threshold (session.count >= 2)
        if sess["count"] >= 2:
            print("   🔴 [consume] From AGG :: Send duplicate Error! (session.count >= 2)")
            err_udr = {
                "dupValue": dup_value,
                "request_id": request_id,
                "errCode": "Duplicate",
                "errMsg": "ERR_DESC_DUP_REQUEST: Duplicate Request detected by MZ Aggregation Profile",
                "bp_id": bp_id,
                "amount": amount
            }
            self.duplicate_rejected_requests.append(err_udr)
            print("   🚫 -> Routed to 'dupRes' router: HTTP 409 Duplicate Request (Blocked from SAP/CC)")
            return err_udr
        else:
            print("   🟢 [consume] From AGG :: No duplicate (session.count == 1)")
            valid_udr = {
                "dupValue": dup_value,
                "request_id": request_id,
                "errCode": "",
                "bp_id": bp_id,
                "amount": amount
            }
            self.successful_requests.append(valid_udr)
            print("   ✅ -> Routed to 'dupRes' router: Passed to SAP CC/CI Service Execution")
            return valid_udr


def main():
    print("=" * 80)
    print("   PRODUCTION MEDIATIONZONE WALLET_API AGGREGATION & DEDUPLICATION DEMO")
    print("=" * 80)
    print("Source: QAS MZ Server 10.4.15.134 -> WalletAPI.WFL_Wallet_API")
    print("Profile: WalletAPI.PRF_AGG_WALLETAPI (ID Field List: ['dupValue'])")
    print("=" * 80)

    engine = ProductionMZWalletAggregationEngine(session_timeout_seconds=5)

    # Simulated sequence of API calls
    test_calls = [
        # Call 1: Normal Topup
        {"dup_value": "TXN_WALLET_9901", "req_id": "REQ_001", "bp": "BP_5001", "amt": 50000.0},
        
        # Call 2: Immediate Duplicate Retry of Call 1
        {"dup_value": "TXN_WALLET_9901", "req_id": "REQ_001_RETRY", "bp": "BP_5001", "amt": 50000.0},
        
        # Call 3: Different Customer Topup
        {"dup_value": "TXN_WALLET_9902", "req_id": "REQ_002", "bp": "BP_5002", "amt": 25000.0},
        
        # Call 4: Delayed Duplicate Retry of Call 1
        {"dup_value": "TXN_WALLET_9901", "req_id": "REQ_001_WEBHOOK_RETRY", "bp": "BP_5001", "amt": 50000.0},
    ]

    for call in test_calls:
        engine.process_incoming_request(call["dup_value"], call["req_id"], call["bp"], call["amt"])

    print("\n" + "=" * 80)
    print("                        SIMULATION SUMMARY RESULTS")
    print("=" * 80)
    print(f"Total Requests Received       : {len(test_calls)}")
    print(f"Processed by SAP/CC Service   : {len(engine.successful_requests)}")
    print(f"Blocked by MZ Aggregation Profile: {len(engine.duplicate_rejected_requests)}")
    print("=" * 80)

    print("\n✅ 1. SUCCESSFUL REQUESTS PROCESSED BY SAP/CC:")
    for s in engine.successful_requests:
        print(f"   - TxnKey: {s['dupValue']} | ReqID: {s['request_id']} | BP: {s['bp_id']} | Amt: {s['amount']:,.2f} IQD")

    print("\n🔴 2. REJECTED DUPLICATE REQUESTS (BLOCKED BY AGGREGATION):")
    for d in engine.duplicate_rejected_requests:
        print(f"   - TxnKey: {d['dupValue']} | ReqID: {d['request_id']} | Error: {d['errCode']} -> {d['errMsg']}")

    print("=" * 80)


if __name__ == "__main__":
    main()
