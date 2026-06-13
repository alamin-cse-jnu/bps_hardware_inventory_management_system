"""
Automatic audit capture.

Generic ``pre_save`` / ``post_save`` / ``post_delete`` receivers diff the
registered data models (assets, catalog, locations). Dedicated receivers turn
status changes (LifecycleEvent) and ownership changes (Assignment) into concise
entries so the activity log is one complete timeline.
"""

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from assignments.models import Assignment
from lifecycle.models import LifecycleEvent

from .registry import TRACKED, model_label, tracked_fields
from .services import record


def _value(instance, field):
    """JSON-serialisable display value for a field (related object → str)."""
    if field.is_relation:
        rel = getattr(instance, field.name, None)
        return str(rel) if rel is not None else None
    val = getattr(instance, field.attname)
    if val is None or isinstance(val, (bool, int, float, str, dict, list)):
        return val
    return str(val)


# ── Generic data-model diffing ──────────────────────────────────────────────────

@receiver(pre_save, dispatch_uid="audit_stash_old")
def _stash_old(sender, instance, raw=False, **kwargs):
    if raw or model_label(sender) not in TRACKED or not instance.pk:
        return
    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    instance._audit_old = {f.name: _value(old, f) for f in tracked_fields(sender)}


@receiver(post_save, dispatch_uid="audit_log_save")
def _log_save(sender, instance, created, raw=False, **kwargs):
    if raw or model_label(sender) not in TRACKED:
        return
    fields = tracked_fields(sender)

    if created:
        changes = {}
        for f in fields:
            v = _value(instance, f)
            if v not in (None, "", {}, []):
                changes[f.name] = [None, v]
        record("CREATE", instance, changes=changes)
        return

    old = getattr(instance, "_audit_old", None) or {}
    changes = {}
    for f in fields:
        new_v = _value(instance, f)
        old_v = old.get(f.name)
        if old_v != new_v:
            changes[f.name] = [old_v, new_v]
    if changes:
        record("UPDATE", instance, changes=changes)


@receiver(post_delete, dispatch_uid="audit_log_delete")
def _log_delete(sender, instance, **kwargs):
    if model_label(sender) not in TRACKED:
        return
    record("DELETE", instance)


# ── Status changes (lifecycle) ──────────────────────────────────────────────────

@receiver(post_save, sender=LifecycleEvent, dispatch_uid="audit_lifecycle")
def _log_lifecycle(sender, instance, created, raw=False, **kwargs):
    if raw or not created:
        return
    record(
        "STATUS", instance.asset,
        actor=instance.performed_by,
        changes={"status": [instance.old_status, instance.new_status]},
        note=instance.get_event_type_display(),
    )


# ── Ownership changes (assignment) ──────────────────────────────────────────────

@receiver(pre_save, sender=Assignment, dispatch_uid="audit_stash_assignment")
def _stash_assignment(sender, instance, raw=False, **kwargs):
    if raw:
        return
    if instance.pk:
        old = sender.objects.filter(pk=instance.pk).only("returned_at").first()
        instance._audit_old_returned = old.returned_at if old else None
    else:
        instance._audit_old_returned = None


@receiver(post_save, sender=Assignment, dispatch_uid="audit_assignment")
def _log_assignment(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    holder = instance.assignee.display_name if instance.assignee_id else "—"
    if created:
        record(
            "ASSIGN", instance.asset,
            actor=instance.performed_by,
            changes={"holder": [None, holder]},
            note=instance.batch.reference if instance.batch_id else "",
        )
        return
    # An existing row gaining returned_at means it was closed (return / transfer-out).
    old_returned = getattr(instance, "_audit_old_returned", None)
    if old_returned is None and instance.returned_at is not None:
        record(
            "RETURN", instance.asset,
            actor=instance.performed_by,
            changes={"holder": [holder, None]},
        )
