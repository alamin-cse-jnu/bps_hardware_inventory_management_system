# Parliament IT Inventory System — User Manual

**Parliament of Bangladesh · IT Division**  
Version 1.0 · June 2026

---

## Table of Contents

1. [Overview](#1-overview)
2. [Login & Dashboard](#2-login--dashboard)
3. [Assets](#3-assets)
4. [Assign & Transfer](#4-assign--transfer)
5. [Active Holders](#5-active-holders)
6. [Alerts](#6-alerts)
7. [Lifecycle Events](#7-lifecycle-events)
8. [QR Codes](#8-qr-codes)
9. [Audits](#9-audits)
10. [Reports](#10-reports)
11. [Quick Reference](#11-quick-reference)

---

## 1. Overview

The Parliament IT Inventory System tracks every IT hardware asset — from the moment it is purchased to the day it is disposed of. It records who holds each asset, where it is, and what has happened to it over time.

### Roles

| Role | What they can do |
|------|-----------------|
| **Admin** | Everything — including managing users, asset catalog, and soft-deleting records |
| **IT Officer** | Add and edit assets, assign/transfer, record lifecycle events, run audits |
| **Viewer** | View assets, holders, and history; download reports — no changes |

---

## 2. Login & Dashboard

1. Open the system URL in your browser.
2. Enter your **username** and **password**, then click **Log In**.

### Dashboard

After login you will see the dashboard. Key areas:

| Area | What it shows |
|------|---------------|
| **KPI Cards** (top row) | Total assets · Assigned · In Stock · Issues (maintenance + lost + damaged) |
| **Alert banners** | Red: inactive holder alerts · Amber: warranties/AMC expiring within 30 days |
| **Status chart** | Donut chart — breakdown of all assets by current status |
| **Category chart** | Bar chart — asset count per category |
| **Recent Assignments** | Last 8 assign/return actions |
| **Expiring soon** | Assets whose warranty or AMC expires within 30 days |
| **Recent Events** | Last 5 lifecycle events (maintenance, lost, damaged, etc.) |
| **Quick Actions** | Shortcuts to Add Asset, View Holders, Reports, Audits, Alerts |

---

## 3. Assets

### 3.1 View & Search Assets

Go to **Assets** in the sidebar. The asset list shows:

| Column | Content |
|--------|---------|
| Asset Tag | Unique tag (e.g. `LAP-2025-0001`) + serial number |
| Type / Brand & Model | Asset category and description |
| Status | Colored badge — see [Quick Reference](#11-quick-reference) |
| Current Holder | Who holds it (empty if In Stock) |
| Location | Storage location or holder name |
| Actions | View · Edit · Assign/Transfer/Return |

**To search:** type in the search box (searches tag, brand, model, serial) and/or use the **Status** and **Asset Type** dropdowns. Click **Clear** to reset.

### 3.2 Add a Single Asset `[IT Officer]`

1. Click **Add Asset**.
2. Select the **Asset Type** — this controls which specification fields appear.
3. Fill in **Brand** and **Model Name** (required).
4. **Asset Tag** — leave blank to auto-generate (format: `PREFIX-YEAR-0001`), or type your own.
5. Fill in optional fields: Serial Number, Storage Location, Purchase Date, Purchase Order, Supplier, Purchase Cost, Warranty Expiry, AMC Expiry, Notes.
6. Fill in any **specification fields** shown for the selected asset type.
7. Click **Save**.

The asset is created with status **In Stock**.

### 3.3 Import Assets from Excel `[IT Officer]`

Use this to add many assets at once.

1. Click **Import from Excel** on the asset list page.
2. Select the **Asset Type** for the import.
3. Click **Download Template** — open it and fill in your asset data. Do not change column headers.
4. Upload the completed file and click **Preview**.
5. Review the preview table:
   - **Valid** rows will be imported.
   - **Warning** rows have minor issues (e.g. missing optional field).
   - **Error** rows will be skipped — fix them in the file and re-upload.
6. Click **Confirm Import** to create all valid assets.

Missing asset tags are auto-generated during import.

### 3.4 View Asset Detail

Click any asset tag or the **View** button. The detail page shows:

- Full specifications and dates
- Current status and holder
- Warranty and AMC expiry with visual expiry bar
- Full assignment history (who held it, when, for how long)
- Lifecycle event history

### 3.5 Edit an Asset `[IT Officer]`

Click **Edit** on the asset list or detail page. Update any field and click **Save**.

### 3.6 Delete an Asset `[IT Officer]`

Click **Delete** and confirm. The asset is soft-deleted (hidden from lists but not permanently removed). Deletion is not reversible from the UI — contact Admin if needed.

---

## 4. Assign & Transfer

### 4.1 Assign an Asset (In Stock → Assigned)

1. Find the asset (status must be **In Stock**).
2. Click **Assign**.
3. Search for the holder by name, designation, PRP ID, or office name.
4. Select the holder from the results.
5. Add an optional note.
6. Click **Confirm**.

The asset status changes to **Assigned**.

### 4.2 Transfer an Asset (Assigned → New Holder)

1. Find the assigned asset.
2. Click **Transfer**.
3. Search and select the new holder.
4. Add an optional note.
5. Click **Confirm**.

The old assignment is closed; a new one opens. History is preserved.

### 4.3 Return an Asset to Stock

1. Find the assigned asset.
2. Click **Return to Stock**.
3. Add an optional note and confirm.

The asset returns to **In Stock**.

### 4.4 Bulk Operations `[IT Officer]`

For multiple assets at once:

| Operation | How |
|-----------|-----|
| **Bulk Assign** | Select multiple In Stock assets → click **Bulk Assign** → choose one holder |
| **Bulk Transfer** | Select multiple Assigned assets → click **Bulk Transfer** → choose one new holder |
| **Bulk Return** | Select multiple Assigned assets → click **Bulk Return** → confirm |

---

## 5. Active Holders

Go to **Holders** in the sidebar. This page shows everyone who currently holds at least one asset.

There are four tabs:

| Tab | Shows |
|-----|-------|
| **Employees** | Name · Designation · Office · Asset count |
| **MPs** | Name · Constituency · Parliament number · Asset count |
| **Offices** | Office/department name · Asset count |
| **Locations** | Full location path · Asset count |

Click any row to open the holder's detail page, which shows all active assignments and the full assignment history for that holder.

---

## 6. Alerts

Alerts are created automatically when an employee, MP, or office that still holds assets is no longer found in the PRP system (i.e., they have left or been deactivated).

Go to **Alerts** to see all open alerts.

### What the Alerts Table Shows

| Column | Meaning |
|--------|---------|
| **Holder Name** | The person or office that triggered the alert |
| **Holder Type** | Employee / MP / Office |
| **Source** | PRP API (synced) or Manual |
| **Date Raised** | When the alert was created |
| **Active Assignments** | Number of assets still assigned to this holder |
| **Status** | Open / Resolved / Dismissed |

### How to Handle an Alert

1. Click **Review** on an alert.
2. The panel shows all assets still assigned to that holder.
3. For each asset, you can:
   - Click **Transfer** to move it to a new holder.
   - Click **Return to Stock** to bring it back to In Stock.
4. Once assets are handled, click **Resolve** (action taken) or **Dismiss** (no action needed).

> **Important:** Resolving or dismissing an alert does NOT automatically return or transfer assets. You must handle each asset manually before closing the alert.

---

## 7. Lifecycle Events

Lifecycle events record what happens to an asset beyond normal assignment — maintenance, damage, loss, or disposal.

### Record an Event `[IT Officer]`

1. Open the asset detail page.
2. Click **Record Event** (or **Report Event** from the mobile scan page).
3. Select the event type:

| Event Type | Result Status |
|------------|--------------|
| Send to Maintenance | Maintenance |
| Return from Maintenance | In Stock |
| Mark as Damaged | Damaged |
| Mark as Lost | Lost |
| Mark as Recovered | In Stock |
| Dispose | Disposed (final — cannot be undone) |

4. Fill in the date, notes, and any additional fields.
5. Click **Save**.

All events are logged permanently in the asset's history.

---

## 8. QR Codes

Every asset has a printed QR code label. Scanning it on a mobile device opens an action page for that asset immediately — no login search needed.

### What the Scan Page Shows

- Asset tag, brand, and model
- Current status badge
- Current holder (name, type, designation)
- Storage location (if set)
- Warranty expiry date
- Assignment date

### Actions Available After Scanning

| Asset Status | Available Actions |
|--------------|------------------|
| In Stock | Assign Asset |
| Assigned | Transfer · Return to Stock |
| Any status | Report Event · Full Detail |

### Spec Label

Each asset also has a printable **spec label** (QR codes section) that shows the asset tag, key specifications, and QR code — suitable for sticking on the physical device.

---

## 9. Audits

An audit session lets you physically verify which assets are present in a location by scanning their tags one by one.

### Run an Audit `[IT Officer]`

**Step 1 — Start a session**

1. Go to **Audits** in the sidebar.
2. Click **New Audit Session**.
3. Enter an optional **location** and **notes**.
4. Click **Start Session**. A reference code is generated (e.g. `AUD-20260604-0001`).

**Step 2 — Scan assets**

1. In the open session, type or scan each **asset tag** into the entry field.
2. Optionally enter the **found location** and a **scan note** for each asset.
3. Click **Add Scan**. The asset appears in the session list with a timestamp.
4. If you scan the same tag twice, the system warns you of a duplicate.
5. Repeat for all assets in the location.

**Step 3 — Complete the session**

1. When done, click **Complete Session**.
2. The session is locked — no further scans can be added.
3. The session record shows all scanned assets with timestamps and notes.

To remove a mistaken scan, click **Delete** next to that scan entry while the session is still open.

---

## 10. Reports

Go to **Reports** in the sidebar. Available report types:

| Report | What it contains |
|--------|-----------------|
| **Inventory** | Full asset list with status, holder, location, specs |
| **Transfer Log** | All assignment and transfer history |
| **Lifecycle Events** | All maintenance, loss, damage, disposal records |
| **Warranty / AMC** | Assets with warranty and AMC expiry dates |
| **Holder Assignments** | Current assignments grouped by holder |
| **Asset History** | Complete history for individual assets |

### How to Use

1. Select a report type.
2. Use the **column picker** to show only the columns you need.
3. Apply any available **filters** (date range, status, type, etc.).
4. Use **Previous / Next** to page through results (50 per page by default; change with the **Per Page** selector).
5. Click **Export Excel** to download as `.xlsx`, or **Export PDF** for a printable A4 landscape file.

> **Note:** Transfer Log and Lifecycle reports are capped at 5,000 rows. A yellow banner appears if your results hit this limit — apply filters to narrow the data before exporting.

---

## 11. Quick Reference

### Asset Status

| Status | Color | Meaning |
|--------|-------|---------|
| In Stock | Green | Available, not assigned |
| Assigned | Blue | Currently held by someone |
| Maintenance | Amber | Sent for repair |
| Lost | Red | Reported missing |
| Damaged | Red | Reported damaged |
| Disposed | Gray | End of life — permanent |

### Allowed Status Transitions

```
In Stock    →  Assigned · Maintenance · Disposed
Assigned    →  In Stock · Maintenance · Lost · Damaged · Disposed
Maintenance →  In Stock · Disposed
Lost        →  In Stock (recovered) · Disposed
Damaged     →  In Stock (repaired) · Maintenance · Disposed
Disposed    →  (no further transitions)
```

### Role Permissions Summary

| Action | Admin | IT Officer | Viewer |
|--------|-------|-----------|--------|
| View assets / reports | ✓ | ✓ | ✓ |
| Download Excel / PDF | ✓ | ✓ | ✓ |
| Add / edit assets | ✓ | ✓ | — |
| Import from Excel | ✓ | ✓ | — |
| Assign / transfer / return | ✓ | ✓ | — |
| Record lifecycle events | ✓ | ✓ | — |
| Run audits | ✓ | ✓ | — |
| Manage users | ✓ | — | — |
| Manage asset catalog / types | ✓ | — | — |
| Delete assets | ✓ | ✓ | — |

---

*Bangladesh Parliament Secretariat*
