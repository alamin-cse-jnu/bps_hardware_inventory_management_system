"""
Office scope resolution for the Office-wise Asset List report.

The Secretariat hierarchy is three levels deep for reporting purposes:

    Wing  →  Branch  →  Section        (units fold into their parent section)

Wings are the children of the node that the employee ``wing_id`` values point
under (SECRETARY, in production data). Branches are the children of wings and
sections the children of branches. That derivation is self-configuring — no
prp_id is hardcoded — and it agrees exactly with the denormalised
``CachedEmployee.wing_id / branch_id / section_id`` fields, which is what makes
DB-side filtering safe.

Selection model
---------------
Each level accepts multiple offices plus an "only the selected office" flag:

* Wing + only    → staff sitting at the wing itself (``branch_id`` empty)
* Branch + only  → staff sitting at the branch itself (``section_id`` empty)
* Section + only → staff sitting at the section itself (``unit_id`` empty)

Selections at different levels are OR'd, with one narrowing rule: a wing term
is dropped when a branch *under that wing* is also selected (unless the wing's
"only" flag is set), and likewise for branches covered by a selected section.
Without that rule, picking a branch would be a no-op — you must select its wing
first in order to see it in the dropdown, and the wing term would swallow it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.db.models import Q

from assignees.models import CachedEmployee, CachedOffice

# (level, office prp_id, only_flag)
ScopeTerm = tuple[str, str, bool]

LEVELS = ("wing", "branch", "section")

# Level → (own field, child field that must be empty when "only" is set)
_LEVEL_FIELDS: dict[str, tuple[str, str]] = {
    "wing": ("wing_id", "branch_id"),
    "branch": ("branch_id", "section_id"),
    "section": ("section_id", "unit_id"),
}


# ─────────────────────────────────────────────────────────────────────────────
# Option tree
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class OfficeOptions:
    """Selectable offices per level, plus the lookups the scope logic needs."""

    wings: list[dict] = field(default_factory=list)
    branches: list[dict] = field(default_factory=list)
    sections: list[dict] = field(default_factory=list)
    # prp_id → parent prp_id, for every office (used to place office holders)
    parent_of: dict[str, str] = field(default_factory=dict)
    name_of: dict[str, str] = field(default_factory=dict)

    @property
    def wing_ids(self) -> set[str]:
        return {w["id"] for w in self.wings}

    @property
    def branch_ids(self) -> set[str]:
        return {b["id"] for b in self.branches}

    @property
    def section_ids(self) -> set[str]:
        return {s["id"] for s in self.sections}

    def ids_for(self, level: str) -> set[str]:
        return {"wing": self.wing_ids, "branch": self.branch_ids,
                "section": self.section_ids}[level]


def build_office_options() -> OfficeOptions:
    """Derive the Wing/Branch/Section option lists from the CachedOffice tree."""
    offices = list(CachedOffice.objects.all().only(
        "prp_id", "parent_prp_id", "name_en"
    ))
    parent_of = {o.prp_id: o.parent_prp_id for o in offices if o.prp_id}
    name_of = {o.prp_id: o.name_en for o in offices if o.prp_id}

    children: dict[str, list] = {}
    for o in offices:
        if o.prp_id:
            children.setdefault(o.parent_prp_id, []).append(o)

    # Wings: children of whatever node the employee wing_ids sit under.
    emp_wing_ids = set(
        CachedEmployee.objects.exclude(wing_id="").values_list("wing_id", flat=True)
    )
    roots = {parent_of[w] for w in emp_wing_ids if w in parent_of}
    if roots:
        wing_objs = [o for r in sorted(roots) for o in children.get(r, [])]
    else:
        # No employee placement data yet — fall back to whatever is referenced.
        wing_objs = [o for o in offices if o.prp_id in emp_wing_ids]

    def _pack(objs, parent_key=True):
        return sorted(
            (
                {"id": o.prp_id, "name": o.name_en,
                 "parent": o.parent_prp_id if parent_key else ""}
                for o in objs if o.prp_id
            ),
            key=lambda d: d["name"].casefold(),
        )

    wings = _pack(wing_objs)
    branch_objs = [o for w in wings for o in children.get(w["id"], [])]
    branches = _pack(branch_objs)
    section_objs = [o for b in branches for o in children.get(b["id"], [])]
    sections = _pack(section_objs)

    return OfficeOptions(
        wings=wings, branches=branches, sections=sections,
        parent_of=parent_of, name_of=name_of,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Request parsing
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class OfficeScope:
    wing: list[str] = field(default_factory=list)
    branch: list[str] = field(default_factory=list)
    section: list[str] = field(default_factory=list)
    wing_only: bool = False
    branch_only: bool = False
    section_only: bool = False

    @property
    def is_empty(self) -> bool:
        return not (self.wing or self.branch or self.section)

    def selected(self, level: str) -> list[str]:
        return getattr(self, level)

    def only(self, level: str) -> bool:
        return getattr(self, f"{level}_only")


def _multi(request, name: str) -> list[str]:
    """Read a repeated *or* comma-separated query param, de-duplicated."""
    raw: list[str] = []
    for value in request.GET.getlist(name):
        raw.extend(part.strip() for part in value.split(","))
    seen, out = set(), []
    for v in raw:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def parse_scope(request, options: OfficeOptions) -> OfficeScope:
    """Read wing/branch/section selections, discarding ids not in the tree."""
    scope = OfficeScope()
    for level in LEVELS:
        valid = options.ids_for(level)
        setattr(scope, level, [v for v in _multi(request, level) if v in valid])
        flag = request.GET.get(f"{level}_only", "")
        setattr(scope, f"{level}_only", flag in ("1", "true", "on", "yes"))
    return scope


# ─────────────────────────────────────────────────────────────────────────────
# Scope → filter terms
# ─────────────────────────────────────────────────────────────────────────────

def scope_terms(scope: OfficeScope, options: OfficeOptions) -> list[ScopeTerm]:
    """
    Reduce a selection to a flat list of (level, prp_id, only) terms.

    Single source of truth: both the employee queryset filter and the
    office-holder predicate are derived from this list, so they cannot drift.
    """
    if scope.is_empty:
        # Nothing chosen → the whole Secretariat, one term per wing.
        return [("wing", w["id"], False) for w in options.wings]

    parent_of = options.parent_of
    # Wings that already have a selected branch beneath them, and branches that
    # already have a selected section beneath them.
    wings_covered = {parent_of.get(b) for b in scope.branch}
    branches_covered = {parent_of.get(s) for s in scope.section}

    terms: list[ScopeTerm] = []
    for level, covered in (
        ("wing", wings_covered),
        ("branch", branches_covered),
        ("section", set()),
    ):
        only = scope.only(level)
        for oid in scope.selected(level):
            if only:
                terms.append((level, oid, True))
            elif oid not in covered:
                terms.append((level, oid, False))
    return terms


def terms_to_q(terms: list[ScopeTerm]) -> Q:
    """Build a CachedEmployee-relative Q from scope terms (OR'd)."""
    if not terms:
        return Q(pk__in=[])
    combined = Q()
    for level, oid, only in terms:
        own_field, child_field = _LEVEL_FIELDS[level]
        term = Q(**{own_field: oid})
        if only:
            term &= Q(**{child_field: ""})
        combined |= term
    return combined


def employee_q(terms: list[ScopeTerm], prefix: str = "") -> Q:
    """Same as terms_to_q but rooted at a related path, e.g. 'assignee__employee'."""
    if not prefix:
        return terms_to_q(terms)
    if not terms:
        return Q(pk__in=[])
    combined = Q()
    for level, oid, only in terms:
        own_field, child_field = _LEVEL_FIELDS[level]
        term = Q(**{f"{prefix}__{own_field}": oid})
        if only:
            term &= Q(**{f"{prefix}__{child_field}": ""})
        combined |= term
    return combined


# ─────────────────────────────────────────────────────────────────────────────
# Placement of an office node within Wing / Branch / Section
# ─────────────────────────────────────────────────────────────────────────────

def office_placement(prp_id: str, options: OfficeOptions) -> dict[str, str]:
    """
    Walk an office up the tree and report which wing/branch/section/unit it
    sits in. ``unit`` is set when the node itself is below section level.
    """
    placement = {"wing_id": "", "branch_id": "", "section_id": "", "unit_id": ""}
    if not prp_id:
        return placement

    chain, cur, guard = [], prp_id, 0
    while cur and guard < 20:
        chain.append(cur)
        nxt = options.parent_of.get(cur)
        if not nxt or nxt == cur or nxt == "0":
            break
        cur, guard = nxt, guard + 1

    wing_ids, branch_ids, section_ids = (
        options.wing_ids, options.branch_ids, options.section_ids
    )
    for node in chain:
        if not placement["wing_id"] and node in wing_ids:
            placement["wing_id"] = node
        if not placement["branch_id"] and node in branch_ids:
            placement["branch_id"] = node
        if not placement["section_id"] and node in section_ids:
            placement["section_id"] = node

    # Anything strictly below its section is a unit.
    known = wing_ids | branch_ids | section_ids
    if placement["section_id"] and prp_id not in known:
        placement["unit_id"] = prp_id
    return placement


def placement_matches(placement: dict[str, str], terms: list[ScopeTerm]) -> bool:
    """Python mirror of terms_to_q, for office holders."""
    for level, oid, only in terms:
        own_field, child_field = _LEVEL_FIELDS[level]
        if placement.get(own_field) != oid:
            continue
        if only and placement.get(child_field):
            continue
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Human-readable scope description (Excel subtitle / page summary)
# ─────────────────────────────────────────────────────────────────────────────

def scope_label(scope: OfficeScope, options: OfficeOptions) -> str:
    if scope.is_empty:
        return "All wings"
    parts: list[str] = []
    for level in LEVELS:
        ids = scope.selected(level)
        if not ids:
            continue
        names = [options.name_of.get(i, i) for i in ids]
        suffix = " (office only)" if scope.only(level) else ""
        parts.append(f"{level.title()}: {', '.join(names)}{suffix}")
    return " · ".join(parts)
