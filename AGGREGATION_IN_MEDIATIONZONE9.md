# Aggregation in MediationZone 9 (InfoZone)

## 1. What is Aggregation in MediationZone 9?

In **DigitalRoute MediationZone 9 (InfoZone)**, **Aggregation** is a fundamental architectural pattern used to collect, hold, summarize, and deduplicate incoming Usage Data Records (UDRs), payment requests, CDRs (Call Detail Records), or financial events before forwarding them to downstream enterprise applications like **SAP (SAP CC/CI, SAP HANA)**, Billing Systems, or CRM databases.

---

## 2. Why Use Aggregation to Avoid Duplicate Requests?

In telecommunications and enterprise event processing:
* **Duplicate Events Happen Frequently**: Network retries, duplicate HTTP webhooks, client resubmissions, and network failures often cause identical transaction requests to be delivered multiple times.
* **Overwhelming Downstream Systems**: If 10,000 micro-transactions or retry requests are passed directly to SAP or billing, it creates database locks, duplicate postings, extra charges, and system degradation.
* **Financial Integrity**: Executing duplicate payment requests results in double billing, incorrect customer balances, and expensive reconciliation cycles.

### How Aggregation Resolves This:
1. **Key-Based In-Memory Buffer**: Aggregation holds incoming events in memory (`map<string, UDR>` in APL) during the workflow execution lifecycle.
2. **Duplicate Rejection / Filter**: For every incoming UDR, the workflow generates a unique **Aggregation Key** (e.g., `Transaction_ID` or `Invoice_No + Account_ID`). If the key has already been seen in the current batch or sliding window, it is flagged as a **Duplicate** and blocked from triggering downstream APIs.
3. **Consolidation & Batch Flushing (`drain()`)**: Multiple valid usage/payment events for the same subscriber are consolidated into a **single summary request** with total amount and count, dispatched at batch completion or timeout.

---

## 3. MediationZone 9 Workflow Lifecycle with Aggregation

A standard MediationZone aggregation workflow consists of 3 distinct phases in APL (Agent Processing Language):

```
       [ Input Stream / Collection Agent ]
                       │ (Raw UDRs)
                       ▼
       ┌───────────────────────────────┐
       │   APL Aggregation Agent       │
       │                               │
       │  1. initialize()              │  <-- Prepare memory maps
       │                               │
       │  2. consume(UDR)              │  <-- Process incoming records
       │     ├── Extract Key           │
       │     ├── Check Duplicate Map   │
       │     ├── Aggregate / Buffer    │
       │     └── Quarantine Duplicate  │
       │                               │
       │  3. drain()                   │  <-- Batch end: emit summary
       └───────────────┬───────────────┘
                       │
       ┌───────────────┴───────────────┐
       ▼                               ▼
[ Valid Aggregated Request ]   [ Duplicate / ECS Audit ]
(Sent to SAP / Billing)         (Quarantined for Review)
```

### APL Methods Explained:
* **`initialize()`**: Executed once when the workflow context starts. Initializes state maps and counter variables.
* **`consume(UDR u)`**: Executed once per incoming record. Checks whether `u` is a duplicate request using an aggregation key map. If valid, accumulates metrics (sums amount, increments transaction count). If duplicate, routes to error/ECS queue.
* **`drain()`**: Executed when the input file/stream ends or buffer timeout expires. Iterates over accumulated map entries and emits consolidated UDRs downstream.

---

## 4. Key Aggregation Strategies in MZ9

| Strategy | Description | Avoids Duplicate Requests By |
| :--- | :--- | :--- |
| **Deduplication Aggregation** | Collects events matching `Transaction_ID` or `External_Reference`. | Dropping/quarantining subsequent requests with an already-processed key. |
| **Time-Window Aggregation** | Buffers events over a fixed time frame (e.g. 5 minutes or 1 hour). | Consolidating multiple retries within the time window into a single downstream request. |
| **Session Aggregation** | Collects events between `START` and `END` session signals. | Emitting a single aggregated charge at session close instead of intermediate billing requests. |
| **Batch Consolidation** | Groups UDRs per Account/Invoice for an entire input file. | Reducing 1,000 raw billing events into 1 summary invoice update in SAP HANA. |
