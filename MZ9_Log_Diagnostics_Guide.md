# MediationZone 9 (InfoZone) — Log Diagnostics & Troubleshooting Guide

This guide provides a comprehensive reference on the logging architecture of **DigitalRoute MediationZone 9 (InfoZone)**. It explains when, where, and why to inspect **`mz/logs`**, **EC Logs**, **Pico Logs**, and **`tmp/debug`** when resolving issues in telecommunications mediation workflows, based on official DigitalRoute MZ9 system configuration documentation.

---

## 🎯 Quick Reference: "When to Check What"

| Diagnostic Objective | Log Location / Property | System Configuration Key | Typical Trigger / Error Symptoms |
| :--- | :--- | :--- | :--- |
| **System & Deployment Status** | `mz/logs/sc.log`<br>`mz/logs/system_event.log` | `mz.syslog.debuglogfile.filedir`<br>(in `platform.xml`) | Workflow fails to start/deploy; System Controller unreachable; Disk space/memory alarms; topology connection drop. |
| **Pico Engine & Protocol Transport** | `mz/logs/pico_*.log`<br>`pico.stdout` / `pico.stderr` | `$MZ_HOME/etc/log4j2.xml` | REST endpoint down; HTTP 500 at server boundary; DB connection pool (JDBC) exhausted; Diameter/GTP socket timeout. |
| **APL Execution & Workflow Logic** | `mz/logs/ec_*.log`<br>(Execution Context log) | Execution Context JVM Process | Workflow aborted; unexpected routing in APL script; UDR field missing runtime exception; aggregation session drops. |
| **Data Payload & Transaction Debugging** | `tmp/debug/`<br>`$MZ_HOME/tmp/debug/` | `mz.wf.debugdir`<br>(defaults to `pico.tmpdir/debug`) | Specific subscriber transaction fails; incorrect duplicate detection (`dupValue`); formatting error during UFL decode. |

---

## 🧭 Official DigitalRoute MZ9 Architecture & Log Mapping

```
                               MediationZone 9 (InfoZone) Node
                                              │
         ┌────────────────────────────────────┼────────────────────────────────────┐
         ▼                                    ▼                                    ▼
   mz/logs/sc.log                    mz/logs/pico_*.log                    mz/logs/ec_*.log
 (System Controller)                   (Pico Framework)                   (Execution Contexts)
  • Topology & Deployments            • pico.stdout / pico.stderr          • APL Execution & WFL Logic
  • platform.xml settings             • Managed via log4j2.xml             • uerror() / JVM Exceptions
                                                                                   │
                                                                                   ▼
                                                                           tmp/debug/
                                                                      (mz.wf.debugdir)
                                                                       • udebug() Outputs
                                                                       • Raw UDR & Payload Dumps
                                                                       • UFL Parsing Traces
```

---

## 1. System & Platform Logs (`sc.log` & `platform.xml`)

### System Configuration Keys
* **System Log Property**: Configured in `platform.xml` under `mz.syslog.debuglogfile.filedir` (managed via command `mzsh topo open platform`).
* **Root Log Directory**: `$MZ_HOME/logs/` (contains `sc.log` and `system_event.log`).

### What it contains
* **Workflow Deployment Status**: Activation errors for APL scripts, Ultra Format profiles (UFL), and Aggregation profiles.
* **Topology & Clustering**: Heartbeats between System Controller (SC) and Execution Contexts (EC).
* **Desktop & CLI Operations**: Logins from Web Desktop UI, `mzcmd` command execution traces.
* **Platform Alarms**: Storage quota exceedance, queue threshold alerts, license key verification.

---

## 2. Pico Engine Logs (`pico logs` & `log4j2.xml`)

### System Configuration Keys
* **Standard Streams**: `pico.stdout` and `pico.stderr` properties.
* **Log Logging Engine**: `$MZ_HOME/etc/log4j2.xml` defines persistent rotation, file naming, and log levels for Pico services.

### What it contains
* **Protocol Listeners**: Inbound/outbound HTTP/REST bindings (e.g. REST server port 8010).
* **Network & TLS Handshakes**: TLS/SSL certificate validation, HTTP header parsing errors before workflow execution.
* **Resource Connection Pools**: Database JDBC pool status, idle connection drops, host disconnects.
* **Pico Daemon Lifecycle**: Container start/stop events and node registration with System Controller.

---

## 3. Execution Context Logs (`ec logs` / `mz/logs/ec_*.log`)

### What it is
An **Execution Context (EC)** is the Java virtual machine (JVM) process executing active workflows (`WFL_PlanRenew_Aggregation.apl`).

### What it contains
* **APL Log Messages**: Output emitted by `uerror()`, `uwarn()`, and `uinfo()`.
* **APL Exceptions**: `NullPointer` exceptions, array out-of-bounds, invalid type casting.
* **Workflow Lifecycle**: Instance start, pause, resume, cancel, or crash events.
* **Real-time Aggregation & Session State**: Buffer overflow notifications, aggregation session creation failures, memory limit warnings for aggregation profiles (`PRF_AGG_PlanRenew`).
* **JVM Health**: OutOfMemory (OOM) stack traces, worker thread lockups.

---

## 4. Debug & Trace Directory (`mz.wf.debugdir` / `tmp/debug/`)

### System Configuration Keys
* **Primary Debug Property**: `mz.wf.debugdir` (explicit path override).
* **Default Directory**: `$MZ_HOME/tmp/debug` (fallback path derived from `pico.tmpdir`).
* **Naming Pattern**: Debug output files are automatically formatted as `<workflow_template>.<workflow_name>` (e.g., `Default.WFL_PlanRenew_Aggregation.1`).

### What it contains
* **APL `udebug()` Outputs**: Granular log traces generated when debug logging is enabled on workflow nodes.
* **UFL Decode / Encode Traces**: Raw hex/ASCII payloads failing format parsing in `UFL_PlanRenew.ufl`.
* **Payload Dumps**: Raw JSON/XML payloads captured at debug node sinks.
* **Aggregation State Snapshots**: Session key-value pairs (e.g., `dupValue = "SUB_44012_TXN_99001"`) and session counters.

---

## ⚙️ EarthLink Plan Renew Workflow — Diagnostic Flowchart

For the EarthLink Plan Renewal Workflow ([WFL_PlanRenew_Aggregation.apl](file:///c:/Users/prana/OneDrive/Desktop/AggregationLearn/WFL_PlanRenew_Aggregation.apl)):

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
                                                    (pico.stderr / log4j2.xml)
                                         │ [Pass]
                                         ▼
                     ┌──────────────────────────────────────┐
                     │   UFL Parser (UFL_PlanRenew.ufl)     │
                     └──────────────────────────────────────┘
                                         │
                        [Fails?] ────────┴────────> CHECK: mz.wf.debugdir
                                                    (tmp/debug/ UFL decode trace)
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

| Issue Symptom | Primary Log / Directory | Configuration Key to Check | Action / Solution |
| :--- | :--- | :--- | :--- |
| **HTTP Connection Refused** | Pico Logs (`pico.stderr`) | Port binding / REST Pico status | Verify port 8010 listener, REST Pico container status. |
| **Client Receives HTTP 500** | EC Logs (`mz/logs/ec_*.log`) | Execution Context JVM | Check EC log for `NullPointerException` or `uerror()` call in APL. |
| **JSON Payload Unparsed** | `tmp/debug/` | `mz.wf.debugdir` | Inspect raw decode trace against `UFL_PlanRenew.ufl` JSON keys. |
| **Deduplication Anomaly** | `tmp/debug/` & EC Logs | `pico.tmpdir` / Aggregation Config | Verify `dupValue` string key and aggregation timeout window in `PRF_AGG_PlanRenew.json`. |

---

## 📌 Log Logging Functions in APL

| APL Function | Output Destination | Official Log Setting |
| :--- | :--- | :--- |
| `udebug("Key: " + dupVal);` | `$MZ_HOME/tmp/debug/` | Enabled via workflow node debug flag (`mz.wf.debugdir`). |
| `uinfo("Processed TXN: " + txId);` | `mz/logs/ec_*.log` | Standard Execution Context logging stream. |
| `uwarn("Retry count high: " + sub);` | `mz/logs/ec_*.log` | Execution Context warning stream. |
| `uerror("SAP Connection Failed!");` | `mz/logs/ec_*.log` & Alarms | High-priority Execution Context error stream & System Alarms. |
