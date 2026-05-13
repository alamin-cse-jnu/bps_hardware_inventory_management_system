from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from config.permissions import it_officer_required, viewer_required

from .models import Assignee, AssigneeType, CachedEmployee, CachedMP, CachedOffice, Source


# ─────────────────────────────────────────────────────────────────────────────
# Assignment search / select (used by assign panel — Session 2.2)
# ─────────────────────────────────────────────────────────────────────────────

@it_officer_required
def search(request):
    q = request.GET.get("q", "").strip()
    results = []
    if len(q) >= 2:
        qs = (
            Assignee.objects.filter(is_active=True)
            .exclude(
                Q(assignee_type="EMPLOYEE", employee__is_active=False)
                | Q(assignee_type="MP", mp__is_active=False)
                | Q(assignee_type="OFFICE", office__is_active=False)
            )
            .filter(
                Q(employee__name_en__icontains=q)
                | Q(employee__section_name_en__icontains=q)
                | Q(employee__office_name_en__icontains=q)
                | Q(mp__name_en__icontains=q)
                | Q(mp__constituency__icontains=q)
                | Q(office__name_en__icontains=q)
                | Q(location__name__icontains=q)
            )
            .select_related("employee", "mp", "office", "location__parent__parent")[:12]
        )
        results = list(qs)

    asset_pk = request.GET.get("asset_pk", "")
    return render(request, "assignees/search_results.html", {
        "results": results,
        "q": q,
        "asset_pk": asset_pk,
    })


@it_officer_required
def select_card(request, pk):
    assignee = get_object_or_404(Assignee, pk=pk)
    asset_pk = request.GET.get("asset_pk", "")
    return render(request, "assignees/selected_card.html", {
        "assignee": assignee,
        "asset_pk": asset_pk,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Employee list / detail / create / edit / deactivate
# ─────────────────────────────────────────────────────────────────────────────

@viewer_required
def employee_list(request):
    qs = CachedEmployee.objects.all()
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name_en__icontains=q) | Q(name_bn__icontains=q)
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
    paginator = Paginator(qs.order_by("name_en"), 25)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    return render(request, "assignees/employee_list.html", {
        "page_obj": page_obj,
        "q": q,
        "source_filter": source_filter,
        "active_filter": active_filter,
    })


@viewer_required
def employee_detail(request, pk):
    emp = get_object_or_404(CachedEmployee, pk=pk)
    from assignments.models import Assignment
    assignments = (
        Assignment.objects.filter(assignee__employee=emp)
        .select_related("asset", "asset__asset_type", "performed_by")
        .order_by("-assigned_at")[:50]
    )
    return render(request, "assignees/holder_detail.html", {
        "holder": emp,
        "holder_type": "employee",
        "holder_type_display": "Employee",
        "assignments": assignments,
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
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name_en__icontains=q) | Q(name_bn__icontains=q)
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
    paginator = Paginator(qs.order_by("name_en"), 25)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    parliament_nos = list(
        CachedMP.objects.values_list("parliament_no", flat=True)
        .distinct().order_by("-parliament_no")
        .exclude(parliament_no__isnull=True)
    )
    return render(request, "assignees/mp_list.html", {
        "page_obj": page_obj,
        "q": q,
        "source_filter": source_filter,
        "active_filter": active_filter,
        "parl_filter": parl_filter,
        "parliament_nos": parliament_nos,
    })


@viewer_required
def mp_detail(request, pk):
    mp = get_object_or_404(CachedMP, pk=pk)
    from assignments.models import Assignment
    assignments = (
        Assignment.objects.filter(assignee__mp=mp)
        .select_related("asset", "asset__asset_type", "performed_by")
        .order_by("-assigned_at")[:50]
    )
    return render(request, "assignees/holder_detail.html", {
        "holder": mp,
        "holder_type": "mp",
        "holder_type_display": "MP",
        "assignments": assignments,
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
    paginator = Paginator(qs.order_by("name_en"), 25)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    return render(request, "assignees/office_list.html", {
        "page_obj": page_obj,
        "q": q,
        "source_filter": source_filter,
        "active_filter": active_filter,
    })


@viewer_required
def office_detail(request, pk):
    office = get_object_or_404(CachedOffice, pk=pk)
    from assignments.models import Assignment
    assignments = (
        Assignment.objects.filter(assignee__office=office)
        .select_related("asset", "asset__asset_type", "performed_by")
        .order_by("-assigned_at")[:50]
    )
    return render(request, "assignees/holder_detail.html", {
        "holder": office,
        "holder_type": "office",
        "holder_type_display": "Office",
        "assignments": assignments,
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
