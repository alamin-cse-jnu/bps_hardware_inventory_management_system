"""
Column definitions for Phase 8 tabular report views.

Each list contains (key, label) pairs in canonical display order.
`parse_cols` reads ?cols= from the request and returns validated keys.
"""

INVENTORY_COLS: list[tuple[str, str]] = [
    ("asset_tag",        "Asset Tag"),
    ("category",         "Category"),
    ("type",             "Type"),
    ("brand",            "Brand"),
    ("model",            "Model"),
    ("serial_no",        "Serial No."),
    ("vendor",           "Vendor"),
    ("cpu",              "CPU"),
    ("gpu",              "GPU"),
    ("ram",              "RAM"),
    ("storage",          "Storage"),
    ("display",          "Display"),
    ("status",           "Status"),
    ("storage_location", "Storage Location"),
    ("current_holder",   "Current Holder"),
    ("holder_type",      "Holder Type"),
    ("assigned_since",   "Assigned Since"),
    ("purchase_date",    "Purchase Date"),
    ("warranty_expiry",  "Warranty Expiry"),
    ("amc_expiry",       "AMC Expiry"),
    ("work_order_ref",   "Work Order Ref"),
]

TRANSFER_LOG_COLS: list[tuple[str, str]] = [
    ("transfer_date", "Transfer Date"),
    ("asset_tag",     "Asset Tag"),
    ("category",      "Category"),
    ("type",          "Type"),
    ("brand",         "Brand"),
    ("model",         "Model"),
    ("assigned_to",   "Assigned To"),
    ("holder_type",   "Holder Type"),
    ("designation",   "Designation"),
    ("status",        "Status"),
    ("performed_by",  "Performed By"),
    ("batch_ref",     "Batch Ref"),
    ("notes",         "Notes"),
]

LIFECYCLE_COLS: list[tuple[str, str]] = [
    ("date",         "Date"),
    ("asset_tag",    "Asset Tag"),
    ("category",     "Category"),
    ("type",         "Type"),
    ("brand",        "Brand"),
    ("model",        "Model"),
    ("event",        "Event"),
    ("old_status",   "Old Status"),
    ("new_status",   "New Status"),
    ("notes",        "Notes"),
    ("performed_by", "Performed By"),
]

WARRANTY_COLS: list[tuple[str, str]] = [
    ("asset_tag",       "Asset Tag"),
    ("category",        "Category"),
    ("type",            "Type"),
    ("brand",           "Brand"),
    ("model",           "Model"),
    ("status",          "Status"),
    ("current_holder",  "Current Holder"),
    ("warranty_expiry", "Warranty Expiry"),
    ("warranty_days",   "Days (WTY)"),
    ("amc_expiry",      "AMC Expiry"),
    ("amc_days",        "Days (AMC)"),
]

HOLDER_ASSIGNMENTS_COLS: list[tuple[str, str]] = [
    ("holder",         "Holder"),
    ("holder_type",    "Holder Type"),
    ("designation",    "Designation"),
    ("department",     "Department"),
    ("asset_tag",      "Asset Tag"),
    ("category",       "Category"),
    ("asset_type",     "Asset Type"),
    ("brand",          "Brand"),
    ("model",          "Model"),
    ("status",         "Status"),
    ("assigned_since", "Assigned Since"),
]

# Office-wise Asset List (Phase 11).
# Fixed column set — the Excel merge geometry is defined in terms of these
# exact groups (identity block A–E, run-merge block Category/Asset Type), so
# this report deliberately has no column picker.
OFFICE_ASSETS_COLS: list[tuple[str, str]] = [
    ("holder",        "Holder"),
    ("designation",   "Designation"),
    ("wing",          "Wing"),
    ("branch",        "Branch"),
    ("section",       "Section"),
    ("category",      "Category"),
    ("asset_type",    "Asset Type"),
    ("brand",         "Brand"),
    ("model",         "Model"),
    ("serial_number", "Serial Number"),
    ("asset_tag",     "Asset Tag"),
]

# Columns merged across a holder's whole row block.
OFFICE_ASSETS_IDENTITY_KEYS = ["holder", "designation", "wing", "branch", "section"]
# Columns merged across consecutive equal runs *within* a holder block.
OFFICE_ASSETS_RUN_KEYS = ["category", "asset_type"]


ASSET_HISTORY_COLS: list[tuple[str, str]] = [
    ("assigned_to",  "Assigned To"),
    ("holder_type",  "Holder Type"),
    ("designation",  "Designation"),
    ("department",   "Department"),
    ("from_date",    "From Date"),
    ("to_date",      "To Date"),
    ("days",         "Days"),
    ("performed_by", "Performed By"),
    ("batch_ref",    "Batch Ref"),
    ("notes",        "Notes"),
]


def parse_cols(request, col_list: list[tuple[str, str]]) -> list[str]:
    """Read ?cols=, validate each key against col_list; return all keys if none valid."""
    valid_keys = {k for k, _ in col_list}
    raw = request.GET.get("cols", "")
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    selected = [k for k in keys if k in valid_keys]
    return selected if selected else [k for k, _ in col_list]
