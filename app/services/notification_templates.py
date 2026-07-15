"""Simple string templates for notification emails."""

TEMPLATES: dict[str, tuple[str, str]] = {
    "account_deactivated": (
        "Your WISPGen account has been deactivated",
        "Your WISPGen account ({email}) has been deactivated. "
        "Contact your administrator if you believe this was a mistake.",
    ),
    "account_reactivated": (
        "Your WISPGen account has been reactivated",
        "Your WISPGen account ({email}) has been reactivated. "
        "You can now log in and continue working.",
    ),
    "roles_updated": (
        "Your WISPGen roles have been updated",
        "Your WISPGen roles have been updated to: {roles}.",
    ),
    "domain_assigned": (
        "You have been assigned to a WISP domain",
        "You have been assigned as {role} for the {domain_name} domain.",
    ),
    "domain_unassigned": (
        "You have been unassigned from a WISP domain",
        "You have been removed as {role} for the {domain_name} domain.",
    ),
    "domain_submitted": (
        "A WISP domain is ready for review",
        "The {domain_name} domain has been submitted for review.",
    ),
    "domain_approved": (
        "A WISP domain has been approved",
        "The {domain_name} domain has been approved.",
    ),
    "domain_revised_and_approved": (
        "A WISP domain has been revised and approved",
        "The {domain_name} domain has been revised and approved.",
    ),
    "domain_deferred": (
        "A WISP domain needs more information",
        "The {domain_name} domain has been returned for more information.",
    ),
    "wisp_complete": (
        "Your WISP is complete",
        "All 14 domains have been approved. Your WISP is complete.",
    ),
    "answer_saved": (
        "Answer saved",
        "Your answer has been saved.",
    ),
    "followups_waived": (
        "Follow-up questions waived",
        "We were unable to generate follow-up questions for one of your answers. "
        "The answer has been marked complete so you can continue.",
    ),
}


def render(kind: str, payload: dict) -> tuple[str, str]:
    """Return (subject, body) for a notification kind and payload."""
    if kind not in TEMPLATES:
        raise KeyError(kind)
    subject_template, body_template = TEMPLATES[kind]
    return subject_template.format(**payload), body_template.format(**payload)
