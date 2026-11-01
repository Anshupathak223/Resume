"""Notification templates and simulated sender. Replace the sender when email is configured."""
import logging
from datetime import datetime, timezone
from string import Template

from candidate_store import NOTIFY_STATUSES, STATUSES, log_notification, update_status

logger = logging.getLogger("candidate_notifications")

EMAIL_TEMPLATES = {
    "Shortlisted": {
        "subject": "An update on your application for ${job_title}",
        "body": """Hello ${candidate_name},

We are pleased to let you know that you have been shortlisted for ${job_title}.

Next steps: ${next_steps}

Thank you,
The Recruiting Team""",
        "next_steps": "Our recruiting team will be in touch with more information.",
    },
    "Interview Scheduled": {
        "subject": "Interview update for ${job_title}",
        "body": """Hello ${candidate_name},

We would like to invite you to interview for ${job_title}.

Next steps: ${next_steps}

Thank you,
The Recruiting Team""",
        "next_steps": "Our team will contact you to confirm a time and share the interview details.",
    },
    "Rejected": {
        "subject": "An update on your application for ${job_title}",
        "body": """Hello ${candidate_name},

Thank you for your interest in ${job_title}. We will not be moving forward with your application at this time.

Next steps: ${next_steps}

We appreciate the time you took to apply and wish you well.
The Recruiting Team""",
        "next_steps": "There is no further action required for this application.",
    },
}


def render_email(status, candidate):
    template = EMAIL_TEMPLATES[status]
    values = {
        "candidate_name": candidate["name"],
        "job_title": candidate["job_title"],
        "next_steps": template["next_steps"],
    }
    return Template(template["subject"]).substitute(values), Template(template["body"]).substitute(values)


def send_simulated_email(*, recipient, subject, body):
    """Simulate transport. Swap this function for SMTP/SendGrid later."""
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if not recipient:
        print(f"SIMULATED EMAIL FAILED at={timestamp} reason=no_candidate_email subject={subject!r}", flush=True)
        logger.warning("SIMULATED EMAIL FAILED at=%s reason=no_candidate_email subject=%r", timestamp, subject)
        return {"success": False, "failure": "Candidate has no email address.", "timestamp": timestamp}
    print(f"SIMULATED EMAIL SENT at={timestamp} to={recipient} subject={subject!r}\n{body}", flush=True)
    logger.info(
        "SIMULATED EMAIL at=%s to=%s subject=%r\n%s",
        timestamp, recipient, subject, body,
    )
    return {"success": True, "failure": None, "timestamp": timestamp}


def update_candidate_status(candidate_id, new_status):
    """The single status-change path: persist status, then notify and log when needed."""
    if new_status not in STATUSES:
        raise ValueError("Invalid status. Choose one of the supported candidate statuses.")

    candidate = update_status(candidate_id, new_status)
    if candidate is None:
        return None
    if candidate["unchanged"]:
        return {"candidate_id": candidate_id, "status": new_status,
                "status_updated_at": candidate["status_updated_at"], "unchanged": True,
                "notification": None}
    response = {
        "candidate_id": candidate_id,
        "status": new_status,
        "status_updated_at": candidate["status_updated_at"],
        "unchanged": False,
        "notification": None,
    }
    if new_status in NOTIFY_STATUSES:
        subject, body = render_email(new_status, candidate)
        try:
            delivery = send_simulated_email(recipient=candidate["email"], subject=subject, body=body)
        except Exception as exc:
            delivery = {"success": False, "failure": str(exc), "timestamp": utc_now()}
            logger.exception("Simulated notification failed for candidate_id=%s", candidate_id)
        log_notification(
            candidate_id, new_status, delivery["timestamp"], delivery["success"],
            delivery["failure"], candidate["email"],
        )
        response["notification"] = {
            "success": delivery["success"], "failure": delivery["failure"],
            "timestamp": delivery["timestamp"], "simulated": True,
        }
    return response
