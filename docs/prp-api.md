# PRP API — Full Specification

> Auth, endpoints, and sync flow are in CLAUDE.md. This file has field mappings, error handling, and manual holder rules.

**Base URL:** `https://prp.parliament.gov.bd`  
**Credentials:** `.env` → `PRP_API_USERNAME` / `PRP_API_PASSWORD` — never hardcoded.

---

## Field Mappings

### EmployeeInformation → CachedEmployee

| API Field | Cache Field | Notes |
|---|---|---|
| `prpId` (String) | `prp_id` | Primary sync key (unique) |
| `nameEn` | `name_en` | Used in snapshots |
| `nameBn` | `name_bn` | Bengali name |
| `mobile` | `mobile` | Nullable |
| `telephone` | `telephone` | Nullable |
| `status` | `api_status` | Raw value from API |
| `gender` | `gender` | Nullable |
| `photo` | `photo_url` | Full URL (e.g. `https://prp.parliament.gov.bd/api/files?_=…`), store as-is |
| `class` (int) | `employee_class` | 1–4 = gazetted classes; 5 = no class. **Added 2026-05.** |
| `designationEn` | `designation_en` | English designation text. **Added 2026-05.** |
| `designationBn` | `designation_bn` | Bengali designation text. **Added 2026-05.** |
| `officeDetails` (Object) | flattened — see below | Null/absent → employee has no office assigned; skip on first sync |

### MPInformation → CachedMP

| API Field | Cache Field | Notes |
|---|---|---|
| `prpId` (String) | `prp_id` | Primary sync key |
| `parliamentNo` (int) | `parliament_no` | e.g. 12 |
| `constituency` | `constituency` | Electoral area |
| `nameEn` | `name_en` | Used in snapshots |
| `nameBn` | `name_bn` | Bengali name |
| `mobile` | `mobile` | Nullable |
| `telephone` | `telephone` | Nullable |
| `status` | `api_status` | |
| `gender` | `gender` | Nullable |
| `photo` | `photo_url` | |
| `officeDetails` (String) | `office_details_raw` | **String, not Object** — parse if structured |

### OfficeInformation → CachedOffice

| API Field | Cache Field | Notes |
|---|---|---|
| `id` (Long) | `prp_id` | Primary sync key |
| `parentId` (Long) | `parent_prp_id` | Nullable — for office hierarchy |
| `nameEn` | `name_en` | Used in snapshots |
| `nameBn` | `name_bn` | Bengali name |
| `isAbstractOffice` (Bool) | `is_abstract` | Grouping node vs real office |

### OfficeDetails (nested in EmployeeInformation)

| API Fields | Cache Fields |
|---|---|
| `wingId` / `wingNameEn` / `wingNameBn` | `wing_id` / `wing_name_en` / `wing_name_bn` |
| `branchId` / `branchNameEn` / `branchNameBn` | `branch_id` / `branch_name_en` / `branch_name_bn` |
| `sectionId` / `sectionNameEn` / `sectionNameBn` | `section_id` / `section_name_en` / `section_name_bn` |
| `unitId` / `unitNameEn` / `unitNameBn` | `unit_id` / `unit_name_en` / `unit_name_bn` |
| `officeId` / `officeNameEn` / `officeNameBn` | `office_id` / `office_name_en` / `office_name_bn` |

Snapshot designation string: `"{designationEn} — {sectionNameEn}, {branchNameEn}, {wingNameEn}"`  
If `designationEn` is absent, fall back to the old pattern `"{sectionNameEn}, {branchNameEn}, {wingNameEn}"`.

---

## Employee Sync — Office-Filter Rules

Employees without an assigned office are not useful for asset tracking. Apply these rules in `_sync_employees()`:

| Situation | Action |
|---|---|
| API record has `officeDetails` (not null/absent) | Sync normally — `update_or_create` as before |
| API record has **no** `officeDetails` — employee **does not exist** in DB yet | Skip entirely — do not create |
| API record has **no** `officeDetails` — employee **exists** in DB — **has asset history** | Flag `is_active=False`; keep record; raise `InactiveHolderAlert` if active assignment |
| API record has **no** `officeDetails` — employee **exists** in DB — **no asset history** | Hard-delete from DB (`CachedEmployee.objects.filter(...).delete()` + delete matching `Assignee` row) |

> **Exception to soft-delete rule:** This hard-delete only applies to `CachedEmployee` records with `source="PRP_API"` that have never held an asset. Manual records are never deleted by sync.

---

## Sync Error Handling

| Scenario | Behaviour |
|---|---|
| API timeout / connection error | Log error, show "Sync Failed" on dashboard. Do NOT modify any cache records. |
| Partial response (some endpoints fail) | Sync succeeded endpoints only; record which failed in `SyncLog`. |
| Token expired mid-sync | Re-authenticate once, retry failed request. Fail if second attempt also fails. |
| Rate limiting | Respect `Retry-After` header. |

---

## Manual Holder Creation

**When:** A holder needs assets but doesn't exist in the PRP API (contractor, external consultant, newly posted employee not yet in PRP).

**Rules:**
- Available to Admin and IT Officer roles
- Required fields: `name_en` + designation / department (minimum for a useful snapshot)
- Optional: `name_bn`, mobile, photo
- Manual records appear alongside API records in all search / assign dialogs
- UI must visually distinguish source — badge or icon (API = blue, Manual = gold)
- Before creating: search existing records (both sources) and warn on similar name — no hard block, officer may legitimately need it
- IT Officer can manually flag a manual record inactive
- `source="MANUAL"` records are completely invisible to sync — sync always filters `source="PRP_API"`

**Key invariant:** MANUAL records are sync-proof. Sync never reads, writes, or flags them.
