"""
MediationZone 9 ProductAPI — End-to-End Pipeline Simulation
============================================================================
Simulates the complete production workflow:
  1. REST Server Agent (Listens on http://localhost:8085/v1/product/*)
  2. Aggregation Engine (Intercepts duplicate requests with session.count >= 2)
  3. SAP SOM RFC Connector (Handles /search and /simulate via RFC)
  4. SAP HANA DB Engine (Executes SQL queries for /getOfferList)
  5. Automated HTTP Test Client Suite
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
# 1. SIMULATED SAP HANA DATABASE ENGINE
# ==============================================================================
class SAPHanaDatabaseEngine:
    """Simulates SAP HANA DB queries for Offer List"""
    def __init__(self):
        self.offers_table = [
            {"MANDT": "100", "LOB": "FIBER", "CONTRACTOR_ID": "0000088011", "CITY": "BAGHDAD", "REGION": "CENTRAL", "OFFER_NAME": "Fiber Ultra 100M", "PRICE": 45000.0},
            {"MANDT": "100", "LOB": "FIBER", "CONTRACTOR_ID": "0000088011", "CITY": "BAGHDAD", "REGION": "CENTRAL", "OFFER_NAME": "Fiber Super 300M", "PRICE": 75000.0},
            {"MANDT": "100", "LOB": "LTE",   "CONTRACTOR_ID": "0000099022", "CITY": "ERBIL",   "REGION": "NORTH",   "OFFER_NAME": "LTE Max Unlimited", "PRICE": 35000.0}
        ]

    def query_offers(self, lob, contractor_id, city):
        results = []
        for row in self.offers_table:
            if row["LOB"] == lob:
                if contractor_id and row["CONTRACTOR_ID"] != contractor_id:
                    continue
                if city and row["CITY"] != city:
                    continue
                results.append(row)
        return results


# ==============================================================================
# 2. SIMULATED SAP SOM RFC CONNECTOR
# ==============================================================================
class SAPSomRfcConnector:
    """Simulates RFC calls to SAP SOM (ZSOM_PRODUCT_GET_DETAIL_API_UDR)"""
    def call_product_search_rfc(self, transaction_id, end_user_id):
        print(f"  ⚡ [SAP SOM RFC] Invoking ZSOM_PRODUCT_GET_DETAIL_API_UDR for User={end_user_id}...")
        time.sleep(0.1)  # Simulate network latency to SAP
        return {
            "TYPE": "S",
            "MESSAGE": "Product details successfully retrieved from SAP SOM",
            "ET_RESULT": [
                {"PRODUCT_ID": "PROD_FIBER_100M", "NAME": "EarthLink Fiber 100 Mbps", "STATUS": "ACTIVE"},
                {"PRODUCT_ID": "PROD_TV_PLUS",    "NAME": "EarthLink IPTV Premium",   "STATUS": "ACTIVE"}
            ]
        }

    def call_product_simulate_rfc(self, transaction_id, end_user_id, zone_id):
        print(f"  ⚡ [SAP SOM RFC] Invoking ZSOM_PRODUCT_SIMULATE_API_UDR for Zone={zone_id}...")
        time.sleep(0.1)
        return {
            "TYPE": "S",
            "MESSAGE": "Plan simulation completed by SAP SOM",
            "SIMULATION_RESULT": {
                "MONTHLY_CHARGE": 45000.0,
                "TAX_AMOUNT": 6750.0,
                "TOTAL_PAYABLE": 51750.0,
                "CURRENCY": "IQD"
            }
        }


# ==============================================================================
# 3. MEDIATIONZONE AGGREGATION ENGINE (Matching APL Production Code)
# ==============================================================================
class MZAggregationEngine:
    """In-memory key buffer matching MZ PRF_AGG_ProductAPI"""
    def __init__(self, session_timeout_seconds=30):
        self.active_sessions = {}
        self.session_timeout = session_timeout_seconds
        self.lock = threading.Lock()

    def process_udr(self, dup_value):
        with self.lock:
            current_time = time.time()

            # Clean expired sessions
            if dup_value in self.active_sessions:
                sess = self.active_sessions[dup_value]
                if current_time - sess["created_at"] > self.session_timeout:
                    print(f"  ⏱️ [sessionRemove] Aggregation Session for '{dup_value}' expired. Cleaning storage.")
                    del self.active_sessions[dup_value]

            # sessionInit (Executed when session key is first created)
            if dup_value not in self.active_sessions:
                print(f"  ⚡ [sessionInit] Initializing new Aggregation Session Key: '{dup_value}'")
                self.active_sessions[dup_value] = {
                    "dupValue": dup_value,
                    "count": 0,
                    "created_at": current_time
                }

            # consume (Increment count)
            sess = self.active_sessions[dup_value]
            sess["count"] += 1
            print(f"  🔍 [consume] Session Match | session.count = {sess['count']}")

            # session.count >= 2 Check
            if sess["count"] >= 2:
                print(f"  🔴 [INTERCEPTED DUPLICATE] Duplicate Request blocked (session.count = {sess['count']})")
                return {
                    "is_duplicate": True,
                    "error_code": "ERR_DUPLICATE_REQUEST",
                    "message": "Duplicate Request Intercepted by MediationZone Aggregation Agent (session.count >= 2)",
                    "session_count": sess["count"]
                }
            else:
                print(f"  🟢 [VALID FIRST REQUEST] Allowed downstream processing (session.count == 1)")
                return {
                    "is_duplicate": False,
                    "error_code": "",
                    "message": "SUCCESS",
                    "session_count": sess["count"]
                }


# Global Singletons
hana_db = SAPHanaDatabaseEngine()
som_rfc = SAPSomRfcConnector()
agg_engine = MZAggregationEngine(session_timeout_seconds=30)


# ==============================================================================
# 4. MEDIATIONZONE REST SERVER AGENT HANDLER
# ==============================================================================
class MZProductAPIRestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress default HTTP logging for clean display

    def do_POST(self):
        path = self.path

        # Read JSON Body
        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length)

        try:
            req_data = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid JSON format"}).encode("utf-8"))
            return

        tx_id = req_data.get("transactionId", f"TXN_{int(time.time())}")
        end_user = req_data.get("endUserId", req_data.get("contractorID", "UNKNOWN"))

        print(f"\n🌐 [REST Server Agent] POST {path} | TxnID={tx_id} | User/Contractor={end_user}")

        # ----------------------------------------------------------------------
        # ENDPOINT 1: /v1/product/search
        # ----------------------------------------------------------------------
        if path == "/v1/product/search":
            dup_value = f"{end_user}_{tx_id}"

            # Apply Aggregation Check
            agg_res = agg_engine.process_udr(dup_value)

            if agg_res["is_duplicate"]:
                # Send HTTP 409 Conflict Rejection
                self.send_response(409)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                response = {
                    "status": "FAILED",
                    "errorCode": agg_res["error_code"],
                    "message": agg_res["message"],
                    "transactionId": tx_id,
                    "sessionCount": agg_res["session_count"]
                }
                self.wfile.write(json.dumps(response, indent=2).encode("utf-8"))
            else:
                # Call SAP SOM RFC
                rfc_res = som_rfc.call_product_search_rfc(tx_id, end_user)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                response = {
                    "status": "SUCCESS",
                    "transactionId": tx_id,
                    "endUserId": end_user,
                    "sapSomMessage": rfc_res["MESSAGE"],
                    "products": rfc_res["ET_RESULT"]
                }
                self.wfile.write(json.dumps(response, indent=2).encode("utf-8"))

        # ----------------------------------------------------------------------
        # ENDPOINT 2: /v1/product/simulate
        # ----------------------------------------------------------------------
        elif path == "/v1/product/simulate":
            zone_id = req_data.get("zoneId", "ZONE_BAGHDAD_01")
            rfc_res = som_rfc.call_product_simulate_rfc(tx_id, end_user, zone_id)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            response = {
                "status": "SUCCESS",
                "transactionId": tx_id,
                "zoneId": zone_id,
                "simulationData": rfc_res["SIMULATION_RESULT"]
            }
            self.wfile.write(json.dumps(response, indent=2).encode("utf-8"))

        # ----------------------------------------------------------------------
        # ENDPOINT 3: /v1/product/getOfferList
        # ----------------------------------------------------------------------
        elif path == "/v1/product/getOfferList":
            lob = req_data.get("LOB", "FIBER")
            contractor_id = req_data.get("contractorID", "")
            city = req_data.get("city", "")

            # Query SAP HANA DB
            offers = hana_db.query_offers(lob, contractor_id, city)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            response = {
                "status": "SUCCESS",
                "transactionId": tx_id,
                "totalOffers": len(offers),
                "offers": offers
            }
            self.wfile.write(json.dumps(response, indent=2).encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()


# ==============================================================================
# 5. SERVER RUNNER & AUTOMATED CLIENT TEST SUITE
# ==============================================================================
def start_server(port=8085):
    server = HTTPServer(("localhost", port), MZProductAPIRestHandler)
    print(f"🚀 [MZ REST Server Agent] Listening on http://localhost:{port}/v1/product/*")
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    return server


def run_test_suite(port=8085):
    time.sleep(0.5)
    base_url = f"http://localhost:{port}/v1/product"

    print("\n" + "=" * 85)
    print("      RUNNING END-TO-END PRODUCT API PIPELINE AUTOMATED TEST SUITE")
    print("=" * 85)

    test_cases = [
        # TEST 1: Initial Product Search (Valid -> SAP SOM RFC)
        {
            "name": "TEST 1: Product Search Initial Request (Txn: TXN_SEARCH_101)",
            "url": f"{base_url}/search",
            "data": {"transactionId": "TXN_SEARCH_101", "endUserId": "USER_88011", "LOB": "FIBER"}
        },
        # TEST 2: Duplicate Product Search Retry (Duplicate -> Blocked by Aggregation)
        {
            "name": "TEST 2: Product Search Immediate Retry (Txn: TXN_SEARCH_101)",
            "url": f"{base_url}/search",
            "data": {"transactionId": "TXN_SEARCH_101", "endUserId": "USER_88011", "LOB": "FIBER"}
        },
        # TEST 3: Product Simulate (Valid -> SAP SOM RFC)
        {
            "name": "TEST 3: Product Plan Simulation Request (Txn: TXN_SIM_202)",
            "url": f"{base_url}/simulate",
            "data": {"transactionId": "TXN_SIM_202", "endUserId": "USER_88011", "zoneId": "BAGHDAD_CENTRAL", "salesOrg": "1000"}
        },
        # TEST 4: Get Offer List (Valid -> SAP HANA DB Query)
        {
            "name": "TEST 4: Get Offer List Database Query (Txn: TXN_OFFER_303)",
            "url": f"{base_url}/getOfferList",
            "data": {"transactionId": "TXN_OFFER_303", "LOB": "FIBER", "contractorID": "0000088011", "city": "BAGHDAD"}
        }
    ]

    for tc in test_cases:
        print(f"\n📲 Client Request: {tc['name']}")
        json_data = json.dumps(tc["data"]).encode("utf-8")
        req = Request(tc["url"], data=json_data, headers={"Content-Type": "application/json"}, method="POST")

        try:
            with urlopen(req) as resp:
                status_code = resp.getcode()
                res_body = json.loads(resp.read().decode("utf-8"))
                print(f"   Response Status: HTTP {status_code} OK")
                print(f"   Response Payload: {json.dumps(res_body, indent=2)}")
        except HTTPError as e:
            status_code = e.code
            err_body = json.loads(e.read().decode("utf-8"))
            print(f"   Response Status: HTTP {status_code} (Interception Response)")
            print(f"   Response Payload: {json.dumps(err_body, indent=2)}")

    print("\n" + "=" * 85)
    print("✅ End-to-End ProductAPI Pipeline execution completed successfully!")
    print("=" * 85)


if __name__ == "__main__":
    server = start_server(port=8085)
    run_test_suite(port=8085)
    server.shutdown()

