# MediationZone 9 (InfoZone) — Log Diagnostics & Troubleshooting Guide

This guide provides a comprehensive reference on the logging architecture of **MediationZone (InfoZone)** across production, QA, and development environments. It explains when, where, and why to inspect **`mz/log`**, **EC Logs**, **Pico Logs**, and **`tmp/debug`** when resolving issues in telecommunications mediation workflows.

---

## 📍 File & Directory Path Reference

In EarthLink / InfoZone MediationZone servers, the platform is installed under `/mz8` or `/mz9` (`$MZ_HOME`). Below are the exact file system paths for each log type:

| Log Component | Server File System Path (EarthLink / MZ Standard) | Key Configuration Property |
| :--- | :--- | :--- |
| **System Controller (SC) Logs** | `/mz8/log/sc.log`<br>`/mz9/log/sc.log`<br>`$MZ_HOME/log/sc/sc.log` | `mz.syslog.debuglogfile.filedir`<br>(in `platform.xml`) |
| **Pico Framework Logs** | `/mz8/log/pico_*.log`<br>`/mz8/instances/<pico_name>/log/`<br>`$MZ_HOME/log/pico/` | `pico.stdout` & `pico.stderr`<br>(in `$MZ_HOME/etc/log4j2.xml`) |
| **Execution Context (EC) Logs** | `/mz8/log/ec_*.log`<br>`/mz8/instances/<ec_name>/log/`<br>`$MZ_HOME/log/ec/` | EC JVM Process / APL Runtime |
| **Debug & Trace Directory** | `/mz8/tmp/debug/`<br>`/tmp/debug/`<br>`$MZ_HOME/tmp/debug/` | `mz.wf.debugdir`<br>(defaults to `pico.tmpdir/debug`) |
| **Project & Custom Logs** | `/opt/EarthLink/logs/`<br>`/home/mzadmin/` | Custom Script Sinks / Shell Monitors |

---

## 🎯 Quick Reference: "When to Check What"

| Diagnostic Objective | Log Location / Target Path | What it Contains | Typical Trigger / Error Symptoms |
| :--- | :--- | :--- | :--- |
| **System & Deployment Status** | `/mz8/log/sc.log`<br>`/mz9/log/sc.log` | Node status, topology heartbeats, WFL deployment failures, license state, system alarms. | Workflow fails to start/deploy; System Controller unreachable; Disk space/memory alarms; topology sync drop. |
| **Pico Engine & Protocol Transport** | `/mz8/log/pico_*.log`<br>`$MZ_HOME/log/pico/` | HTTP/REST port binding (e.g. port 8010), socket timeouts, TLS/SSL handshakes, DB connection pools (JDBC). | REST endpoint down; HTTP 500 at server boundary; DB connection pool (JDBC) exhausted; Diameter/GTP socket timeout. |
| **APL Execution & Workflow Logic** | `/mz8/log/ec_*.log`<br>`$MZ_HOME/log/ec/` | APL runtime errors (`uerror()`, `uwarn()`), unhandled exceptions (NullPointer, IndexOutOfBounds), thread pool status. | Workflow aborted; unexpected routing in APL script; UDR field missing runtime exception; aggregation session drops. |
| **Data Payload & Transaction Debugging** | `/mz8/tmp/debug/`<br>`/tmp/debug/` | Raw payload dumps (JSON/XML/UDR), `udebug()` log traces, intermediate aggregation key states, UFL parse failure traces. | Specific subscriber transaction fails; incorrect duplicate detection (`dupValue`); formatting error during UFL decode. |

---

## 🧭 System Architecture & Directory Hierarchy Mapping

```
                         MediationZone Server (/mz8 or /mz9 / $MZ_HOME)
                                               │
         ┌─────────────────────────────────────┼─────────────────────────────────────┐
         ▼                                     ▼                                     ▼
  /mz8/log/sc.log                       /mz8/log/pico_*.log                   /mz8/log/ec_*.log
 (System Controller)                    (Pico Framework)                     (Execution Contexts)
  • Topology & Deployments             • pico.stdout / pico.stderr            • APL Execution & WFL Logic
  • platform.xml settings              • Managed via log4j2.xml               • uerror() / JVM Exceptions
                                                                                     │
                                                                                     ▼
                                                                             /mz8/tmp/debug/
                                                                             (mz.wf.debugdir)
                                                                              • udebug() Outputs
                                                                              • Raw UDR & Payload Dumps
                                                                              • UFL Parsing Traces
```

---

## 1. System & Platform Logs (`/mz8/log/sc.log` & `platform.xml`)

### Paths & Configuration Keys
* **Primary Path**: `/mz8/log/sc.log` or `/mz9/log/sc.log` (`$MZ_HOME/log/sc/sc.log`).
* **System Log Property**: Configured in `platform.xml` under `mz.syslog.debuglogfile.filedir` (managed via `mzsh topo open platform`).

### What it contains
* **Workflow Deployment Status**: Activation errors for APL scripts (`WFL_PlanRenew_Aggregation.apl`), Ultra Format profiles (`UFL_PlanRenew.ufl`), and Aggregation profiles.
* **Topology & Clustering**: Heartbeats between System Controller (SC) and Execution Contexts (EC).
* **Desktop & CLI Operations**: Logins from Web Desktop UI, `mzcmd` / `mzsh` command execution traces.
* **Platform Alarms**: Storage quota exceedance, queue threshold alerts, license key verification.

---

## 2. Pico Engine Logs (`/mz8/log/pico_*.log` & `log4j2.xml`)

### Paths & Configuration Keys
* **Primary Paths**: `/mz8/log/pico_*.log` or `/mz8/instances/<pico_name>/log/` (`$MZ_HOME/log/pico/`).
* **Standard Streams**: `pico.stdout` and `pico.stderr` properties.
* **Log Logging Engine**: `$MZ_HOME/etc/log4j2.xml` defines persistent rotation, file naming, and log levels for Pico services.

### What it contains
* **Protocol Listeners**: Inbound/outbound HTTP/REST bindings (e.g. REST server port 8010).
* **Network & TLS Handshakes**: TLS/SSL certificate validation, HTTP header parsing errors before workflow execution.
* **Resource Connection Pools**: Database JDBC pool status (e.g. Oracle / HANA connection pool), idle connection drops, host disconnects.
* **Pico Daemon Lifecycle**: Container start/stop events and node registration with System Controller.

---

## 3. Execution Context Logs (`/mz8/log/ec_*.log`)

### Paths & Configuration Keys
* **Primary Paths**: `/mz8/log/ec_*.log` or `/mz8/instances/<ec_name>/log/` (`$MZ_HOME/log/ec/`).
* **JVM Engine**: The Execution Context (EC) is the Java virtual machine process running workflow instances.

### What it contains
* **APL Log Messages**: Output emitted by `uerror()`, `uwarn()`, and `uinfo()`.
* **APL Exceptions**: `NullPointer` exceptions, array out-of-bounds, invalid type casting.
* **Workflow Lifecycle**: Instance start, pause, resume, cancel, or crash events (`RUNNING`, `ABORTED`, `UNEXPECTED_STOP`).
* **Real-time Aggregation & Session State**: Buffer overflow notifications, aggregation session creation failures, memory limit warnings for aggregation profiles (`PRF_AGG_PlanRenew`).
* **JVM Health**: OutOfMemory (OOM) stack traces, worker thread lockups.

---

## 4. Debug & Trace Directory (`/mz8/tmp/debug/` or `/tmp/debug/`)

### Paths & Configuration Keys
* **Primary Path**: `/mz8/tmp/debug/` or `/tmp/debug/` (`$MZ_HOME/tmp/debug/`).
* **Primary Property**: `mz.wf.debugdir` (explicit path override).
* **Default Fallback**: Derived from `pico.tmpdir` (`$MZ_HOME/tmp/debug`).
* **File Naming Pattern**: `<workflow_template>.<workflow_name>` (e.g., `Default.WFL_PlanRenew_Aggregation.1`).

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
                                                    (/mz8/log/pico_rest.log)
                                         │ [Pass]
                                         ▼
                     ┌──────────────────────────────────────┐
                     │   UFL Parser (UFL_PlanRenew.ufl)     │
                     └──────────────────────────────────────┘
                                         │
                        [Fails?] ────────┴────────> CHECK: /mz8/tmp/debug/
                                                    (UFL decode trace file)
                                         │ [Pass]
                                         ▼
                     ┌──────────────────────────────────────┐
                     │   Execution Context & APL Script     │
                     │   (WFL_PlanRenew_Aggregation.apl)   │
                     └──────────────────────────────────────┘
                                         │
                        [Fails?] ────────┴────────> CHECK: EC Logs
                                                    (/mz8/log/ec_*.log for uerror)
                                         │ [Pass]
                                         ▼
                     ┌──────────────────────────────────────┐
                     │  Real-Time Aggregation & Dup Check  │
                     │  (dupValue = SUB_ID + "_" + TRANS_ID)│
                     └──────────────────────────────────────┘
                                         │
                        [Fails?] ────────┴────────> CHECK: /mz8/tmp/debug/ & EC Logs
                                                    (udebug traces & session counter)
```

---

## 🛠️ Step-by-Step Troubleshooting Matrix

| Issue Symptom | Primary Server Path | Configuration Key to Check | Action / Solution |
| :--- | :--- | :--- | :--- |
| **HTTP Connection Refused** | `/mz8/log/pico_rest.log` | Port binding / REST Pico status | Verify port 8010 listener, REST Pico container status. |
| **Client Receives HTTP 500** | `/mz8/log/ec_*.log` | Execution Context JVM | Check EC log for `NullPointerException` or `uerror()` call in APL. |
| **JSON Payload Unparsed** | `/mz8/tmp/debug/` | `mz.wf.debugdir` | Inspect raw decode trace against `UFL_PlanRenew.ufl` JSON keys. |
| **Deduplication Anomaly** | `/mz8/tmp/debug/` & EC Logs | `pico.tmpdir` / Aggregation Config | Verify `dupValue` string key and aggregation timeout window in `PRF_AGG_PlanRenew.json`. |

---

## 📌 Log Logging Functions in APL

| APL Function | Server Log Target Path | Official Log Setting |
| :--- | :--- | :--- |
| `udebug("Key: " + dupVal);` | `/mz8/tmp/debug/` | Enabled via workflow node debug flag (`mz.wf.debugdir`). |
| `uinfo("Processed TXN: " + txId);` | `/mz8/log/ec_*.log` | Standard Execution Context logging stream. |
| `uwarn("Retry count high: " + sub);` | `/mz8/log/ec_*.log` | Execution Context warning stream. |
| `uerror("SAP Connection Failed!");` | `/mz8/log/ec_*.log` & Alarms | High-priority Execution Context error stream & System Alarms. |
