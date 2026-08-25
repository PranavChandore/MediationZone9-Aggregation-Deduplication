# MediationZone 9 — REST Server Agent: Localhost Configuration Guide

This guide tells you **exactly what to fill in every field** of the REST Server Agent
profile in the MediationZone EC Console for the PlanRenewal example.

---

## Step 1 — Open MZ EC Console

Go to: `http://localhost:9000` (or whatever port your local MZ runs on)

Login: `mzadmin` / `Security#1`

Navigate to:
```
Configuration → Profiles → New Profile → REST Server Agent Profile
```

---

## Step 2 — Fill In the REST Server Agent Profile

### 🔷 Tab: General

| Field | Value to Enter |
|:---|:---|
| **Name** | `PRF_PlanRenewal_Rest_Server` |
| **Folder** | `PlanOperation_API` |
| **Description** | `REST Server Agent for Plan Renewal API with Aggregation Deduplication` |

---

### 🔷 Tab: Agent Configuration

| Field | Value to Enter | Notes |
|:---|:---|:---|
| **Port** | `8090` | This is the HTTP port your REST agent listens on |
| **Host** | `0.0.0.0` | Listen on all interfaces (or `localhost` for local only) |
| **Max Connections** | `100` | Leave default or increase for high load |
| **Request Timeout (ms)** | `30000` | 30 seconds |
| **Use HTTPS** | ❌ Unchecked | No TLS for local testing |

---

### 🔷 Tab: Endpoint URIs

> This tells MZ which URL paths this agent handles.

Click **Add URI**:

| Field | Value |
|:---|:---|
| **URI Path** | `/v1/plan/` |
| **HTTP Methods** | `POST` |

> ✅ This means the agent will handle: `POST http://localhost:8090/v1/plan/renew`

---

### 🔷 Tab: OpenAPI Profile

> Links the REST agent to your OpenAPI 3.0 spec so it knows how to decode JSON bodies into UDRs.

| Field | Value |
|:---|:---|
| **OpenAPI Profile** | `PlanOperation_API.PRF_PlanRenewal_OpenAPI` |

> 📋 The OpenAPI profile defines:
> - The request schema (what JSON fields it accepts)
> - The response schemas (HTTP 200, HTTP 409)
> - The mapping between JSON fields → UDR fields

---

### 🔷 Tab: UDR Mapping

> Tells MZ which UDR type represents the decoded incoming request.

| Field | Value |
|:---|:---|
| **Input UDR Type** | `PlanOperation_API.UFL_PlanRenewal_Data.PlanRenewalReqInt` |
| **Output UDR Type** | `PlanOperation_API.UFL_PlanRenewal_Data.PlanRenewalResInt` |

---

## Step 3 — Workflow Agent Configuration (in the Workflow)

After creating the REST Server Agent profile, the Workflow (`WFL_PlanRenewal_Aggregation`) 
connects to it. In the workflow editor:

### Agent: REST Server Agent
```
Agent Type:     com.digitalroute.wfc.http.RestServerAgent
Profile:        PlanOperation_API.PRF_PlanRenewal_Rest_Server
```

### Agent: Aggregation Real-Time
```
Agent Type:     com.digitalroute.wfc.aggregation.AggregationRealtimeInsp
Profile:        PlanOperation_API.PRF_AGG_PlanRenewal
Session Time:   30   (seconds)
```

---

## Step 4 — Full Localhost URL Reference

Once configured and the MZ workflow is running, your REST server will respond to:

| Endpoint | Method | Purpose |
|:---|:---|:---|
| `http://localhost:8090/v1/plan/renew` | `POST` | Submit a new plan renewal request |

---

## Step 5 — Test It with cURL (from your PC)

### Test 1: Valid Request (Expect HTTP 200 OK)
```bash
curl -X POST http://localhost:8090/v1/plan/renew \
  -H "Content-Type: application/json" \
  -d '{
    "transactionId": "TXN_RENEW_9001",
    "subscriberId":  "SUB_44012",
    "planId":        "PLAN_FIBER_100M",
    "amount":        45000.0,
    "channel":       "MOBILE_APP"
  }'
```

**Expected Response:**
```json
{
  "status": "SUCCESS",
  "message": "Plan renewal successfully processed and posted to SAP HANA",
  "transactionId": "TXN_RENEW_9001",
  "subscriberId": "SUB_44012",
  "planId": "PLAN_FIBER_100M",
  "amount": 45000.0,
  "sapInvoiceDocNo": "300098445"
}
```

---

### Test 2: Duplicate Retry (Expect HTTP 409 Conflict)
```bash
curl -X POST http://localhost:8090/v1/plan/renew \
  -H "Content-Type: application/json" \
  -d '{
    "transactionId": "TXN_RENEW_9001",
    "subscriberId":  "SUB_44012",
    "planId":        "PLAN_FIBER_100M",
    "amount":        45000.0,
    "channel":       "MOBILE_APP_RETRY"
  }'
```

**Expected Response:**
```json
{
  "status": "FAILED",
  "errorCode": "ERR_DUPLICATE_REQUEST",
  "message": "Duplicate Request detected by MZ Aggregation Profile (PRF_AGG_PlanRenewal)",
  "transactionId": "TXN_RENEW_9001",
  "sessionCount": 2
}
```

---

### Test 3: Invalid Amount (Expect HTTP 400 Bad Request)
```bash
curl -X POST http://localhost:8090/v1/plan/renew \
  -H "Content-Type: application/json" \
  -d '{
    "transactionId": "TXN_RENEW_9002",
    "subscriberId":  "SUB_55099",
    "planId":        "PLAN_FIBER_100M",
    "amount":        -100.0,
    "channel":       "WEB_PORTAL"
  }'
```

**Expected Response:**
```json
{
  "status": "FAILED",
  "errorCode": "ERR_INVALID_AMOUNT",
  "message": "Payment amount must be greater than 0. Quarantined to ECS Queue."
}
```

---

## Step 6 — Run Python Simulation (If You Don't Have MZ Locally)

If you don't have MediationZone running locally, run the Python simulation instead:

```bash
# Simulates the REST Server Agent + Aggregation Engine on localhost:8090
python run_e2e_plan_renewal_pipeline.py
```

This simulates:
- REST Server Agent (listening on `http://localhost:8090/v1/plan/renew`)
- Aggregation Agent (session.count duplicate check)
- ECS Quarantine Agent
- SAP HANA DB (ZEL_PYMNT & DFKKINVDOC_I inserts)

---

## Summary: What Goes in the REST Server Agent

| Section | What to Put |
|:---|:---|
| **Port** | `8090` |
| **URI Path** | `/v1/plan/` |
| **HTTP Method** | `POST` |
| **OpenAPI Profile** | `PRF_PlanRenewal_OpenAPI` |
| **Input UDR** | `PlanRenewalReqInt` |
| **Output UDR** | `PlanRenewalResInt` |
| **Aggregation Profile** | `PRF_AGG_PlanRenewal` |
| **Session Field** | `dupValue` = `subscriberId + "_" + transactionId` |
| **Duplicate Threshold** | `session.count >= 2` → HTTP 409 |
| **Valid Request** | `session.count == 1` → HTTP 200 + SAP posting |
