import json

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Case, Count, F, IntegerField, Q, Value, When
from django.db.models.functions import Cast
from django.shortcuts import get_object_or_404, redirect, render

from config.permissions import it_officer_required, viewer_required

from .models import Assignee, AssigneeType, CachedEmployee, CachedMP, CachedOffice, Source


# ─────────────────────────────────────────────────────────────────────────────
# Assignment search / select (used by assign panel — Session 2.2)
# ─────────────────────────────────────────────────────────────────────────────

@it_officer_required
def search(request):
    q = request.GET.get("q", "").strip()
    holder_type = request.GET.get("holder_type", "").strip().upper()
    asset_pk = request.GET.get("asset_pk", "")
    results = []

    valid_types = {"EMPLOYEE", "MP", "OFFICE", "LOCATION"}
    if holder_type not in valid_types:
        holder_type = ""

    # Show results when: type selected (browse/search), or cross-type search with >=2 chars
    should_search = (holder_type and len(q) >= 0) or (not holder_type and len(q) >= 2)

    if should_search:
        qs = (
            Assignee.objects.filter(is_active=True)
            .exclude(
                Q(assignee_type="EMPLOYEE", employee__is_active=False)
                | Q(assignee_type="MP", mp__is_active=False)
                | Q(assignee_type="OFFICE", office__is_active=False)
            )
        )

        if holder_type:
            qs = qs.filter(assignee_type=holder_type)

        if q:
            qs = qs.filter(
                Q(employee__name_en__icontains=q)
                | Q(employee__name_bn__icontains=q)
                | Q(employee__prp_id__icontains=q)
                | Q(employee__designation_en__icontains=q)
                | Q(employee__section_name_en__icontains=q)
                | Q(employee__office_name_en__icontains=q)
                | Q(mp__name_en__icontains=q)
                | Q(mp__name_bn__icontains=q)
                | Q(mp__prp_id__icontains=q)
                | Q(mp__constituency__icontains=q)
                | Q(office__name_en__icontains=q)
                | Q(location__name__icontains=q)
                | Q(location__parent__name__icontains=q)
            )
            # Exact / prefix PRP-ID matches bubble to the top
            rank = Case(
                When(Q(employee__prp_id=q) | Q(mp__prp_id=q), then=Value(0)),
                When(
                    Q(employee__prp_id__startswith=q) | Q(mp__prp_id__startswith=q),
                    then=Value(1),
                ),
                default=Value(2),
                output_field=IntegerField(),
            )
            qs = qs.annotate(_rank=rank).order_by(
                "_rank", "employee__name_en", "mp__name_en", "office__name_en", "location__name"
            )
        else:
            qs = qs.order_by(
                "employee__name_en", "mp__name_en", "office__name_en", "location__name"
            )

        qs = qs.select_related(
            "employee", "mp", "office", "location__parent__parent"
        )[:25]
        results = list(qs)

    return render(request, "assignees/search_results.html", {
        "results": results,
        "q": q,
        "holder_type": holder_type,
        "asset_pk": asset_pk,
    })


@it_officer_required
def select_card(request, pk):
    from django.urls import reverse
    assignee = get_object_or_404(Assignee, pk=pk)
    asset_pk = request.GET.get("asset_pk", "")
    if asset_pk == "bulk":
        clear_url = reverse("assignments:bulk_clear_assignee")
    elif asset_pk:
        clear_url = reverse("assignments:clear_assignee", args=[asset_pk])
    else:
        clear_url = ""
    return render(request, "assignees/selected_card.html", {
        "assignee": assignee,
        "asset_pk": asset_pk,
        "clear_url": clear_url,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Employee list / detail / create / edit / deactivate
# ─────────────────────────────────────────────────────────────────────────────

_PER_PAGE_OPTIONS = (25, 50, 100, 350)


@viewer_required
def employee_list(request):
    qs = CachedEmployee.objects.all()

    # ── Filters ───────────────────────────────────────────────────────────────
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name_en__icontains=q) | Q(name_bn__icontains=q)
            | Q(prp_id__icontains=q)
            | Q(designation_en__icontains=q)
            | Q(section_name_en__icontains=q) | Q(branch_name_en__icontains=q)
            | Q(office_name_en__icontains=q)
        )
    source_filter = request.GET.get("source", "")
    if source_filter in (Source.PRP_API, Source.MANUAL):
        qs = qs.filter(source=source_filter)
    active_filter = request.GET.get("active", "")
    if active_filter == "1":
        qs = qs.filter(is_active=True)
    elif active_filter == "0":
        qs = qs.filter(is_active=False)

    # ── Class-tab counts (computed before class filter so all tabs always show real numbers)
    # API sends class=5 for employees with no gazetted class; MANUAL records may have null.
    class_counts = qs.aggregate(
        c1=Count(Case(When(employee_class=1, then=1), output_field=IntegerField())),
        c2=Count(Case(When(employee_class=2, then=1), output_field=IntegerField())),
        c3=Count(Case(When(employee_class=3, then=1), output_field=IntegerField())),
        c4=Count(Case(When(employee_class=4, then=1), output_field=IntegerField())),
        c5=Count(Case(
            When(Q(employee_class=5) | Q(employee_class__isnull=True), then=1),
            output_field=IntegerField(),
        )),
    )

    # ── Class tab filter ──────────────────────────────────────────────────────
    class_filter = request.GET.get("class", "").strip()
    if class_filter == "5":
        qs = qs.filter(Q(employee_class=5) | Q(employee_class__isnull=True))
    elif class_filter in ("1", "2", "3", "4"):
        qs = qs.filter(employee_class=int(class_filter))

    # ── Per-page ──────────────────────────────────────────────────────────────
    try:
        per_page = int(request.GET.get("per_page", 25))
        if per_page not in _PER_PAGE_OPTIONS:
            per_page = 25
    except (ValueError, TypeError):
        per_page = 25

    # ── Ordering: numeric PRP ID asc (MANUAL nulls last), then name ──────────
    qs = (
        qs.annotate(prp_id_num=Cast("prp_id", output_field=IntegerField()))
        .order_by(F("prp_id_num").asc(nulls_last=True), "name_en")
    )

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    # Build base query string for pagination links (all active filters except page)
    filter_parts = []
    if q:
        filter_parts.append(f"q={q}")
    if source_filter:
        filter_parts.append(f"source={source_filter}")
    if active_filter:
        filter_parts.append(f"active={active_filter}")
    if class_filter:
        filter_parts.append(f"class={class_filter}")
    filter_parts.append(f"per_page={per_page}")
    filter_qs = "&".join(filter_parts)

    return render(request, "assignees/employee_list.html", {
        "page_obj": page_obj,
        "q": q,
        "source_filter": source_filter,
        "active_filter": active_filter,
        "class_filter": class_filter,
        "class_counts": class_counts,
        "per_page": per_page,
        "per_page_options": _PER_PAGE_OPTIONS,
        "filter_qs": filter_qs,
    })


@viewer_required
def employee_detail(request, pk):
    emp = get_object_or_404(CachedEmployee, pk=pk)
    from assignments.models import Assignment
    base_qs = (
        Assignment.objects.filter(assignee__employee=emp)
        .select_related("asset", "asset__asset_type", "performed_by")
    )
    active_assignments = list(base_qs.filter(returned_at__isnull=True).order_by("assigned_at"))
    history = list(base_qs.filter(returned_at__isnull=False).order_by("-returned_at")[:50])
    return render(request, "assignees/holder_detail.html", {
        "holder": emp,
        "holder_type": "employee",
        "holder_type_display": "Employee",
        "active_assignments": active_assignments,
        "history": history,
        "list_url": "assignees:employees",
        "list_label": "Employees",
        "edit_url": "assignees:employee_edit",
        "deactivate_url": "assignees:employee_deactivate",
    })


@it_officer_required
def employee_create(request):
    errors = {}
    form_data = {}
    duplicates = []
    if request.method == "POST":
        form_data = request.POST
        name_en = form_data.get("name_en", "").strip()
        if not name_en:
            errors["name_en"] = "Name (English) is required."
        if not errors:
            duplicates = list(
                CachedEmployee.objects.filter(name_en__icontains=name_en[:30])[:5]
            )
            if duplicates and not form_data.get("confirmed"):
                pass  # show duplicate warning — don't save yet
            else:
                emp = CachedEmployee.objects.create(
                    source=Source.MANUAL,
                    name_en=name_en,
                    name_bn=form_data.get("name_bn", "").strip(),
                    section_name_en=form_data.get("section_name_en", "").strip(),
                    branch_name_en=form_data.get("branch_name_en", "").strip(),
                    wing_name_en=form_data.get("wing_name_en", "").strip(),
                    office_name_en=form_data.get("office_name_en", "").strip(),
                    mobile=form_data.get("mobile", "").strip(),
                    telephone=form_data.get("telephone", "").strip(),
                    created_by=request.user,
                )
                Assignee.objects.create(
                    assignee_type=AssigneeType.EMPLOYEE,
                    employee=emp,
                    is_active=True,
                    created_by=request.user,
                )
                messages.success(request, f"Employee '{emp.name_en}' created successfully.")
                return redirect("assignees:employees")
    return render(request, "assignees/employee_form.html", {
        "action": "Add",
        "form_data": form_data,
        "errors": errors,
        "duplicates": duplicates,
        "holder": None,
    })


@it_officer_required
def employee_edit(request, pk):
    emp = get_object_or_404(CachedEmployee, pk=pk)
    if emp.source == Source.PRP_API:
        messages.error(request, "API-sourced employees are managed by sync and cannot be edited here.")
        return redirect("assignees:employee_detail", pk=pk)
    errors = {}
    form_data = {}
    if request.method == "POST":
        form_data = request.POST
        name_en = form_data.get("name_en", "").strip()
        if not name_en:
            errors["name_en"] = "Name (English) is required."
        if not errors:
            emp.name_en = name_en
            emp.name_bn = form_data.get("name_bn", "").strip()
            emp.section_name_en = form_data.get("section_name_en", "").strip()
            emp.branch_name_en = form_data.get("branch_name_en", "").strip()
            emp.wing_name_en = form_data.get("wing_name_en", "").strip()
            emp.office_name_en = form_data.get("office_name_en", "").strip()
            emp.mobile = form_data.get("mobile", "").strip()
            emp.telephone = form_data.get("telephone", "").strip()
            emp.save()
            messages.success(request, f"Employee '{emp.name_en}' updated successfully.")
            return redirect("assignees:employee_detail", pk=emp.pk)
    return render(request, "assignees/employee_form.html", {
        "action": "Edit",
        "form_data": form_data,
        "errors": errors,
        "duplicates": [],
        "holder": emp,
    })


@it_officer_required
def employee_deactivate(request, pk):
    emp = get_object_or_404(CachedEmployee, pk=pk)
    from assignments.models import Assignment
    active_count = Assignment.objects.filter(
        assignee__employee=emp, returned_at__isnull=True
    ).count()
    if request.method == "POST":
        if active_count:
            messages.error(request, f"Cannot deactivate — {active_count} active assignment(s) must be resolved first.")
        else:
            emp.mark_inactive()
            messages.success(request, f"Employee '{emp.name_en}' deactivated.")
        return redirect("assignees:employees")
    return render(request, "assignees/holder_deactivate_confirm.html", {
        "holder": emp,
        "holder_type_display": "Employee",
        "active_count": active_count,
        "deactivate_url_name": "assignees:employee_deactivate",
        "list_url_name": "assignees:employees",
    })


# ─────────────────────────────────────────────────────────────────────────────
# MP list / detail / create / edit / deactivate
# ─────────────────────────────────────────────────────────────────────────────

@viewer_required
def mp_list(request):
    qs = CachedMP.objects.all()

    # ── Filters ───────────────────────────────────────────────────────────────
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name_en__icontains=q) | Q(name_bn__icontains=q)
            | Q(prp_id__icontains=q)
            | Q(constituency__icontains=q)
        )
    source_filter = request.GET.get("source", "")
    if source_filter in (Source.PRP_API, Source.MANUAL):
        qs = qs.filter(source=source_filter)
    active_filter = request.GET.get("active", "")
    if active_filter == "1":
        qs = qs.filter(is_active=True)
    elif active_filter == "0":
        qs = qs.filter(is_active=False)
    parl_filter = request.GET.get("parliament_no", "").strip()
    if parl_filter.isdigit():
        qs = qs.filter(parliament_no=int(parl_filter))

    # ── Per-page ──────────────────────────────────────────────────────────────
    try:
        per_page = int(request.GET.get("per_page", 25))
        if per_page not in _PER_PAGE_OPTIONS:
            per_page = 25
    except (ValueError, TypeError):
        per_page = 25

    paginator = Paginator(
        qs.annotate(prp_id_num=Cast("prp_id", output_field=IntegerField()))
        .order_by(F("prp_id_num").asc(nulls_last=True), "name_en"),
        per_page,
    )
    page_obj = paginator.get_page(request.GET.get("page", 1))

    parliament_nos = list(
        CachedMP.objects.values_list("parliament_no", flat=True)
        .distinct().order_by("-parliament_no")
        .exclude(parliament_no__isnull=True)
    )

    # Build base query string for pagination links
    filter_parts = []
    if q:
        filter_parts.append(f"q={q}")
    if source_filter:
        filter_parts.append(f"source={source_filter}")
    if active_filter:
        filter_parts.append(f"active={active_filter}")
    if parl_filter:
        filter_parts.append(f"parliament_no={parl_filter}")
    filter_parts.append(f"per_page={per_page}")
    filter_qs = "&".join(filter_parts)

    return render(request, "assignees/mp_list.html", {
        "page_obj": page_obj,
        "q": q,
        "source_filter": source_filter,
        "active_filter": active_filter,
        "parl_filter": parl_filter,
        "parliament_nos": parliament_nos,
        "per_page": per_page,
        "per_page_options": _PER_PAGE_OPTIONS,
        "filter_qs": filter_qs,
    })


@viewer_required
def mp_detail(request, pk):
    mp = get_object_or_404(CachedMP, pk=pk)
    from assignments.models import Assignment
    base_qs = (
        Assignment.objects.filter(assignee__mp=mp)
        .select_related("asset", "asset__asset_type", "performed_by")
    )
    active_assignments = list(base_qs.filter(returned_at__isnull=True).order_by("assigned_at"))
    history = list(base_qs.filter(returned_at__isnull=False).order_by("-returned_at")[:50])
    return render(request, "assignees/holder_detail.html", {
        "holder": mp,
        "holder_type": "mp",
        "holder_type_display": "MP",
        "active_assignments": active_assignments,
        "history": history,
        "list_url": "assignees:mps",
        "list_label": "MPs",
        "edit_url": "assignees:mp_edit",
        "deactivate_url": "assignees:mp_deactivate",
    })


@it_officer_required
def mp_create(request):
    errors = {}
    form_data = {}
    duplicates = []
    if request.method == "POST":
        form_data = request.POST
        name_en = form_data.get("name_en", "").strip()
        if not name_en:
            errors["name_en"] = "Name (English) is required."
        if not errors:
            duplicates = list(CachedMP.objects.filter(name_en__icontains=name_en[:30])[:5])
            if duplicates and not form_data.get("confirmed"):
                pass
            else:
                parl_no = form_data.get("parliament_no", "").strip()
                mp = CachedMP.objects.create(
                    source=Source.MANUAL,
                    name_en=name_en,
                    name_bn=form_data.get("name_bn", "").strip(),
                    constituency=form_data.get("constituency", "").strip(),
                    parliament_no=int(parl_no) if parl_no.isdigit() else None,
                    mobile=form_data.get("mobile", "").strip(),
                    telephone=form_data.get("telephone", "").strip(),
                    created_by=request.user,
                )
                Assignee.objects.create(
                    assignee_type=AssigneeType.MP,
                    mp=mp,
                    is_active=True,
                    created_by=request.user,
                )
                messages.success(request, f"MP '{mp.name_en}' created successfully.")
                return redirect("assignees:mps")
    return render(request, "assignees/mp_form.html", {
        "action": "Add",
        "form_data": form_data,
        "errors": errors,
        "duplicates": duplicates,
        "holder": None,
    })


@it_officer_required
def mp_edit(request, pk):
    mp = get_object_or_404(CachedMP, pk=pk)
    if mp.source == Source.PRP_API:
        messages.error(request, "API-sourced MPs are managed by sync and cannot be edited here.")
        return redirect("assignees:mp_detail", pk=pk)
    errors = {}
    form_data = {}
    if request.method == "POST":
        form_data = request.POST
        name_en = form_data.get("name_en", "").strip()
        if not name_en:
            errors["name_en"] = "Name (English) is required."
        if not errors:
            parl_no = form_data.get("parliament_no", "").strip()
            mp.name_en = name_en
            mp.name_bn = form_data.get("name_bn", "").strip()
            mp.constituency = form_data.get("constituency", "").strip()
            mp.parliament_no = int(parl_no) if parl_no.isdigit() else None
            mp.mobile = form_data.get("mobile", "").strip()
            mp.telephone = form_data.get("telephone", "").strip()
            mp.save()
            messages.success(request, f"MP '{mp.name_en}' updated successfully.")
            return redirect("assignees:mp_detail", pk=mp.pk)
    return render(request, "assignees/mp_form.html", {
        "action": "Edit",
        "form_data": form_data,
        "errors": errors,
        "duplicates": [],
        "holder": mp,
    })


@it_officer_required
def mp_deactivate(request, pk):
    mp = get_object_or_404(CachedMP, pk=pk)
    from assignments.models import Assignment
    active_count = Assignment.objects.filter(
        assignee__mp=mp, returned_at__isnull=True
    ).count()
    if request.method == "POST":
        if active_count:
            messages.error(request, f"Cannot deactivate — {active_count} active assignment(s) must be resolved first.")
        else:
            mp.mark_inactive()
            messages.success(request, f"MP '{mp.name_en}' deactivated.")
        return redirect("assignees:mps")
    return render(request, "assignees/holder_deactivate_confirm.html", {
        "holder": mp,
        "holder_type_display": "MP",
        "active_count": active_count,
        "deactivate_url_name": "assignees:mp_deactivate",
        "list_url_name": "assignees:mps",
    })


# ─────────────────────────────────────────────────────────────────────────────
# Office list / detail / create / edit / deactivate
# ─────────────────────────────────────────────────────────────────────────────

@viewer_required
def office_list(request):
    tab = request.GET.get("tab", "list")
    if tab not in ("list", "tree"):
        tab = "list"

    # ── Hierarchy (tree) tab — pass all offices as JSON ───────────────────
    offices_json = "[]"
    if tab == "tree":
        offices_data = []
        for office in CachedOffice.objects.all():
            try:
                oid = int(office.prp_id) if office.prp_id else office.pk
            except (ValueError, TypeError):
                oid = office.pk
            try:
                parent_id = int(office.parent_prp_id) if office.parent_prp_id else 0
            except (ValueError, TypeError):
                parent_id = 0
            offices_data.append({
                "id": oid,
                "parentId": parent_id,
                "nameEn": office.name_en,
                "nameBn": office.name_bn,
                "isAbstractOffice": office.is_abstract,
            })
        offices_json = json.dumps(offices_data)

    # ── Flat list tab ─────────────────────────────────────────────────────
    qs = CachedOffice.objects.all()
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name_en__icontains=q) | Q(name_bn__icontains=q))
    source_filter = request.GET.get("source", "")
    if source_filter in (Source.PRP_API, Source.MANUAL):
        qs = qs.filter(source=source_filter)
    active_filter = request.GET.get("active", "")
    if active_filter == "1":
        qs = qs.filter(is_active=True)
    elif active_filter == "0":
        qs = qs.filter(is_active=False)

    try:
        per_page = int(request.GET.get("per_page", 25))
        if per_page not in _PER_PAGE_OPTIONS:
            per_page = 25
    except (ValueError, TypeError):
        per_page = 25

    paginator = Paginator(qs.order_by("name_en"), per_page)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    filter_parts = []
    if q:
        filter_parts.append(f"q={q}")
    if source_filter:
        filter_parts.append(f"source={source_filter}")
    if active_filter:
        filter_parts.append(f"active={active_filter}")
    filter_parts.append(f"per_page={per_page}")
    filter_qs = "&".join(filter_parts)

    return render(request, "assignees/office_list.html", {
        "tab": tab,
        "page_obj": page_obj,
        "q": q,
        "source_filter": source_filter,
        "active_filter": active_filter,
        "per_page": per_page,
        "per_page_options": _PER_PAGE_OPTIONS,
        "filter_qs": filter_qs,
        "offices_json": offices_json,
    })


@viewer_required
def office_detail(request, pk):
    office = get_object_or_404(CachedOffice, pk=pk)
    from assignments.models import Assignment
    base_qs = (
        Assignment.objects.filter(assignee__office=office)
        .select_related("asset", "asset__asset_type", "performed_by")
    )
    active_assignments = list(base_qs.filter(returned_at__isnull=True).order_by("assigned_at"))
    history = list(base_qs.filter(returned_at__isnull=False).order_by("-returned_at")[:50])
    return render(request, "assignees/holder_detail.html", {
        "holder": office,
        "holder_type": "office",
        "holder_type_display": "Office",
        "active_assignments": active_assignments,
        "history": history,
        "list_url": "assignees:offices",
        "list_label": "Offices",
        "edit_url": "assignees:office_edit",
        "deactivate_url": "assignees:office_deactivate",
    })


@it_officer_required
def office_create(request):
    errors = {}
    form_data = {}
    duplicates = []
    if request.method == "POST":
        form_data = request.POST
        name_en = form_data.get("name_en", "").strip()
        if not name_en:
            errors["name_en"] = "Name (English) is required."
        if not errors:
            duplicates = list(CachedOffice.objects.filter(name_en__icontains=name_en[:30])[:5])
            if duplicates and not form_data.get("confirmed"):
                pass
            else:
                office = CachedOffice.objects.create(
                    source=Source.MANUAL,
                    name_en=name_en,
                    name_bn=form_data.get("name_bn", "").strip(),
                    created_by=request.user,
                )
                Assignee.objects.create(
                    assignee_type=AssigneeType.OFFICE,
                    office=office,
                    is_active=True,
                    created_by=request.user,
                )
                messages.success(request, f"Office '{office.name_en}' created successfully.")
                return redirect("assignees:offices")
    return render(request, "assignees/office_form.html", {
        "action": "Add",
        "form_data": form_data,
        "errors": errors,
        "duplicates": duplicates,
        "holder": None,
    })


@it_officer_required
def office_edit(request, pk):
    office = get_object_or_404(CachedOffice, pk=pk)
    if office.source == Source.PRP_API:
        messages.error(request, "API-sourced offices are managed by sync and cannot be edited here.")
        return redirect("assignees:office_detail", pk=pk)
    errors = {}
    form_data = {}
    if request.method == "POST":
        form_data = request.POST
        name_en = form_data.get("name_en", "").strip()
        if not name_en:
            errors["name_en"] = "Name (English) is required."
        if not errors:
            office.name_en = name_en
            office.name_bn = form_data.get("name_bn", "").strip()
            office.save()
            messages.success(request, f"Office '{office.name_en}' updated successfully.")
            return redirect("assignees:office_detail", pk=office.pk)
    return render(request, "assignees/office_form.html", {
        "action": "Edit",
        "form_data": form_data,
        "errors": errors,
        "duplicates": [],
        "holder": office,
    })


@it_officer_required
def office_deactivate(request, pk):
    office = get_object_or_404(CachedOffice, pk=pk)
    from assignments.models import Assignment
    active_count = Assignment.objects.filter(
        assignee__office=office, returned_at__isnull=True
    ).count()
    if request.method == "POST":
        if active_count:
            messages.error(request, f"Cannot deactivate — {active_count} active assignment(s) must be resolved first.")
        else:
            office.mark_inactive()
            messages.success(request, f"Office '{office.name_en}' deactivated.")
        return redirect("assignees:offices")
    return render(request, "assignees/holder_deactivate_confirm.html", {
        "holder": office,
        "holder_type_display": "Office",
        "active_count": active_count,
        "deactivate_url_name": "assignees:office_deactivate",
        "list_url_name": "assignees:offices",
    })


# ─────────────────────────────────────────────────────────────────────────────
# Print history views (standalone print-friendly pages)
# ─────────────────────────────────────────────────────────────────────────────

@viewer_required
def employee_history_print(request, pk):
    from assignments.models import Assignment
    from django.utils import timezone
    emp = get_object_or_404(CachedEmployee, pk=pk)
    base_qs = (
        Assignment.objects.filter(assignee__employee=emp)
        .select_related("asset", "asset__asset_type", "performed_by")
        .order_by("assigned_at")
    )
    active_assignments = list(base_qs.filter(returned_at__isnull=True))
    history = list(base_qs.filter(returned_at__isnull=False).order_by("-returned_at"))
    return render(request, "print/history_print.html", {
        "page_title": f"Assignment History — {emp.name_en}",
        "holder": emp,
        "holder_type": "employee",
        "holder_type_display": "Employee",
        "active_assignments": active_assignments,
        "history": history,
        "generated_at": timezone.now(),
    })


@viewer_required
def mp_history_print(request, pk):
    from assignments.models import Assignment
    from django.utils import timezone
    mp = get_object_or_404(CachedMP, pk=pk)
    base_qs = (
        Assignment.objects.filter(assignee__mp=mp)
        .select_related("asset", "asset__asset_type", "performed_by")
        .order_by("assigned_at")
    )
    active_assignments = list(base_qs.filter(returned_at__isnull=True))
    history = list(base_qs.filter(returned_at__isnull=False).order_by("-returned_at"))
    return render(request, "print/history_print.html", {
        "page_title": f"Assignment History — {mp.name_en}",
        "holder": mp,
        "holder_type": "mp",
        "holder_type_display": "MP",
        "active_assignments": active_assignments,
        "history": history,
        "generated_at": timezone.now(),
    })


@viewer_required
def office_history_print(request, pk):
    from assignments.models import Assignment
    from django.utils import timezone
    office = get_object_or_404(CachedOffice, pk=pk)
    base_qs = (
        Assignment.objects.filter(assignee__office=office)
        .select_related("asset", "asset__asset_type", "performed_by")
        .order_by("assigned_at")
    )
    active_assignments = list(base_qs.filter(returned_at__isnull=True))
    history = list(base_qs.filter(returned_at__isnull=False).order_by("-returned_at"))
    return render(request, "print/history_print.html", {
        "page_title": f"Assignment History — {office.name_en}",
        "holder": office,
        "holder_type": "office",
        "holder_type_display": "Office",
        "active_assignments": active_assignments,
        "history": history,
        "generated_at": timezone.now(),
    })
