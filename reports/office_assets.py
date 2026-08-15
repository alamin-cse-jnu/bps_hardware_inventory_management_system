"""
Row + group construction for the Office-wise Asset List report.

Rows are grouped by holder; each group becomes one merged block in Excel and
one rowspan block in the HTML table. Both outputs consume the same groups, so
the on-screen table and the spreadsheet cannot disagree.

Placement (Wing/Branch/Section) is read from the *live* CachedEmployee record
rather than Assignment.holder_snapshot: this report answers "where is this
asset now", not "which desk did it go to originally".
"""

from __future__ import annotations

from django.db.models import Q
from django.urls import reverse

from assignees.models import AssigneeType, CachedOffice

from .office_scope import (
    OfficeOptions,
    ScopeTerm,
    employee_q,
    office_placement,
    placement_matches,
)

# Rendered in Wing/Branch/Section when the holder sits above that level —
# matches the convention already used in docs/office wise asset list.xlsx.
MISSING = "…"


def _office_holder_ids(terms: list[ScopeTerm], options: OfficeOptions) -> dict[str, dict]:
    """prp_id → placement, for every office node inside the scope."""
    matches: dict[str, dict] = {}
    for prp_id in options.parent_of:
        placement = office_placement(prp_id, options)
        if placement_matches(placement, terms):
            matches[prp_id] = placement
    return matches


def build_groups(terms: list[ScopeTerm], options: OfficeOptions) -> list[dict]:
    """
    Return holder groups, ordered Wing → Branch → Section → staff → office,
    each with its asset rows ordered Category → Asset Type → Tag.
    """
    from assignments.models import Assignment

    office_scope_map = _office_holder_ids(terms, options)
    office_pks = list(
        CachedOffice.objects
        .filter(prp_id__in=office_scope_map.keys())
        .values_list("pk", flat=True)
    ) if office_scope_map else []

    holder_q = Q(
        assignee__assignee_type=AssigneeType.EMPLOYEE
    ) & employee_q(terms, "assignee__employee")
    if office_pks:
        holder_q |= Q(
            assignee__assignee_type=AssigneeType.OFFICE,
            assignee__office__pk__in=office_pks,
        )

    qs = (
        Assignment.objects
        .filter(returned_at__isnull=True)
        .filter(holder_q)
        .select_related(
            "asset__asset_type__category",
            "assignee__employee",
            "assignee__office",
        )
    )

    groups: dict[int, dict] = {}
    for asgn in qs:
        assignee = asgn.assignee
        asset = asgn.asset

        if assignee.assignee_type == AssigneeType.EMPLOYEE and assignee.employee_id:
            emp = assignee.employee
            inactive = not emp.is_active
            meta = {
                "holder": f"{emp.name_en} (Inactive)" if inactive else emp.name_en,
                "designation": emp.designation_en or "",
                "wing": emp.wing_name_en or MISSING,
                "branch": emp.branch_name_en or MISSING,
                "section": emp.section_name_en or MISSING,
                "_inactive": inactive,
                "_is_office": False,
                "_sort_wing": (emp.wing_name_en or "").casefold(),
                "_sort_branch": (1, (emp.branch_name_en or "").casefold()) if emp.branch_id else (0, ""),
                "_sort_section": (1, (emp.section_name_en or "").casefold()) if emp.section_id else (0, ""),
                "_sort_name": emp.name_en.casefold(),
            }
        elif assignee.assignee_type == AssigneeType.OFFICE and assignee.office_id:
            office = assignee.office
            placement = office_scope_map.get(office.prp_id) or {}
            name = options.name_of.get
            wing_id = placement.get("wing_id", "")
            branch_id = placement.get("branch_id", "")
            section_id = placement.get("section_id", "")
            meta = {
                "holder": office.name_en,
                "designation": "",
                "wing": name(wing_id, "") or MISSING,
                "branch": name(branch_id, "") or MISSING,
                "section": name(section_id, "") or MISSING,
                "_inactive": not office.is_active,
                "_is_office": True,
                "_sort_wing": (name(wing_id, "") or "").casefold(),
                "_sort_branch": (1, (name(branch_id, "") or "").casefold()) if branch_id else (0, ""),
                "_sort_section": (1, (name(section_id, "") or "").casefold()) if section_id else (0, ""),
                "_sort_name": office.name_en.casefold(),
            }
        else:
            continue

        group = groups.get(assignee.pk)
        if group is None:
            group = {**meta, "rows": []}
            groups[assignee.pk] = group

        group["rows"].append({
            "asset_tag": asset.asset_tag,
            "category": asset.asset_type.category.name,
            "asset_type": asset.asset_type.name,
            "brand": asset.brand or "",
            "model": asset.model_name or "",
            "_detail_url": reverse("assets:detail", args=[asset.pk]),
            "_status_raw": asset.status,
        })

    ordered = sorted(
        groups.values(),
        key=lambda g: (
            g["_sort_wing"],
            g["_sort_branch"],
            g["_sort_section"],
            1 if g["_is_office"] else 0,   # office's own assets last in its node
            g["_sort_name"],
        ),
    )
    for group in ordered:
        group["rows"].sort(
            key=lambda r: (r["category"].casefold(), r["asset_type"].casefold(), r["asset_tag"])
        )
        group["rowspan"] = len(group["rows"])
        annotate_runs(group["rows"], RUN_KEYS)
    return ordered


# Columns merged across consecutive equal runs inside a holder block.
RUN_KEYS = ("category", "asset_type")


def annotate_runs(rows: list[dict], keys=RUN_KEYS) -> None:
    """
    Mark vertical merge runs on each row: ``_span_<key>`` is the run length on
    the anchor row and 0 on every continuation row.

    Computed once here so the HTML rowspan and the Excel merge geometry are
    driven by the same numbers.
    """
    for key in keys:
        span_key = f"_span_{key}"
        start = 0
        for i in range(1, len(rows) + 1):
            if i < len(rows) and rows[i].get(key) == rows[start].get(key):
                continue
            rows[start][span_key] = i - start
            for j in range(start + 1, i):
                rows[j][span_key] = 0
            start = i


def flatten(groups: list[dict]) -> list[dict]:
    """Groups → flat row dicts carrying their holder's identity columns."""
    out: list[dict] = []
    for group in groups:
        for row in group["rows"]:
            out.append({
                "holder": group["holder"],
                "designation": group["designation"],
                "wing": group["wing"],
                "branch": group["branch"],
                "section": group["section"],
                **row,
            })
    return out


def asset_count(groups: list[dict]) -> int:
    return sum(len(g["rows"]) for g in groups)
