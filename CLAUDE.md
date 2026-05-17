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

## Assignee Layer — Important Notes

`Assignee` is a unified wrapper over `CachedEmployee`, `CachedMP`, `CachedOffice`, `Location`. Must be kept in sync:
- **PRP sync** — `_sync_employees/mps/offices` call `Assignee.objects.get_or_create(...)` after every `update_or_create`. Inactive cached records set `Assignee.is_active=False`.
- **Location creation** (`locations/views.py` → `_save_location`) — creates an `Assignee(LOCATION)` row.
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

## Current State

**Phases 1–8: ✅ All complete · 247 tests passing**

| Phase | Scope | Status |
|-------|-------|--------|
| 1–5 | Models, migrations, core logic, QR, sync, RBAC | ✅ Complete |
| 6 | Main UI — Asset CRUD, Location, Employee/MP/Office, Sync, Assign, Reports | ✅ Complete |
| 7 | Employee/MP/Office UI overhaul — class tabs, photos, hierarchy browser | ✅ Complete |
| 8 | Report tabular views — column picker, pagination, Excel + PDF download | ✅ Complete |

**Dev fixtures:** 5 categories · 12 asset types · 15 locations · RBAC groups
