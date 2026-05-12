# Parliament IT Inventory Management System

## Project Overview
Web-based IT hardware asset tracking system for the Bangladesh National Parliament Secretariat. Tracks every physical IT asset from procurement to disposal — who holds it, where it is, and its complete history over time.

**Scale:** 1,000–5,000 assets · ~50,000 historical assignment rows (10 years) · 10–20 concurrent users · Under 1 GB database · <500ms response for common queries

**Deployment:** Parliament intranet · Docker containers · Nginx + Gunicorn

---

## Tech Stack

| Layer              | Choice                                        |
|--------------------|-----------------------------------------------|
| Framework          | Django 5.x + Django REST Framework             |
| Database           | PostgreSQL (JSONField for flexible specs)      |
| Frontend           | Django templates + HTMX for interactivity      |
| QR Codes           | `qrcode` Python library                        |
| Excel              | `openpyxl`                                     |
| PDF                | `WeasyPrint`                                   |
| Task Queue         | Celery + Redis broker                          |
| Auth               | Django Allauth · Groups for RBAC               |
| Server             | Nginx + Gunicorn                               |
| Deploy             | Docker + docker-compose                        |
| Branding           | Parliament Green `#006633` · Gold `#C8A951`    |
| Language           | English only                                   |

---

## Design System

**Design reference:** A full 9-screen HTML prototype exists at `it-inventory/project/IT Inventory.html` (from Claude Design). Read this file before building any frontend. It defines exact layout, components, and interactions. However, the prototype's white sidebar and plain card backgrounds must be replaced with the richer color treatment described below.

**Design direction:** The prototype structure is correct (layout, screens, components) but NEEDS MORE COLOR. Reference the PRP portal (`prp.parliament.gov.bd`) for the vibrant feel — purple/violet gradient cards, orange/gold stat cards, colored sidebar. The system should look like a government institutional tool, not a minimal SaaS dashboard.

### Color Palette

**Core Brand**
```
Parliament Green:     #006633  (primary actions, success states, header accents)
Parliament Green Dk:  #005229  (hover state for green)
Parliament Gold:      #C8A951  (secondary accents, badges, decorative)
Gold Light:           #FBF5E6  (gold tinted backgrounds)
```

**Dark Theme (Login + optional sidebar)**
```
Dark Base:       #13122A  (login background, sidebar background)
Dark Surface:    #1A1830  (card backgrounds on dark)
Dark Elevated:   #252340  (hover/active on dark)
Dark Muted:      #35325A  (borders on dark)
Purple Accent:   #6D5AE6  (focus rings, active states, CTA on dark)
Purple Hover:    #5B49D4  (hover for purple accent)
Purple Soft:     rgba(109,90,230,0.18)  (purple glow/tint)
```

**PRP-Inspired Accent Colors (for cards, dashboards, stats)**
```
Violet Gradient:   linear-gradient(135deg, #6D5AE6, #8B5CF6)  — stat cards, highlights
Orange Gradient:   linear-gradient(135deg, #F59E0B, #EF8A20)  — alert cards, secondary stats
Green Gradient:    linear-gradient(135deg, #006633, #10B981)  — success cards
```

**Status Colors (used in pills, badges, table rows)**
```
In Stock:      #10B981  bg: #ECFDF5
Assigned:      #3B82F6  bg: #EFF6FF
Maintenance:   #F59E0B  bg: #FFFBEB
Lost:          #EF4444  bg: #FEF2F2
Damaged:       #EF4444  bg: #FEF2F2
Disposed:      #9CA3AF  bg: #F3F4F6
```

**Neutral Palette**
```
Background:     #F8F9FA  (main content area)
White:          #FFFFFF  (cards, modals)
Border:         #E5E7EB
Border Mid:     #D1D5DB
Text:           #212529
Text Mid:       #495057
Text Muted:     #6C757D
Placeholder:    #9CA3AF
```

### Typography

```
Primary Font:    'Inter', sans-serif       — all UI text
Monospace Font:  'JetBrains Mono', mono    — asset tags, IDs, codes
```

Font sizes: 10/11/12/13/14/15/16/17/18/20/22/26/28px. Body default 14px.

### Layout

```
Sidebar:         240px wide, DARK background (#13122A), not white
Topbar:          56px height, white, subtle bottom border
Content area:    Fills remaining space, #F8F9FA background, scrollable
Card radius:     8px standard, 12px for larger cards
Spacing base:    4px grid (8, 12, 16, 20, 24, 32px common values)
```

### Key Design Rules for Claude Code

1. **Sidebar must be DARK** (#13122A background, white/light text, green active indicator) — NOT the white sidebar from the prototype
2. **Dashboard KPI cards use gradient backgrounds** (violet, green, orange) with white text — not flat white cards
3. **Status pills** are colored with matching light background (e.g. green text on green-tinted bg)
4. **Asset tags** always render in `JetBrains Mono` monospace
5. **Action buttons** use Parliament Green (#006633) as primary color
6. **Destructive actions** (dispose, delete) use red (#EF4444) with confirmation step
7. **Warning states** (inactive holder, expiring warranty) use amber (#F59E0B) with amber-tinted backgrounds
8. **The login page** uses the full dark theme (#13122A) with purple accent, Parliament logo, and footer credit: "Designed & Developed by Md. Al-Amin Hossain"
9. **Mobile QR scan page** uses Parliament Green header with large monospace asset tag

### Screen Inventory (from design prototype)

| #  | Screen                         | Key Elements                                                   |
|----|-------------------------------|----------------------------------------------------------------|
| 0  | Login                          | Dark split-card, logo, purple CTA, SSO, error state            |
| 1  | Dashboard                      | 4 KPI cards, activity feed, quick actions, charts              |
| 2  | Asset List                     | Filter bar, table, status pills, bulk select, pagination       |
| 3  | Asset Detail + History         | Tabs (Overview/History/Components/Events), timeline            |
| 4  | Assign/Transfer Modal          | Slide-over panel, search assignee, quick picks, signature      |
| 5  | History Search                 | Search + filters, grouped results (In Stock/Assigned/Unavail)  |
| 6  | Bulk Transfer Wizard           | Step indicator, per-row destination picker, mixed destinations  |
| 7  | Inactive Holder Alerts         | Alert cards, expandable asset lists, action buttons            |
| 8  | Mobile QR Scan                 | Phone bezel, asset info, 4 action buttons, toast confirmations |

---

## Django Apps (7 total)

| App           | Responsibility                                                              |
|---------------|-----------------------------------------------------------------------------|
| `assets`      | Asset catalog: categories, types, specification schemas, items, components   |
| `assignees`   | Cached Employee/MP/Office records + unified Assignee layer                   |
| `assignments` | Assignment records, holder snapshots, TransferBatch for bulk moves           |
| `lifecycle`   | Events: maintenance, lost, damaged, disposed, component swaps                |
| `locations`   | Self-referential hierarchy: building → floor → room (room is OPTIONAL)       |
| `qrcodes`     | QR generation, mobile scan views, physical audit sessions                    |
| `sync`        | External API synchronisation + inactive holder detection                     |
| `reports`     | Excel and PDF generation for all reports and forms                           |

---

## 9 Core Architectural Decisions

These are NON-NEGOTIABLE. Every model, view, and workflow must respect them.

1. **Parent + child components** — A PC Set is one trackable unit, but monitor/CPU/keyboard/mouse/RAM are individually replaceable AssetComponents with their own history.

2. **Unified Assignee table (NO GenericForeignKey)** — One table with four FK fields (employee, mp, office, location). Exactly one is populated based on `assignee_type`. All queries use one JOIN.

3. **Immutable assignment rows (close + open)** — Every transfer closes the old Assignment (sets `returned_at`) and opens a new one. Once `returned_at` is set, that row is NEVER modified again.

4. **Assignee snapshot (JSONField)** — Freezes holder name, designation, and department at assignment time. Historical reports always show the designation the person held AT THAT TIME, not their current one.

5. **TransferBatch for bulk operations** — Groups multiple assignment transitions under one batch reference. Each asset in a batch can have a DIFFERENT destination.

6. **Status state machine** — Asset status follows strict transitions. Impossible states (assigning a disposed asset) are prevented at the model level. Transitions must be validated in `clean()` or a dedicated method.

7. **Dual-source holders (PRP API + manual creation)** — "Sync Now" pulls Employee/MP/Office data from the PRP API into local cache. But holders can ALSO be created manually when they don't exist in the API. The `source` field (`PRP_API` or `MANUAL`) determines ownership. Sync ONLY touches `PRP_API` records — manual records are invisible to sync and never flagged inactive by it.

8. **QR code identification** — Every asset gets a printed QR code (encodes asset tag). Scanning on phone opens a mobile action page: current status, transfer, event logging, audit scan.

9. **Inactive holder alerts (flag, NEVER delete)** — When a holder disappears from the external API, flag as inactive + raise alert. Active assignments preserved for human remediation. No automatic returns to stock. No silent data mutation.

---

## Data Model Summary

### Asset Side
- `AssetCategory` — top-level grouping (Computing, Networking, Printing)
- `AssetType` — kind of asset (PC_SET, LAPTOP, PRINTER) with a spec schema defining which fields apply
- `AssetItem` — the trackable unit: unique asset tag (QR-encoded), serial, brand, model, specs (JSONField), current status, storage location, optional procurement fields
- `AssetComponent` — child of a PC Set: own serial, specs, swap history. Removed components keep their record with removal timestamp + reason

### Holder Side
- `CachedEmployee`, `CachedMP`, `CachedOffice` — local cache. Each has: `source` field (`PRP_API` | `MANUAL`), active flag, inactive timestamp, last-seen-active timestamp. NEVER deleted. Sync only touches records where `source="PRP_API"`. Manual records are sync-proof.
- `Location` — single self-referential model with `level_type` (BUILDING | FLOOR | ROOM) and nullable `parent` FK. Room is OPTIONAL — a location can be just building + floor. Created entirely within the system (no API). Validation: BUILDING has no parent, FLOOR's parent must be BUILDING, ROOM's parent must be FLOOR. Display path built by walking parent chain.
- `Assignee` — unified holder. One of four FKs populated (employee/mp/office/location), determined by `assignee_type`

### History Side
- `Assignment` — links AssetItem to Assignee. Fields: assigned_at, returned_at, holder_snapshot (JSON), performed_by (IT officer), optional TransferBatch FK. IMMUTABLE once returned_at is set.
- `TransferBatch` — groups multiple Assignment transitions. One batch, many assets, each with independent destination.
- `LifecycleEvent` — non-ownership events: maintenance, lost, damaged, disposed, component swap
- `InactiveHolderAlert` — raised by sync. Tracks remediation progress.
- `AuditSession` + `AuditScan` — physical inventory audit via QR scanning. Produces found/misplaced/missing report.

### Key Indexes
- `(asset_id, returned_at)` on Assignment
- `(assignee_id, is_active)` on Assignment

---

## Asset Status State Machine

Valid statuses and their allowed transitions:

```
IN_STOCK    → ASSIGNED, MAINTENANCE, DISPOSED
ASSIGNED    → IN_STOCK, MAINTENANCE, LOST, DAMAGED, DISPOSED
MAINTENANCE → IN_STOCK, DISPOSED
LOST        → IN_STOCK (if recovered), DISPOSED
DAMAGED     → IN_STOCK (if repaired), MAINTENANCE, DISPOSED
DISPOSED    → (terminal state, no transitions out)
```

Enforce in model-level validation. Never allow skipping transitions.

---

## Roles (Django Groups)

| Role       | Can Do                                                                 | Cannot Do                                    |
|------------|------------------------------------------------------------------------|----------------------------------------------|
| Admin      | Everything: catalog, assignments, lifecycle, sync, users, soft-delete  | (unrestricted)                               |
| IT Officer | Add assets, assign, transfer, lifecycle events, handovers, audits, sync | Manage catalog/types, delete records, manage users |
| Viewer     | View assets/holders/history, generate & download reports               | Any modification                             |

---

## Security Rules
- HTTPS mandatory (even on intranet)
- 30-minute idle session timeout
- Strong password policy; 2FA for Admin
- Soft-delete ONLY — no hard deletions ever
- Daily DB backup; weekly full backup; quarterly restore test
- Audit log for sensitive data views (especially MP records)

---

## Reports (all in Excel + PDF with Parliament branding)

Current Inventory · Asset History · Person/Office History · Transfer Log · Lifecycle Events · Warranty/AMC Expiry · Physical Audit · Handover Form (single + batch) · Clearance List · Disposal Certificate · Saved Searches

---

## Development Phases

| Phase                  | Duration  | Status      |
|------------------------|-----------|-------------|
| 1. Foundation          | 3 weeks   | NOT STARTED |
| 2. Assignment Engine   | 3 weeks   | NOT STARTED |
| 3. Lifecycle and QR    | 2-3 weeks | NOT STARTED |
| 4. Reports and Alerts  | 2 weeks   | NOT STARTED |
| 5. Hardening           | 1-2 weeks | NOT STARTED |

### Phase 1 Deliverables
- Django project scaffolding + Docker + PostgreSQL setup
- `assets` app: categories, types, items, components
- `locations` app: self-referential hierarchy (building/floor/room, room optional)
- Polished Django admin
- Excel import tool for legacy data migration

### Phase 2 Deliverables
- PRP API sync + inactive holder detection (`sync` app)
- Unified Assignee layer with dual-source holders: API + manual creation (`assignees` app)
- Assignment, Transfer, snapshot, TransferBatch (`assignments` app)
- HTMX-based interactive UI for core workflows

### Phase 3 Deliverables
- Lifecycle events: maintenance, lost, damaged, disposed (`lifecycle` app)
- QR code generation + printing (`qrcodes` app)
- Mobile scan views
- Physical audit sessions with discrepancy reporting

### Phase 4 Deliverables
- Excel + PDF report generation (`reports` app)
- History search page
- Celery Beat scheduled alerts (warranty, AMC, inactive holders)
- Dashboard with metrics + alert banners

### Phase 5 Deliverables
- User training materials
- UAT with Software Development Branch team
- Backup/restore testing
- Production deployment to Parliament intranet

---

## Edge Cases to Remember

- **Designation changes:** Snapshot handles it. Never trust current cached data for historical reports.
- **Inactive holders:** Flag + alert. Never auto-return assets. Human remediation only.
- **Parliament term ends:** 300 MPs become inactive at once. Dedicated mass-clearance workflow needed.
- **Office restructuring:** Old office flagged inactive. Bulk transfer assets to new office.
- **Deceased employee:** Manual inactive-reason flag with sensitivity suppression.
- **Wrong transfer:** Standard transfer corrects it. Original mistake stays in history for accountability.
- **API down:** System runs on local cache. Dashboard shows staleness indicator.
- **Component swap:** Old component gets removed_at + reason. New component linked to same parent. Both queryable.
- **Holder not in PRP API:** IT Officer creates a manual record. Same fields required (name, designation, department) so snapshots work identically.

---

## PRP API Specification

**Base URL:** `https://prp.parliament.gov.bd`
**Credentials:** stored in `.env` as `PRP_API_USERNAME` and `PRP_API_PASSWORD` — NEVER hardcoded.

### Authentication
```
POST /api/authentication/external?action=token
Content-Type: application/json
Body: { "username": "...", "password": "..." }
Response: { "responseCode": 200, "payload": "Bearer eyJ...", "msg": "Success" }
```
- Token is a JWT with expiry (from the payload, `exp` claim)
- All subsequent requests use header: `Authorization: <payload value>` (the payload already includes "Bearer")
- The sync service must handle token refresh: re-authenticate if a request returns 401 or if token is near expiry

### Endpoints

| Endpoint                                              | Method | Returns            |
|-------------------------------------------------------|--------|--------------------|
| `/api/secure/external?action=mpInformations`          | GET    | `[MPInformation]`  |
| `/api/secure/external?action=employeeInformations`    | GET    | `[EmployeeInformation]` |
| `/api/secure/external?action=offices`                 | GET    | `[OfficeInformation]` |

All return `{ "responseCode": 200, "payload": [...], "msg": "Success" }`.

### API Data Models → Cache Field Mapping

**EmployeeInformation → CachedEmployee**
```
API Field               → Cache Field              Notes
─────────────────────────────────────────────────────────────
prpId (String)          → prp_id (unique key)      Primary identifier for sync matching
nameEn (String)         → name_en                   Used in snapshots
nameBn (String)         → name_bn                   Bengali name
mobile (String)         → mobile                    Nullable
telephone (String)      → telephone                 Nullable
status (String)         → api_status                Raw status from API
gender (String)         → gender                    Nullable
photo (String)          → photo_url                 URL or base64, store as-is
officeDetails (Object)  → see OfficeDetails below   Flattened into designation fields
```

**MPInformation → CachedMP**
```
API Field               → Cache Field              Notes
─────────────────────────────────────────────────────────────
prpId (String)          → prp_id (unique key)      Primary identifier for sync matching
parliamentNo (int)      → parliament_no             Which parliament (e.g. 12th)
constituency (String)   → constituency              Electoral area
nameEn (String)         → name_en                   Used in snapshots
nameBn (String)         → name_bn                   Bengali name
mobile (String)         → mobile                    Nullable
telephone (String)      → telephone                 Nullable
status (String)         → api_status                Raw status from API
gender (String)         → gender                    Nullable
photo (String)          → photo_url                 URL or base64
officeDetails (String)  → office_details_raw        NOTE: String, not Object — parse if structured
```

**OfficeInformation → CachedOffice**
```
API Field               → Cache Field              Notes
─────────────────────────────────────────────────────────────
id (Long)               → prp_id (unique key)      Primary identifier for sync matching
parentId (Long)         → parent_prp_id             For building office hierarchy (nullable)
nameEn (String)         → name_en                   Used in snapshots
nameBn (String)         → name_bn                   Bengali name
isAbstractOffice (Bool) → is_abstract               Grouping node vs real office
```

**OfficeDetails (nested in EmployeeInformation):**
```
API Field               → Cache Field              Notes
─────────────────────────────────────────────────────────────
wingId / wingNameEn/Bn       → wing_id, wing_name_en/bn
branchId / branchNameEn/Bn   → branch_id, branch_name_en/bn
sectionId / sectionNameEn/Bn → section_id, section_name_en/bn
unitId / unitNameEn/Bn       → unit_id, unit_name_en/bn
officeId / officeNameEn/Bn   → office_id, office_name_en/bn
```
OfficeDetails fields give the employee's placement in the office hierarchy.
For snapshots, build a designation string like: `"{sectionNameEn}, {branchNameEn}, {wingNameEn}"`.

### Sync Process Flow (sync app)

1. Authenticate → get Bearer token
2. Fetch all three endpoints (employees, MPs, offices)
3. For each record type, compare ONLY against `source="PRP_API"` cached records:
   - **Match by `prp_id`** — if exists, update all fields from API
   - **No match** — create new cache record with `source="PRP_API"`, `is_active=True`
   - **Cache record exists but NOT in API response** — set `is_active=False`, record `inactive_since` timestamp, raise `InactiveHolderAlert` if holder has active assignments
4. Record sync timestamp (`last_synced_at`) and result counts on a `SyncLog` model
5. Dashboard shows: last sync time, records added/updated/flagged, any errors

### Sync Error Handling
- API timeout or connection error → log error, show "Sync Failed" on dashboard, do NOT modify any cache records
- Partial response (some endpoints fail) → sync only the ones that succeeded, flag which failed
- Token expired mid-sync → re-authenticate once, retry failed request, fail if second attempt also fails
- Rate limiting → respect any Retry-After headers

---

## Manual Holder Creation Rules

**When:** A holder needs to receive assets but does not exist in the PRP API (e.g. temporary contractor, external consultant, newly posted employee not yet in PRP).

**Dual-source field:** Every `CachedEmployee`, `CachedMP`, `CachedOffice` record has:
```
source = "PRP_API"   →  owned by sync process, updated/flagged by sync
source = "MANUAL"    →  owned by IT Officer, sync NEVER reads/writes/flags these
```

**Manual creation rules:**
- Available to Admin and IT Officer roles
- Required fields: name (en), designation/department (minimum for a useful snapshot)
- Bengali name, mobile, photo are optional but encouraged
- Manual records appear in all search/assignment dialogs alongside API records
- Manual records can be flagged inactive manually by the IT Officer
- UI should visually distinguish manual vs API-sourced records (e.g. a small badge or icon)

**Sync isolation:** `source="MANUAL"` records are completely invisible to the sync process. Sync queries always filter `source="PRP_API"`.

**Duplicate prevention:**
- Before manual creation, search existing records (both API and manual) and warn if a similar name exists
- No hard block — the officer may legitimately need it

---

## Location Hierarchy Rules

**Locations are system-only** — no external API. Created and managed entirely within the application.

**Single model, self-referential:**
```
Location
├── name: str
├── level_type: "BUILDING" | "FLOOR" | "ROOM"
├── parent: FK → Location (nullable)
├── is_active: bool
```

**Validation rules:**
- BUILDING → parent must be NULL
- FLOOR → parent must be a BUILDING
- ROOM → parent must be a FLOOR
- Room is OPTIONAL — assets can be assigned to a floor with no room specified

**Display path:** Walk parent chain upward and reverse:
- Full: `NOC Room → 3rd Floor → Parliament Bhaban` displays as `Parliament Bhaban → 3rd Floor → NOC Room`
- Without room: `3rd Floor → Parliament Bhaban` displays as `Parliament Bhaban → 3rd Floor`

**Asset/Assignment linking:** The FK to Location can point to ANY level (building, floor, or room). The system does not force room-level precision.

---

## Conventions

- Python: follow Django conventions, use type hints where practical
- Models: always include `created_at`, `updated_at` auto-fields and `created_by`/`updated_by` where relevant
- Soft delete: use `is_deleted` flag + `deleted_at` timestamp, never `Model.delete()`
- Secrets: all credentials in `.env` file, loaded via `django-environ` or `python-decouple`. `.env` is in `.gitignore`.
- Tests: write tests for state machine transitions and edge cases
- Commits: descriptive messages, one logical change per commit
- Branch strategy: feature branches off main, merge after review

---

## Session Log

> Updated after each significant Claude Code session. Newest entries at the top.

- **Session 3.2:** UI access fixes. Created `templates/account/login.html` — allauth login page at `/accounts/login/` now uses the same dark split-card design as the admin login (left panel with geo SVG background + Parliament branding + stats, right panel with dark inputs, purple CTA, password toggle, secure strip, footer credit). This is what `@login_required` redirects unauthenticated users to. Fixed logout in `base.html` to use a `<form method="post">` instead of an `<a>` href — allauth 65+ rejects GET-based logouts as a CSRF protection measure. Loaded `assets/fixtures/initial_data.json` and `locations/fixtures/initial_data.json` into the dev database (32 objects: 5 categories, 12 types, 15 locations). Main app now accessible at `http://localhost:8000/` with dark login → asset list flow working end-to-end. **170 tests still pass.**

- **Session 3.1:** Phase 3 — Lifecycle & QR. `lifecycle` app: `LifecycleEvent` model (8 event types: MAINTENANCE_SENT, MAINTENANCE_RETURN, LOST, DAMAGED, RECOVERED, REPAIRED, DISPOSED, COMPONENT_SWAP; records old_status/new_status pair + performed_by + optional component FK); `lifecycle/services.py` with 7 public service functions (`send_to_maintenance`, `return_from_maintenance`, `report_lost`, `report_damaged`, `recover_asset`, `repair_asset`, `dispose_asset`) + `swap_component`; each validates current status explicitly (e.g. `repair_asset` guards `asset.status == DAMAGED`) then delegates to `asset.change_status()`; `_close_active_assignment()` helper uses `update()` to bypass immutability guard; `EVENT_HANDLERS` dict maps EventType → service fn; `APPLICABLE_EVENTS` dict maps Status → applicable event list. `lifecycle/views.py`: `event_panel()` with GET (radio buttons for applicable events) and POST (dispatch via EVENT_HANDLERS, returns success overlay or panel with error). `lifecycle/admin.py`: LifecycleEventAdmin fully read-only with colored event type badges. `lifecycle/tests.py`: 22 tests covering all service functions and edge cases (invalid status guards, assignment closure on transition from ASSIGNED). `qrcodes` app: `AuditSession` (auto-reference `AUD-YYYY-NNNN`, `is_complete` property, `complete()` method) + `AuditScan` (unique_together session+asset). `qrcodes/views.py`: `mobile_scan()` (standalone green-header mobile page), `qr_download()` (returns image/png with Parliament Green fill), `qr_label()` (base64 QR embedded in printable label). `qrcodes/admin.py`: AuditSessionAdmin with AuditScanInline. `qrcodes/tests.py`: 18 tests. Templates: `lifecycle/event_panel.html` (radio-button event selector, JS highlight), `lifecycle/event_success.html` (checkmark overlay with new status badge), `qrcodes/mobile_scan.html` (standalone, green header, own HTMX CSRF, #panel-container), `qrcodes/qr_label.html` (print-ready label with base64 QR + Print/Download/Back). `assets/asset_detail.html` updated with amber "Event" button (hx-get lifecycle:event_panel) and QR label link. `assets/views.py` updated to pass `lifecycle_events` to detail context. Bug fixed: `repair_asset()` must guard `status == DAMAGED` explicitly because MAINTENANCE→IN_STOCK is also a valid state-machine transition. **170 tests pass** (40 new: 22 lifecycle + 18 qrcodes). **Phase 3 complete.**

- **Session 2.2:** HTMX-based assign/transfer UI. Wired up URL routing: `assets/` → asset list, `assets/<pk>/` → detail, `assignees/search/` → live search endpoint, `assignees/<pk>/select/` → select card, `assignments/<pk>/assign/` (GET/POST) → slide-over panel + confirmation, `assignments/<pk>/assign/clear/` → reset assignee field, `assignments/<pk>/return/` (GET/POST) → return confirmation. Views: `assets/views.py` (list with status/type/q filters + `(asset, asgn)` tuple rows), `assignees/views.py` (search with Q filter across all holder types, `select_card` returns swappable partial), `assignments/views.py` (assign_panel handles GET → panel HTML, POST → success/error; _past_holders helper de-dupes and caps at 4 active past holders). Templates: `base.html` (dark sidebar #13122A + HTMX CDN + `hx-headers` CSRF on body), `assets/asset_list.html` (filter bar, status pills, Assign/Transfer HTMX buttons), `assets/asset_detail.html` (gradient header card, JS tab switcher for Overview/History/Components), `assignments/assign_panel.html` (480px slide-over, HTMX form), `assignments/assignee_field.html` (search box with HTMX live results, JS show/hide dropdown), `assignees/search_results.html` (HTMX-swappable results list), `assignees/selected_card.html` (green card with hidden `assignee_id` input, clear button), `assignments/assign_success.html` (checkmark success state), `assignments/return_confirm.html` (return confirmation panel), `assignments/return_success.html`. All 130 tests still pass. **Phase 2 complete.**

- **Session 2.1:** Phase 2 — Assignment Engine. `assignees` app: `CachedEmployee` (all office-placement fields: wing/branch/section/unit/office, `designation` property, `mark_inactive()`), `CachedMP` (parliament_no, constituency, raw office details), `CachedOffice` (parent_prp_id for hierarchy), all three with dual-source (`PRP_API`/`MANUAL`), null prp_id for MANUAL records (PostgreSQL allows multiple NULLs in unique column), `is_active`/`inactive_since`/`last_seen_active`. `Assignee` unified table: 4 FK fields (employee/mp/office/location), `AssigneeType` choices, `clean()` validates exactly one FK matches `assignee_type`, `display_name` property, `holder_source` property, `build_snapshot()` freezes name+designation+department at assignment time. Admin: PRP_API records are locked readonly (sync owns them), source/active badges, designation column. `assignments` app: `TransferBatch` with auto-reference `TB-YYYY-NNNN`, `Assignment` with `holder_snapshot` JSONField + immutability guard in `save()` (raises ValidationError if DB `returned_at` already set), `is_active` property, indexes on `(asset, returned_at)` and `(assignee, returned_at)`. `InactiveHolderAlert` with `resolve()`/`dismiss()` methods. `assignments/services.py`: `perform_transfer()` (handles IN_STOCK→ASSIGNED and ASSIGNED→ASSIGNED transfers, closes old assignment via `update()` to bypass immutability guard, validates asset status/deleted/assignee active) and `return_to_stock()`. Admin: Assignment fully readonly (no add/change permissions). **130 tests pass** (56 new: 31 assignees + 25 assignments).

- **Session 1.5:** Admin login + interface redesign. Created `templates/admin/login.html` — complete standalone dark split-card login (no Django admin chrome): left panel (#0E0D20) with 7×10 rotated-rect geo background SVG, Parliament logo, IT Inventory title, 3 stats; right panel (#1A1830) with dark inputs (#252340), purple CTA button (#6D5AE6 with glow), SSO ghost button, password show/hide toggle, error box, security strip, footer credit. Rewrote `templates/admin/base_site.html`: full CSS variable coverage for Django admin 5.x, dark sidebar (#13122A) with gold captions and purple hover, per-app gradient module captions (assets=green, locations=violet, assignments=blue, lifecycle=red/amber, auth=grey), styled changelist table with hover rows, filter sidebar, paginator, submit rows, messages, delete buttons, search bar, object-tools. All existing import/changelist templates inherit cleanly.

- **Session 1.4:** Admin branding + fixtures. `templates/admin/base_site.html`: Parliament Green `#006633` header with gold `#C8A951` border and branding text, dark sidebar `#13122A`, Inter/JetBrains Mono fonts via Google Fonts, full CSS-variable override for buttons/links/breadcrumbs/module headers/login page. Footer credit. Admin site title/header/index set in `config/urls.py`. Assets fixture: 5 categories, 12 types with realistic `spec_schema` arrays. Locations fixture: 15 locations (2 buildings, 9 floors, 4 rooms) with correct hierarchy. Both fixtures load cleanly (17 + 15 objects). Fix noted: `loaddata` uses `raw=True` — `auto_now_add` fields must be explicit in fixtures.

- **Session 1.3:** Excel import/export tool — `assets/services/excel_import.py`. Three service classes: `ExcelTemplateGenerator` (3-sheet workbook: Data Entry with dynamic `spec_*` cols + Parliament Green headers + example row, Instructions, Valid Locations), `ExcelImportValidator` (column-position-agnostic, location path normalisation for `→`/`>`, intra-batch duplicate tag detection, date/decimal parsing), `ExcelImportExecutor` (auto-tag `LAP-YYYY-NNNN`, per-type batch counter, full `transaction.atomic()` rollback on any failure). Admin: `get_urls()` wires download-template, import (GET form + POST preview), import/confirm views. Session-based preview→confirm handoff. Three admin templates. 24 new tests. **74 total tests pass.**

- **Session 1.2:** `assets` app — four models: `AssetCategory`, `AssetType` (`spec_schema` JSONField), `AssetItem` (status state machine: `VALID_TRANSITIONS` dict + `change_status()` + `soft_delete()` + `is_assignable`), `AssetComponent` (`clean()` enforces `has_components`). Admin: component inline conditional on `has_components`, full readonly on soft-deleted items. Fix noted: `specifications` JSONField needs `blank=True` (empty dict `{}` is falsy). 37 tests covering all 15 valid transitions, 13 invalid transitions, component allow/reject, soft delete, uniqueness, `is_assignable`. **50 total tests pass.**

- **Session 1.1:** `locations` app — `Location` model: self-referential FK, `LevelType` choices (BUILDING/FLOOR/ROOM), `clean()` hierarchy validation, `full_path` property (walks parent chain, joins with ` → `). Django admin: filtered parent dropdown by level, child inline, `created_by` auto-stamp. 13 tests (valid creation, invalid hierarchy, full_path at all 3 levels, floor-only is valid). **13 total tests pass.**

- **Session 1:** Phase 1 skeleton — Django 5.x `config` package at root, `manage.py` at root, all 8 apps (`assets`, `assignees`, `assignments`, `lifecycle`, `locations`, `qrcodes`, `sync_prp`, `reports`), `docker-compose.yml` (web + db PG16 + redis + celery + celery-beat), `Dockerfile` (Python 3.12-slim, WeasyPrint deps — note: `libgdk-pixbuf-xlib-2.0-0` not `libgdk-pixbuf2.0-0` on Debian Trixie), `requirements.txt`, `.env` (local defaults), `.gitignore`. `docker-compose build` passes; all apps load cleanly.

- **Session 0.3:** Design system documented — dark sidebar `#13122A`, gradient KPI cards (violet/green/orange), PRP-portal colour direction. Full 9-screen inventory with key elements. Overrides the white-sidebar prototype.

- **Session 0.2:** PRP API specification added — auth flow (JWT), 3 endpoints (employees, MPs, offices), all field mappings (`EmployeeInformation`, `MPInformation`, `OfficeInformation`, `OfficeDetails`), sync process flow, error handling. Credentials in `.env`.

- **Session 0.1:** Dual-source holder design (`PRP_API` vs `MANUAL`, sync isolation), flexible location hierarchy (room optional, FK can point to any level). Data model and phase deliverables updated.

- **Session 0:** CLAUDE.md created from architecture document. No code written yet.

---

## Current State (as of Session 3.2)

### What exists
| App | Status | Key files |
|---|---|---|
| `locations` | ✅ Complete | `models.py`, `admin.py`, `tests.py`, migration `0001` |
| `assets` | ✅ Complete | `models.py`, `admin.py`, `tests.py`, migrations `0001`–`0002`, `services/excel_import.py`, `urls.py`, `views.py` |
| `assignees` | ✅ Complete | `models.py`, `admin.py`, `tests.py`, migration `0001`, `urls.py`, `views.py` |
| `assignments` | ✅ Complete | `models.py`, `services.py`, `admin.py`, `tests.py`, migration `0001`, `urls.py`, `views.py` |
| `lifecycle` | ✅ Complete | `models.py`, `services.py`, `admin.py`, `views.py`, `tests.py`, migration `0001`, `urls.py` |
| `qrcodes` | ✅ Complete | `models.py`, `admin.py`, `views.py`, `tests.py`, migration `0001`, `urls.py` |
| `sync_prp` | ⬜ Skeleton only | stub files only |
| `reports` | ⬜ Skeleton only | stub files only |

**Frontend templates:** `base.html`, `account/login.html` (allauth dark login), `assets/asset_list.html`, `assets/asset_detail.html`, `assignments/assign_panel.html`, `assignments/assignee_field.html`, `assignments/assign_success.html`, `assignments/return_confirm.html`, `assignments/return_success.html`, `assignees/search_results.html`, `assignees/selected_card.html`, `lifecycle/event_panel.html`, `lifecycle/event_success.html`, `qrcodes/mobile_scan.html`, `qrcodes/qr_label.html`

**Dev database:** Fixtures loaded — 5 categories, 12 asset types, 15 locations (2 buildings, 9 floors, 4 rooms). No AssetItems yet.

**Test count:** 170 passing (13 locations + 61 assets + 31 assignees + 25 assignments + 22 lifecycle + 18 qrcodes)

### Phase completion
| Phase | Status |
|---|---|
| Phase 1 — Foundation | ✅ Complete |
| Phase 2 — Assignment Engine | ✅ Complete |
| Phase 3 — Lifecycle & QR | ✅ Complete |
| Phase 4 — Reports & Alerts | ⬜ Not started |
| Phase 5 — Hardening | ⬜ Not started |

---

## Next To Do

### Phase 3 (Lifecycle & QR)
- [x] `lifecycle` app: `LifecycleEvent` (maintenance, lost, damaged, disposed, component swap) ✅
- [x] `qrcodes` app: QR generation, mobile scan view, `AuditSession` + `AuditScan` ✅

### Phase 4 (Reports & Alerts)
- [ ] `reports` app: Excel + PDF generation (openpyxl + WeasyPrint)
- [ ] `sync_prp` app: PRP API client, token refresh, sync process, `SyncLog`
- [ ] Celery Beat scheduled tasks (warranty alerts, inactive holder detection)
- [ ] Dashboard with KPI cards, activity feed, alert banners

### Phase 5 (Hardening)
- [ ] Frontend templates (login dark theme, dashboard, asset list, asset detail)
- [ ] Role-based access control (Admin / IT Officer / Viewer groups)
- [ ] 2FA for Admin role
- [ ] Nginx config refinement, production `.env` guidance
- [ ] UAT + backup/restore test