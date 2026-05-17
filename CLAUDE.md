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

**Phases 1–7: ✅ All complete · 247 tests passing | Phase 8: 🔜 Planned**

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
| Report infrastructure + index      | 🔜 Session 8.1              |
| Inventory + Holder Assignments UI  | 🔜 Session 8.2              |
| Transfer Log + Lifecycle Events UI | 🔜 Session 8.3              |
| Warranty/AMC + Asset History UI    | 🔜 Session 8.4              |

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

---

## Phase 8 — Report Tabular Views (column-selectable in-browser + dual download)

**Goal:** Every report type gets an in-system tabular view page. Users choose which columns to display, then download Excel or PDF containing only those columns.

### Architecture decisions (apply to all Phase 8 sessions)

- **Column state in URL** — `?cols=col1,col2,...` (comma-separated keys). Makes pages bookmarkable; download links inherit the selection automatically via `{{ request.GET.urlencode }}`.
- **Central column registry** — `reports/columns.py` defines `(key, label)` pairs per report type in canonical display order.
- **Excel generators** — each gets an optional `columns: list[str] | None = None` param. `None` = all columns (fully backward compatible with existing download links).
- **Tabular PDF** — a new `tabular_pdf(title, subtitle, column_labels, rows, generated_at)` function in `pdf.py`, rendered via a shared `reports/pdf/tabular.html` WeasyPrint template. Separate from the existing per-record handover/disposal PDFs, which are unchanged.
- **Download links on view pages** — "Download Excel" and "Download PDF" buttons are `<a>` tags pointing to their respective download URLs with `?{{ request.GET.urlencode }}` appended. No JS needed to wire them up.
- **Pagination on view pages** — `?page=` (default 1) and `?per_page=` (25 / 50 / 100; default 50).
- **SL column** — always rendered as the first column in the table regardless of `?cols=`; never in the column picker.

---

### Session 8.1 — Infrastructure

**Goal:** Shared building blocks all view sessions depend on. No view pages yet — just foundation code and index redesign.

**Steps:**

1. Create `reports/columns.py` — define column lists as `list[tuple[str, str]]` (`key`, `label`):

   ```python
   INVENTORY_COLS = [
       ("asset_tag", "Asset Tag"), ("category", "Category"), ("type", "Type"),
       ("brand", "Brand"), ("model", "Model"), ("serial_no", "Serial No."),
       ("status", "Status"), ("storage_location", "Storage Location"),
       ("current_holder", "Current Holder"), ("holder_type", "Holder Type"),
       ("assigned_since", "Assigned Since"), ("purchase_date", "Purchase Date"),
       ("warranty_expiry", "Warranty Expiry"), ("amc_expiry", "AMC Expiry"),
   ]
   TRANSFER_LOG_COLS = [
       ("transfer_date", "Transfer Date"), ("asset_tag", "Asset Tag"),
       ("category", "Category"), ("type", "Type"), ("brand", "Brand"),
       ("model", "Model"), ("assigned_to", "Assigned To"),
       ("holder_type", "Holder Type"), ("designation", "Designation"),
       ("status", "Status"), ("performed_by", "Performed By"),
       ("batch_ref", "Batch Ref"), ("notes", "Notes"),
   ]
   LIFECYCLE_COLS = [
       ("date", "Date"), ("asset_tag", "Asset Tag"), ("category", "Category"),
       ("type", "Type"), ("brand", "Brand"), ("model", "Model"),
       ("event", "Event"), ("old_status", "Old Status"), ("new_status", "New Status"),
       ("notes", "Notes"), ("performed_by", "Performed By"),
   ]
   WARRANTY_COLS = [
       ("asset_tag", "Asset Tag"), ("category", "Category"), ("type", "Type"),
       ("brand", "Brand"), ("model", "Model"), ("status", "Status"),
       ("current_holder", "Current Holder"), ("warranty_expiry", "Warranty Expiry"),
       ("warranty_days", "Days (WTY)"), ("amc_expiry", "AMC Expiry"),
       ("amc_days", "Days (AMC)"),
   ]
   HOLDER_ASSIGNMENTS_COLS = [
       ("holder", "Holder"), ("holder_type", "Holder Type"),
       ("designation", "Designation"), ("department", "Department"),
       ("asset_tag", "Asset Tag"), ("category", "Category"),
       ("asset_type", "Asset Type"), ("brand", "Brand"), ("model", "Model"),
       ("status", "Status"), ("assigned_since", "Assigned Since"),
   ]
   ASSET_HISTORY_COLS = [
       ("assigned_to", "Assigned To"), ("holder_type", "Holder Type"),
       ("designation", "Designation"), ("department", "Department"),
       ("from_date", "From Date"), ("to_date", "To Date"), ("days", "Days"),
       ("performed_by", "Performed By"), ("batch_ref", "Batch Ref"), ("notes", "Notes"),
   ]
   ```

   Also add `parse_cols(request, col_list) -> list[str]`: reads `?cols=`, validates each key against `col_list`, returns valid keys or all keys if none given / none valid.

2. Refactor all 6 Excel generators in `generators/excel.py`:
   - Add `columns: list[str] | None = None` param to each function signature.
   - Compute effective column set: `cols = columns if columns else [k for k, _ in COL_LIST]`.
   - Build header row and each data row using only those keys (in that order).
   - Map each key to its value via a local `row_dict` (key → value) per data row.

3. Add `tabular_pdf(title, subtitle, column_labels, rows, generated_at) -> bytes` to `generators/pdf.py`:
   - `column_labels`: `list[str]` — already-filtered header strings.
   - `rows`: `list[list]` — cell values (already computed by the view).
   - Calls `_render_pdf("reports/pdf/tabular.html", {...})`.

4. Create `templates/reports/pdf/tabular.html`:
   - Parliament letterhead: logo data URL + "Bangladesh Parliament Secretariat · IT Inventory".
   - Report title (large) + subtitle (small, italic) + generated date.
   - `<table>` with Parliament Blue (`#0076A7`) header row, white header text, alternating row fill (`#E8F3F8`).
   - Page layout: A4 landscape, 1cm margins, font-size 8pt (Calibri/Arial fallback).
   - Footer: "Generated on {date} · Bangladesh Parliament Secretariat" + page numbers via CSS `@page` counter.

5. Update `templates/reports/index.html`:
   - Each report card gets a "View Report" button (`btn btn-primary`) that links to the new view URL, placed above the filter form.
   - Existing filter forms + "Download Excel" buttons become secondary (outline style).
   - Update heading copy: "Download Excel and PDF reports" → "View and download reports".

---

### Session 8.2 — Inventory + Holder Assignments Views

**URLs:**
- `reports/view/inventory/` → `view_inventory` (name: `reports:inventory_view`)
- `reports/view/holder-assignments/` → `view_holder_assignments` (name: `reports:holder_assignments_view`)
- `reports/pdf/inventory/` → `download_inventory_pdf` (name: `reports:inventory_pdf`)
- `reports/pdf/holder-assignments/` → `download_holder_assignments_pdf` (name: `reports:holder_assignments_pdf`)

**Steps:**

1. Add view functions to `reports/views.py`:

   `view_inventory(request)`:
   - Parse filters: `status`, `category`, `type` (same as `download_inventory`).
   - Parse cols via `parse_cols(request, INVENTORY_COLS)`.
   - Parse `per_page` (25/50/100, default 50) and `page`.
   - Build queryset: same as `inventory_excel` (non-deleted assets + active assignment join).
   - Paginate with Django `Paginator`.
   - Compute `rows` — list of dicts keyed by column key; template iterates `selected_cols` to render each cell.
   - Context: `selected_cols`, `all_cols` (full `INVENTORY_COLS` list), `page_obj`, `per_page`, filter values.

   `view_holder_assignments(request)`:
   - Same pattern; parse `holder_type` filter.

2. Add PDF download views:

   `download_inventory_pdf(request)`:
   - Parse same filters + `?cols=`.
   - Build full queryset (no pagination, cap at 5000 rows).
   - Compute `rows` as list of lists matching selected column order.
   - Call `tabular_pdf(title, subtitle, labels, rows, generated_at)` → `_pdf_response(...)`.

   `download_holder_assignments_pdf(request)`: same pattern.

3. Update existing `download_inventory` and `download_holder_assignments` Excel views to read `?cols=` and pass to generator.

4. Add 4 URL patterns to `reports/urls.py` (2 view + 2 PDF).

5. Create `templates/reports/view_inventory.html` (extend `base.html`):

   **Layout (top to bottom):**
   - Breadcrumb: `Reports → Current Inventory`
   - Page header: title + row count badge ("1,234 assets") + action bar (Download Excel, Download PDF — both `<a>` tags with `?{{ request.GET.urlencode }}`).
   - **Filter panel** (card, collapsible via `<details>`): Status / Category / Type selects + Apply button (GET form, preserves `cols` in a hidden input).
   - **Column picker panel** (card): checkbox grid (wrap layout, ~4 per row). "Select All" / "Clear All" are `<a>` JS helpers that check/uncheck all boxes. "Apply Columns" submits the form (GET, preserves current filters).
   - **Data table**: `<table class="table">` — SL + selected columns only. Pagination footer below table.
   - **Pagination**: prev/next links + page info + per_page switcher (25/50/100) that preserves all other params.

   `templates/reports/view_holder_assignments.html`: identical layout; filter = holder_type only.

---

### Session 8.3 — Transfer Log + Lifecycle Events Views

**URLs:**
- `reports/view/transfer-log/` → `view_transfer_log` (name: `reports:transfer_log_view`)
- `reports/view/lifecycle/` → `view_lifecycle` (name: `reports:lifecycle_view`)
- `reports/pdf/transfer-log/` → `download_transfer_log_pdf` (name: `reports:transfer_log_pdf`)
- `reports/pdf/lifecycle/` → `download_lifecycle_pdf` (name: `reports:lifecycle_pdf`)

**Steps:** Same pattern as Session 8.2.

**Filter specifics:**
- Transfer Log: `date_from`, `date_to` date inputs.
- Lifecycle Events: `date_from`, `date_to` date inputs + `event_type` select.

**Cap warning:** If queryset row count reaches 5000 (the generator cap), show a yellow info banner above the table: "Results capped at 5,000 rows. Narrow the date range to see more."

**Template column notes:**
- Transfer Log `status` cell: render "Active" (green badge) or "Returned DD Mon YYYY" (grey badge).
- Lifecycle Events `old_status` / `new_status`: use `AssetItem.Status(val).label` for human-readable display.

---

### Session 8.4 — Warranty/AMC + Asset History Views

**URLs:**
- `reports/view/warranty/` → `view_warranty` (name: `reports:warranty_view`)
- `reports/view/asset-history/<int:pk>/` → `view_asset_history` (name: `reports:asset_history_view`)
- `reports/pdf/warranty/` → `download_warranty_pdf` (name: `reports:warranty_pdf`)
- `reports/pdf/asset-history/<int:pk>/` → `download_asset_history_pdf` (name: `reports:asset_history_pdf`)

**Steps:**

1. `view_warranty(request)`:
   - Parse `days` (int, 1–3650, default 90).
   - Parse `?cols=` via `parse_cols(request, WARRANTY_COLS)`.
   - Build queryset: same as `warranty_expiry_excel`.
   - Compute `warranty_days` / `amc_days` as integers (or `""` if no date).
   - Paginate (50/page default).
   - Colour-code `warranty_days` / `amc_days` cells in template: ≤ 0 → red; ≤ 30 → orange; else default.

2. `view_asset_history(request, pk)`:
   - `get_object_or_404(AssetItem, pk=pk, is_deleted=False)`.
   - Parse `?cols=` via `parse_cols(request, ASSET_HISTORY_COLS)`.
   - No pagination (single-asset history, rarely > 100 rows).
   - Render asset header card (tag, type, brand/model, current status) above the table.
   - Column picker + dual download still apply.

3. PDF download views: `download_warranty_pdf`, `download_asset_history_pdf` — same pattern as 8.2.

4. Update existing `download_asset_history` Excel view to accept `?cols=`.

5. Add URL patterns.

6. Create templates:
   - `templates/reports/view_warranty.html` — filter: `days` input; no cap warning (warranty queries are naturally small).
   - `templates/reports/view_asset_history.html` — asset header card above column picker; breadcrumb: `Assets → [Tag] → History`.

7. **Link from asset detail page**: add "View History" button (alongside existing "Download Excel History") that links to `{% url 'reports:asset_history_view' asset.pk %}`.

8. Update `templates/reports/index.html` to add "View Report" link for Warranty/AMC card pointing to `reports:warranty_view`.
