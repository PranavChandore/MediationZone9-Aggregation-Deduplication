"""
MediationZone 9 REST Server Agent & Aggregation Engine Implementation
======================================================================
Simulates the exact end-to-end pipeline:
  1. REST Server Agent (Listens for HTTP POST /v1/wallet/topup)
  2. OpenAPI / UDR Decoder (Converts JSON HTTP payload to UDR)
  3. Real-Time Aggregation Agent (Checks dupValue & session.count)
  4. Decision Routing:
     - session.count == 1 -> HTTP 200 OK (Processed by SAP CC)
     - session.count >= 2 -> HTTP 409 Conflict / ERR_DESC_DUP_REQUEST (Duplicate Blocked)
"""

import json
import time
import threading
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import HTTPError

sys.stdout.reconfigure(encoding='utf-8')


# ==============================================================================
# 1. MEDIATIONZONE REAL-TIME AGGREGATION ENGINE (Matching Production APL)
# ==============================================================================
class ProductionAggregationEngine:
    def __init__(self, session_timeout_seconds=30):
        self.active_sessions = {}
        self.session_timeout = session_timeout_seconds
        self.lock = threading.Lock()

    def process_udr(self, dup_value, req_payload):
        with self.lock:
            current_time = time.time()

            # Clean expired sessions
            if dup_value in self.active_sessions:
                sess = self.active_sessions[dup_value]
                if current_time - sess["created_at"] > self.session_timeout:
                    print(f"⏱️ [MZ Aggregation] Session for '{dup_value}' expired. Running sessionRemove().")
                    del self.active_sessions[dup_value]

            # sessionInit block (Runs when session is created)
            if dup_value not in self.active_sessions:
                print(f"⚡ [sessionInit] Initializing new Aggregation Session for dupValue='{dup_value}'...")
                self.active_sessions[dup_value] = {
                    "dupValue": dup_value,
                    "count": 0,
                    "created_at": current_time
                }

            # consume block
            sess = self.active_sessions[dup_value]
            sess["count"] += 1
            print(f"🔍 [consume] From AGG :: Count block | session.count = {sess['count']}")

            # Duplicate Check Threshold (session.count >= 2)
            if sess["count"] >= 2:
                print("🔴 [consume] From AGG :: Send duplicate Error! (session.count >= 2)")
                return {
                    "is_duplicate": True,
                    "error_code": "ERR_DESC_DUP_REQUEST",
                    "message": "Duplicate Request detected by MZ Aggregation Profile (WalletAPI.PRF_AGG_WALLETAPI)",
                    "dup_value": dup_value,
                    "session_count": sess["count"]
                }
            else:
                print("🟢 [consume] From AGG :: No duplicate (session.count == 1)")
                return {
                    "is_duplicate": False,
                    "error_code": "",
                    "message": "Topup request successfully validated & forwarded to SAP CC",
                    "dup_value": dup_value,
                    "session_count": sess["count"]
                }


# Global Aggregation Instance
agg_engine = ProductionAggregationEngine(session_timeout_seconds=30)


# ==============================================================================
# 2. MEDIATIONZONE REST SERVER AGENT (HTTP Request Handler)
# ==============================================================================
class MZRESTServerAgentHandler(BaseHTTPRequestHandler):
    """
    Simulates MediationZone REST Server Agent listening on Endpoint URIs: [/v1/wallet/]
    Profile: WalletAPI.PRF_WalletAPI_Rest_Server
    OpenAPI: WalletAPI.PRF_WalletAPI_OpenAPI
    """

    def log_message(self, format, *args):
        pass  # Suppress standard HTTP server stdout logging for clean output

    def do_POST(self):
        # 1. Check Endpoint URI Routing (/v1/wallet/topup)
        if self.path != "/v1/wallet/topup":
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            response_body = {"error": f"Endpoint {self.path} not found on REST Server Agent"}
            self.wfile.write(json.dumps(response_body).encode("utf-8"))
            return

        # 2. Decode HTTP Request Payload (OpenAPI Decoder)
        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length)
        
        try:
            req_data = json.loads(body_bytes.decode("utf-8"))
        except Exception as e:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid JSON format"}).encode("utf-8"))
            return

        # Extract Transaction Key (dupValue)
        tx_id = req_data.get("transactionId")
        bp_id = req_data.get("businessPartnerId")
        amount = req_data.get("amount", 0)

        if not tx_id or not bp_id:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Missing transactionId or businessPartnerId"}).encode("utf-8"))
            return

        dup_value = f"{bp_id}_{tx_id}"

        print(f"\n🌐 [REST Server Agent] Received HTTP POST /v1/wallet/topup | TxnID={tx_id} | BP={bp_id} | Amt={amount} IQD")

        # 3. Pass UDR to Aggregation Agent
        agg_result = agg_engine.process_udr(dup_value, req_data)

        # 4. Format HTTP REST Response according to Aggregation Result
        if agg_result["is_duplicate"]:
            # Route: dupRes (Duplicate Error Response) -> HTTP 409 Conflict
            self.send_response(409)
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            response_payload = {
                "status": "FAILED",
                "errorCode": agg_result["error_code"],
                "message": agg_result["message"],
                "transactionId": tx_id,
                "businessPartnerId": bp_id,
                "sessionCount": agg_result["session_count"]
            }
            self.wfile.write(json.dumps(response_payload, indent=2).encode("utf-8"))
        else:
            # Route: SAP CC / Success Response -> HTTP 200 OK
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            response_payload = {
                "status": "SUCCESS",
                "message": agg_result["message"],
                "transactionId": tx_id,
                "businessPartnerId": bp_id,
                "amount": amount,
                "currency": "IQD",
                "walletBalance": amount * 1.15,  # Simulated updated wallet balance
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            self.wfile.write(json.dumps(response_payload, indent=2).encode("utf-8"))


# ==============================================================================
# 3. SERVER RUNNER & HTTP CLIENT TEST SUITE
# ==============================================================================
def start_server(port=8080):
    server = HTTPServer(("localhost", port), MZRESTServerAgentHandler)
    print(f"🚀 [MZ REST Server Agent] Listening on http://localhost:{port}/v1/wallet/topup")
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    return server


def run_http_client_test(port=8080):
    time.sleep(0.5)
    url = f"http://localhost:{port}/v1/wallet/topup"

    print("\n" + "=" * 80)
    print("        RUNNING HTTP REST CLIENT TEST SUITE AGAINST MZ REST SERVER AGENT")
    print("=" * 80)

    test_payloads = [
        # TEST 1: Initial Valid Wallet Topup
        {
            "description": "TEST 1: Initial Topup Request (Txn: TXN_88001)",
            "data": {"transactionId": "TXN_88001", "businessPartnerId": "BP_10099", "amount": 10000.0}
        },
        # TEST 2: Immediate Duplicate Retry (Network retry / double-click)
        {
            "description": "TEST 2: Immediate Duplicate Retry (Txn: TXN_88001)",
            "data": {"transactionId": "TXN_88001", "businessPartnerId": "BP_10099", "amount": 10000.0}
        },
        # TEST 3: Different Customer Topup Request
        {
            "description": "TEST 3: Different Customer Topup Request (Txn: TXN_88002)",
            "data": {"transactionId": "TXN_88002", "businessPartnerId": "BP_20055", "amount": 35000.0}
        },
        # TEST 4: Delayed Duplicate Retry (Webhook retry)
        {
            "description": "TEST 4: Delayed Webhook Duplicate Retry (Txn: TXN_88001)",
            "data": {"transactionId": "TXN_88001", "businessPartnerId": "BP_10099", "amount": 10000.0}
        }
    ]

    for test in test_payloads:
        print(f"\n📲 Client Request: {test['description']}")
        json_data = json.dumps(test["data"]).encode("utf-8")
        req = Request(url, data=json_data, headers={"Content-Type": "application/json"}, method="POST")

        try:
            with urlopen(req) as resp:
                status_code = resp.getcode()
                response_json = json.loads(resp.read().decode("utf-8"))
                print(f"   Response Status: HTTP {status_code}")
                print(f"   Response Payload: {json.dumps(response_json, indent=2)}")
        except HTTPError as e:
            status_code = e.code
            error_json = json.loads(e.read().decode("utf-8"))
            print(f"   Response Status: HTTP {status_code} (Rejection Response)")
            print(f"   Response Payload: {json.dumps(error_json, indent=2)}")

    print("\n" + "=" * 80)
    print("✅ REST Server Agent + Aggregation Engine test completed successfully!")
    print("=" * 80)


if __name__ == "__main__":
    server_port = 8080
    srv = start_server(port=server_port)
    run_http_client_test(port=server_port)
    srv.shutdown()
