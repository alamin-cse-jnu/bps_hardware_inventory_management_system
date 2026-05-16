from django.utils import timezone

from assignees.models import Assignee, AssigneeType, CachedEmployee, CachedMP, CachedOffice, Source
from assignments.models import Assignment, InactiveHolderAlert

from .client import PRPApiClient
from .models import SyncLog


def run_entity_sync(entity: str, triggered_by=None) -> SyncLog:
    """
    Sync a single entity type: 'employees', 'mps', or 'offices'.
    Creates its own SyncLog; only the relevant counters are populated.
    """
    log = SyncLog.objects.create(triggered_by=triggered_by)
    client = PRPApiClient()

    entity_map = {
        "employees": (client.get_employees, _sync_employees),
        "mps": (client.get_mps, _sync_mps),
        "offices": (client.get_offices, _sync_offices),
    }

    fetch_fn, sync_fn = entity_map[entity]
    try:
        records = fetch_fn()
        sync_fn(records, log)
        log.status = SyncLog.Status.SUCCESS
    except Exception as exc:
        log.status = SyncLog.Status.FAILED
        log.error_message = str(exc)

    log.completed_at = timezone.now()
    log.save(update_fields=["status", "completed_at", "error_message"])
    return log


def run_full_sync(triggered_by=None) -> SyncLog:
    """
    Main entry point for a full PRP data sync.

    Creates a SyncLog, attempts each endpoint independently (partial failure
    is better than total abort), and marks the log SUCCESS/PARTIAL/FAILED.
    Only touches source=PRP_API records — MANUAL records are invisible here
    (architectural decision #7).
    """
    log = SyncLog.objects.create(triggered_by=triggered_by)
    client = PRPApiClient()
    failures: list[str] = []

    for fetch_fn, sync_fn, label in [
        (client.get_employees, _sync_employees, "employees"),
        (client.get_mps, _sync_mps, "mps"),
        (client.get_offices, _sync_offices, "offices"),
    ]:
        try:
            records = fetch_fn()
            sync_fn(records, log)
        except Exception as exc:
            failures.append(f"{label}: {exc}")

    log.completed_at = timezone.now()
    if not failures:
        log.status = SyncLog.Status.SUCCESS
    elif len(failures) == 3:
        log.status = SyncLog.Status.FAILED
        log.error_message = "\n".join(failures)
    else:
        log.status = SyncLog.Status.PARTIAL
        log.error_message = "\n".join(failures)

    log.save(update_fields=["status", "completed_at", "error_message"])
    return log


# ─────────────────────────────────────────────────────────────────────────────
# Per-entity sync helpers
# ─────────────────────────────────────────────────────────────────────────────

def _sync_employees(api_records: list, log: SyncLog) -> None:
    # prp_ids_with_office: present in API AND have officeDetails — upsert these
    # prp_ids_no_office: present in API but officeDetails missing/null — handle separately
    prp_ids_with_office: set[str] = set()
    prp_ids_no_office: set[str] = set()

    for rec in api_records:
        prp_id = str(rec.get("prpId") or "").strip()
        if not prp_id:
            continue

        od = rec.get("officeDetails")
        if not od:
            # No office assigned — do not create; handle existing DB records below
            prp_ids_no_office.add(prp_id)
            continue

        prp_ids_with_office.add(prp_id)

        defaults = {
            "name_en": rec.get("nameEn") or "",
            "name_bn": rec.get("nameBn") or "",
            "mobile": rec.get("mobile") or "",
            "telephone": rec.get("telephone") or "",
            "gender": rec.get("gender") or "",
            "photo_url": rec.get("photo") or "",
            "api_status": rec.get("status") or "",
            "employee_class": rec.get("class"),
            "designation_en": rec.get("designationEn") or "",
            "designation_bn": rec.get("designationBn") or "",
            "is_active": True,
            "last_seen_active": timezone.now(),
            "wing_id": str(od.get("wingId") or ""),
            "wing_name_en": od.get("wingNameEn") or "",
            "wing_name_bn": od.get("wingNameBn") or "",
            "branch_id": str(od.get("branchId") or ""),
            "branch_name_en": od.get("branchNameEn") or "",
            "branch_name_bn": od.get("branchNameBn") or "",
            "section_id": str(od.get("sectionId") or ""),
            "section_name_en": od.get("sectionNameEn") or "",
            "section_name_bn": od.get("sectionNameBn") or "",
            "unit_id": str(od.get("unitId") or ""),
            "unit_name_en": od.get("unitNameEn") or "",
            "unit_name_bn": od.get("unitNameBn") or "",
            "office_id": str(od.get("officeId") or ""),
            "office_name_en": od.get("officeNameEn") or "",
            "office_name_bn": od.get("officeNameBn") or "",
        }

        emp, created = CachedEmployee.objects.update_or_create(
            prp_id=prp_id, source=Source.PRP_API, defaults=defaults,
        )
        if created:
            log.employees_added += 1
        else:
            log.employees_updated += 1
        Assignee.objects.get_or_create(
            assignee_type=AssigneeType.EMPLOYEE, employee=emp,
            defaults={"is_active": True},
        )

    # Employees that exist in API but now have no office —
    # keep if they have asset history, hard-delete if they do not.
    prp_all_seen = prp_ids_with_office | prp_ids_no_office
    for emp in CachedEmployee.objects.filter(
        source=Source.PRP_API, prp_id__in=prp_ids_no_office,
    ):
        has_history = Assignment.objects.filter(assignee__employee=emp).exists()
        if has_history:
            if emp.is_active:
                emp.mark_inactive()
                log.employees_flagged += 1
                _maybe_raise_alert(employee=emp)
        else:
            # Safe hard-delete: no assignments ever referenced this employee
            Assignee.objects.filter(
                assignee_type=AssigneeType.EMPLOYEE, employee=emp,
            ).delete()
            emp.delete()
            log.employees_deleted += 1

    # Employees completely absent from the API response — flag inactive as before
    for emp in CachedEmployee.objects.filter(
        source=Source.PRP_API, is_active=True,
    ).exclude(prp_id__in=prp_all_seen):
        emp.mark_inactive()
        log.employees_flagged += 1
        Assignee.objects.filter(
            assignee_type=AssigneeType.EMPLOYEE, employee=emp,
        ).update(is_active=False)
        _maybe_raise_alert(employee=emp)

    log.save(update_fields=[
        "employees_added", "employees_updated", "employees_flagged", "employees_deleted",
    ])


def _sync_mps(api_records: list, log: SyncLog) -> None:
    prp_ids_seen: set[str] = set()

    for rec in api_records:
        prp_id = str(rec.get("prpId") or "").strip()
        if not prp_id:
            continue
        prp_ids_seen.add(prp_id)

        defaults = {
            "name_en": rec.get("nameEn") or "",
            "name_bn": rec.get("nameBn") or "",
            "mobile": rec.get("mobile") or "",
            "telephone": rec.get("telephone") or "",
            "gender": rec.get("gender") or "",
            "photo_url": rec.get("photo") or "",
            "api_status": rec.get("status") or "",
            "parliament_no": rec.get("parliamentNo"),
            "constituency": rec.get("constituency") or "",
            "office_details_raw": str(rec.get("officeDetails") or ""),
            "is_active": True,
            "last_seen_active": timezone.now(),
        }

        mp, created = CachedMP.objects.update_or_create(
            prp_id=prp_id, source=Source.PRP_API, defaults=defaults,
        )
        if created:
            log.mps_added += 1
        else:
            log.mps_updated += 1
        Assignee.objects.get_or_create(
            assignee_type=AssigneeType.MP, mp=mp,
            defaults={"is_active": True},
        )

    for mp in CachedMP.objects.filter(
        source=Source.PRP_API, is_active=True,
    ).exclude(prp_id__in=prp_ids_seen):
        mp.mark_inactive()
        log.mps_flagged += 1
        Assignee.objects.filter(
            assignee_type=AssigneeType.MP, mp=mp,
        ).update(is_active=False)
        _maybe_raise_alert(mp=mp)

    log.save(update_fields=["mps_added", "mps_updated", "mps_flagged"])


def _sync_offices(api_records: list, log: SyncLog) -> None:
    prp_ids_seen: set[str] = set()

    for rec in api_records:
        prp_id = str(rec.get("id") or "").strip()
        if not prp_id:
            continue
        prp_ids_seen.add(prp_id)

        defaults = {
            "name_en": rec.get("nameEn") or "",
            "name_bn": rec.get("nameBn") or "",
            "parent_prp_id": str(rec.get("parentId") or ""),
            "is_abstract": bool(rec.get("isAbstractOffice", False)),
            "is_active": True,
            "last_seen_active": timezone.now(),
        }

        office, created = CachedOffice.objects.update_or_create(
            prp_id=prp_id, source=Source.PRP_API, defaults=defaults,
        )
        if created:
            log.offices_added += 1
        else:
            log.offices_updated += 1
        Assignee.objects.get_or_create(
            assignee_type=AssigneeType.OFFICE, office=office,
            defaults={"is_active": True},
        )

    for office in CachedOffice.objects.filter(
        source=Source.PRP_API, is_active=True,
    ).exclude(prp_id__in=prp_ids_seen):
        office.mark_inactive()
        log.offices_flagged += 1
        Assignee.objects.filter(
            assignee_type=AssigneeType.OFFICE, office=office,
        ).update(is_active=False)
        _maybe_raise_alert(office=office)

    log.save(update_fields=["offices_added", "offices_updated", "offices_flagged"])


def _maybe_raise_alert(*, employee=None, mp=None, office=None) -> None:
    """
    Create an InactiveHolderAlert if the now-inactive holder still has active
    assignments. Uses get_or_create to avoid duplicates on repeated syncs.
    No alert is raised for holders with no active assignments.
    """
    from assignees.models import Assignee, AssigneeType

    if employee is not None:
        active_filter = {"assignee__employee": employee, "returned_at__isnull": True}
        assignee_filter = {"assignee_type": AssigneeType.EMPLOYEE, "employee": employee}
    elif mp is not None:
        active_filter = {"assignee__mp": mp, "returned_at__isnull": True}
        assignee_filter = {"assignee_type": AssigneeType.MP, "mp": mp}
    elif office is not None:
        active_filter = {"assignee__office": office, "returned_at__isnull": True}
        assignee_filter = {"assignee_type": AssigneeType.OFFICE, "office": office}
    else:
        return

    if not Assignment.objects.filter(**active_filter).exists():
        return

    assignee = Assignee.objects.filter(**assignee_filter).first()
    if assignee:
        InactiveHolderAlert.objects.get_or_create(
            assignee=assignee, status="OPEN",
        )
