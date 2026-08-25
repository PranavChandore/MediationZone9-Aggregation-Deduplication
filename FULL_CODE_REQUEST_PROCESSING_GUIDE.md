# Complete MediationZone 9 Request Processing & Aggregation Code Guide

This document presents the complete end-to-end code, request processing pipeline, and step-by-step execution flow for **MediationZone 9 (InfoZone)** Aggregation, Deduplication, and REST Server processing.

---

## 1. Request Processing Lifecycle Overview

```
   [ 1. Client HTTP POST Request ]
     Headers: Content-Type: application/json
     Body: { "transactionId": "TXN_RENEW_1001", "subscriberId": "SUB_44012", "amount": 45000.0 }
                     │
                     ▼
   [ 2. REST Server Agent & OpenAPI Decoder ]
     Profile: PRF_PlanRenewal_OpenAPI.json (Listening on /v1/plan/renew)
     Maps JSON payload into UFL_PlanRenewal_Data.PlanRenewalReqInt UDR
                     │
                     ▼
   [ 3. Aggregation Profile Key Generation ]
     Profile: PRF_AGG_PlanRenewal.json
     ID Field List: ["dupValue"] -> Key: "SUB_44012_TXN_RENEW_1001"
                     │
                     ▼
   [ 4. APL Aggregation Workflow Execution ]
     Script: WFL_PlanRenewal_Aggregation.apl
                     │
                     ├───► If amount <= 0: Route to "ECS_Quarantine_Queue"
                     │
                     ├───► If session.count >= 2:
                     │     Flag errCode = "ERR_DUPLICATE_REQUEST"
                     │     Route to "dupRes" -> HTTP 409 Conflict (Client Rejection)
                     │
                     └───► If session.count == 1:
                           Flag errCode = ""
                           Route to "SAP_HANA_DB_Agent" -> Writes to ZEL_PYMNT & DFKKINVDOC_I
                           Returns HTTP 200 OK
```

---

## 2. Ultra Data Format Definition (`UFL_PlanRenewal_Data.ufl`)

```apl
// Ultra Format: UFL_PlanRenewal_Data
// Folder: PlanOperation_API

session PlanRenewalSession {
    string dupValue;            // Aggregation Key Signature (SubscriberID + "_" + TransactionID)
    int count;                  // Request Counter per session window
    string subscriberId;
    string planId;
    double totalAmount;
    date firstRequestTime;
    drudr activeRequestUdr;
};

internal PlanRenewalReqInt {
    string dupValue;            // Aggregation Key
    string transactionId;       // Client Transaction ID
    string subscriberId;        // EarthLink Subscriber / BP ID
    string planId;              // Target Plan Code
    double amount;              // Renewal payment amount in IQD
    string channel;             // Channel (MOBILE_APP, POS_KIOSK, WEB_PORTAL)
    string requestTimestamp;    // Timestamp string
    string errCode;             // Aggregation Error Code ("ERR_DUPLICATE_REQUEST" or "")
    string errorMsg;            // Detailed Error Description
    drudr rawRestRequestUdr;    // Original HTTP REST Request UDR reference
};

internal PlanRenewalResInt {
    string transactionId;
    string subscriberId;
    string planId;
    double amount;
    string currency;
    string status;              // "SUCCESS" or "FAILED"
    string errorCode;
    string message;
    string sapInvoiceDocNo;     // Generated SAP DFKKINVDOC_I Document Number
    date sapPostingDate;        // SAP HANA Posting Date
};
```

---

## 3. Aggregation Profile Config (`PRF_AGG_PlanRenewal.json`)

```json
{
  "Key": "MZ1749623491100",
  "Name": "PRF_AGG_PlanRenewal",
  "Type": "Aggregation Profile",
  "Folder": "PlanOperation_API",
  "Data": {
    "Association config": [
      {
        "UDR type": {
          "TypeName": "PlanOperation_API.UFL_PlanRenewal_Data.PlanRenewalReqInt",
          "FormatName": "PlanOperation_API.UFL_PlanRenewal_Data"
        },
        "Association rules": [
          {
            "ID field list": [
              "dupValue"
            ],
            "Create session on failure": true
          }
        ]
      }
    ],
    "Storage config": {
      "Directory": "/mz8/Agg_Session/PlanRenewal/",
      "Partial File Count": 10,
      "Max Session Count": 100000
    },
    "UDR Type": {
      "TypeName": "PlanOperation_API.UFL_PlanRenewal_Data.PlanRenewalSession",
      "FormatName": "PlanOperation_API.UFL_PlanRenewal_Data"
    }
  }
}
```

---

## 4. Production APL Workflow Logic (`WFL_PlanRenewal_Aggregation.apl`)

```apl
import ultra.PlanOperation_API.UFL_PlanRenewal_Data;

// 1. sessionInit: Executed when a new Aggregation session key is created
sessionInit {
    debug("INFO: [sessionInit] New session key created.");
    PlanRenewalReqInt inputUdr = (PlanRenewalReqInt) input;
    
    session.dupValue          = inputUdr.dupValue;
    session.subscriberId      = inputUdr.subscriberId;
    session.planId            = inputUdr.planId;
    session.totalAmount       = 0.0;
    session.count             = 0;
    session.firstRequestTime  = sysdate();
    session.activeRequestUdr  = inputUdr;

    int sTime;
    strToInt(sTime, sessionTime);
    debug("INFO: Setting session timeout to " + sTime + " seconds for key: " + session.dupValue);
    sessionTimeout(session, sTime);
}

// 2. consume: Executed per incoming PlanRenewalReqInt UDR
consume {
    PlanRenewalReqInt inputUdr = (PlanRenewalReqInt) input;
    PlanRenewalReqInt outUdr   = udrCreate(PlanRenewalReqInt);

    // STEP 1: VALIDATION CHECK (Amount must be positive)
    if (inputUdr.amount <= 0.0) {
        debug("WARN: Invalid payment amount (" + inputUdr.amount + ") for subscriber " + inputUdr.subscriberId);
        inputUdr.errCode  = "ERR_INVALID_AMOUNT";
        inputUdr.errorMsg = "Payment amount must be greater than 0. Quarantined to ECS Queue.";
        
        udrRoute(inputUdr, "ECS_Quarantine_Queue");
        return;
    }

    // STEP 2: AGGREGATION & COUNTER CHECK
    if (session.dupValue == inputUdr.dupValue) {
        session.count       = session.count + 1;
        session.totalAmount = session.totalAmount + inputUdr.amount;
        debug("INFO: Session Match. session.count = " + session.count);
    }

    // STEP 3: DUPLICATE INTERCEPTION THRESHOLD (session.count >= 2)
    if (session.count >= 2) {
        debug("ERROR: DUPLICATE REQUEST INTERCEPTED! session.count = " + session.count);
        
        outUdr.dupValue         = inputUdr.dupValue;
        outUdr.transactionId    = inputUdr.transactionId;
        outUdr.subscriberId     = inputUdr.subscriberId;
        outUdr.planId           = inputUdr.planId;
        outUdr.amount           = inputUdr.amount;
        outUdr.errCode          = "ERR_DUPLICATE_REQUEST";
        outUdr.errorMsg         = "Duplicate plan renewal request intercepted by MZ Aggregation Profile (PRF_AGG_PlanRenewal)";

        // Route to "dupRes" (Returns HTTP 409 Conflict to Client without calling SAP)
        udrRoute(outUdr, "dupRes");
        return;
    } else {
        debug("SUCCESS: First valid request for session. Forwarding to SAP CC / DB Agent.");
        
        outUdr.dupValue         = inputUdr.dupValue;
        outUdr.transactionId    = inputUdr.transactionId;
        outUdr.subscriberId     = inputUdr.subscriberId;
        outUdr.planId           = inputUdr.planId;
        outUdr.amount           = inputUdr.amount;
        outUdr.errCode          = "";
        outUdr.errorMsg         = "SUCCESS";

        // Route to SAP HANA DB Agent (Returns HTTP 200 OK & inserts into SAP tables)
        udrRoute(outUdr, "SAP_HANA_DB_Agent");
        return;
    }
}

// 3. timeout: Executed when session window expires
timeout {
    debug("INFO: Session window expired for key: " + session.dupValue + ". Flushing session state.");
    sessionRemove(session);
}
```

---

## 5. Complete Executable End-to-End Application (`run_e2e_plan_renewal_pipeline.py`)

To run the complete pipeline on your system:

```bash
python run_e2e_plan_renewal_pipeline.py
```

### What `run_e2e_plan_renewal_pipeline.py` Does:
1. **Starts HTTP REST Server Agent** listening on `http://localhost:8090/v1/plan/renew`.
2. **Receives JSON Payloads** & decodes them into UDRs.
3. **Applies Aggregation Session Matching** (`session.count` counter).
4. **Executes SAP HANA Inserter** (`ZEL_PYMNT` & `DFKKINVDOC_I` posting) for valid requests.
5. **Intercepts Duplicates** & returns `HTTP 409 Conflict`.
6. **Routes Invalid Amounts** to the **ECS Quarantined Error Queue**.
7. **Displays Final Summary Report Tables** in the terminal.
