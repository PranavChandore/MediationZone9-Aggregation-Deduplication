# MediationZone 9 — REST Server Agent with Aggregation & Deduplication

This guide explains how **REST Server Agents** work together with **Real-Time Aggregation & Deduplication** in MediationZone 9, based on your production architecture (`WalletAPI.PRF_WalletAPI_Rest_Server` & `WalletAPI.WFL_Wallet_API`).

---

## 1. How REST Server Agents Work in MediationZone 9

In MediationZone 9, a **REST Server Agent**:
1. **Exposes HTTP/REST Endpoints**: Listens on configured URIs (e.g. `http://10.4.4.128:8007/v1/wallet/topup`).
2. **OpenAPI / Schema Binding**: Binds OpenAPI 3.0 JSON specifications to internal UDR structures (e.g. `walletTopupRequest` -> `DuplicateCheckInt`).
3. **Decodes HTTP Requests**: Converts incoming HTTP POST headers, query params, and JSON body into UDR fields.
4. **Streams to Aggregation Agent**: Passes the decoded UDR down the workflow pipeline.
5. **Formulates HTTP Response**: Converts the output UDR (Success vs Error) into standard HTTP status codes (`HTTP 200 OK` vs `HTTP 409 Conflict`).

---

## 2. End-to-End REST + Aggregation Pipeline

```
  Client (Mobile App / Webhook)
              │
              │  HTTP POST /v1/wallet/topup
              ▼
  ┌─────────────────────────────────────────┐
  │  REST Server Agent                      │
  │  (WalletAPI.PRF_WalletAPI_Rest_Server)  │
  └───────────────────┬─────────────────────┘
                      │ (Decodes JSON payload into UDR)
                      ▼
  ┌─────────────────────────────────────────┐
  │  APL Pre-Processing / Key Creation      │
  │  dupValue = BP_ID + "_" + TxnID         │
  └───────────────────┬─────────────────────┘
                      │
                      ▼
  ┌─────────────────────────────────────────┐
  │  Real-Time Aggregation Agent            │
  │  (WalletAPI.PRF_AGG_WALLETAPI)          │
  │                                         │
  │  session.count == 1:                    │
  │    Forward to SAP CC -> HTTP 200 OK     │
  │                                         │
  │  session.count >= 2:                    │
  │    Flag ERR_DESC_DUP_REQUEST            │
  │    Route to "dupRes" -> HTTP 409        │
  └─────────────────────────────────────────┘
```

---

## 3. Production Configuration Details

### REST Server Profile (`WalletAPI.PRF_WalletAPI_Rest_Server`)
* **Endpoint URIs**: `["/v1/wallet/"]`
* **OpenAPI Profile**: `WalletAPI.PRF_WalletAPI_OpenAPI` (Specifies `/wallet/topup`, `/wallet/transfer`, etc.)

### REST Response Codes Returned to Client
* **HTTP 200 OK**:
  ```json
  {
    "status": "SUCCESS",
    "message": "Topup request successfully validated & forwarded to SAP CC",
    "transactionId": "TXN_88001",
    "businessPartnerId": "BP_10099",
    "amount": 10000.0,
    "currency": "IQD"
  }
  ```
* **HTTP 409 Conflict (Duplicate Request Intercepted by Aggregation)**:
  ```json
  {
    "status": "FAILED",
    "errorCode": "ERR_DESC_DUP_REQUEST",
    "message": "Duplicate Request detected by MZ Aggregation Profile (WalletAPI.PRF_AGG_WALLETAPI)",
    "transactionId": "TXN_88001",
    "businessPartnerId": "BP_10099",
    "sessionCount": 2
  }
  ```

---

## 4. How to Run the Included Demonstration Scripts

In `c:\Users\prana\OneDrive\Desktop\AggregationLearn`:

```bash
# 1. Run production logic aggregation simulation
python production_mz_aggregation_demo.py

# 2. Run REST Server Agent + Aggregation Engine HTTP endpoint simulation
python rest_agent_aggregation_server.py
```
