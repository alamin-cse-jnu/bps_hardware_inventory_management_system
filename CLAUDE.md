# Parliament IT Inventory Management System

Web-based IT hardware asset tracking for the Bangladesh National Parliament Secretariat. Tracks every physical IT asset from procurement to disposal.

**Scale:** 1,000–5,000 assets · ~50,000 historical rows · 10–20 concurrent users · <500ms common queries  
**Deployment:** Parliament intranet · Docker · Nginx + Gunicorn

---

## Tech Stack

Django 5.x · PostgreSQL (JSONField for specs) · Django templates + HTMX · `qrcode` / `openpyxl` / `WeasyPrint` · Celery + Redis · Django Allauth (RBAC + 2FA) · Nginx + Gunicorn · Docker

---

## Design System

**Full reference:** `docs/design-system.md`
- Sidebar: `#0076A7` (Parliament Blue) — NOT dark, NOT green
- Primary button: `#0076A7` hover `#005d85` · Login page only: `#13122A` bg + `#6D5AE6` CTA
- Asset tags: `JetBrains Mono`, color `#0076A7`
- Destructive actions: `#EF4444` with confirmation step

---

## Django Apps

| App | Responsibility |
|-----|----------------|
| `assets` | Asset catalog: categories, types, spec schemas, items, components |
| `catalogue` | Centrally-managed master data: 4-level cascade (Main=AssetCategory → Sub=AssetType → CatalogBrand → CatalogModel) + per-Sub `SubAssetSpecField` schema; JSON dropdown API + single Master Data admin page |
| `assignees` | Cached Employee/MP/Office records + unified Assignee layer |
| `assignments` | Assignment records, holder snapshots, TransferBatch for bulk moves |
| `lifecycle` | Events: maintenance, lost, damaged, disposed, component swaps |
| `locations` | Self-referential hierarchy: building → floor → room |
| `qrcodes` | QR generation, mobile scan views, physical audit sessions |
| `sync_prp` | PRP API synchronisation + inactive holder detection |
| `reports` | Tabular view pages + Excel/PDF downloads |

---

## Core Architecture (NON-NEGOTIABLE)

1. **Parent + child components** — PC Set is one unit; components are `AssetComponent` records with their own history.
2. **Unified Assignee table (NO GenericForeignKey)** — One table, four FK fields (employee/mp/office/location). Exactly one populated per `assignee_type`.
3. **Immutable assignment rows** — Transfer closes old row (`returned_at`), opens new one. Closed rows never modified.
4. **Assignee snapshot (JSONField)** — Freezes name/designation/department at assignment time. History shows designation held AT THAT TIME.
5. **TransferBatch for bulk operations** — Groups transitions under one reference. Each asset can have a DIFFERENT destination.
6. **Status state machine** — Strict transitions enforced in `clean()` / `change_status()`. Never skipped.
7. **Dual-source holders** — `source="PRP_API"` owned by sync; `source="MANUAL"` invisible to sync, never flagged inactive.
8. **QR code identification** — Every asset has a QR (encodes asset tag). Mobile scan → action page.
9. **Inactive holder alerts (flag, NEVER delete)** — Absent from API → flag + raise `InactiveHolderAlert`. No auto-returns.

---

## Status State Machine

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

| Role | Can Do | Cannot Do |
|------|--------|-----------|
| Admin | Everything incl. catalog, users, soft-delete (2FA enforced) | — |
| IT Officer | Add assets, assign/transfer, lifecycle events, sync, audits | Manage catalog/types, delete, manage users |
| Viewer | View assets/holders/history, download reports | Any modification |

Decorators: `viewer_required` / `it_officer_required` / `admin_required` in `config/permissions.py`.  
Template flags: `user_is_admin` / `user_is_it_officer` / `user_is_viewer` from `config/context_processors.py`.

---

## Security & Conventions

- Soft-delete ONLY — `is_deleted` + `deleted_at`, never `Model.delete()`
- 2FA for Admin (TOTP via `allauth.mfa`, enforced by `AdminMFARequiredMiddleware`)
- Secrets in `.env` via `django-environ`/`python-decouple`, never hardcoded
- Models: always `created_at`, `updated_at` · `created_by`/`updated_by` where relevant
- Tests: cover state machine transitions and edge cases

---

## PRP API

**Base URL:** `https://prp.parliament.gov.bd` · credentials: `PRP_API_USERNAME` / `PRP_API_PASSWORD` in `.env`  
**Full field mappings, sync flow, error handling:** `docs/prp-api.md`

---

## Performance

**Full reference:** `docs/performance.md`
- **Never reference a CDN from a template** — the intranet has no route out, so an external `<link>`/`<script>` hangs the page until it times out. Vendor into `static/vendor/`, reference with `{% static %}`.
- Paginate every list view — `config/pagination.py` + `{% include "partials/pagination.html" %}`
- Role checks go through `config.permissions._group_names` (memoised); aggregate counts, don't loop them

---

## Assignee Layer — Important Notes

`Assignee` is a unified wrapper over `CachedEmployee`, `CachedMP`, `CachedOffice`, `Location`. Must be kept in sync:
- **PRP sync** — `_sync_employees/mps/offices` call `Assignee.objects.get_or_create(...)` after every `update_or_create`. Inactive cached records set `Assignee.is_active=False`.
- **Locations** — `Location.sync_assignee()` upserts the `Assignee(LOCATION)` row and mirrors `is_active` onto it. Call it after **every** save that can change `is_active`, not just on create: `_save_location` (the edit form has an is_active checkbox, so locations reactivate too) and `location_delete`. A LOCATION assignee has no independent lifecycle — leaving it active after deactivating the location is what puts dead locations back in the assign panel.
- **Manual assignee creation** (`assignees/views.py`) — creates an `Assignee` row on save.

The assign-panel search (`assignees:search`) queries `Assignee` directly. Missing rows = empty search results.

---

## Reports App Architecture (Phase 8)

- **Column registry** — `reports/columns.py`: `INVENTORY_COLS`, `TRANSFER_LOG_COLS`, `LIFECYCLE_COLS`, `WARRANTY_COLS`, `HOLDER_ASSIGNMENTS_COLS`, `ASSET_HISTORY_COLS` + `parse_cols(request, col_list) -> list[str]`
- **Column state in URL** — `?cols=col1,col2,...` (bookmarkable; download links inherit via `{{ request.GET.urlencode }}`)
- **Excel generators** — `reports/generators/excel.py`: all 6 generators accept `columns: list[str] | None = None`
- **Tabular PDF** — `tabular_pdf(title, subtitle, column_labels, rows, generated_at)` in `generators/pdf.py`, template `reports/pdf/tabular.html` (A4 landscape, 8pt, Parliament Blue header, alternating rows)
- **View pages** — paginated (25/50/100, default 50), `?page=`, `?per_page=`; SL column always first, never in picker
- **Private row dict keys** — `_detail_url`, `_status_raw`, `_is_active`, `_old_status_raw`, `_new_status_raw`, `_warranty_days_color`, `_amc_days_color` carry rendering hints without polluting column namespace
- **Cap warning** — Transfer Log and Lifecycle views show yellow banner when results hit 5,000 row limit. Use `list(qs[:5000])` (not sliced QuerySet) to avoid Paginator `.count()` error.
- **Template tag** — `reports/templatetags/report_tags.py`: `get_item` filter for dict access by variable key

---

## Catalogue App — Cascading Master Data (Phase 9)

Centrally-managed catalogue replacing the old 3 admin pages (Asset Catalog / Dropdowns / Spec Options) with one **Master Data** page (`/catalogue/manage/`, Admin only).

- **Hierarchy** — Main Asset (`AssetCategory`) → Sub Asset (`AssetType`) → `CatalogBrand` (FK Sub) → `CatalogModel` (FK Brand). Levels 1–2 reuse existing models; `AssetItem` schema is untouched (still `asset_type` FK + `brand`/`model_name` CharFields).
- **Spec schema** — `SubAssetSpecField` per Sub Asset: `widget` ∈ {text, number, units, select, toggle} + `options`/`unit`. Master-data-driven replacement for the old hardcoded spec widgets + `SpecChoice`. Helpers in `catalogue/specs.py` (`collect_values`, `form_values`, `display_rows`).
- **Dependent dropdown JSON API** (honours `is_active=True`) — `/catalogue/sub-assets/?main=`, `/brands/?sub=`, `/models/?brand=`, `/spec/?model=`. Consumed by the Add/Edit/Bulk asset forms via `templates/catalogue/partials/cascade_script.html`; spec widgets load through the existing `assets:spec_fields` HTMX endpoint (re-pointed to `SubAssetSpecField`).
- **Seed** — `python manage.py seed_catalogue` (idempotent) loads `docs/Asset_Master_Data_Polished.xlsx` → 6 Main / 18 Sub / 51 Brand / 137 Model / 73 spec fields.
- **Legacy** — old `assets` catalog/dropdowns/spec-choices routes/views remain (unlinked from nav) so legacy `Brand`/`AssetModelName`/`SpecChoice` data isn't orphaned. Vendors are managed from a section on the Master Data page.

## Office-wise Asset List (Phase 11)

Assets grouped by office placement, with the merged-cell Excel layout from
`docs/office wise asset list.xlsx`. Routes: `/reports/view/office-assets/` +
`/reports/excel/office-assets/` (Viewer and above).

- **Hierarchy** — Wing → Branch → Section. Wings are derived as the children of
  whichever node the employee `wing_id`s sit under (SECRETARY in prod) — no
  prp_id is hardcoded. Filtering uses the denormalised
  `CachedEmployee.wing_id / branch_id / section_id`, which match the
  `CachedOffice` parent tree exactly (verified: 0 mismatches over 1,212 branch
  and 1,103 section placements). Units fold into their parent section.
- **Selection** — multi-select per level, `?wing=56,69&branch=66&wing_only=1`.
  Each level has an "only the selected office" flag meaning *staff at that node
  itself* (`wing_only` → `branch_id=""`, `branch_only` → `section_id=""`,
  `section_only` → `unit_id=""`).
- **Narrowing rule** — a wing term is dropped when a branch beneath it is also
  selected (unless `wing_only` is set); likewise branch/section. Without this,
  picking a branch would be a no-op, since its wing must be selected first for
  the branch to appear in the dropdown. `scope_terms()` in
  `reports/office_scope.py` is the single source of truth — both the employee
  `Q` and the office-holder predicate derive from it, so they cannot drift.
- **Columns** — `SL` · `Holder`/`Designation`/`Wing`/`Branch`/`Section` ·
  `Category`/`Asset Type` · `Brand`/`Model`/`Serial Number`/`Asset Tag`
  (serial number sits before the tag, which closes the row).
- **Merge geometry** — `SL` + `Holder…Section` merge across the holder's whole
  row block; `Category`/`Asset Type` merge across consecutive equal runs
  *within* a block; `Brand`/`Model`/`Serial Number`/`Asset Tag` never merge;
  merges never cross a holder boundary. Spans are computed once by `office_assets.annotate_runs()`
  and consumed by both the HTML `rowspan` and the Excel `merge_cells`.
- **SL column** — Excel column A, numbering *holders* not rows, merged down its
  holder's block (matches the `#` column on the view page).
- **Borders** — thin grid over the header and all data cells, applied to every
  constituent cell of a merged range (Excel draws a merged block's edges from
  the cells beneath it, so bordering only the anchor loses the bottom edge).
  Note openpyxl's *reader* reports `MergedCell` styles as default no matter
  what the file holds, so border coverage must be asserted against the written
  XML — a round-trip read cannot see it.
- **Fixed columns** — no column picker: merge geometry is defined in terms of
  these exact column groups.
- **Ordering** — Wing → Branch → Section → staff → the office's own assets
  last within its node. Rows within a holder sort Category → Type → Tag so the
  merge runs are maximal. Missing levels render as `…`.
- **Pagination is by holder**, never by row, so a merged block is never split
  across pages.
- **Included** — employee holders plus `OFFICE`-type assignees; inactive
  employees still holding assets appear flagged (never dropped — decision #9).
  Placement is read live from `CachedEmployee`, not `holder_snapshot`.

## Office Change Alerts (Phase 12)

Second alert stream alongside Inactive Holder Alerts: PRP employees who **moved
to a different office** while still holding assets. Routes:
`/assignments/office-changes/` (Viewer and above) +
`/assignments/office-changes/<pk>/` (IT Officer, HTMX panel).

- **Model** — `assignments.OfficeChangeAlert`: `assignee` FK, `old_placement` /
  `new_placement` JSON snapshots, `detected_at`, plus the same
  `AlertStatus` / `resolve()` / `dismiss()` / `note` / `resolved_by` surface as
  `InactiveHolderAlert`. `detected_at` is a plain default (not `auto_now_add`)
  so a second move can refresh an open alert.
- **Detection** — `_maybe_raise_office_change_alert()` in `sync_prp/services.py`,
  called from `_sync_employees` after each `update_or_create` of an *existing*
  record. `_sync_employees` reads every PRP employee's placement into
  `placements_before` in one query up front, so spotting a move costs no extra
  SELECT per employee.
- **What counts as a move** — only the ids
  (`wing_id/branch_id/section_id/unit_id/office_id`, `PLACEMENT_ID_FIELDS`)
  are compared, via `placement_ids()`. A PRP-side *rename* of a wing/branch/
  section therefore raises nothing. Names are stored anyway so an old alert
  still reads correctly after a rename. `placement_of()` / `placement_path()`
  live in `assignments/models.py` next to them.
- **Raised only for holders with active assignments** — mirrors
  `_maybe_raise_alert`. An employee first seen this run has no "before"
  placement and never alerts.
- **Repeat moves** — while an alert is OPEN, a further move advances
  `new_placement` and `detected_at` but keeps the original `old_placement`
  (that is where the assets were last confirmed). After resolve/dismiss, the
  next move raises a fresh alert.
- **Actions** — identical to the inactive-holder panel: per-asset **Transfer**
  and **Return to Stock** buttons plus **Resolve**/**Dismiss** with an optional
  note. Nothing is ever moved automatically (architectural decision #9).
- **Nav** — own sidebar item under Monitoring with its own badge
  (`open_office_changes_count`, cached under `OFFICE_CHANGE_COUNT_CACHE_KEY`,
  invalidated by a post_save/post_delete signal like the alert badge). The
  Alerts item's active-state check now excludes `office_change` url names so
  only one item highlights.

## Current State

**Phases 1–12: ✅ All complete · 404 tests**

| Phase | Scope | Status |
|-------|-------|--------|
| 1–5 | Models, migrations, core logic, QR, sync, RBAC | ✅ Complete |
| 6 | Main UI — Asset CRUD, Location, Employee/MP/Office, Sync, Assign, Reports | ✅ Complete |
| 7 | Employee/MP/Office UI overhaul — class tabs, photos, hierarchy browser | ✅ Complete |
| 8 | Report tabular views — column picker, pagination, Excel + PDF download | ✅ Complete |
| 9 | Catalogue — cascading Master Data page, spec schema, seed command | ✅ Complete |
| 10 | Performance — vendored assets, pagination, caching, nginx gzip | ✅ Complete |
| 11 | Office-wise Asset List — Wing/Branch/Section scope, merged-cell Excel | ✅ Complete |
| 12 | Office Change Alerts — flag holders who moved office, transfer/return/dismiss | ✅ Complete |

**Known failing tests (pre-existing, unrelated to Phase 10):**
`audit.tests.test_assignment_logs_assign` creates an `Assignment` without
`holder_snapshot`, which is `NOT NULL` with no default — it cannot pass as
written. `assets.tests.test_invalid_date_format_fails` and
`test_template_fixed_columns_in_data_entry` expect Excel headers without the
`(YYYY-MM-DD)` suffix the generator now emits.

**Dev fixtures:** 5 categories · 12 asset types · 15 locations · RBAC groups
