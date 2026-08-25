# Complete End-to-End Production Guide: MediationZone 9 ProductAPI with Aggregation & SAP Integration

This guide presents the **complete, end-to-end production implementation** for your **`ProductAPI` MediationZone workflow**. It combines your exact production APL REST router logic (handling `Cycle`, `Request`, `Response`, CORS, Auth, `search`, `simulate`, `getOfferList`, `currentSubscription`, `scheduledCancel`) with **Real-Time Aggregation Deduplication** (`sessionInit`, `consume`, `session.count >= 2`) and **SAP SOM RFC / HANA Database integration**.

---

## 1. System Architecture Diagram

```
  Client Application (Mobile App / Web Portal / Fiori)
                           │
                           │ HTTP POST /v1/product/search
                           ▼
  ┌──────────────────────────────────────────────────┐
  │  MediationZone REST Server Agent                 │
  │  Profile: ProductAPI.PRF_OpenAPI_ProductAPI     │
  │  Creates `Cycle` UDR (Request + Response)        │
  └────────────────────────┬─────────────────────────┘
                           │
                           ▼
  ┌──────────────────────────────────────────────────┐
  │  APL Pre-Processing Router                        │
  │  WFL_ProductAPI_Aggregation_Router.apl           │
  │  - Checks S/4 Database availability              │
  │  - CORS Preflight (HTTP OPTIONS)                 │
  │  - Client Authentication check                   │
  │  - Generates Aggregation Key: endUserId + TxnId  │
  └────────────────────────┬─────────────────────────┘
                           │
                           ▼
  ┌──────────────────────────────────────────────────┐
  │  Real-Time Aggregation Agent                     │
  │  Profile: ProductAPI.PRF_AGG_ProductAPI          │
  │                                                  │
  │  session.count == 1:                             │
  │    Forward to SAP SOM RFC (toSOMRFC)             │
  │    └─► SAP SOM returns data -> HTTP 200 OK       │
  │                                                  │
  │  session.count >= 2:                             │
  │    Flag ERR_DUPLICATE_REQUEST                    │
  │    └─► Route to response -> HTTP 409 Conflict    │
  └──────────────────────────────────────────────────┘
```

---

## 2. File Index & Location Reference

All project files are saved in `c:\Users\prana\OneDrive\Desktop\AggregationLearn`:

| File Name | Type | Description |
|:---|:---|:---|
| **[UFL_Product_API.ufl](file:///c:/Users/prana/OneDrive/Desktop/AggregationLearn/UFL_Product_API.ufl)** | Ultra Data Format | UDR definitions for `Cycle`, `Request`, `Response`, `DuplicateCheckInt`, `ProductSession`, `ZSOM_*_API_UDR`. |
| **[WFL_ProductAPI_Aggregation_Router.apl](file:///c:/Users/prana/OneDrive/Desktop/AggregationLearn/WFL_ProductAPI_Aggregation_Router.apl)** | Production APL | Complete workflow script with REST routing, Aggregation engine, SAP SOM RFCs, and HANA DB queries. |
| **[PRF_AGG_ProductAPI.json](file:///c:/Users/prana/OneDrive/Desktop/AggregationLearn/PRF_AGG_ProductAPI.json)** | MZ Aggregation Profile | Configured key matching `["dupValue"]` and session storage directory `/mz8/Agg_Session/ProductAPI/`. |
| **[PRF_OpenAPI_ProductAPI.json](file:///c:/Users/prana/OneDrive/Desktop/AggregationLearn/PRF_OpenAPI_ProductAPI.json)** | MZ OpenAPI Profile | OpenAPI 3.0 specification mapping HTTP POST JSON payloads to UDRs. |
| **[run_e2e_product_api_pipeline.py](file:///c:/Users/prana/OneDrive/Desktop/AggregationLearn/run_e2e_product_api_pipeline.py)** | Runnable Python Pipeline | Complete executable simulation of REST Server, Aggregation Engine, SAP SOM RFC, HANA DB, & automated test suite. |

---

## 3. How the Duplicate Rejection Lifecycle Works

1. **Client Sends Initial Request (`TXN_SEARCH_101`)**:
   - `sessionInit` creates session key `USER_88011_TXN_SEARCH_101`.
   - `consume` increments `session.count` to `1`.
   - `session.count >= 2` evaluates to **FALSE**.
   - Forwarded to SAP SOM RFC (`toSOMRFC`). Returns **`HTTP 200 OK`**.

2. **Client Sends Duplicate Request Retry (`TXN_SEARCH_101`)**:
   - Aggregation matches active session `USER_88011_TXN_SEARCH_101`.
   - `consume` increments `session.count` to `2`.
   - `session.count >= 2` evaluates to **TRUE**.
   - Intercepted! Returns **`HTTP 409 Conflict` (`ERR_DUPLICATE_REQUEST`)** directly to client **without touching SAP**.

3. **Session Expiry**:
   - After `sessionTime` seconds, `timeout` block executes `sessionRemove(session)` to purge session memory.

---

## 4. Execution & Verification Command

To run the complete pipeline test suite:

```bash
python run_e2e_product_api_pipeline.py
```

### Verification Results Output:

```
🚀 [MZ REST Server Agent] Listening on http://localhost:8085/v1/product/*

=====================================================================================
      RUNNING END-TO-END PRODUCT API PIPELINE AUTOMATED TEST SUITE
=====================================================================================

📲 Client Request: TEST 1: Product Search Initial Request (Txn: TXN_SEARCH_101)
  ⚡ [sessionInit] Initializing new Aggregation Session Key: 'USER_88011_TXN_SEARCH_101'
  🔍 [consume] Session Match | session.count = 1
  🟢 [VALID FIRST REQUEST] Allowed downstream processing (session.count == 1)
  ⚡ [SAP SOM RFC] Invoking ZSOM_PRODUCT_GET_DETAIL_API_UDR for User=USER_88011...
   Response Status: HTTP 200 OK

📲 Client Request: TEST 2: Product Search Immediate Retry (Txn: TXN_SEARCH_101)
  🔍 [consume] Session Match | session.count = 2
  🔴 [INTERCEPTED DUPLICATE] Duplicate Request blocked (session.count = 2)
   Response Status: HTTP 409 Conflict (ERR_DUPLICATE_REQUEST)

📲 Client Request: TEST 3: Product Plan Simulation Request (Txn: TXN_SIM_202)
  ⚡ [SAP SOM RFC] Invoking ZSOM_PRODUCT_SIMULATE_API_UDR for Zone=BAGHDAD_CENTRAL...
   Response Status: HTTP 200 OK

📲 Client Request: TEST 4: Get Offer List Database Query (Txn: TXN_OFFER_303)
   Response Status: HTTP 200 OK (Retrieved 2 Offers from SAP HANA DB)

=====================================================================================
✅ End-to-End ProductAPI Pipeline execution completed successfully!
=====================================================================================
```
