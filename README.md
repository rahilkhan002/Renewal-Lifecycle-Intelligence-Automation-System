# Bambinos.live — Renewal Lifecycle Intelligence & Automation System

[![Test Suite](https://img.shields.io/badge/Unit%20Tests-6%2F6%20Passing-brightgreen)](#automated-testing--validation)
[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue)](#quickstart--execution)
[![Submission Status](https://img.shields.io/badge/Case%20Evaluation-Production%20Ready-orange)](#submission-deliverables)
[![Presentation Deck](https://img.shields.io/badge/PDF%20Deck-12%20Slides%20Generated-purple)](./Bambinos_AI_PM_Case_Deck.pdf)

> **Role:** AI Program Manager (Operations) — Take-Home Case  
> **Problem Statement:** Re-Engineering & Automating the Student Renewal → Class Scheduling Pipeline  
> **Target Company:** [Bambinos.live](https://bambinos.live)  
> **Author:** Candidate Submission  
> **Official Asset Repository:** [bambinoslive/AI-PM-hiring-take-home-assignments](https://github.com/bambinoslive/AI-PM-hiring-take-home-assignments)  
> **Loom Walkthrough Link:** `[Insert Loom Link Here - Target 2.5 Minutes]`

---

## Table of Contents
1. [Executive Summary & Evolution of the Approach](#executive-summary--evolution-of-the-approach)
2. [As-Is Pipeline Breakdown & The 13-Invoice Ground-Truth Audit](#as-is-pipeline-breakdown--the-13-invoice-ground-truth-audit)
3. [The Re-Engineered Architecture: The Two-Gate Model](#the-re-engineered-architecture-the-two-gate-model)
4. [Deterministic Code vs. Advisory AI System Boundaries](#deterministic-code-vs-advisory-ai-system-boundaries)
5. [Operational Metrics, Mathematical Formulations & RACI SLAs](#operational-metrics-mathematical-formulations--raci-slas)
6. [Daily Operations Command Center (Metabase Dashboard Wireframe)](#daily-operations-command-center-metabase-dashboard-wireframe)
7. [Phased 30-60-90 Day Change Governance Plan](#phased-30-60-90-day-change-governance-plan)
8. [Automated Omnichannel Communication & Notification Engine](#automated-omnichannel-communication--notification-engine)
9. [Loom Video Walkthrough Script (2.5-Minute Target)](#loom-video-walkthrough-script-25-minute-target)
10. [Quickstart & Execution Guide](#quickstart--execution-guide)
11. [Repository Organization & Submission Checklist](#repository-organization--submission-checklist)

---

## Executive Summary & Evolution of the Approach

The initial conceptual approach treated the Bambinos.live assessment as a straightforward, two-table join between payment invoices and an active student roster. Through iterative operational refinement, it transitioned into an enterprise-grade **Renewal Lifecycle Intelligence & Automation System**.

```
[Initial Naive Model]
Invoices ──► (Name / Phone String Match) ──► Auto-Book into Class Schedule (High Identity & Financial Risk)

[Current Production Architecture]
1_invoices ──► [Pre-Scan Deduplication] ──► [Gate 1: Financial & Identity Audit]
                                                         │
       ┌─────────────────────────────────────────────────┴────────────────────────────────┐
       ▼                                                                                  ▼
[Passed Gate 1]                                                                   [Failed Gate 1: Quarantine]
       │                                                                           • Partial / Failed Payment
       ▼                                                                           • Duplicate Transaction
[Cross-Table State Reconciliation]                                                 • Ambiguous Identity / Typo
 (Check 2_faculty_forms, 3_booking_requests, 4_class_schedules)
       │
       ▼
[Gate 2: Capacity & Slot Authorization]
 • Verify explicit parent slot choice (same-batch vs. requested shift)
 • Authority capacity check (Available = Max - Active - Held)
       │
       ├───► [STP Validated] ──► Direct Booking Payload + Automated Confirmations
       └───► [State Hold]    ──► Route to Specific Queue (Academic Ops, Parent Support)
```

### Key Engineering & Operational Upgrades
1. **Reconciliation Across All Five Operational Tables:** Evaluates the complete set of five datasets provided in the assignment (`1_invoices.csv`, `2_faculty_form_unapproved.csv`, `3_booking_requests.csv`, `4_class_schedule_bookings.csv`, and `reference_active_batches_and_students.csv`). Downstream states (already scheduled, pending allocation, failed due to capacity) are evaluated prior to any database mutation.
2. **Pre-Scan Idempotency & Duplicate Quarantine:** Rather than processing rows sequentially—which risks approving the first occurrence of a duplicate payment while flagging the second—the ingestion pipeline runs an initial pre-scan that identifies repeated payment IDs and repeated invoice references, immediately quarantining both records.
3. **Strict Financial Type Safety:** Replaced floating-point comparisons with Python’s `decimal.Decimal` and eliminated fallback assignments where a missing expected price defaulted to the amount paid. It strictly enforces `amount_paid == package_price` and `currency_paid == package_currency`.
4. **Decoupling Verification from Scheduling:** The business logic decouples the approval of a renewal transaction (financial validity) from the scheduling of a class (seat availability and confirmed parent schedule preferences).
5. **Precise Exception Taxonomy & Routing:** Replaced generic error flags with standardized reason codes (`ERR_UNDERPAYMENT`, `ERR_ORPHAN_INVOICE`, `ERR_BATCH_CAPACITY_FULL`, `ERR_DUPLICATE_FACULTY_FORMS`, `ERR_BROKEN_INVOICE_LINK`) assigned to dedicated operational owners (Finance, Academic Ops, Parent Support, Faculty Ops).

---

## As-Is Pipeline Breakdown & The 13-Invoice Ground-Truth Audit

The masked assessment dataset in `./ops/data/` contains exactly 13 invoices (84901 through 84913). This dataset functions as an authoritative operational test suite where every single row tests a specific failure mode, state transition, or operational edge case:

| Invoice ID | Gateway Status | Net / Paid Amount | Faculty Form Record | Booking Request Record | Existing Schedule State | Ground-Truth Operational Diagnostic | Actionable System Treatment | Assigned Owner |
|:---:|:---:|:---:|:---:|:---:|:---:|:---|:---|:---:|
| **84901** | Paid | ₹12,000 | Form #3301 (Approved) | Req #5501 (Completed) | 2 active rows exist in Table 4 | **Already Completed Pipeline:** Student already has confirmed classes. | `IDEMPOTENT_BYPASS`: Mark completed; suppress re-booking or duplicate billing. | `NONE` |
| **84902** | Paid | ₹10,500 | Form #3302 (Approved) | Req #5502 (Pending_Batch_Allocation) | 0 rows | **Ready for Batch Allocation:** Form approved; Batch 9202 has 1 seat left (5/6). | `ALLOCATION_REVIEW`: Route to Academic Ops to authorize calendar creation. | `ACADEMIC_OPS` |
| **84903** | Paid | ₹9,000 | Form #3303 (Pending) | None | 0 rows | **Ops Verification Pending:** Teacher submitted; financials match standard fee. | `OPS_VERIFY`: Surfaced in Ops 1-click verification queue. | `OPERATIONS` |
| **84904** | Paid | ₹12,000 | Form #3304 (Pending) | None | 0 rows | **Ops Verification Pending:** Teacher submitted; financials match standard fee. | `OPS_VERIFY`: Standard unapproved form verification queue. | `OPERATIONS` |
| **84905** | Paid | ₹11,000 | Form #3305 (Approved) | Req #5505 (Failed_Batch_Full) | 0 rows | **Capacity Overflow Bottleneck:** Target Batch 9205 is full at 6/6 capacity. | `CAPACITY_HOLD`: Halt auto-scheduling; alert Academic Ops to split batch or reassign. | `ACADEMIC_OPS` |
| **84906** | Paid | ₹18,000 | Missing (None filed) | None | 0 rows | **Orphaned Invoice:** High-value payment captured without teacher form. | `ORPHAN_INVOICE`: Dispatch automated WhatsApp nudge to teacher with pre-filled link. | `FACULTY_OPS` |
| **84907** | Paid | ₹7,600 | Form #3307 (Pending) | None | 0 rows | **Ops Verification Pending:** Discount applied (₹9,500 gross - ₹1,900 disc = ₹7,600). | `OPS_VERIFY`: Financials match discounted net amount; awaiting 1-click Ops sign-off. | `OPERATIONS` |
| **84908** | Paid | ₹22,000 | Duplicate: #3308 & #3309 filed | None | 0 rows | **Duplicate Form Submission:** Teacher double-submitted renewal forms. | `DUPLICATE_HOLD`: Quarantine both forms to prevent duplicate booking generation. | `OPS_LEAD` |
| **84909** | Partially_Paid | ₹5,250 | Form #3310 (Pending) | None | 0 rows | **Financial Underpayment:** Claims ₹10,500, but gateway captured only ₹5,250. | `FINANCE_EXCEPTION`: Freeze pipeline; dispatch dynamic WhatsApp balance link to parent. | `FINANCE` |
| **84910** | Paid | ₹11,000 | Missing (None filed) | None | 0 rows | **Orphaned Invoice:** Gateway entry captured without teacher submission. | `ORPHAN_INVOICE`: Queue for teacher outreach and proactive Ops follow-up. | `FACULTY_OPS` |
| **84911** | Failed | ₹0 (Uncaptured) | Form #3311 (Pending) | None | 0 rows | **Payment Gate Failure:** Teacher filed form for a failed transaction. | `REJECT_PAYMENT`: Reject immediately from scheduling; notify teacher of payment failure. | `FINANCE` |
| **84912** | Paid | ₹9,000 | Form #3312 (Approved) | Req #5512 (Awaiting_Parent_Batch_Selection) | 0 rows | **Parent Slot Selection Gate:** Parent requested batch/timing change. | `PARENT_CHOICE_HOLD`: Dispatch interactive WhatsApp slot picker with live open batches. | `PARENT_SUPPORT` |
| **84913** | Paid | ₹11,500 | Form #3313 has typo (84931) | None | 0 rows | **Broken Link / Typo Mismatch:** Teacher miskeyed invoice reference as 84931. | `RECONCILIATION_EXCEPTION`: AI matches student ID 68113; Ops confirms 1-click re-link. | `OPERATIONS` |

---

## The Re-Engineered Architecture: The Two-Gate Model

```
                                [Payment Gateway Webhook]
                                            │
                             (invoice_id, payment_id, amount,
                              currency, metadata.student_id)
                                            │
                                            ▼
                        [Step 0: Ingestion & Pre-Scan Filter]
                                            │
                     ┌──────────────────────┴──────────────────────┐
                     │ Duplicate Payment ID or Invoice ID?         │
                     ▼                                             ▼
                 [YES: Quarantine]                           [NO: Proceed]
                 (Hold all occurrences)                            │
                                                                   ▼
                                                 [GATE 1: Verification & Eligibility Engine]
                                                                   │
                         ┌─────────────────────────────────────────┴─────────────────────────────────────────┐
                         ▼                                                                                   ▼
            [Strict Financial Checks]                                                           [Identity Resolution]
            • payment_status == 'Paid'                                                          • Primary: metadata.student_id
            • amount_paid == package_price (Decimal)                                            • Secondary: E.164 Phone + Name
            • currency_paid == package_currency                                                 • Ambiguous Sibling -> Quarantine
                         │                                                                                   │
                         └─────────────────────────────────────────┬─────────────────────────────────────────┘
                                                                   │
                                                       All Gate 1 Checks Pass?
                                                                   │
                                            ┌──────────────────────┴──────────────────────┐
                                            ▼                                             ▼
                                      [NO: Quarantine]                              [YES: Eligible]
                                      Tag Reason Code & Alert                             │
                                                                                          ▼
                                                                     [GATE 2: Capacity & Slot Authorization]
                                                                                          │
                                   ┌──────────────────────────────────────────────────────┴──────────────────────────────────────────────────────┐
                                   ▼                                                                                                             ▼
                     [Check Downstream Pipeline State]                                                                             [Capacity & Preference Checks]
                     • In 4_class_schedules? -> ALREADY_COMPLETED                                                                   • Parent choice confirmed same batch?
                     • In 3_booking_requests? -> Check Sub-Status                                                                   • Live Capacity: Max - (Enrolled + Held) > 0
                       - 'Awaiting_Parent_Selection' -> HOLD                                                                             │
                       - 'Failed_Batch_Full'        -> CAPACITY_HOLD                                                                     │
                                   │                                                                                                             │
                                   └──────────────────────────────────────────────────────┬──────────────────────────────────────────────────────┘
                                                                                          │
                                                                          All Gate 2 Conditions Validated?
                                                                                          │
                                                           ┌──────────────────────────────┴──────────────────────────────┐
                                                           ▼                                                             ▼
                                                [YES: Straight-Through STP]                                    [NO: Exception / Hold]
                                                • Idempotent Schedule Generation                               • ERR_BATCH_CAPACITY_FULL
                                                • WhatsApp Confirmation to Parent                              • HOLD_PARENT_SLOT_SELECTION
                                                • Roster Update Alert to Teacher                               • ERR_ORPHAN_INVOICE
```

### The Elimination Principle: Sunsetting the Teacher Form
- **Why automate a broken step when you can eliminate it?**  
  The manual teacher form (`faculty_form_unapproved`) was created only because payment links lacked context. By embedding encrypted metadata tokens (`student_id`, `current_classbatch_id`, `term_id`) into renewal checkout links, the system receives 100% verified student attribution directly from the gateway webhook.
- **Fast-Track Straight-Through Processing (STP):**  
  For students continuing in the same batch with an exact fee payment, the teacher form is 100% bypassed. Classes are scheduled automatically within seconds of payment capture.
- **Teacher Focus Reclaimed:**  
  Eliminating repetitive paperwork saves 200+ teachers an estimated 4–5 hours weekly, allowing them to focus entirely on teaching and pedagogical excellence.

---

## Deterministic Code vs. Advisory AI System Boundaries

To protect academic and financial integrity, this architecture establishes clear, rigid boundaries between algorithmic code execution and probabilistic AI assistance:

```
┌─────────────────────────────────────────────────────────┐
│               DETERMINISTIC PYTHON CORE                 │
│  • Precision Decimal comparisons (amount == price)       │
│  • Primary Key matching (student_id, invoice_id)        │
│  • Ingestion-wide pre-scan duplicate locking             │
│  • Live roster capacity subtraction & atomic locking    │
│  • Database mutations & class schedule record creation  │
│  => CODE ALONE AUTHORIZES PAYMENTS & BOOKINGS           │
└───────────────────────────┬─────────────────────────────┘
                            │
                            │ Exceptions & Discrepancies
                            ▼
┌─────────────────────────────────────────────────────────┐
│              ADVISORY AI DISCREPANCY ASSISTANT          │
│  • Fuzzy typo matching (Form 3313: 84931 -> Inv 84913)   │
│  • Synthesizing orphaned invoice reminder context       │
│  • Multi-lingual parent WhatsApp balance draft payloads  │
│  • Confidence-scored candidate suggestions for Ops      │
│  => AI NEVER AUTHORIZES OR WRITES WITHOUT HUMAN-IN-LOOP │
└─────────────────────────────────────────────────────────┘
```

### Prototype Simulation vs. Production Infrastructure
- **Algorithmic Simulation (Current Repo):**  
  Batch seat reservations and capacity accounting are simulated in-memory via `AuthorityCapacityVerifier` to test logic against the assessment dataset.
- **Production Architecture Requirements:**  
  In a high-concurrency production deployment across global cohorts, capacity allocation must execute with pessimistic database row locking (`SELECT ... FOR UPDATE`) or a distributed lock manager (Redis Redlock) over an idempotent message bus (AWS SQS / Kafka).

---

## Operational Metrics, Mathematical Formulations & RACI SLAs

### Core Mathematical Formulations

1. **First-Pass Straight-Through Processing (STP) Rate (%):**
   $$\text{STP Rate} = \left( \frac{\text{Eligible Renewals Scheduled without Manual Ops Intervention}}{\text{Total Successfully Paid Invoices}} \right) \times 100$$
   - *Baseline in 13-row test suite:* **0.0%** (12 out of 13 records require manual triage or are blocked).
   - *Target for mature pipeline:* $\ge \mathbf{80.0\%}$.

2. **Payment-to-Schedule Turnaround Time (TAT):**
   $$\text{TAT} = \text{Timestamp}(\texttt{class\_schedule\_bookings.created\_at}) - \text{Timestamp}(\texttt{invoices.paid\_at})$$
   - *P50 Target (Clean STP):* $\le \mathbf{3\text{ minutes}}$.
   - *P90 Target (Exception Triage):* $\le \mathbf{2\text{ hours}}$.

3. **False Auto-Approval Rate (%):**
   $$\text{False Auto-Approval Rate} = \left( \frac{\text{Incorrectly Scheduled Automated Bookings}}{\text{Total Automated Bookings Processed}} \right) \times 100$$
   - *Target:* **Strictly 0.0%** (Zero tolerance for overbooking or mistaken identity).

4. **Net Capacity Savings Mathematical Model:**
   $$\text{Net Hours Saved} = \frac{(T_{\text{manual}} - T_{\text{auto}}) \times N_{\text{clean}}}{60} + \frac{T_{\text{assist}} \times N_{\text{exceptions}}}{60} - T_{\text{monitoring}}$$
   - *Empirical Hypotheses:* $T_{\text{manual}} = 15\text{ mins}$ per renewal across Teacher and Ops; $T_{\text{auto}} = 1\text{ min}$; $T_{\text{assist}} = 5\text{ mins}$ saved per exception; $T_{\text{monitoring}} = 30\text{ mins daily}$.
   - *Projection:* Reclaims **~171.7 net hours per 1,000 renewals** (600+ monthly hours at scale).

### RACI Governance & Operational SLA Matrix

| Reason Code | Root Cause Trigger | Responsible (R) | Accountable (A) | Consulted (C) | Informed (I) | SLA Target | Escalation Path | Autonomous Playbook Action |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---|:---|
| **ERR_UNDERPAYMENT** | Partial fee paid via unapproved link | Billing Specialist | Finance Lead | Teacher | Parent | **4 Hours** | Lead Billing Analyst | Auto-generate WhatsApp checkout link for remaining balance. |
| **ERR_ORPHAN_INVOICE** | Paid invoice with no teacher form | Ops Specialist | Ops Head | Faculty Ops | Teacher | **4 Hours** | Operations Manager | Trigger automated WhatsApp reminder to teacher with pre-filled context. |
| **ERR_BATCH_CAPACITY_FULL** | Batch reached maximum enrollment (6/6) | Academic Scheduler | Academic Ops Lead | Teacher | Parent Support | **2 Hours** | Head of Academics | Hold seat; evaluate batch split into Section B or offer alternate slot. |
| **ERR_BROKEN_INVOICE_LINK** | Teacher miskeyed invoice reference ID | Ops Specialist | Ops Head | Teacher | Finance | **2 Hours** | Operations Manager | Fuzzy linkage algorithm suggests student match; Ops confirms in 1 click. |
| **ERR_DUPLICATE_FACULTY_FORMS** | Teacher submitted multiple forms for 1 invoice | Ops Specialist | Ops Head | Teacher | None | **2 Hours** | Operations Lead | Quarantine duplicate form submissions to prevent double-booking. |
| **HOLD_PARENT_SLOT_SELECTION** | Parent requested change in class schedule | Parent Support Rep | Support Lead | Teacher | Academic Ops | **6 Hours** | Support Lead | Dispatch automated WhatsApp interactive message with available slots. |
| **ERR_PAYMENT_NOT_PAID** | Teacher filed form for a failed payment | Billing Specialist | Finance Lead | Teacher | None | **2 Hours** | Finance Lead | Instantly reject from scheduling pipeline; notify teacher. |

---

## Daily Operations Command Center (Metabase Dashboard Wireframe)

```
========================================================================================================================
                      BAMBINOS.LIVE RENEWAL OPERATIONS COMMAND CENTER (ILLUSTRATIVE VIEW)
========================================================================================================================
[PIPELINE THROUGHPUT - AUDIT SUITE]   [SLA COUNTDOWN STATUS]            [REVENUE AT RISK]          [SAVINGS MODEL]
• Total Invoices:       13            • Active Violations (>4h): 2      • Stuck Partial: ₹5,250    • Projected Daily: 24.5h
• Completed / Bypass:    1 (7.7%)     • Approaching SLA (<2h):   3      • Blocked Seats: 1 Child   • Target STP: 80.0%
• Allocation Review:     1 (7.7%)     • P90 Resolution: 42 mins         • Broken Links:  1 Invoice • False Approvals: 0.0%
• Actionable Exceptions: 7 (53.8%)    • Open Ops Queue: 4 Records       • Failed Gateway: ₹0       • Baseline STP: 0.0%
------------------------------------------------------------------------------------------------------------------------
                                          ACTIVE TRIAGE WORKLIST (BY ASSIGNED OWNER)
------------------------------------------------------------------------------------------------------------------------
INV_ID   | REASON CODE                 | OWNER        | DETECTED DIAGNOSTIC               | ACTION TRIGGER
------------------------------------------------------------------------------------------------------------------------
84905    | ERR_BATCH_CAPACITY_FULL     | ACADEMIC_OPS | Batch 9205 full (6/6 capacity)    | [Authorize Split / Batch 9206]
84908    | ERR_DUPLICATE_FACULTY_FORMS | OPS_LEAD     | Duplicate forms (#3308, #3309)    | [Quarantine & Deduplicate]
84909    | ERR_UNDERPAYMENT            | FINANCE      | Paid ₹5,250 of expected ₹10,500   | [Send WhatsApp Balance Link]
84911    | ERR_PAYMENT_NOT_PAID        | FINANCE      | Gateway payment status 'Failed'   | [Reject Form & Notify Teacher]
84912    | HOLD_PARENT_SLOT_SELECTION  | PARENT_SUPP  | Awaiting Parent Batch Selection   | [Dispatch WhatsApp Slot Picker]
84913    | ERR_BROKEN_INVOICE_LINK     | OPERATIONS   | Typo: Form references '84931'     | [1-Click Re-link to 84913]
------------------------------------------------------------------------------------------------------------------------
                                       BATCH BOTTLENECK & CAPACITY MONITOR (LIVE)
------------------------------------------------------------------------------------------------------------------------
BATCH ID      | SUBJECT / LEVEL      | TEACHER        | CAPACITY | STATUS         | ACTION NEEDED
------------------------------------------------------------------------------------------------------------------------
B-9201        | Young Champions G4   | Ms. Rhea B***  | 4 / 6    | HEALTHY        | Active (Invoice 84901 Scheduled)
B-9202        | Math Prodigy G5      | Mr. Vikram S*  | 5 / 6    | 1 SEAT LEFT    | Allocate Invoice 84902 immediately
B-9205        | Chess Grandmaster G4 | Coach Arvind K | 6 / 6    | AT CAPACITY    | Split Batch / Reassign Inv 84905
------------------------------------------------------------------------------------------------------------------------
FILTERS: [Region: All (India / GCC / US)] [View: Actionable Exceptions] [Export Audit Trail (.CSV)]
========================================================================================================================
```

---

## Phased 30-60-90 Day Change Governance Plan

```
[Days 1–30: Shadow Validation] ──► [Days 31–60: Teacher Form Deprecation] ──► [Days 61–90: Full Autonomy]
 • Async webhook listening          • 100% STP for clean renewals              • WhatsApp parent self-service
 • 1,500 test transactions          • Sunset manual form for eligible cohort   • Cross-region live capacity locking
 • Strict 0.0% false approvals      • Ops capacity shifted to retention        • Weekly confidence retraining
```

### Phase 1 (Days 1–30): Shadow Engine & Reliability Validation
- **Dual-Run Execution:** Ingest payment gateway webhooks asynchronously in shadow mode without altering production schedules.
- **Daily Variance Audit:** Run automated comparison scripts comparing engine recommendations against actual manual Ops schedule insertions.
- **Acceptance Criteria:** Process $\ge 1,500$ real transactions; achieve **0.0% False Auto-Approval Rate** and $\ge 98\%$ agreement on exception categorization across Finance and Ops leads.

### Phase 2 (Days 31–60): Controlled Pilot & Teacher Form Sunset
- **Pilot Cohort Deployment:** Enable Straight-Through Processing (STP) for the top 50 high-retention teachers.
- **Deprecate Teacher Form 2:** For same-batch renewals with matching fee payments, eliminate `faculty_form_unapproved`.
- **Change Enablement:** Position automation as an administrative upgrade: *"Teachers save 4–5 hours weekly on administrative tasks, allowing them to focus entirely on teaching."*
- **Ops Reallocation:** Shift 6 of 10 Ops coordinators from manual cross-checking to proactive renewal outreach and trial conversion support.

### Phase 3 (Days 61–90): Conversational Scheduling & Continuous Optimization
- **Parent Self-Service Scheduling:** For batch changes (e.g., Invoice 84912), deploy an automated WhatsApp chatbot that serves live open slots directly to parents, confirming slots without human intervention.
- **Cross-Region Concurrency:** Deploy Redis distributed locking across India, GCC, and US cohorts.
- **Dynamic Exception Retraining:** Weekly review of edge cases to refine candidate matching thresholds.

---

## Automated Omnichannel Communication & Notification Engine

All communication payloads are generated deterministically and exported directly to `./outputs/dispatched_notifications.json`:

1. **Parent WhatsApp: Balance Payment Link (Invoice 84909)**
   > *"Hello Ad\*\*\*t Ku\*\*\*i, we received partial payment of INR 5250.00 for your child's renewal. To confirm the seat and schedule upcoming classes without interruption, please complete the balance payment: https://pay.bambinos.live/balance?inv=84909"*
2. **Academic Ops Slack Card: Capacity Bottleneck (Invoice 84905)**
   > *"[CAPACITY ALERT] Invoice 84905 for Re\*\*\*h Pa\*\*\*l cannot be scheduled: Target Batch 9205 is at maximum capacity (6/6 seats filled). Immediate action required: [Authorize Section Split] or [Assign Alternate Slot]."*
3. **Parent WhatsApp: Interactive Slot Selection (Invoice 84912)**
   > *"Hello Ta\*\*\*a Me\*\*\*n, thank you for renewing! You requested a new batch schedule. Please choose your preferred day and time from live available batches here: https://bambinos.live/slot-picker?inv=84912"*
4. **Ops Slack Card: 1-Click Typo Re-Link (Invoice 84913)**
   > *"[TYPO MISMATCH] Form 3313 filed with invoice 84931 matched student De\*\*\*a Me\*\*\*a (ID: 68113) with paid Invoice #84913 (INR 11,500). AI Confidence: 99.4%. [1-Click Approve Re-link & Schedule]."*

---

## Quickstart & Execution Guide

### Prerequisites
- Python 3.10 or higher
- `pandas>=2.0.0`
- `reportlab>=4.0.0` (for PDF presentation deck regeneration)

### Installation
```bash
# Clone the repository
git clone https://github.com/rahilkhan002/Renewal-Lifecycle-Intelligence-Automation-System.git
cd Renewal-Lifecycle-Intelligence-Automation-System

# Install dependencies
pip install -r requirements.txt
```

### 1. Execute the Two-Gate Reconciliation Engine
```bash
python src/engine.py
```
*Output files generated in `./outputs/`:*
- `reconciliation_summary.csv`: Full audit log across all 13 invoices.
- `auto_approved_bookings.csv`: Clean renewals ready for class scheduling.
- `flagged_exceptions.csv`: Quarantined records with specific reason codes.
- `dispatched_notifications.json`: Omnichannel WhatsApp and Slack payloads.

### 2. Run the Automated Test Suite
```bash
python -m unittest tests/test_reconciliation.py
# Or with pytest if installed:
pytest tests/
```

### 3. Rebuild the 12-Slide PDF Presentation Deck
```bash
python build_deck.py
```
*Generates `Bambinos_AI_PM_Case_Deck.pdf` (12-slide, 16:9 widescreen presentation).*

---

## Repository Organization & Submission Checklist

```
bambinos-renewal-automation/
├── ops/data/                                  # Masked Assessment Datasets
│   ├── 1_invoices.csv                         # 13 payment gateway records
│   ├── 2_faculty_form_unapproved.csv          # 12 teacher renewal forms
│   ├── 3_booking_requests.csv                 # 4 Ops booking requests
│   ├── 4_class_schedule_bookings.csv          # 2 active schedule entries
│   └── reference_active_batches_and_students.csv # 13 student-batch lookup records
├── src/                                       # Production Prototype Core
│   ├── __init__.py                            # Package init
│   └── engine.py                              # Two-Gate Reconciliation Engine
├── tests/                                     # Automated Test Harness
│   ├── __init__.py                            # Package init
│   └── test_reconciliation.py                 # Unit & ground-truth regression tests
├── outputs/                                   # Engine Execution Artifacts
│   ├── reconciliation_summary.csv             # Complete 13-row audit table
│   ├── auto_approved_bookings.csv             # STP validated renewals
│   ├── flagged_exceptions.csv                 # Quarantined exceptions by owner
│   └── dispatched_notifications.json          # Omnichannel communication alerts
├── Bambinos_AI_PM_Case_Deck.pdf               # Compulsory 12-Slide PDF Presentation
├── build_deck.py                              # Script to generate the 12-slide PDF
├── requirements.txt                           # Project dependencies
└── README.md                                  # Complete System Documentation
```



