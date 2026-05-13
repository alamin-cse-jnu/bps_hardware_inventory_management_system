# Design System — Full Reference

> Essential colors and rules are in CLAUDE.md. This file has the screen inventory and full typography/layout details.

## Screen Inventory (from `it-inventory/project/IT Inventory.html`)

| #  | Screen                   | Key Elements                                                    |
|----|--------------------------|-----------------------------------------------------------------|
| 0  | Login                    | Dark split-card, logo, purple CTA, SSO, error state             |
| 1  | Dashboard                | 4 KPI cards, activity feed, quick actions, charts               |
| 2  | Asset List               | Filter bar, table, status pills, bulk select, pagination        |
| 3  | Asset Detail + History   | Tabs (Overview / History / Components / Events), timeline       |
| 4  | Assign/Transfer Modal    | Slide-over panel, search assignee, quick picks, signature       |
| 5  | History Search           | Search + filters, grouped results (In Stock/Assigned/Unavail)   |
| 6  | Bulk Transfer Wizard     | Step indicator, per-row destination picker, mixed destinations   |
| 7  | Inactive Holder Alerts   | Alert cards, expandable asset lists, action buttons             |
| 8  | Mobile QR Scan           | Phone bezel, asset info, 4 action buttons, toast confirmations  |

## Full Color Reference

### Primary Brand (Parliament Blue — used everywhere)
```
Parliament Blue:      #0076A7  (sidebar bg, btn-primary, links, asset tags, table headers, focus rings)
Blue Hover:           #005d85  (hover for Parliament Blue)
Blue Table Header bg: #E8F3F8  (thead background)
Blue Row Hover:       #EBF4FA  (tbody tr:hover)
Logo mark gradient:   linear-gradient(135deg, #005d85, #0099CC)
```

### Secondary Accents
```
Parliament Gold:  #C8A951  (active nav left-border, badges)   light bg: #FBF5E6
Parliament Green: #006633  (accent only: asset icon bg gradient, tab active indicator, login stat card)
Green gradient:   linear-gradient(135deg, #006633, #10B981)   — used only on asset detail icon + login
```

### Dark Theme (Login page only)
```
Dark Base:     #13122A  (login page background)
Dark Surface:  #1A1830  (login card background)
Dark Elevated: #252340  (input fields on login)
Dark Muted:    #35325A  (borders on dark)
Purple Accent: #6D5AE6  hover: #5B49D4  soft: rgba(109,90,230,0.18)
```

### Dashboard KPI Card Gradients
```
Violet: linear-gradient(135deg, #6D5AE6, #8B5CF6)  — Total Assets card
Blue:   linear-gradient(135deg, #3B82F6, #6D5AE6)  — Assigned card
Teal:   linear-gradient(135deg, #0076A7, #10B981)  — In Stock card
Orange: linear-gradient(135deg, #F59E0B, #EF8A20)  — Issues card
```

### Admin Panel App Gradients (admin only, not main UI)
```
Assets app:      linear-gradient(135deg, #0076A7, #00B4D8)
Locations app:   linear-gradient(135deg, #6D5AE6, #8B5CF6)
Assignees app:   linear-gradient(135deg, #F59E0B, #EF8A20)
Assignments app: linear-gradient(135deg, #3B82F6, #6D5AE6)
Lifecycle app:   linear-gradient(135deg, #EF4444, #F59E0B)
Auth app:        linear-gradient(135deg, #495057, #212529)
```

### Status Pills
```
In Stock:    text #10B981  bg #ECFDF5
Assigned:    text #3B82F6  bg #EFF6FF
Maintenance: text #F59E0B  bg #FFFBEB
Lost:        text #EF4444  bg #FEF2F2
Damaged:     text #EF4444  bg #FEF2F2
Disposed:    text #9CA3AF  bg #F3F4F6
```

### Neutral
```
Background:  #F8F9FA    White:       #FFFFFF
Border:      #E5E7EB    Border Mid:  #D1D5DB
Text:        #212529    Text Mid:    #495057
Text Muted:  #6C757D    Placeholder: #9CA3AF
```

## Typography

```
Primary:   'Inter', sans-serif          — all UI text
Monospace: 'JetBrains Mono', monospace  — asset tags, IDs, codes
```

Font sizes used: 10 / 11 / 12 / 13 / 14 / 15 / 16 / 17 / 18 / 20 / 22 / 26 / 28px  
Body default: **14px**

## Layout Dimensions

```
Sidebar:      240px wide
Topbar:       56px height
Card radius:  8px standard · 12px for larger cards
Spacing grid: 4px base (common values: 8 / 12 / 16 / 20 / 24 / 32px)
```
