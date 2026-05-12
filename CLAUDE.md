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

- **Session 6.1:** Phase 6 — Asset CRUD + Excel Import in main system. `assets/views.py`: added `asset_create` (GET/POST — auto-tag via `_generate_asset_tag`, inline validation via `_validate_asset_form`, `messages.success` on save), `asset_edit` (GET pre-fills dict from `AssetItem` fields, POST updates in-place; status not editable here — use lifecycle), `asset_delete` (GET returns HTMX delete-confirm panel, POST calls `asset.soft_delete()`), `asset_spec_fields` (HTMX endpoint — returns spec fields partial when asset_type select changes; `hx-include="this"` passes `asset_type` GET param), `asset_tag_check` (HTMX live uniqueness check, returns ✓/✗ span), `import_template` (downloads `.xlsx` template via `ExcelTemplateGenerator`), `import_upload` (GET=form, POST=validate → store rows in session → render preview), `import_confirm` (POST=`ExcelImportExecutor.execute()` → clears session → redirect to list). `assets/urls.py`: 8 new patterns: `new/`, `import/`, `import/confirm/`, `import/template/`, `spec-fields/`, `tag-check/`, `<pk>/edit/`, `<pk>/delete/`. Templates: `assets/asset_form.html` (shared add/edit form — 2-col grid: Identity card left + Status/Location card right; HTMX spec fields section updates on type change; 3-col procurement grid; inline field error display), `assets/asset_delete_confirm.html` (HTMX slide-over panel with red confirmation + soft-delete explanation + ASSIGNED warning), `assets/import_upload.html` (3-step indicator; template download by JS; file upload form), `assets/import_preview.html` (3-stat summary cards; per-row valid/warning/error colour coding; confirm/re-upload actions), `assets/partials/spec_fields.html` (HTMX-swappable spec field grid, rendered via `{% include %}` on page load and swapped by HTMX on type change). `templates/asset_list.html`: topbar now has "Import" + "Add Asset" buttons (hidden for Viewers via `user_is_it_officer`); per-row Edit (pencil) + Delete (trash) icon buttons added (Viewer-hidden); empty-state shows Import/Add shortcuts. `templates/base.html`: sidebar restructured with Holders section (Employees/MPs/Offices — disabled), Setup section (Locations — disabled), correct active highlighting for new asset URL names; role label in footer uses `user_is_admin/it_officer/viewer` flags; flash messages block added above `{% block content %}` using `.flash-success/error/warning/info` CSS classes; `.nav-badge` utility class added. **247 tests still pass** (no new tests added — CRUD covered by system check + manual verification).

- **Session 5.1:** Phase 5 — RBAC, logo integration, 2FA, nginx. `config/permissions.py`: 3 predicates (`is_admin`, `is_it_officer_or_above`, `is_viewer_or_above`) + 3 decorators (`viewer_required`, `it_officer_required`, `admin_required`) using `redirect_to_login` for unauthenticated + `PermissionDenied` for unauthorised. Superusers bypass all checks. `config/context_processors.py`: `role_flags` context processor injects `user_is_admin/it_officer/viewer` booleans into every template. All views updated: read-only views use `viewer_required`, write views use `it_officer_required`, sync trigger uses `it_officer_required`. `assets/management/commands/create_groups.py`: `create_groups` management command creates Admin (all perms), IT Officer (32 perms: operational), Viewer (16 perms: read-only) — idempotent, runs on every container start via docker-compose. `allauth.mfa` added to INSTALLED_APPS (requires `fido2==1.1.3` dep added to requirements.txt). 3 MFA migrations applied. `config/middleware.py`: `AdminMFARequiredMiddleware` checks Admin-group users have TOTP configured; if not, redirects to `/accounts/2fa/totp/activate/` (superusers exempt). `MFA_TOTP_ISSUER = "Parliament IT Inventory"` in settings. **Logo** in `static/images/parliament_logo.png` now shown in: sidebar (`base.html`), allauth login page (`account/login.html`), both PDF templates (`reports/pdf/handover.html` + `disposal.html` — logo loaded as base64 data URL in generator, cached via `@lru_cache`). `templates/403.html`: custom 403 page with red X icon + Parliament logo. `nginx/nginx.conf`: HTTP→HTTPS redirect, TLS 1.2/1.3, static/media served directly, proxy to gunicorn. `docker-compose.yml`: nginx service added (ports 80+443); `web` changed to `expose: 8000` (no longer directly mapped); `create_groups` added to startup command. `.env.example` updated with production defaults and deployment notes. `config/tests.py`: 30 RBAC tests — predicate tests (is_admin/officer/viewer for all role combinations + superuser), decorator tests (viewer/officer/admin required with all role types), role_context tests, create_groups idempotency test, HTTP 403 integration tests. Test users in reports/tests.py and qrcodes/tests.py updated to `is_superuser=True` so existing view tests pass. **247 tests pass** (30 new: config RBAC).

- **Session 4.2:** Phase 4 — reports app complete. `reports/generators/excel.py`: 5 Excel report functions — `inventory_excel` (14 cols: asset tag → AMC expiry, with active-assignment holder lookup), `transfer_log_excel` (13 cols, date-range filter, 5000-row cap), `lifecycle_events_excel` (11 cols, date+event_type filters), `warranty_expiry_excel` (days-ahead window, Q filter for warranty OR amc), `asset_history_excel` (per-asset full assignment history including "Current" for active rows). All use Parliament Blue `#0076A7` headers + `#E8F3F8` alternating rows. `reports/generators/pdf.py`: `handover_pdf(assignment_pk)` and `disposal_pdf(asset_pk)` using WeasyPrint — both call `render_to_string` then `HTML(string=...).write_pdf()`; WeasyPrint import wrapped in try/except for environments without display. `reports/views.py`: login-required views for all 5 Excel downloads (with query param parsing for filters, date ranges, days) + 2 PDF downloads (mocked in tests). `reports/urls.py`: 8 URL patterns under `/reports/`. `reports/tests.py`: 25 tests — Excel byte output (XLSX magic bytes check), view HTTP responses (Content-Type checks), PDF views (mocked), 404 for missing objects, unauthenticated redirects, filter/param edge cases. `templates/reports/index.html`: report catalog page (2 sections: Excel with inline filter forms, PDF section with navigation hints). `templates/reports/pdf/handover.html`: A4 WeasyPrint template — letterhead, 3-sig-block (IT Officer + Receiver + Verifier). `templates/reports/pdf/disposal.html`: A4 WeasyPrint disposal certificate — red disposal banner, 3-sig-block (Recommended + Approved + Authorised). Wired into `config/urls.py`. Reports nav link in `base.html` made active. `assets/asset_detail.html`: added "Handover PDF" link on active-assignment card, "Disposal PDF" + "History XLS" buttons in topbar. Bug fixed: `LifecycleEvent.EventType` is a standalone class — `pdf.py` imports it directly (not as `LifecycleEvent.EventType`). Tests import `AssigneeType` from `assignees.models` (standalone, not nested). **217 tests pass** (25 new: reports).

- **Session 4.1:** Phase 4 — sync_prp + Dashboard. `sync_prp` app: `SyncLog` model (status: RUNNING/SUCCESS/PARTIAL/FAILED; per-entity counts for employees/mps/offices; `total_added`/`total_updated`/`total_flagged` properties; `duration_seconds`). `sync_prp/client.py`: `PRPApiClient` with JWT auth (`_fetch_token`, `_token_ttl` parses exp claim without a JWT library), Bearer token cached in Django cache, transparent 401-retry with `_raw_get`. `sync_prp/services.py`: `run_full_sync()` orchestrates all three endpoints independently (partial failure model); `_sync_employees/mps/offices` use `update_or_create` matching on `prp_id + source=PRP_API`; flags missing records as inactive via `mark_inactive()`; `_maybe_raise_alert` creates `InactiveHolderAlert` (get_or_create) only when holder has active assignments — MANUAL records completely invisible to sync. `sync_prp/tasks.py`: `scheduled_sync` (daily 1 AM) and `check_expiry` (daily 6 AM) Celery Beat tasks. `sync_prp/admin.py`: `SyncLogAdmin` fully read-only with colored status badges and +/~/! columns. `sync_prp/views.py`: `trigger_sync` (POST, returns JSON) and `sync_status` (GET). `sync_prp/urls.py` + wired into `config/urls.py`. Added `requests==2.32.3` to requirements (missing dep). Celery Beat schedule added to `config/settings.py` behind `try/except ImportError`. `config/__init__.py` celery import also wrapped in try/except for local dev. Dashboard: new `dashboard` view in `assets/views.py` — KPI counts (total/assigned/in_stock/issues), expiring assets within 30 days, open `InactiveHolderAlert` records, recent assignments + lifecycle events, last sync log. `templates/dashboard.html`: 4 gradient KPI cards (violet/blue/teal/orange), alert banners (inactive holders + expiry), two-column layout (activity feed + quick actions + sync status + alerts sidebar), HTMX Sync Now button with JS page-reload on success. Dashboard added to sidebar nav. `assets/urls.py` updated with `dashboard/` path. **192 tests pass** (22 new: sync_prp).

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

## Current State (as of Session 6.1)

### What exists
| App / Module | Status | Key files |
|---|---|---|
| `locations` | ✅ Complete | `models.py`, `admin.py`, `tests.py`, migration `0001` |
| `assets` | ✅ Complete | `models.py`, `admin.py`, `tests.py`, migrations `0001`–`0002`, `services/excel_import.py`, `urls.py`, `views.py`, `management/commands/create_groups.py` |
| `assignees` | ✅ Complete | `models.py`, `admin.py`, `tests.py`, migration `0001`, `urls.py`, `views.py` |
| `assignments` | ✅ Complete | `models.py`, `services.py`, `admin.py`, `tests.py`, migration `0001`, `urls.py`, `views.py` |
| `lifecycle` | ✅ Complete | `models.py`, `services.py`, `admin.py`, `views.py`, `tests.py`, migration `0001`, `urls.py` |
| `qrcodes` | ✅ Complete | `models.py`, `admin.py`, `views.py`, `tests.py`, migration `0001`, `urls.py` |
| `sync_prp` | ✅ Complete | `models.py`, `client.py`, `services.py`, `tasks.py`, `admin.py`, `views.py`, `urls.py`, `tests.py`, migration `0001` |
| `reports` | ✅ Complete | `generators/excel.py`, `generators/pdf.py`, `views.py`, `urls.py`, `tests.py` |
| `config` (RBAC) | ✅ Complete | `permissions.py`, `context_processors.py`, `middleware.py`, `tests.py` |
| Asset CRUD (main UI) | ✅ Complete | `assets/views.py` (create/edit/delete/spec_fields/tag_check), `assets/urls.py`, `templates/assets/asset_form.html`, `asset_delete_confirm.html`, `import_upload.html`, `import_preview.html`, `partials/spec_fields.html` |

**Frontend templates:** `base.html` (Parliament logo in sidebar, flash messages, updated sidebar nav), `account/login.html` (logo), `403.html`, `assets/asset_list.html` (Add Asset + Import buttons, edit/delete per row), `assets/asset_detail.html`, `assets/asset_form.html` (new), `assets/asset_delete_confirm.html` (new), `assets/import_upload.html` (new), `assets/import_preview.html` (new), `assets/partials/spec_fields.html` (new), `assignments/*`, `assignees/*`, `lifecycle/*`, `qrcodes/*`, `dashboard.html`, `reports/index.html`, `reports/pdf/handover.html` (logo), `reports/pdf/disposal.html` (logo)

**Infrastructure:** `nginx/nginx.conf` (HTTPS, TLS 1.2/1.3, static serving), `docker-compose.yml` (nginx service added), `.env.example` (production guidance)

**RBAC Groups (auto-created on startup):**
- `Admin` — all permissions (enforced 2FA via AdminMFARequiredMiddleware)
- `IT Officer` — operational: assign/transfer/lifecycle/sync
- `Viewer` — read-only: browse + download reports

**Dev database:** Fixtures loaded — 5 categories, 12 asset types, 15 locations. Groups created.

**Test count:** 247 passing (13 locations + 61 assets + 31 assignees + 25 assignments + 22 lifecycle + 18 qrcodes + 22 sync_prp + 25 reports + 30 config/RBAC)

### Phase completion
| Phase | Status |
|---|---|
| Phase 1 — Foundation | ✅ Complete |
| Phase 2 — Assignment Engine | ✅ Complete |
| Phase 3 — Lifecycle & QR | ✅ Complete |
| Phase 4 — Reports & Alerts | ✅ Complete |
| Phase 5 — Hardening | ✅ Complete |

---

## Phase 6 Plan — UI Completeness (replacing Django admin for daily work)

> Goal: Every operation an IT Officer or Viewer performs day-to-day must be doable from the main system — no Django admin required. Admin panel remains only for superuser/developer use.

### Gap analysis (what exists vs what is needed)

| Feature | Current state | Target |
|---|---|---|
| Add / Edit / Delete asset | Admin only | Custom forms in main system |
| Excel import | Admin-only tool | `/assets/import/` in main system |
| Excel download reports | `/reports/` page exists | Keep + improve placement |
| Sync | Single "Sync All" on dashboard | Custom sync page with per-entity (Employee/MP/Office) control |
| Employee/MP/Office lists | Admin only | Sidebar pages with search & filter |
| Manual holder add | Admin only | Forms in main system |
| Location CRUD | Admin only (`locations/urls.py` is empty stubs) | Sidebar page with tree view + CRUD forms |
| Assign asset | From asset detail only | Also accessible from asset list + dedicated assign flow |
| Return to stock | From asset detail only | Also from asset list |
| Inactive holder alerts | Dashboard banner only | Dedicated management page |
| Batch transfer | Model exists, no UI | Multi-select on asset list → batch transfer wizard |
| Audit sessions | QR scan exists, no session management UI | Audit session list + start/complete UI |
| Handover PDF | Button on asset detail | Also from assignment history list |
| User management | Admin only | Basic page for Admins: create user, assign group |

---

### Session 6.1 — Asset CRUD + Excel Import in main system

**Scope:** Full asset lifecycle management without touching Django admin.

**Views to add (`assets/views.py`):**
- `asset_create` (GET/POST) — form with category/type/brand/model/serial/specs/procurement fields; auto-tag generation option
- `asset_edit` (GET/POST) — same form pre-filled; only non-readonly fields editable
- `asset_delete` (POST) — soft-delete with confirmation modal (HTMX overlay); Admin + IT Officer only
- `import_template` (GET) — download Excel template for the chosen asset type
- `import_upload` (GET/POST) — upload → validate → preview rows → confirm → execute; uses existing `ExcelImportValidator` + `ExcelImportExecutor`
- `import_confirm` (POST) — session-based preview→confirm handoff (same pattern as admin import)

**URL patterns to add (`assets/urls.py`):**
```
assets/new/                    → asset_create
assets/<pk>/edit/              → asset_edit
assets/<pk>/delete/            → asset_delete
assets/import/                 → import_upload (GET=form, POST=preview)
assets/import/confirm/         → import_confirm
assets/import/template/        → import_template (query: ?type_id=N)
```

**Templates:**
- `assets/asset_form.html` — shared add/edit form; Parliament Blue header, spec fields rendered dynamically from `asset_type.spec_schema`
- `assets/asset_delete_confirm.html` — HTMX slide-over modal with red confirmation
- `assets/import_upload.html` — drag-and-drop file input + asset type selector
- `assets/import_preview.html` — table of parsed rows (valid/invalid highlighted); Confirm or Cancel

**Asset list changes:**
- Add "New Asset" (primary button) and "Import" (outline button) to topbar
- Add Edit (pencil) and Delete (trash) icon buttons per row — hidden for Viewers

**Permission:** `asset_create`, `asset_edit`, `asset_delete` → `it_officer_required`; import → `it_officer_required`

---

### Session 6.2 — Location CRUD in main system

**Scope:** Full location hierarchy management from sidebar. Currently `locations/urls.py` is empty stubs.

**Views to add (`locations/views.py`):**
- `location_list` — table of all locations grouped by building; shows Building → Floor → Room tree
- `location_create` (GET/POST) — form with name, level_type, parent (filtered dropdown based on level_type)
- `location_edit` (GET/POST) — same form pre-filled
- `location_delete` (POST) — soft-delete or deactivate; block if assets are stored there

**URL patterns:**
```
locations/                  → location_list
locations/new/              → location_create
locations/<pk>/edit/        → location_edit
locations/<pk>/delete/      → location_delete (POST only)
```

**Templates:**
- `locations/location_list.html` — tree-structured table; Building rows span floors; room column optional
- `locations/location_form.html` — add/edit form with HTMX-powered parent dropdown (parent options update when level_type changes)
- `locations/location_delete_confirm.html` — HTMX modal

**Sidebar change:** Add "Locations" nav item under a new "Setup" section.

**Permission:** list → `viewer_required`; create/edit/delete → `it_officer_required`

---

### Session 6.3 — Employee / MP / Office list pages + manual holder creation

**Scope:** IT Officers need to browse holders and create manual records without Django admin.

**Views to add (`assignees/views.py`):**
- `employee_list` — paginated list; filter by source (API/Manual), active status; search by name/designation/department
- `employee_create` (GET/POST) — manual employee form; shows API badge warning if similar name found
- `employee_edit` (GET/POST) — edit manual records only (API records show as read-only with edit blocked)
- `mp_list` — similar; filter by parliament_no, status
- `mp_create` / `mp_edit` — manual MP forms
- `office_list` — hierarchical; filter by active
- `office_create` / `office_edit` — manual office forms
- `assignee_detail` — shows all assignments for a holder with history

**URL patterns:**
```
assignees/employees/                → employee_list
assignees/employees/new/            → employee_create
assignees/employees/<pk>/edit/      → employee_edit
assignees/mps/                      → mp_list
assignees/mps/new/                  → mp_create
assignees/mps/<pk>/edit/            → mp_edit
assignees/offices/                  → office_list
assignees/offices/new/              → office_create
assignees/offices/<pk>/edit/        → office_edit
assignees/<pk>/                     → assignee_detail (all assignments)
```

**Templates:**
- `assignees/employee_list.html` — table with source badge (API=blue, Manual=gold), active pill, search bar
- `assignees/mp_list.html` — similar with parliament_no column
- `assignees/office_list.html` — indented hierarchy
- `assignees/holder_form.html` — shared form partial (name, designation, department fields); warning banner if similar name found
- `assignees/assignee_detail.html` — holder card + assignment history table + "Assign Asset" button

**Sidebar change:** Add "Holders" section with Employee, MP, Office sub-items.

**Permission:** lists → `viewer_required`; create/edit → `it_officer_required`

---

### Session 6.4 — Custom Sync page (per-entity control)

**Scope:** Replace single "Sync All" with separate Employee/MP/Office controls and full sync history.

**Backend changes (`sync_prp/`):**
- Add per-entity sync functions in `services.py`: `sync_employees_only()`, `sync_mps_only()`, `sync_offices_only()` — each creates its own SyncLog with entity type tag
- Add `entity` field to `SyncLog` model: `ALL | EMPLOYEES | MPS | OFFICES` (migration needed)
- New views: `trigger_sync_entity` (POST, accepts `entity` param) + `sync_page` (GET — renders full page)

**URL changes:**
```
sync/                       → sync_page (full management page)
sync/trigger/               → trigger_sync (existing, ALL entities)
sync/trigger/<entity>/      → trigger_sync_entity (EMPLOYEES | MPS | OFFICES)
sync/status/                → sync_status (JSON)
```

**Template `sync_prp/sync_page.html`:**
- 3 panels side by side: Employees | MPs | Offices
- Each panel: last sync time, records (added/updated/flagged), status badge, "Sync Now" HTMX button
- Below panels: sync history table (last 20 SyncLog rows) with status, duration, counts
- Error messages displayed inline per entity

**Sidebar change:** "Sync" nav item links to `/sync/` (not just the dashboard trigger button). Remove the sync widget from dashboard or keep as summary only.

**Permission:** `sync_page` → `viewer_required`; `trigger_sync_entity` → `it_officer_required`

---

### Session 6.5 — Assignment from asset list + Inactive Alerts page

**Scope:** Make assignment accessible without entering asset detail; manage inactive holder alerts.

**Assignment from list:**
- Asset list: each row's "Assign" / "Transfer" button triggers the same HTMX slide-over panel that currently exists on asset detail — no page navigation needed
- Return to stock also accessible from list row

**Inactive holder alerts page (`assignments/views.py`):**
- `alert_list` — paginated list of InactiveHolderAlerts; filter by status (Open/Resolved/Dismissed); shows holder, raised date, number of affected assets, action buttons
- `alert_resolve` (POST) — resolves an alert with a note
- `alert_dismiss` (POST) — dismisses an alert with a note

**URL patterns:**
```
assignments/alerts/              → alert_list
assignments/alerts/<pk>/resolve/ → alert_resolve (POST)
assignments/alerts/<pk>/dismiss/ → alert_dismiss (POST)
```

**Template `assignments/alert_list.html`:**
- Amber header for Open alerts, grey for Resolved/Dismissed
- Each row: holder name, source badge, raised date, asset count, Resolve/Dismiss HTMX buttons
- Resolve/Dismiss opens a mini modal for note input

**Sidebar change:** Add "Alerts" nav item with open-alert count badge; this replaces the current disabled "Alerts" link.

**Batch transfer (stretch goal for this session):**
- Asset list: checkbox column (hidden unless IT Officer)
- "Transfer Selected" sticky bar appears when ≥1 asset checked
- Links to batch transfer wizard (existing `TransferBatch` model)

**Permission:** `alert_list` → `viewer_required`; resolve/dismiss → `it_officer_required`

---

### Session 6.6 — Reports polish, Audit sessions, User management

**Scope:** Fill remaining gaps — reports in right places, audit UI, basic user management.

**Reports placement:**
- Asset list topbar: "Export" dropdown (Current Inventory Excel, Warranty Report)
- Asset detail topbar: already has History XLS + Handover PDF + Disposal PDF — add "Transfer Log for this asset" link
- Assignment history table: per-row "Handover PDF" link
- Reports sidebar link already active — keep as central catalog

**Audit session UI (`qrcodes/views.py`):**
- `audit_list` — list of AuditSessions with status, date, scan counts
- `audit_start` (POST) — create new AuditSession; returns to session detail
- `audit_detail` — show scanned assets, missing assets (in-stock but not scanned), unexpected assets
- `audit_complete` (POST) — mark session complete

**URL patterns:**
```
qr/audits/                 → audit_list
qr/audits/start/           → audit_start (POST)
qr/audits/<pk>/            → audit_detail
qr/audits/<pk>/complete/   → audit_complete (POST)
```

**User management page (Admin only, `config/views.py`):**
- `user_list` — list all users with group badges, last login, active status
- `user_create` (GET/POST) — create user + assign groups
- `user_edit` (GET/POST) — change groups, active status, reset password link
- Accessible via sidebar Admin section

**URL patterns:**
```
users/                     → user_list
users/new/                 → user_create
users/<pk>/edit/           → user_edit
```

**Permission:** All user management → `admin_required`

---

### What else is necessary (not explicitly requested but essential)

1. **Asset type selector in asset form is HTMX-powered** — when type changes, spec fields re-render dynamically from `spec_schema`
2. **Duplicate asset tag warning** — HTMX live check on asset tag field during create
3. **Inactive/API-source guard on holder edit** — API-sourced holders show read-only badge; only manual holders are editable
4. **Pagination on all list pages** — employees, MPs, offices, locations, alerts, audit sessions (use Django Paginator, 25/page)
5. **"Assign Asset" entry point from holder detail** — from Employee/MP/Office detail, click "Assign Asset" → asset search → assign flow
6. **Dashboard quick-action cards** — "Add Asset", "Assign Asset", "Run Sync", "View Alerts" — replace current static quick-action list
7. **Breadcrumb consistency** — all new pages need correct breadcrumb block
8. **403 shown for Viewer on write actions** — already wired but confirm UI hides write buttons for Viewers using `user_is_it_officer` template flag

---

### Session execution order

| Session | Effort | Dependency |
|---|---|---|
| **6.1** Asset CRUD + Import | Large | ✅ Complete |
| **6.2** Location CRUD | Medium | None — can be parallel |
| **6.3** Employee/MP/Office lists | Large | None |
| **6.4** Custom Sync page | Medium | 6.3 (needs entity context) |
| **6.5** Assignment from list + Alerts | Medium | 6.1 (asset list changes) |
| **6.6** Reports polish + Audit + Users | Medium | 6.1, 6.3, 6.5 |

---

## Deployment Checklist (when ready for production)

- [ ] UAT with Software Development Branch team (after 6.x sessions)
- [ ] Backup/restore drill (PostgreSQL pg_dump + restore test)
- [ ] Production SSL certs installed at `nginx/ssl/`
- [ ] `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`
- [ ] Superuser creation + group assignment for pilot users
- [ ] Load real asset data via Excel import
- [ ] Verify PRP API credentials in `.env`