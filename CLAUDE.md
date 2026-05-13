# Parliament IT Inventory Management System

## Project Overview
Web-based IT hardware asset tracking system for the Bangladesh National Parliament Secretariat. Tracks every physical IT asset from procurement to disposal — who holds it, where it is, and its complete history.

**Scale:** 1,000–5,000 assets · ~50,000 historical rows · 10–20 concurrent users · <500ms common queries  
**Deployment:** Parliament intranet · Docker · Nginx + Gunicorn

---

## Tech Stack

| Layer            | Choice                                          |
|------------------|-------------------------------------------------|
| Framework        | Django 5.x + Django REST Framework              |
| Database         | PostgreSQL (JSONField for flexible specs)       |
| Frontend         | Django templates + HTMX                         |
| QR / Excel / PDF | `qrcode` · `openpyxl` · `WeasyPrint`            |
| Task Queue       | Celery + Redis                                  |
| Auth             | Django Allauth · Groups for RBAC                |
| Server           | Nginx + Gunicorn · Docker + docker-compose      |

---

## Design System

**Full reference:** `docs/design-system.md`  
**Critical rules (do not deviate):**
- Sidebar background: `#0076A7` (Parliament Blue) — NOT dark, NOT green
- Primary button: `#0076A7`, hover `#005d85`
- Login page only: dark theme `#13122A` + purple CTA `#6D5AE6`
- Asset tags: `JetBrains Mono`, color `#0076A7`
- Destructive actions: red `#EF4444` with confirmation step

---

## Django Apps

| App           | Responsibility                                                        |
|---------------|-----------------------------------------------------------------------|
| `assets`      | Asset catalog: categories, types, spec schemas, items, components     |
| `assignees`   | Cached Employee/MP/Office records + unified Assignee layer            |
| `assignments` | Assignment records, holder snapshots, TransferBatch for bulk moves    |
| `lifecycle`   | Events: maintenance, lost, damaged, disposed, component swaps         |
| `locations`   | Self-referential hierarchy: building → floor → room (room optional)   |
| `qrcodes`     | QR generation, mobile scan views, physical audit sessions             |
| `sync_prp`    | PRP API synchronisation + inactive holder detection                   |
| `reports`     | Excel and PDF report generation                                       |

---

## 9 Core Architectural Decisions (NON-NEGOTIABLE)

1. **Parent + child components** — A PC Set is one unit; monitor/CPU/keyboard/mouse/RAM are individually replaceable `AssetComponent` records with their own history.

2. **Unified Assignee table (NO GenericForeignKey)** — One table, four FK fields (employee/mp/office/location). Exactly one populated per `assignee_type`. All queries use one JOIN.

3. **Immutable assignment rows** — Every transfer closes the old `Assignment` (sets `returned_at`) and opens a new one. Once `returned_at` is set, that row is NEVER modified again.

4. **Assignee snapshot (JSONField)** — Freezes name, designation, department at assignment time. Historical reports always show the designation held AT THAT TIME, not current.

5. **TransferBatch for bulk operations** — Groups multiple transitions under one batch reference. Each asset in a batch can have a DIFFERENT destination.

6. **Status state machine** — Strict transitions enforced at model level in `clean()` / `change_status()`. Impossible states prevented, transitions never skipped.

7. **Dual-source holders** — `source="PRP_API"` records owned by sync; `source="MANUAL"` owned by IT Officer. Sync always filters `source="PRP_API"` — manual records are completely invisible to sync and never flagged inactive by it.

8. **QR code identification** — Every asset has a QR code (encodes asset tag). Mobile scan → action page: status, transfer, event logging, audit.

9. **Inactive holder alerts (flag, NEVER delete)** — Holder absent from API → flag inactive + raise `InactiveHolderAlert`. Active assignments preserved for human remediation. No auto-returns. No silent mutation.

---

## Asset Status State Machine

```
IN_STOCK    → ASSIGNED, MAINTENANCE, DISPOSED
ASSIGNED    → IN_STOCK, MAINTENANCE, LOST, DAMAGED, DISPOSED
MAINTENANCE → IN_STOCK, DISPOSED
LOST        → IN_STOCK (recovered), DISPOSED
DAMAGED     → IN_STOCK (repaired), MAINTENANCE, DISPOSED
DISPOSED    → (terminal)
```

---

## Roles & RBAC

| Role       | Can Do                                                        | Cannot Do                                   |
|------------|---------------------------------------------------------------|---------------------------------------------|
| Admin      | Everything incl. catalog, users, soft-delete (2FA enforced)   | —                                           |
| IT Officer | Add assets, assign/transfer, lifecycle events, sync, audits   | Manage catalog/types, delete, manage users  |
| Viewer     | View assets/holders/history, download reports                 | Any modification                            |

Decorators: `viewer_required` / `it_officer_required` / `admin_required` in `config/permissions.py`.  
Template flags: `user_is_admin` / `user_is_it_officer` / `user_is_viewer` from `config/context_processors.py`.

---

## Security Rules
- Soft-delete ONLY — `is_deleted` flag + `deleted_at`, never `Model.delete()`
- 2FA for Admin (TOTP via `allauth.mfa`, enforced by `AdminMFARequiredMiddleware`)
- Secrets in `.env` via `django-environ`/`python-decouple`, never hardcoded

---

## PRP API

**Base URL:** `https://prp.parliament.gov.bd` · credentials: `PRP_API_USERNAME` / `PRP_API_PASSWORD` in `.env`  
**Full field mappings, sync flow, error handling:** `docs/prp-api.md`

---

## Conventions
- Models: always `created_at`, `updated_at` · `created_by`/`updated_by` where relevant
- Soft delete: `is_deleted` + `deleted_at`, never `Model.delete()`
- Tests: cover state machine transitions and edge cases
- Type hints where practical · Django conventions throughout

---

## Current State

**Phases 1–5: ✅ All complete · 247 tests passing**

| App / Module                       | Status                      |
|------------------------------------|-----------------------------|
| `locations`                        | ✅ Complete                 |
| `assets`                           | ✅ Complete                 |
| `assignees`                        | ✅ Complete                 |
| `assignments`                      | ✅ Complete                 |
| `lifecycle`                        | ✅ Complete                 |
| `qrcodes`                          | ✅ Complete                 |
| `sync_prp`                         | ✅ Complete                 |
| `reports`                          | ✅ Complete                 |
| `config` (RBAC + 2FA + nginx)      | ✅ Complete                 |
| Asset CRUD + Import (main UI)      | ✅ Complete (Session 6.1)   |
| Location CRUD (main UI)            | ✅ Complete (Session 6.2)   |
| Employee/MP/Office lists (main UI) | ✅ Complete (Session 6.3)   |

**Dev fixtures:** 5 categories · 12 asset types · 15 locations · RBAC groups

---

## Phase 6 — Remaining Sessions

| Session | Scope | Status |
|---------|-------|--------|
| **6.4** | Custom Sync page — per-entity Employee/MP/Office control + sync history | Pending |
| **6.5** | Assign from asset list + Inactive holder alerts page | Pending |
| **6.6** | Reports polish + Audit sessions + User management | Pending |
