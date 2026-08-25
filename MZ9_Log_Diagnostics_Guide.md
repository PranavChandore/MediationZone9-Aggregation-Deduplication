# MediationZone 9 (InfoZone) — Log Diagnostics & Troubleshooting Guide

This guide provides a comprehensive reference on the logging architecture of **MediationZone 9 (InfoZone)**. It explains when, where, and why to inspect **`mz/logs`**, **EC Logs**, **Pico Logs**, and **`tmp/debug`** when resolving issues in telecommunications mediation workflows.

---

## 🎯 Quick Reference: "When to Check What"

| Diagnostic Objective | Log Location / Target | Key Info Contained | Typical Trigger / Error Symptoms |
| :--- | :--- | :--- | :--- |
| **System & Deployment Status** | `mz/logs/sc.log`<br>`mz/logs/system_event.log` | Node status, cluster sync, WFL deployment failures, license issues, system alarms. | Workflow fails to start/deploy; System Controller unreachable; Disk space/memory alarms. |
| **Protocol & Network Transport** | `mz/logs/pico_*.log`<br>(or `$MZ_HOME/logs/pico/`) | HTTP/REST port binding, socket timeouts, TLS/SSL handshakes, DB connection pools (JDBC), SFTP/FTP collectors. | REST endpoint down; HTTP 500 at server boundary; DB connection pool exhausted; diameter disconnects. |
| **APL Execution & Workflow Logic** | `mz/logs/ec_*.log`<br>(or Execution Context log) | APL runtime errors (`uerror()`, `uwarn()`), unhandled exceptions (NullPointer, IndexOutOfBounds), thread pool health, workflow state transitions. | Workflow aborted; unexpected routing in APL script; UDR field missing runtime exception; aggregation session drops. |
| **Data Payload & Transaction Debugging** | `tmp/debug/`<br>(or `$MZ_HOME/tmp/debug/`) | Raw payload dumps (JSON/XML/UDR), `udebug()` log traces, intermediate aggregation key states, UFL parse failure traces. | Specific subscriber transaction fails; incorrect duplicate detection (`dupValue`); formatting error during UFL decode. |

---

## 🧭 System Log Architecture Breakdown

```
                             MediationZone 9 (InfoZone) Node
                                           │
         ┌─────────────────────────────────┼─────────────────────────────────┐
         ▼                                 ▼                                 ▼
   mz/logs/sc.log                 mz/logs/pico_*.log                 mz/logs/ec_*.log
 (System Controller)                (Pico Engines)                  (Execution Contexts)
  • Deployments & Cluster          • Protocol Servers (REST/DB)       • APL Execution & WFL Logic
  • System Alarms & Auth           • Network Sockets & Adapters       • uerror() / JVM Exceptions
                                                                             │
                                                                             ▼
                                                                     tmp/debug/
                                                                   (Debug Traces)
                                                                    • udebug() Outputs
                                                                    • Raw UDR & Payload Dumps
                                                                    • UFL Parsing Traces
```

---

## 1. System Logs (`mz/logs/` & `sc.log`)

### What it is
`mz/logs` is the root log directory of the MediationZone installation (`$MZ_HOME/logs/`). The central log file is `sc.log` (System Controller log).

### What it contains
* **Workflow Deployment Status**: Errors when activating or deploying APL workflows, format profiles (UFL), or aggregation profiles.
* **Cluster & Node Topology**: Heartbeats between System Controller (SC) and Execution Contexts (EC).
* **Security & Access Control**: Desktop GUI logins, CLI tool (`mzcmd`) executions, user permissions.
* **System Alarms**: Storage quota exceedance, queue backup warnings, memory alarms.

### When to inspect
1. You edited a workflow/profile in the Desktop GUI and **deployment failed**.
2. An Execution Context or Pico engine is shown as **Offline / Red** in the MZ Management Console.
3. License key expiration or cluster node synchronization issues occur.

---

## 2. Pico Logs (`pico logs` / `mz/logs/pico_*.log`)

### What it is
A **Pico** in MZ9 is a lightweight container or service responsible for protocol adapters, external interfaces, and platform helper daemons (e.g., REST Server Pico, Diameter Pico, Oracle DB Pico, File Collector Pico).

### What it contains
* **Inbound/Outbound Network Connections**: Port bindings (e.g., REST Server listener on `0.0.0.0:8010`).
* **Transport Protocol Handshakes**: TLS/SSL certificate validation failures, HTTP header parsing at network layer.
* **External Resource Connection Pools**: Database JDBC pool status, idle timeout disconnects, target host unreachable.
* **Low-Level Protocol Frame Errors**: Malformed HTTP requests before reaching UFL/APL layer.

### When to inspect
1. **API / Webhook is Unresponsive**: Clients receive `Connection Refused` or timeout when POSTing to `/pranav/v1/plan/renew`.
2. **Database Sinks/Collectors Failing**: DB agent cannot acquire a connection from the pool.
3. **HTTP Server Level Errors**: HTTP `400 Bad Request`, `404 Not Found`, or `500 Internal Server Error` logged before workflow execution starts.

---

## 3. Execution Context Logs (`ec logs` / `mz/logs/ec_*.log`)

### What it is
An **Execution Context (EC)** is the Java virtual machine (JVM) process that executes active workflows and APL scripts (`WFL_PlanRenew_Aggregation.apl`).

### What it contains
* **APL Log Messages**: Output generated by APL functions `uerror()`, `uwarn()`, and `uinfo()`.
* **APL Runtime Exceptions**:
  * `NullPointer` exceptions (e.g., trying to access `planReq.TRANS_ID` when `planReq` is null).
  * Array out-of-bounds or invalid type cast errors.
* **Workflow Lifecycle Events**: Workflow instance start, pause, resume, cancel, or crash events.
* **Real-time Aggregation & Session State**: Buffer overflow notifications, aggregation session creation failures, memory limit warnings for aggregation profiles (`PRF_AGG_PlanRenew`).
* **JVM Heap & Thread Dumps**: OutOfMemory (OOM) stack traces, worker thread lockups.

### When to inspect
1. A transaction enters the workflow but **never comes out** (workflow thread trapped or crashed).
2. You see `uerror(...)` calls triggering in your APL script logic.
3. Requests return `HTTP 500` generated by an uncaught exception inside your APL code (`sessionInit`, `consume`, `timeout`).

---

## 4. Debug & Trace Directory (`tmp/debug/` or `$MZ_HOME/tmp/debug/`)

### What it is
The `tmp/debug` folder is the specialized diagnostic area used during active development, testing, and root-cause analysis of transaction payload failures.

### What it contains
* **APL `udebug()` Outputs**: Granular log statements emitted when debug mode is enabled on a workflow or agent.
* **UFL Decode / Encode Traces**: Raw hex/ASCII payloads that failed parsing in Ultra Format Language (`UFL_PlanRenew.ufl`).
* **Raw Payload Dumps**: Sinks or debug agents configured to write incoming JSON/XML payloads for inspection.
* **Aggregation State Snapshots**: Intermediate key-value pairs (e.g., `dupValue = "SUB_44012_TXN_99001"`) and session counter snapshots.

### When to inspect
1. **Data Parsing Issues**: Client sent a JSON payload, but UFL failed to populate fields in `PlanRenewReq`.
2. **Business Logic Anomalies**: Duplicate requests are being allowed through (or valid requests are being blocked as false duplicates).
3. **Field Value Verification**: You need to inspect exact parameter values (e.g. `TRANS_ID`, `SUB_ID`, `AMT`) at step-by-step points in the workflow.

---

## ⚙️ EarthLink Plan Renew Workflow — Practical Diagnostic Flowchart

For the EarthLink Plan Renewal Workflow (`WFL_PlanRenew_Aggregation.apl`):

```
                                  INCOMING REQUEST
                         POST /pranav/v1/plan/renew
                                         │
                                         ▼
                     ┌──────────────────────────────────────┐
                     │ REST Server Pico (Port 8010 Binding) │
                     └──────────────────────────────────────┘
                                         │
                        [Fails?] ────────┴────────> CHECK: Pico Logs
                                                    (mz/logs/pico_rest.log)
                                         │ [Pass]
                                         ▼
                     ┌──────────────────────────────────────┐
                     │   UFL Parser (UFL_PlanRenew.ufl)     │
                     └──────────────────────────────────────┘
                                         │
                        [Fails?] ────────┴────────> CHECK: tmp/debug/
                                                    (Raw payload & UFL decode trace)
                                         │ [Pass]
                                         ▼
                     ┌──────────────────────────────────────┐
                     │   Execution Context & APL Script     │
                     │   (WFL_PlanRenew_Aggregation.apl)   │
                     └──────────────────────────────────────┘
                                         │
                        [Fails?] ────────┴────────> CHECK: EC Logs
                                                    (mz/logs/ec_*.log for uerror)
                                         │ [Pass]
                                         ▼
                     ┌──────────────────────────────────────┐
                     │  Real-Time Aggregation & Dup Check  │
                     │  (dupValue = SUB_ID + "_" + TRANS_ID)│
                     └──────────────────────────────────────┘
                                         │
                        [Fails?] ────────┴────────> CHECK: tmp/debug/ & EC Logs
                                                    (udebug traces & session counter)
```

---

## 🛠️ Step-by-Step Troubleshooting Matrix

When a production or QA issue is reported, follow this step-by-step checklist:

### Step 1: Client cannot connect / HTTP Connection Refused
* **Primary Check**: `Pico Logs` (`mz/logs/pico_rest.log`)
* **Look For**: `Address already in use`, `SSL Handshake Failed`, `Connection reset by peer`.
* **Action**: Verify REST port 8010 is open, REST Server agent is running, and security certificates are valid.

### Step 2: Request received but client gets HTTP 500 (Internal Error)
* **Primary Check**: `EC Logs` (`mz/logs/ec_plan_renew.log`)
* **Look For**: Java stack trace, `NullPointerException`, `uerror("Invalid transaction format")`.
* **Action**: Fix unhandled null checks or invalid variable access in `WFL_PlanRenew_Aggregation.apl`.

### Step 3: Request payload rejected or unparsed
* **Primary Check**: `tmp/debug/` (and UFL trace)
* **Look For**: UFL decoding errors, mismatched JSON keys (`TRANS_ID` vs `trans_id`).
* **Action**: Inspect raw payload file in `tmp/debug` and verify against `UFL_PlanRenew.ufl` definitions.

### Step 4: Deduplication fail (Duplicate passed to SAP or valid blocked with 409)
* **Primary Check**: `tmp/debug/` (`udebug()` statements) & `EC Logs`
* **Look For**: Logged `dupValue` string, session `count`, timeout expiry log in `sessionInit` / `consume`.
* **Action**: Verify `dupValue` key creation (`SUB_ID + "_" + TRANS_ID`) and session timeout window in `PRF_AGG_PlanRenew.json`.

---

## 📌 Log Logging Functions in APL (Code Examples)

| APL Function | Output Destination | Usage Scenario |
| :--- | :--- | :--- |
| `udebug("Key: " + dupVal);` | `tmp/debug/` (when debug enabled) | Detailed transaction trace during dev/testing. |
| `uinfo("Processed TXN: " + txId);` | `mz/logs/ec_*.log` | Operational metrics & successful milestones. |
| `uwarn("Retry count high for: " + sub);` | `mz/logs/ec_*.log` | Non-fatal anomaly requiring operational review. |
| `uerror("SAP Connection Failed!");` | `mz/logs/ec_*.log` & Alarms | Fatal error requiring immediate intervention. |
