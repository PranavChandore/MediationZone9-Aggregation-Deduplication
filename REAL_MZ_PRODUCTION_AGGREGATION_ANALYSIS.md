# Production MediationZone Aggregation & Deduplication Analysis

This document details the exact **Aggregation & Deduplication Workflow** extracted directly from your production/QAS MediationZone system (`10.4.15.134`).

---

## 1. Production Architecture Overview

In your MediationZone environment, the **Wallet API Workflow (`WalletAPI.WFL_Wallet_API`)** uses **Real-Time Aggregation (`com.digitalroute.wfc.aggregation.AggregationRealtimeInsp`)** paired with **`WalletAPI.PRF_AGG_WALLETAPI`** to intercept duplicate topup / payment requests before calling downstream services.

```
       [ Client HTTP REST Request / Wallet Topup ]
                           │
                           ▼
          [ WFL_Wallet_API (Main Router) ]
                           │
                           ▼ (Creates DuplicateCheckInt UDR with dupValue = TransactionID/Key)
          ┌──────────────────────────────────┐
          │  Aggregation Realtime Agent      │
          │  (com.digitalroute.wfc... Insp)  │
          │                                  │
          │  1. sessionInit                  │ <-- Creates session by dupValue & sets timeout
          │  2. consume                      │ <-- Increments session.count
          │                                  │
          │  if (session.count >= 2):        │
          │    errCode = "Duplicate"         │ --> Sent to "dupRes" Router (Rejection Response)
          │  else:                           │
          │    errCode = "" (Valid Request)  │ --> Passed to SAP / CC Service Processing
          └──────────────────────────────────┘
```

---

## 2. Exact Production Code Breakdown

### A. Aggregation Profile (`WalletAPI.PRF_AGG_WALLETAPI`)
* **ID Field List**: `["dupValue"]` (Unique request signature created from transaction ID & account).
* **Session UDR Type**: `WalletAPI.UFL_Int_WalletData.DuplicateChecks`
* **Input UDR Type**: `WalletAPI.UFL_Int_WalletData.DuplicateCheckInt`
* **Storage Path**: `/mz8/Agg_Session/`

### B. Session & Internal UDR Definitions (`WalletAPI.UFL_Int_WalletData`)

```apl
session DuplicateChecks {
    string dupValue;
    int count;
    drudr endUserOnboardUdr; 
    drudr cycleReqUDR;
};

internal DuplicateCheckInt {
    string errCode;
    string dupValue;
    int count;
    drudr ResUDR; 
    drudr cycleReqUDR;
};
```

### C. Aggregation Agent APL Script (`WalletAPI.WFL_Wallet_API`)

```apl
sessionInit {
    debug("SessionInit block initiated");
    DuplicateCheckInt rec = (DuplicateCheckInt)input;    
    session.dupValue = rec.dupValue;
    session.count = 0;
    int sTime;
    strToInt(sTime, sessionTime);
    sessionTimeout(session, sTime);
}

consume {
    DuplicateCheckInt rec = (DuplicateCheckInt)input; 
    openapi.WalletAPI.PRF_WalletAPI_OpenAPI.WalletTopupRequest opReqUDR = 
        (openapi.WalletAPI.PRF_WalletAPI_OpenAPI.WalletTopupRequest) rec.ResUDR; 

    DuplicateCheckInt duprec = udrCreate(DuplicateCheckInt);

    if (session.dupValue == rec.dupValue) {
        session.count = session.count + 1;
        debug(" From AGG :: Count block");
        debug("session.count :: " + session.count);
    }

    if (session.count >= 2) {
        debug(" From AGG :: Send duplicate Error");
        duprec.errCode = "Duplicate"; 
        duprec.ResUDR = rec.ResUDR;
        duprec.cycleReqUDR = rec.cycleReqUDR;
        udrRoute(duprec, "dupRes");
        return;
    } else {
        debug(" From AGG :: No duplicate");
        duprec.errCode = ""; 
        duprec.ResUDR = rec.ResUDR;
        duprec.cycleReqUDR = rec.cycleReqUDR;
        udrRoute(duprec, "dupRes");
        return;
    }
}

timeout {
    sessionRemove(session);
}
```

---

## 3. How the Duplicate Rejection Works Step-by-Step

1. **First Request Arrives**:
   * `sessionInit` triggers, creating a new session keyed by `dupValue` (e.g. `TXN998811`).
   * `session.count` initialized to `0`.
   * `consume` runs: `session.count` becomes `1`.
   * `session.count >= 2` evaluates to **FALSE**.
   * `duprec.errCode = ""` (Empty / No Error). Request proceeds downstream to SAP/CC.

2. **Duplicate Request Arrives (Retry / Double-Click within timeout window)**:
   * The existing active session for `dupValue` is found. `sessionInit` is **skipped**.
   * `consume` runs: `session.count` increments to `2`.
   * `session.count >= 2` evaluates to **TRUE**.
   * `duprec.errCode = "Duplicate"`.
   * `udrRoute(duprec, "dupRes")` routes the UDR immediately to the duplicate error handler, returning an HTTP duplicate request response to the client **without calling SAP**.

3. **Session Expiry**:
   * After the configured `sessionTime` timeout expires, the `timeout` block executes `sessionRemove(session)` to clean up disk/memory storage in `/mz8/Agg_Session/`.
