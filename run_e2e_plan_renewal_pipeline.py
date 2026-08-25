"""
End-to-End EarthLink Plan Renewal & Payment Aggregation Pipeline
================================================================
MediationZone 9 (InfoZone) End-to-End Production Simulation:
  1. REST Server Agent (HTTP Listener on /v1/plan/renew)
  2. OpenAPI Decoder (JSON -> PlanRenewalReqInt UDR)
  3. Real-Time Aggregation Engine (dupValue = SubscriberID + "_" + TxnID)
  4. ECS Error Forwarding Agent (Quarantines invalid amounts)
  5. SAP HANA DB Output Agent (Stores clean records in ZEL_PYMNT & DFKKINVDOC_I)
"""

import json
import time
import threading
import sys
import random
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import HTTPError

sys.stdout.reconfigure(encoding='utf-8')


# ==============================================================================
# 1. SIMULATED SAP HANA DATABASE ENGINE
# ==============================================================================
class SimulatedSAPHANADB:
    """Simulates SAP HANA Tables: DFKKINVDOC_I & ZEL_PYMNT"""
    def __init__(self):
        self.zel_pymnt = []
        self.dfkkinvdoc_i = []

    def insert_transaction(self, subscriber_id, txn_id, plan_id, amount, channel):
        doc_no = f"3000{random.randint(100000, 999999)}"
        created_date = time.strftime("%Y-%m-%d %H:%M:%S")

        # Insert into ZEL_PYMNT (Payment Record)
        zel_rec = {
            "INV_NO": f"PREL_{txn_id}",
            "DOCUMENT_NO": doc_no,
            "BPCODE": subscriber_id,
            "AMOUNT": amount,
            "PROCESS": "PLAN_RENEWAL",
            "STATUS": "Complete",
            "CHANNEL": channel,
            "CREATED_DATE": created_date
        }
        self.zel_pymnt.append(zel_rec)

        # Insert into DFKKINVDOC_I (Invoicing Line Item)
        inv_rec = {
            "INVDOCNO": doc_no,
            "ZZPREL_INVNO": f"PREL_{txn_id}",
            "BETRW": amount,
            "ZZPOSTING_KEY": "WLCH",
            "ITEMTYPE": "0INVBILL",
            "SPART": "PLAN_RENEW",
            "CREATED_DATE": created_date
        }
        self.dfkkinvdoc_i.append(inv_rec)

        return doc_no


# ==============================================================================
# 2. MEDIATIONZONE REAL-TIME AGGREGATION & ECS ENGINE
# ==============================================================================
class MZ9PlanRenewalAggregationEngine:
    """
    Simulates WFL_PlanRenewal_Aggregation.apl running inside MediationZone Execution Context.
    Uses PRF_AGG_PlanRenewal profile settings.
    """
    def __init__(self, session_timeout_seconds=60):
        self.active_sessions = {}
        self.session_timeout = session_timeout_seconds
        self.sap_db = SimulatedSAPHANADB()
        self.ecs_quarantine_queue = []
        self.duplicate_audit_log = []
        self.lock = threading.Lock()

    def process_renewal_udr(self, input_udr):
        with self.lock:
            dup_value     = input_udr["dupValue"]
            sub_id        = input_udr["subscriberId"]
            txn_id        = input_udr["transactionId"]
            plan_id       = input_udr["planId"]
            amount        = input_udr["amount"]
            channel       = input_udr["channel"]
            current_time  = time.time()

            # STEP 1: VALIDATION CHECK (Quarantine to ECS if amount <= 0)
            if amount <= 0:
                err_rec = input_udr.copy()
                err_rec["error_code"] = "ERR_INVALID_AMOUNT"
                err_rec["error_msg"]  = f"Invalid payment amount ({amount:,.2f} IQD). Quarantined to ECS."
                self.ecs_quarantine_queue.append(err_rec)
                print(f"   ❌ [ECS Quarantine Agent] Invalid amount ({amount:,.2f} IQD) for sub={sub_id}. Routed to ECS Queue.")
                return {
                    "status_code": 400,
                    "payload": {
                        "status": "FAILED",
                        "errorCode": "ERR_INVALID_AMOUNT",
                        "message": "Payment amount must be greater than 0"
                    }
                }

            # STEP 2: SESSION EXPIRY CLEANUP (timeout block)
            if dup_value in self.active_sessions:
                sess = self.active_sessions[dup_value]
                if current_time - sess["created_at"] > self.session_timeout:
                    print(f"   ⏱️ [timeout] Session for '{dup_value}' expired. Executing sessionRemove().")
                    del self.active_sessions[dup_value]

            # STEP 3: sessionInit BLOCK
            if dup_value not in self.active_sessions:
                print(f"   ⚡ [sessionInit] Creating Aggregation Session for dupValue='{dup_value}'...")
                self.active_sessions[dup_value] = {
                    "dupValue": dup_value,
                    "subscriberId": sub_id,
                    "planId": plan_id,
                    "count": 0,
                    "totalAmount": 0.0,
                    "created_at": current_time
                }

            # STEP 4: consume BLOCK
            sess = self.active_sessions[dup_value]
            sess["count"]       += 1
            sess["totalAmount"] += amount
            print(f"   🔍 [consume] Session matched key '{dup_value}' | session.count = {sess['count']}")

            # STEP 5: DUPLICATE INTERCEPTION THRESHOLD (session.count >= 2)
            if sess["count"] >= 2:
                print(f"   🔴 [consume] DUPLICATE INTERCEPTED! session.count={sess['count']} >= 2. Routing to 'dupRes'.")
                dup_audit = {
                    "dupValue": dup_value,
                    "transactionId": txn_id,
                    "subscriberId": sub_id,
                    "planId": plan_id,
                    "amount": amount,
                    "sessionCount": sess["count"],
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                self.duplicate_audit_log.append(dup_audit)
                return {
                    "status_code": 409,
                    "payload": {
                        "status": "FAILED",
                        "errorCode": "ERR_DUPLICATE_REQUEST",
                        "message": "Duplicate plan renewal request intercepted by MediationZone Aggregation Profile (PRF_AGG_PlanRenewal)",
                        "transactionId": txn_id,
                        "subscriberId": sub_id,
                        "sessionCount": sess["count"]
                    }
                }
            else:
                # session.count == 1 -> Valid Request -> Write to SAP HANA
                print(f"   🟢 [consume] First valid request for session. Forwarding to SAP HANA DB Agent...")
                doc_no = self.sap_db.insert_transaction(sub_id, txn_id, plan_id, amount, channel)
                print(f"   ✅ [SAP HANA DB Agent] Created SAP Invoice Document: {doc_no} in ZEL_PYMNT & DFKKINVDOC_I")

                return {
                    "status_code": 200,
                    "payload": {
                        "status": "SUCCESS",
                        "message": "Plan renewal successfully processed and posted to SAP HANA",
                        "transactionId": txn_id,
                        "subscriberId": sub_id,
                        "planId": plan_id,
                        "amount": amount,
                        "currency": "IQD",
                        "sapInvoiceDocNo": doc_no,
                        "postingTimestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                }


# Global Engine Instance
pipeline_engine = MZ9PlanRenewalAggregationEngine(session_timeout_seconds=60)


# ==============================================================================
# 3. REST SERVER AGENT (HTTP Request Listener)
# ==============================================================================
class MZPlanRenewalRestAgentHandler(BaseHTTPRequestHandler):
    """
    Simulates REST Server Agent listening on Endpoint URI: /v1/plan/renew
    Profile: PRF_PlanRenewal_OpenAPI
    """
    def log_message(self, format, *args):
        pass

    def do_POST(self):
        if self.path != "/v1/plan/renew":
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode("utf-8"))
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes     = self.rfile.read(content_length)

        try:
            req_json = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Malformed JSON payload"}).encode("utf-8"))
            return

        sub_id = req_json.get("subscriberId")
        txn_id = req_json.get("transactionId")
        plan_id= req_json.get("planId")
        amount = req_json.get("amount", 0.0)
        channel= req_json.get("channel", "MOBILE_APP")

        print(f"\n🌐 [REST Server Agent] HTTP POST /v1/plan/renew | Txn={txn_id} | Sub={sub_id} | Plan={plan_id} | Amt={amount:,.2f} IQD")

        # Decode into PlanRenewalReqInt UDR
        input_udr = {
            "dupValue": f"{sub_id}_{txn_id}",
            "transactionId": txn_id,
            "subscriberId": sub_id,
            "planId": plan_id,
            "amount": amount,
            "channel": channel
        }

        # Stream UDR into Aggregation Engine
        result = pipeline_engine.process_renewal_udr(input_udr)

        # Formulate REST Response
        self.send_response(result["status_code"])
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(result["payload"], indent=2).encode("utf-8"))


# ==============================================================================
# 4. SERVER RUNNER & TEST CLIENT RUNNER
# ==============================================================================
def start_pipeline_server(port=8090):
    server = HTTPServer(("localhost", port), MZPlanRenewalRestAgentHandler)
    print(f"🚀 [MZ9 Pipeline] REST Server Agent listening on http://localhost:{port}/v1/plan/renew")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def execute_test_suite(port=8090):
    time.sleep(0.5)
    url = f"http://localhost:{port}/v1/plan/renew"

    print("\n" + "=" * 85)
    print("          STARTING AUTOMATED E2E TEST SUITE FOR EARTHLINK PLAN RENEWAL")
    print("=" * 85)

    test_cases = [
        {
            "num": 1,
            "title": "Valid Plan Renewal Request (Subscriber SUB_44012)",
            "payload": {
                "transactionId": "TXN_RENEW_1001",
                "subscriberId": "SUB_44012",
                "planId": "PLAN_FIBER_100M",
                "amount": 45000.0,
                "channel": "MOBILE_APP"
            }
        },
        {
            "num": 2,
            "title": "Immediate Duplicate Retry (Txn: TXN_RENEW_1001)",
            "payload": {
                "transactionId": "TXN_RENEW_1001",
                "subscriberId": "SUB_44012",
                "planId": "PLAN_FIBER_100M",
                "amount": 45000.0,
                "channel": "MOBILE_APP_RETRY"
            }
        },
        {
            "num": 3,
            "title": "Second Valid Subscriber Plan Renewal (Subscriber SUB_99041)",
            "payload": {
                "transactionId": "TXN_RENEW_1002",
                "subscriberId": "SUB_99041",
                "planId": "PLAN_FTTH_200M",
                "amount": 75000.0,
                "channel": "POS_KIOSK"
            }
        },
        {
            "num": 4,
            "title": "Delayed Webhook Duplicate Retry (Txn: TXN_RENEW_1001)",
            "payload": {
                "transactionId": "TXN_RENEW_1001",
                "subscriberId": "SUB_44012",
                "planId": "PLAN_FIBER_100M",
                "amount": 45000.0,
                "channel": "WEBHOOK_RETRY"
            }
        },
        {
            "num": 5,
            "title": "Invalid Amount Payment Request (Amount: -1000 IQD)",
            "payload": {
                "transactionId": "TXN_RENEW_1003",
                "subscriberId": "SUB_11099",
                "planId": "PLAN_FIBER_50M",
                "amount": -1000.0,
                "channel": "API_GATEWAY"
            }
        }
    ]

    for tc in test_cases:
        print(f"\n🧪 TEST CASE #{tc['num']}: {tc['title']}")
        body = json.dumps(tc["payload"]).encode("utf-8")
        req  = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")

        try:
            with urlopen(req) as resp:
                code = resp.getcode()
                res_body = json.loads(resp.read().decode("utf-8"))
                print(f"   HTTP Status Code : {code} OK")
                print(f"   Response Payload : {json.dumps(res_body)}")
        except HTTPError as e:
            code = e.code
            res_body = json.loads(e.read().decode("utf-8"))
            print(f"   HTTP Status Code : {code} (Rejection Response)")
            print(f"   Response Payload : {json.dumps(res_body)}")

    # Display SAP DB & ECS Summary Reports
    print("\n" + "=" * 85)
    print("                     E2E PIPELINE EXECUTION SUMMARY")
    print("=" * 85)

    print("\n💾 1. SAP HANA DATABASE POSTINGS (ZEL_PYMNT & DFKKINVDOC_I):")
    print("-" * 85)
    print(f"{'DOC NO':<12} {'SUBSCRIBER':<14} {'AMOUNT (IQD)':<16} {'STATUS':<10} {'CHANNEL':<18} {'POSTING DATE'}")
    print("-" * 85)
    for rec in pipeline_engine.sap_db.zel_pymnt:
        print(f"{rec['DOCUMENT_NO']:<12} {rec['BPCODE']:<14} {rec['AMOUNT']:<16,.2f} {rec['STATUS']:<10} {rec['CHANNEL']:<18} {rec['CREATED_DATE']}")

    print("\n🚫 2. INTERCEPTED DUPLICATE REQUESTS (BLOCKED BY AGGREGATION):")
    print("-" * 85)
    print(f"{'TXN ID':<16} {'SUBSCRIBER':<14} {'PLAN ID':<16} {'AMOUNT (IQD)':<14} {'SESSION COUNT'}")
    print("-" * 85)
    for dup in pipeline_engine.duplicate_audit_log:
        print(f"{dup['transactionId']:<16} {dup['subscriberId']:<14} {dup['planId']:<16} {dup['amount']:<14,.2f} {dup['sessionCount']}")

    print("\n❌ 3. QUARANTINED ECS RECORDS (ROUTED TO ECS ERROR QUEUE):")
    print("-" * 85)
    print(f"{'TXN ID':<16} {'SUBSCRIBER':<14} {'AMOUNT (IQD)':<14} {'ERROR MSG'}")
    print("-" * 85)
    for err in pipeline_engine.ecs_quarantine_queue:
        print(f"{err['transactionId']:<16} {err['subscriberId']:<14} {err['amount']:<14,.2f} {err['error_msg']}")

    print("=" * 85)
    print("✅ End-to-End Plan Renewal Aggregation Pipeline completed successfully!")
    print("=" * 85)


if __name__ == "__main__":
    server_port = 8090
    srv = start_pipeline_server(port=server_port)
    execute_test_suite(port=server_port)
    srv.shutdown()
