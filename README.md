# MediationZone 9 — EarthLink Plan Renew Aggregation & Deduplication

Production-grade **MediationZone 9 (InfoZone)** APL Workflow and Aggregation Configuration for EarthLink Subscriber Plan Renewals.

---

## 📌 Endpoint & Payload Specification

* **Target URL**: `https://elcmqaap1.earthlink.iq:8010/pranav/v1/plan/renew`
* **HTTP Method**: `POST`
* **Content-Type**: `application/json`
* **JSON Payload**:
  ```json
  {
      "TRANS_ID": "TXN_99001",
      "SUB_ID": "SUB_44012",
      "AMT": "45000"
  }
  ```

---

## 📁 Repository Structure

```
├── UFL_PlanRenew.ufl               # Ultra Format (DuplicateCheck, DuplicateCheckINT, PlanRenewReq)
├── WFL_PlanRenew_Aggregation.apl   # Production APL Workflow (sessionInit, consume, timeout)
├── PRF_AGG_PlanRenew.json          # Aggregation Profile Config (Key: dupValue)
├── PRF_PlanRenew_OpenAPI.json      # OpenAPI 3.0 Spec Profile
├── MZ9_Log_Diagnostics_Guide.md    # Log Diagnostics & Troubleshooting Guide
└── README.md                       # Project Overview
```

---

## ⚙️ Workflow Execution Flow

```
Client POST /pranav/v1/plan/renew
         │
         ▼
REST Server Agent (Decodes JSON payload into PlanRenewReq)
         │
         ▼
Package into DuplicateCheckINT (dupValue = SUB_ID + "_" + TRANS_ID)
         │
         ▼
Real-Time Aggregation Agent (PRF_AGG_PlanRenew)
         │
         ├── session.count == 1 ──► Route to "toSAP" (HTTP 200 OK)
         └── session.count >= 2 ──► Route to "dupRes" (HTTP 409 Conflict) [Blocked!]
```

---

## 🧪 Request Interception Matrix

| Request | Payload Signature | Aggregation Key (`dupValue`) | `session.count` | Outcome | Hits SAP? |
|:---|:---|:---|:---:|:---|:---:|
| **Request 1** | `SUB_44012` + `TXN_99001` | `SUB_44012_TXN_99001` | **1** | **`HTTP 200 OK`** | ✅ **YES** |
| **Request 2 (Retry)** | `SUB_44012` + `TXN_99001` | `SUB_44012_TXN_99001` | **2** | **`HTTP 409 Conflict`** | ❌ **NO (Blocked)** |
| **Request 3 (New)** | `SUB_44012` + `TXN_99002` | `SUB_44012_TXN_99002` | **1** | **`HTTP 200 OK`** | ✅ **YES** |
