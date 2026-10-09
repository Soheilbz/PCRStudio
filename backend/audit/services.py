from audit.models import AuditEvent

_ALLOWED_METADATA = {"version", "role", "reason", "target_membership_id"}


def record(actor, workspace, subject_id, action: str, **metadata):
    if metadata.get("reason") not in {
        None,
        "owner_removed",
        "owner_suspended",
        "security_revocation",
    }:
        raise ValueError("Unapproved audit reason")
    if not metadata.keys() <= _ALLOWED_METADATA:
        raise ValueError("Unapproved audit metadata")
    return AuditEvent.objects.create(
        actor=actor,
        workspace_id=workspace.id if workspace else None,
        subject_id=subject_id,
        action=action,
        metadata=metadata,
    )
