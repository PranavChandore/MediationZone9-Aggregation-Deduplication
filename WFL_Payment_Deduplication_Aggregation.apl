// ============================================================================
// MediationZone 9 (InfoZone) - APL Aggregation & Deduplication Example
// Workflow: WFL_Payment_Deduplication_Aggregation.apl
// Target: Prevent duplicate payment requests and consolidate UDRs for SAP
// ============================================================================

import udr.stdf;
import udr.zel;

// ----------------------------------------------------------------------------
// GLOBAL AGGREGATION STATE MAPS
// ----------------------------------------------------------------------------
// Map to hold unique aggregated records by transaction/customer key
map<string, record> agg_map = map<string, record>();

// Map to track processed request IDs to prevent duplicate requests across batches
map<string, date> processed_requests_cache = map<string, date>();

// Counters for workflow stats
int count_received = 0;
int count_aggregated = 0;
int count_duplicates_dropped = 0;
int count_quarantined = 0;

// ----------------------------------------------------------------------------
// INITIALIZE AGENT - Called when workflow starts
// ----------------------------------------------------------------------------
void initialize() {
    count_received = 0;
    count_aggregated = 0;
    count_duplicates_dropped = 0;
    count_quarantined = 0;
    
    debug("INFO: WFL_Payment_Deduplication_Aggregation initialized successfully.");
}

// ----------------------------------------------------------------------------
// CONSUME RECORD - Called per incoming UDR
// ----------------------------------------------------------------------------
void consume(udr u) {
    count_received = count_received + 1;
    
    string req_id   = u.transaction_id;
    string inv_no   = u.preliminary_inv_no;
    string cust_id  = u.customer_id;
    double amt      = u.amount;
    string status   = u.status;

    // STEP 1: VALIDATION CHECK
    if (amt <= 0.0) {
        debug("WARN: Invalid amount (" + amt + ") for customer " + cust_id + ". Forwarding to ECS Error Queue.");
        u.error_code = "ERR_INV_AMOUNT";
        u.error_msg  = "Amount must be strictly positive";
        count_quarantined = count_quarantined + 1;
        
        // Route to ECS Forwarding Agent (Error Queue)
        udrRoute(u, "ECS_Error_Queue");
        return;
    }

    // STEP 2: DEDUPLICATION CHECK (Avoid Duplicate Payment Request)
    // Construct unique request signature key: PREL_INV + TXN_ID
    string dedupe_key = inv_no + "_" + req_id;

    if (mapContains(processed_requests_cache, dedupe_key)) {
        debug("DUPLICATE DETECTED: Request " + dedupe_key + " already processed! Rejection triggered.");
        count_duplicates_dropped = count_duplicates_dropped + 1;

        // Tag UDR as Duplicate for Audit/Reversal routing
        u.is_duplicate = true;
        u.duplicate_reason = "DUPLICATE_REQUEST_ID_BLOCKED";
        
        // Route to Duplicate Audit Output Agent instead of SAP DB
        udrRoute(u, "Duplicate_Audit_Agent");
        return;
    }

    // STEP 3: AGGREGATION BUFFERING (Grouping by Preliminary Invoice & Customer)
    string agg_key = inv_no + "_" + cust_id;

    if (mapContains(agg_map, agg_key)) {
        // Record already exists in current batch -> Accumulate / Aggregate values
        record existing_rec = mapGet(agg_map, agg_key);
        existing_rec.total_amount     = existing_rec.total_amount + amt;
        existing_rec.transaction_cnt  = existing_rec.transaction_cnt + 1;
        existing_rec.last_update_date = sysdate();

        mapPut(agg_map, agg_key, existing_rec);
        debug("AGGREGATING: Updated key " + agg_key + " | New Total: " + existing_rec.total_amount);
    } else {
        // New record in current batch -> Create initial aggregated UDR structure
        record agg_rec = new record();
        agg_rec.preliminary_inv_no = inv_no;
        agg_rec.customer_id        = cust_id;
        agg_rec.total_amount       = amt;
        agg_rec.transaction_cnt    = 1;
        agg_rec.status             = "AGGREGATED";
        agg_rec.creation_date      = sysdate();

        mapPut(agg_map, agg_key, agg_rec);
        debug("AGGREGATING: Created new entry for key " + agg_key + " | Amount: " + amt);
    }

    // Register request ID in deduplication cache to block future retries
    mapPut(processed_requests_cache, dedupe_key, sysdate());
}

// ----------------------------------------------------------------------------
// DRAIN AGENT - Called at end of batch/stream to emit consolidated records
// ----------------------------------------------------------------------------
void drain() {
    debug("DRAIN TRIGGERED: Emitting aggregated records to SAP Output Agent...");

    list<string> keys = mapKeys(agg_map);
    for (int i = 0; i < listSize(keys); i = i + 1) {
        string key = listGet(keys, i);
        record consolidated_udr = mapGet(agg_map, key);

        count_aggregated = count_aggregated + 1;

        // Dispatch clean, consolidated UDR downstream to SAP HANA Output Agent
        udrRoute(consolidated_udr, "SAP_HANA_Output_Agent");
    }

    debug("================ SUMMARY STATS ================");
    debug("Total Raw UDRs Received   : " + count_received);
    debug("Clean Aggregated Output   : " + count_aggregated);
    debug("Duplicates Blocked        : " + count_duplicates_dropped);
    debug("Quarantined to ECS        : " + count_quarantined);
    debug("===============================================");
}
