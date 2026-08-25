// ============================================================================
// MediationZone 9 (InfoZone) - Production APL Workflow Script
// Workflow: WFL_PlanRenewal_Aggregation.apl
// Folder: PlanOperation_API
// Description: Real-time Aggregation, Deduplication, & ECS Error Quarantining
//              for EarthLink Subscriber Plan Renewals
// ============================================================================

import ultra.PlanOperation_API.UFL_PlanRenewal_Data;

// ----------------------------------------------------------------------------
// SESSION INITIALIZATION BLOCK (Triggered on new Aggregation session key)
// ----------------------------------------------------------------------------
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

// ----------------------------------------------------------------------------
// CONSUME BLOCK (Triggered per incoming PlanRenewalReqInt UDR)
// ----------------------------------------------------------------------------
consume {
    PlanRenewalReqInt inputUdr = (PlanRenewalReqInt) input;
    PlanRenewalReqInt outUdr   = udrCreate(PlanRenewalReqInt);

    // STEP 1: VALIDATION CHECK (Amount must be positive)
    if (inputUdr.amount <= 0.0) {
        debug("WARN: [consume] Invalid payment amount (" + inputUdr.amount + ") for subscriber " + inputUdr.subscriberId);
        inputUdr.errCode  = "ERR_INVALID_AMOUNT";
        inputUdr.errorMsg = "Payment amount must be greater than 0. Quarantined to ECS Queue.";
        
        // Route to ECS Error Forwarding Agent
        udrRoute(inputUdr, "ECS_Quarantine_Queue");
        return;
    }

    // STEP 2: AGGREGATION & DEDUPLICATION COUNTER CHECK
    if (session.dupValue == inputUdr.dupValue) {
        session.count       = session.count + 1;
        session.totalAmount = session.totalAmount + inputUdr.amount;
        debug("INFO: [consume] Active Session Match. session.count = " + session.count + " | Total Amount = " + session.totalAmount);
    }

    // STEP 3: DUPLICATE INTERCEPTION THRESHOLD (session.count >= 2)
    if (session.count >= 2) {
        debug("ERROR: [consume] DUPLICATE REQUEST INTERCEPTED! session.count = " + session.count + " for key: " + inputUdr.dupValue);
        
        outUdr.dupValue         = inputUdr.dupValue;
        outUdr.transactionId    = inputUdr.transactionId;
        outUdr.subscriberId     = inputUdr.subscriberId;
        outUdr.planId           = inputUdr.planId;
        outUdr.amount           = inputUdr.amount;
        outUdr.errCode          = "ERR_DUPLICATE_REQUEST";
        outUdr.errorMsg         = "Duplicate plan renewal request intercepted by MZ Aggregation Profile (PRF_AGG_PlanRenewal)";
        outUdr.rawRestRequestUdr= inputUdr.rawRestRequestUdr;

        // Route to Duplicate Error Response Router (Returns HTTP 409 Conflict)
        udrRoute(outUdr, "dupRes");
        return;
    } else {
        debug("SUCCESS: [consume] First valid request for session. Forwarding to SAP CC / DB Agent.");
        
        outUdr.dupValue         = inputUdr.dupValue;
        outUdr.transactionId    = inputUdr.transactionId;
        outUdr.subscriberId     = inputUdr.subscriberId;
        outUdr.planId           = inputUdr.planId;
        outUdr.amount           = inputUdr.amount;
        outUdr.errCode          = "";
        outUdr.errorMsg         = "SUCCESS";
        outUdr.rawRestRequestUdr= inputUdr.rawRestRequestUdr;

        // Route to SAP HANA DB Output Agent (Returns HTTP 200 OK & writes to SAP tables)
        udrRoute(outUdr, "SAP_HANA_DB_Agent");
        return;
    }
}

// ----------------------------------------------------------------------------
// TIMEOUT BLOCK (Triggered when sessionTime window expires)
// ----------------------------------------------------------------------------
timeout {
    debug("INFO: [timeout] Aggregation session window expired for key: " + session.dupValue + ". Flushing session state.");
    sessionRemove(session);
}
