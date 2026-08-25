// ============================================================================
// DigitalRoute MediationZone 9 — Complete Production APL Workflow
// Workflow Name: ProductAPI.WFL_ProductAPI_Aggregation_Router
// Description  : Complete REST Agent Router + Real-Time Aggregation Deduplication
//                + SAP S/4HANA SOM RFC Integration & HANA Database Querier
// ============================================================================

import ultra.openapi.ProductAPI.PRF_OpenAPI_ProductAPI;
import ultra.SAP_RFC.Common.PRF_RFC_PRODUCT;
import ultra.SAP_RFC.Common.PRF_RFC_PRODUCT.subUdr;
import apl.Common.APL_Functions;
import apl.Common.APL_Constant;
import apl.ProductAPI.APL_Functions;
import apl.ProductAPI.APL_Constants;
import apl.ProductAPI.APL_ProductAPI_RFC_Mapping;
import ultra.ProductAPI.UFL_Product_API;


// ============================================================================
// 1. AGGREGATION BLOCK — SESSION INITIALIZATION
// ============================================================================
sessionInit {
    debug("INFO: [sessionInit] Initializing new Aggregation Session Key...");
    DuplicateCheckInt rec = (DuplicateCheckInt) input;
    
    session.dupValue         = rec.dupValue;
    session.count            = 0;
    session.firstRequestTime = sysdate();
    session.activeRequestUdr = rec.ResUDR;

    int sTime;
    strToInt(sTime, sessionTime);
    debug("INFO: Setting session timeout to " + sTime + " seconds for dupValue: " + session.dupValue);
    sessionTimeout(session, sTime);
}


// ============================================================================
// 2. MAIN WORKFLOW CONSUME BLOCK (Processes HTTP Requests, Aggregation, & RFCs)
// ============================================================================
consume {
    int wfId = (int) mimGet("Workflow", "Workflow ID");
    date start_Dt = dateCreateNow();
    long start_Ms = dateCreateNowMilliseconds();

    // ------------------------------------------------------------------------
    // CASE A: INCOMING HTTP REST REQUEST (Cycle UDR from REST Server Agent)
    // ------------------------------------------------------------------------
    if (instanceOf(input, Cycle)) {
        Cycle cycleUDR = (Cycle) input;

        // STEP 1: S/4HANA Database & System Availability Check
        if (!isS4DatabaseActive(1)) {
            debug("ERROR: S/4HANA Database is unavailable.");
            cycleUDR.response = createPortalFailedResponse(500);
            udrRoute(cycleUDR, "response");
            return;
        }

        Request RESTreq = cycleUDR.request;

        // STEP 2: Validate Path Parameters
        if (RESTreq.pathParams == null || listSize(RESTreq.pathParams) == 0) {
            cycleUDR.response = createPortalFailedResponse(HTTP_RESPONSE_CODE_RESOURCE_NOT_FOUND);
            udrRoute(cycleUDR, "response");
            return;
        }

        // STEP 3: Handle CORS Options Preflight Request
        if (RESTreq.httpMethod == HTTP_OPTIONS_METHOD) {
            Response responseUDR = udrCreate(Response);
            map<string, list<string>> headerFields = mapCreate(string, list<string>);
            mapSet(headerFields, "Access-Control-Allow-Origin", listCreate(string, RESTreq.clientHost));
            mapSet(headerFields, "Access-Control-Allow-Methods", listCreate(string, accessControlAllowMethod));
            mapSet(headerFields, "Access-Control-Allow-Headers", listCreate(string, accessControlAllowHeaders));
            responseUDR.headerFields = headerFields;
            responseUDR.httpResponseCode = HTTP_RESPONSE_CODE_CONTENT_NOT_FOUND;
            cycleUDR.response = responseUDR;
            udrRoute(cycleUDR, "response");
            return;
        }

        // STEP 4: Authenticate REST Request
        boolean authResult = authticateRequest(authType, cycleUDR.request.authentication);
        if (!authResult) {
            debug("ERROR: Client authentication failed.");
            cycleUDR.response = createPortalFailedResponse(HTTP_RESPONSE_CODE_CLIENT_UNAUTHORIZED);
            udrRoute(cycleUDR, "response");
            return;
        }

        string path = listGet(RESTreq.pathParams, 0);

        // =================================================-------------------
        // ROUTE ROUTER FOR WORKFLOW INSTANCE 1
        // =================================================================---
        if (wfId == 1) {
            
            // ----------------------------------------------------------------
            // ENDPOINT 1: /search or /search1
            // ----------------------------------------------------------------
            if (strEqualsIgnoreCase(path, "search1") || strEqualsIgnoreCase(path, "search")) {
                if (listSize(RESTreq.pathParams) > 1) {
                    cycleUDR.response = createPortalFailedResponse(HTTP_RESPONSE_CODE_RESOURCE_NOT_FOUND);
                    udrRoute(cycleUDR, "response");
                    return;
                }

                if (RESTreq.httpMethod == HTTP_POST_METHOD) {
                    ProductSearchRequest prodReqeust = udrCreate(ProductSearchRequest);
                    boolean isBadReq = false;

                    if (RESTreq.body == null) {
                        isBadReq = true;
                    }

                    if (isBadReq || !decodeJSONRequest(baToStr(RESTreq.body), prodReqeust)) {
                        debug("ERROR: Failed to decode ProductSearch JSON body.");
                        cycleUDR.response = createPortalFailedResponse(HTTP_RESPONSE_CODE_BAD_REQUEST);
                        udrRoute(cycleUDR, "response");
                        return;
                    }

                    // --- REAL-TIME AGGREGATION & DEDUPLICATION CHECK ---
                    string dupKey = prodReqeust.endUserId + "_" + prodReqeust.transactionId;
                    DuplicateCheckInt dupCheck = udrCreate(DuplicateCheckInt);
                    dupCheck.dupValue = dupKey;
                    dupCheck.ResUDR   = cycleUDR;

                    // Route to Aggregation Agent Profile
                    udrRoute(dupCheck, "toAggregationAgent");
                    return;
                } else {
                    cycleUDR.response = createPortalFailedResponse(HTTP_RESPONSE_CODE_METHOD_NOT_IMPLEMENTED);
                    udrRoute(cycleUDR, "response");
                    return;
                }
            }

            // ----------------------------------------------------------------
            // ENDPOINT 2: /simulate
            // ----------------------------------------------------------------
            else if (strEqualsIgnoreCase(path, "simulate")) {
                if (listSize(RESTreq.pathParams) > 1) {
                    cycleUDR.response = createPortalFailedResponse(HTTP_RESPONSE_CODE_RESOURCE_NOT_FOUND);
                    udrRoute(cycleUDR, "response");
                    return;
                }

                if (RESTreq.httpMethod == HTTP_POST_METHOD) {
                    NewProductSimulateRequest prodReqeust = udrCreate(NewProductSimulateRequest);
                    boolean isBadReq = false;

                    if (RESTreq.body == null) {
                        isBadReq = true;
                    }

                    if (isBadReq || !decodeJSONRequest(baToStr(RESTreq.body), prodReqeust)) {
                        debug("ERROR: Failed to decode ProductSimulate JSON payload.");
                        cycleUDR.response = createPortalFailedResponse(HTTP_RESPONSE_CODE_BAD_REQUEST);
                        udrRoute(cycleUDR, "response");
                        return;
                    }

                    prodReqeust.zoneId = strToUpper(prodReqeust.zoneId);
                    string errorCodeInfo = valiadateProductSimulateRequest(prodReqeust);

                    prodSimulation simData = getCityAndRegionByZone(prodReqeust.zoneId, (string) prodReqeust.salesOrg);
                    prodReqeust.city = simData.city;
                    prodReqeust.region = simData.region;

                    if (isEmpty(prodReqeust.city)) {
                        errorCodeInfo = (string) CITY_INVALID_OR_BLANK + "_" + ERR_DESC_CITY_INVALID;
                    }

                    if (isEmpty(errorCodeInfo)) {
                        if (isEmpty(prodReqeust.currency)) {
                            prodReqeust.currency = getCurrency(padStrByZeros(prodReqeust.endUserId, 10), (string) prodReqeust.LOB);
                        }

                        // Build SAP SOM RFC Request
                        ZSOM_PRODUCT_SIMULATE_API_UDR rfcUdr = createNewProductSimulateRfcRequest(prodReqeust);
                        debug("INFO: Forwarding Product Simulate RFC Request to SAP SOM...");
                        rfcUdr.context = cycleUDR;
                        udrRoute(rfcUdr, "toSOMRFC");
                        return;
                    } else {
                        NewProductSimulateResponse resUdr = createNewProductSimulateResponse(prodReqeust, errorCodeInfo, null, HTTP_RESPONSE_CODE_NOT_ACCEPTABLE, null, null);
                        cycleUDR.response = createProductPortalResponse(resUdr, HTTP_SUCCESS_RESPONSE_CODE);
                        udrRoute(cycleUDR, "response");
                        return;
                    }
                } else {
                    cycleUDR.response = createPortalFailedResponse(HTTP_RESPONSE_CODE_METHOD_NOT_IMPLEMENTED);
                    udrRoute(cycleUDR, "response");
                    return;
                }
            }

            // ----------------------------------------------------------------
            // ENDPOINT 3: /getOfferList (HANA Database SQL Query)
            // ----------------------------------------------------------------
            else if (strEqualsIgnoreCase(path, "getOfferList")) {
                if (listSize(RESTreq.pathParams) > 1) {
                    cycleUDR.response = createPortalFailedResponse(HTTP_RESPONSE_CODE_RESOURCE_NOT_FOUND);
                    udrRoute(cycleUDR, "response");
                    return;
                }

                if (RESTreq.httpMethod == HTTP_POST_METHOD) {
                    OfferListRequest offListReq = udrCreate(OfferListRequest);
                    boolean isBadReq = false;

                    if (RESTreq.body == null) {
                        isBadReq = true;
                    }

                    if (isBadReq || !decodeJSONRequest(baToStr(RESTreq.body), offListReq)) {
                        cycleUDR.response = createPortalFailedResponse(HTTP_RESPONSE_CODE_BAD_REQUEST);
                        udrRoute(cycleUDR, "response");
                        return;
                    }

                    string errorMsgInfo = validateGetOfferListRequest(offListReq);
                    if (isEmpty(errorMsgInfo)) {
                        OfferListResponse offListRes;
                        table offerListTable;
                        string SQL_TO_GET_OFFER = "";
                        list<any> parameters = listCreate(any);
                        listAdd(parameters, MANDT);
                        listAdd(parameters, offListReq.LOB);

                        if (!isEmpty(offListReq.contractorID)) {
                            listAdd(parameters, padStrByZeros(offListReq.contractorID, 10));
                            SQL_TO_GET_OFFER = SQL_TO_GET_OFFER_LIST_DATA + CONTRACTOR_FILTER;
                        }

                        if (!isEmpty(offListReq.city)) {
                            listAdd(parameters, offListReq.city);
                            SQL_TO_GET_OFFER = SQL_TO_GET_OFFER + CITY_FILTER;
                        }

                        if (isEmpty(SQL_TO_GET_OFFER)) {
                            offerListTable = sqlPrepDynamicSelect(SQL_TO_GET_OFFER_LIST_DATA, parameters, HDB_PROFILE);
                        } else {
                            offerListTable = sqlPrepDynamicSelect(SQL_TO_GET_OFFER, parameters, HDB_PROFILE);
                        }

                        debug("INFO: Retrieved Offer List Table from SAP HANA DB: " + offerListTable);
                        if (offerListTable != null && tableRowCount(offerListTable) > 0) {
                            offListRes = createGetOfferListResponse(HTTP_SUCCESS_RESPONSE_CODE, offListReq, errorMsgInfo, offerListTable);
                        } else {
                            errorMsgInfo = (string) NO_OFFERS_FOUND + "-" + ERR_DESC_NO_OFFERS_FOUND;
                            offListRes = createGetOfferListResponse(HTTP_SUCCESS_RESPONSE_CODE, offListReq, errorMsgInfo, offerListTable);
                        }

                        cycleUDR.response = createProductPortalResponse(offListRes, HTTP_SUCCESS_RESPONSE_CODE);
                        udrRoute(cycleUDR, "response");
                        return;
                    } else {
                        OfferListResponse offListRes = createGetOfferListResponse(HTTP_RESPONSE_CODE_NOT_ACCEPTABLE, offListReq, errorMsgInfo, null);
                        cycleUDR.response = createProductPortalResponse(offListRes, HTTP_SUCCESS_RESPONSE_CODE);
                        udrRoute(cycleUDR, "response");
                        return;
                    }
                } else {
                    cycleUDR.response = createPortalFailedResponse(HTTP_RESPONSE_CODE_METHOD_NOT_IMPLEMENTED);
                    udrRoute(cycleUDR, "response");
                    return;
                }
            }
        }
    }

    // ------------------------------------------------------------------------
    // CASE B: AGGREGATION ENGINE EVALUATION (DuplicateCheckInt UDR)
    // ------------------------------------------------------------------------
    else if (instanceOf(input, DuplicateCheckInt)) {
        DuplicateCheckInt rec = (DuplicateCheckInt) input;
        Cycle cycleUDR        = (Cycle) rec.ResUDR;
        ProductSearchRequest prodReq = udrCreate(ProductSearchRequest);
        decodeJSONRequest(baToStr(cycleUDR.request.body), prodReq);

        // Update Session Counters
        if (session.dupValue == rec.dupValue) {
            session.count = session.count + 1;
            debug("INFO: [Aggregation Engine] Matching Session. Count = " + session.count);
        }

        // DUPLICATE REJECTION THRESHOLD (session.count >= 2)
        if (session.count >= 2) {
            debug("ERROR: [AGGREGATION INTERCEPTED DUPLICATE REQUEST] session.count = " + session.count);
            
            // Build HTTP 409 Conflict Response directly to client without calling SAP!
            ProductSearchResponse dupResUdr = udrCreate(ProductSearchResponse);
            dupResUdr.transactionId = prodReq.transactionId;
            dupResUdr.status        = "FAILED";
            dupResUdr.errorCode     = "ERR_DUPLICATE_REQUEST";
            dupResUdr.message       = "Duplicate Request Intercepted by MediationZone Aggregation Agent (session.count >= 2)";
            dupResUdr.totalCount    = 0;

            cycleUDR.response = createProductPortalResponse(dupResUdr, 409); // HTTP 409 Conflict
            udrRoute(cycleUDR, "response");
            return;
        } 
        // FIRST VALID REQUEST (session.count == 1)
        else {
            debug("SUCCESS: [AGGREGATION VALID FIRST REQUEST] Forwarding to SAP SOM RFC.");
            ZSOM_PRODUCT_GET_DETAIL_API_UDR rfcUdr = createProductSearchRFCRequest(prodReq);
            rfcUdr.context = cycleUDR;
            udrRoute(rfcUdr, "toSOMRFC");
            return;
        }
    }

    // ------------------------------------------------------------------------
    // CASE C: SAP SOM RFC RESPONSE (Returns asynchronously from SAP)
    // ------------------------------------------------------------------------
    else if (instanceOf(input, ZSOM_PRODUCT_GET_DETAIL_API_UDR)) {
        ZSOM_PRODUCT_GET_DETAIL_API_UDR rfcResUDR = (ZSOM_PRODUCT_GET_DETAIL_API_UDR) input;
        debug("INFO: Received RFC Response from SAP SOM: " + rfcResUDR.exportParams);
        
        Cycle cycleUDR = (Cycle) rfcResUDR.context;
        ProductSearchRequest prSearchUdr = udrCreate(ProductSearchRequest);
        decodeJSONRequest(baToStr(cycleUDR.request.body), prSearchUdr);

        boolean isRFCError = false;
        string errMessage;

        if (rfcResUDR.exportParams != null && mapContainsKey(rfcResUDR.exportParams, "TYPE") && rfcResUDR.exportParams["TYPE"] == "E") {
            errMessage = "SAP_SOM_RFC_ERROR";
            isRFCError = true;
        }

        ProductSearchResponse resUdr;
        if (isRFCError) {
            resUdr = createProductRfcErrorResponse(prSearchUdr, errMessage, 500, "RFC", HTTP_RESPONSE_CODE_NOT_ACCEPTABLE);
        } else {
            resUdr = createProductSearchResponse(prSearchUdr, EMPTY_STRING, rfcResUDR.exportParams["ET_RESULT"], HTTP_SUCCESS_RESPONSE_CODE, 10);
        }

        cycleUDR.response = createProductPortalResponse(resUdr, HTTP_SUCCESS_RESPONSE_CODE);
        udrRoute(cycleUDR, "response");
        return;
    }
}


// ============================================================================
// 3. SESSION TIMEOUT CLEANUP BLOCK
// ============================================================================
timeout {
    debug("INFO: [timeout] Aggregation Session Expired for key: " + session.dupValue + ". Purging session.");
    sessionRemove(session);
}
