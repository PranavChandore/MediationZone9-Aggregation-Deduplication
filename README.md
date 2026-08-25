# AggregationLearn — MediationZone 9 (InfoZone) End-to-End Aggregation & Request Processing

This project contains the complete documentation, Ultra formats, Aggregation profiles, production APL scripts, and runnable simulations of **MediationZone 9 (InfoZone)** Aggregation, Deduplication, REST Server Agents, and SAP HANA posting.

---

## 📁 Repository Files

```
AggregationLearn/
│
├── FULL_CODE_REQUEST_PROCESSING_GUIDE.md     # Complete step-by-step code request processing guide
├── REAL_MZ_PRODUCTION_AGGREGATION_ANALYSIS.md # Production QAS MZ Aggregation Profile & APL analysis
├── REST_AGENT_WITH_AGGREGATION.md            # REST Server Agent + OpenAPI + Aggregation guide
├── AGGREGATION_IN_MEDIATIONZONE9.md          # Architectural guide on MZ9 Aggregation & Deduplication
│
├── UFL_PlanRenewal_Data.ufl                  # Ultra Format specification file
├── PRF_AGG_PlanRenewal.json                  # Aggregation Profile configuration export JSON
├── PRF_PlanRenewal_OpenAPI.json              # OpenAPI 3.0 REST endpoint specification
│
├── WFL_PlanRenewal_Aggregation.apl           # Production APL workflow script
├── WFL_Payment_Deduplication_Aggregation.apl # Standard MZ9 APL workflow script example
├── run_e2e_plan_renewal_pipeline.py          # Complete E2E HTTP REST + Aggregation + SAP DB application
├── production_mz_aggregation_demo.py         # Simulation of exact production WalletAPI session.count logic
├── rest_agent_aggregation_server.py          # HTTP REST Server Agent + Aggregation Engine demo
└── aggregation_demo.py                       # Batch/stream UDR aggregation & ECS error queue demo
```

---

## ⚡ How to Run the End-to-End Pipeline

Run the end-to-end EarthLink Plan Renewal & Payment Aggregation Pipeline directly in your terminal:

```bash
python run_e2e_plan_renewal_pipeline.py
```
