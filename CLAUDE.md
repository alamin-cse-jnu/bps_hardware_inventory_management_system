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

**Phases 1–6: ✅ All complete · 247 tests passing | Phase 7: 🔄 In progress**

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
| Sync UI + per-entity control       | ✅ Complete (Session 6.4)   |
| Assign panel + Inactive alerts     | ✅ Complete (Session 6.5)   |
| Reports + Audits + User management | ✅ Complete (Session 6.6)   |
| Employee model + sync overhaul     | ✅ Complete (Session 7.1)   |
| Employee list UI (class tabs)      | ✅ Complete (Session 7.2)   |
| MP list UI (photo + constituency)  | ✅ Complete (Session 7.3)   |
| Office hierarchy browser           | ✅ Complete (Session 7.4)   |

**Dev fixtures:** 5 categories · 12 asset types · 15 locations · RBAC groups

---

## Assignee Layer — Important Notes

The `Assignee` table is a **separate unified wrapper** over `CachedEmployee`, `CachedMP`, `CachedOffice`, and `Location`. It must be kept in sync:

- **PRP sync** (`sync_prp/services.py`) — `_sync_employees/mps/offices` each call `Assignee.objects.get_or_create(...)` after every `update_or_create`. When a cached record is flagged inactive, the corresponding `Assignee` is also set `is_active=False`.
- **Location creation** (`locations/views.py` → `_save_location`) — creates an `Assignee(LOCATION)` row for every new location.
- **Manual employee/MP/office creation** (`assignees/views.py`) — already creates an `Assignee` row on save.
- **Backfill** — a one-time shell script was run to create Assignee rows for all 4,464 pre-existing records (3,549 employees + 348 MPs + 552 offices + 15 locations).

The assign-panel search (`assignees:search`) queries `Assignee`, not the cached tables directly. If `Assignee` rows are missing, search returns empty.

---

## Phase 6 — Sessions

| Session | Scope | Status |
|---------|-------|--------|
| **6.1** | Asset CRUD + Import | ✅ Complete |
| **6.2** | Location CRUD | ✅ Complete |
| **6.3** | Employee/MP/Office lists | ✅ Complete |
| **6.4** | Custom Sync page — per-entity Employee/MP/Office control + sync history | ✅ Complete |
| **6.5** | Assign from asset list + Inactive holder alerts page | ✅ Complete |
| **6.6** | Reports polish + Audit sessions + User management | ✅ Complete |

---

## Phase 7 — Sessions (API schema update + UI overhaul)

> **Pre-requisite:** Employee/MP/Office data wiped from DB before Session 7.1 starts. Re-sync after model changes.

| Session | Scope | Status |
|---------|-------|--------|
| **7.1** | `CachedEmployee` model update + migration + DB wipe + sync logic overhaul | ✅ Complete |
| **7.2** | Employee list UI — class tabs, photo column, new columns, pagination | ✅ Complete |
| **7.3** | MP list UI — photo column, constituency sort, pagination | ✅ Complete |
| **7.4** | Office page — flat list tab + hierarchy browser tab | ✅ Complete |

---

### Session 7.1 — Model + Sync Overhaul

**Goal:** Align `CachedEmployee` with updated API schema; implement office-filter sync rules; wipe stale data.

**Steps:**
1. Add fields to `CachedEmployee` model:
   - `employee_class` — `IntegerField(null=True, blank=True)` (0 = no class; 1–4 = gazetted class from `class` API field)
   - `designation_en` — `CharField(max_length=255, blank=True, default="")`
   - `designation_bn` — `CharField(max_length=255, blank=True, default="")`
2. Run `makemigrations assignees` + `migrate`.
3. Wipe all PRP-sourced data:
   ```sql
   DELETE FROM assignees_cachedemployee WHERE source = 'PRP_API';
   DELETE FROM assignees_cachedmp        WHERE source = 'PRP_API';
   DELETE FROM assignees_cachedoffice    WHERE source = 'PRP_API';
   -- cascade will clean Assignee rows linked to deleted records
   ```
4. Update `sync_prp/services.py` → `_sync_employees()`:
   - **Filter:** skip any API record where `officeDetails` is null/absent (do not create).
   - **On update:** map `class` → `employee_class`, `designationEn` → `designation_en`, `designationBn` → `designation_bn`.
   - **Office-loss detection (second+ syncs):**
     - If DB record exists but API now returns no `officeDetails`:
       - Has active `Assignment` → set `is_active=False`, raise `InactiveHolderAlert` (existing logic).
       - No asset history at all → hard-delete `CachedEmployee` + matching `Assignee` row (PRP_API only).
5. Update snapshot builder — designation string: `"{designation_en} — {section}, {branch}, {wing}"`.
6. Run a fresh sync to repopulate.

---

### Session 7.2 — Employee List UI

**URL:** `/assignees/employees/`  
**Goal:** Replace flat list with class-tabbed view; add photo and new columns.

**Steps:**
1. Update `assignees/views.py` → `EmployeeListView`:
   - Accept `?class=` query param (values: `1`, `2`, `3`, `4`, `5`; default: all). `5` = no class.
   - Annotate/filter queryset by `employee_class`.
   - Accept `?per_page=` (25 / 50 / 100 / 350; default 25).
   - Default ordering: `prp_id` ascending (numeric cast).
2. Update `templates/assignees/employee_list.html`:
   - 5 tab buttons: **Class 1 · Class 2 · Class 3 · Class 4 · No Class** — each links with `?class=N`.
   - Table columns: `SL · Photo · PRP ID · Name · Designation · Office · Class · Source · Status · Actions`.
   - Photo cell: `<img>` tag with `photo_url`; fallback to avatar placeholder if blank.
   - Designation: `designation_en` (primary) + `designation_bn` (smaller below).
   - Office: `office_name_en` from `officeDetails` flatten.
   - Pagination footer with per-page switcher: 25 / 50 / 100 / 350.
3. No JS framework needed — HTMX `hx-push-url` for tab switching is fine; plain links are acceptable.

---

### Session 7.3 — MP List UI

**URL:** `/assignees/mps/`  
**Goal:** Add photo column; sort by constituency; pagination.

**Steps:**
1. Update `assignees/views.py` → `MPListView`:
   - Default ordering: `constituency` ascending.
   - Accept `?per_page=` (25 / 50 / 100 / 350; default 25).
2. Update `templates/assignees/mp_list.html`:
   - Table columns: `SL · Photo · PRP ID · Name · Constituency · Parliament · Source · Status · Actions`.
   - Photo cell: same pattern as employees.
   - Parliament: `parliament_no` field (e.g. "12th Parliament").
   - Pagination footer with per-page switcher: 25 / 50 / 100 / 350.

---

### Session 7.4 — Office Hierarchy Browser

**URL:** `/assignees/offices/`  
**Goal:** Add macOS Finder-style column browser as a second tab alongside the existing flat list.

**Steps:**
1. Update `assignees/views.py` → `OfficeListView`:
   - Pass all `CachedOffice` objects as JSON to the template for the hierarchy tab.
   - Flat list tab: `per_page` pagination (25 / 50 / 100 / 350).
2. Update `templates/assignees/office_list.html`:
   - Two tab buttons: **All Offices** (existing flat list) · **Office Hierarchy**.
   - The hierarchy tab embeds a `<div id="office-browser">` and loads the JS component.
3. Write `static/js/office_browser.js` — self-contained, no external dependencies:
   - `buildTree(data)` — returns `{ byId, byParent }` maps.
   - `getAncestors(id, byId)` — walks `parentId` chain to root; returns ordered array.
   - **Column browser (default mode):**
     - Horizontally scrollable `<div class="column-browser">`.
     - Column 0 = children of root (`parentId === 0`).
     - Clicking a node: mark selected (highlight `#006633`); if has children → append next column; auto-scroll right.
     - Breadcrumb strip above columns; clicking ancestor resets trail to that depth.
     - If a column has > 12 items → show a small filter `<input>` at column top.
   - **Search mode** (activates when user types in search box):
     - Filter across `nameEn` (case-insensitive) + `nameBn`.
     - Show up to 25 results in a dropdown; each shows `nameEn`, `nameBn`, full ancestor breadcrumb.
     - Clicking result selects node AND syncs column browser trail.
     - Clear (×) button resets search.
   - **Selected office panel** (shown below browser whenever a node is selected):
     - Displays: `nameEn` (bold), `nameBn`, full ancestor path, node `id`.
     - If `isAbstractOffice === true` → show subtle "Group — not a selectable office" warning badge.
     - Confirm/submit button (for future use as a picker component).
   - Styling: use existing CSS variables (`--parliament-blue`, etc.); both `nameEn` and `nameBn` visible in every row.
4. The component accepts an optional `initialValue` (office id) — pre-selects and pre-expands the correct column trail on load.
