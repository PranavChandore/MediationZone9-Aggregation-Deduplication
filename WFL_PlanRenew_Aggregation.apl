// ============================================================================
// DigitalRoute MediationZone 9 — Production APL Workflow
// Workflow Name: PlanRenew.WFL_PlanRenew_Aggregation
// Target Endpoint: https://elcmqaap1.earthlink.iq:8010/pranav/v1/plan/renew
// Payload Format: { "TRANS_ID": "...", "SUB_ID": "...", "AMT": "..." }
// ============================================================================

import ultra.PlanRenew.UFL_PlanRenew;

// ----------------------------------------------------------------------------
// 1. SESSION INITIALIZATION (Runs ONLY when a new SUB_ID + TRANS_ID key arrives)
// ----------------------------------------------------------------------------
sessionInit {
    DuplicateCheckINT rec = (DuplicateCheckINT) input;
    
    session.dupValue    = rec.dupValue;
    session.count       = 0;
    session.cycleReqUDR = rec.cycleReqUDR;

    int sTime;
    strToInt(sTime, sessionTime);
    sessionTimeout(session, sTime);
}

// ----------------------------------------------------------------------------
// 2. MAIN CONSUME BLOCK (Processes HTTP Requests & Real-Time Deduplication)
// ----------------------------------------------------------------------------
consume {

    // ------------------------------------------------------------------------
    // STEP A: INCOMING HTTP REST REQUEST FROM REST SERVER AGENT
    // ------------------------------------------------------------------------
    if (instanceOf(input, Cycle)) {
        Cycle cycleUDR = (Cycle) input;
        Request req    = cycleUDR.request;

        // Decode JSON Payload: { "TRANS_ID": "...", "SUB_ID": "...", "AMT": "..." }
        PlanRenewReq renewReq = udrCreate(PlanRenewReq);
        
        if (!decodeJSONRequest(baToStr(req.body), renewReq)) {
            cycleUDR.response = createPortalFailedResponse(400); // HTTP 400 Bad Request
            udrRoute(cycleUDR, "response");
            return;
        }

        // Package into DuplicateCheckINT
        DuplicateCheckINT dupCheck = udrCreate(DuplicateCheckINT);
        dupCheck.dupValue    = renewReq.SUB_ID + "_" + renewReq.TRANS_ID; // Signature key
        dupCheck.ResUDR      = renewReq;                                  // Decoded Request UDR
        dupCheck.cycleReqUDR = cycleUDR;                                 // Original REST Cycle

        // Route to Real-Time Aggregation Agent Profile
        udrRoute(dupCheck, "toAggregationAgent");
        return;
    }

    // ------------------------------------------------------------------------
    // STEP B: AGGREGATION DEDUPLICATION EVALUATION
    // ------------------------------------------------------------------------
    else if (instanceOf(input, DuplicateCheckINT)) {
        DuplicateCheckINT rec = (DuplicateCheckINT) input;
        Cycle cycleUDR        = (Cycle) rec.cycleReqUDR;
        PlanRenewReq renewReq = (PlanRenewReq) rec.ResUDR;

        // Increment session count
        if (session.dupValue == rec.dupValue) {
            session.count = session.count + 1;
        }

        // --- DUPLICATE INTERCEPTION THRESHOLD ---
        if (session.count >= 2) {
            debug("ERROR: Duplicate Plan Renew Request Intercepted for Key: " + session.dupValue);
            
            rec.errCode = "ERR_DUPLICATE_REQUEST";
            rec.count   = session.count;

            // Route to duplicate response handler -> Returns HTTP 409 Conflict WITHOUT calling SAP!
            udrRoute(rec, "dupRes");
            return;
        } 
        else {
            debug("SUCCESS: First Valid Request. Forwarding to SAP.");
            
            rec.errCode = "";
            rec.count   = session.count;

            // Forward First Valid Request to SAP Billing / SOM
            udrRoute(rec, "toSAP");
            return;
        }
    }
}

// ----------------------------------------------------------------------------
// 3. TIMEOUT BLOCK (Purges Session Storage After Timeout Expires)
// ----------------------------------------------------------------------------
timeout {
    sessionRemove(session);
}
