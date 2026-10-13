"""Offline export adapters. No upstream SDKs, credentials, or network calls."""
from kernel.core.agent_receipts import ReceiptError


def append_openbot(session, event):
    """CopilotKit/OpenBot AuditEvent at afe6233, server/src/audit.ts.

    Input is one exported event, not a claim that a running upstream deployment
    has been instrumented or that every action is represented in its audit log.
    """
    if not isinstance(event, dict):
        raise ReceiptError("OpenBot event must be an object")
    if not isinstance(event.get("payload"), dict):
        raise ReceiptError("OpenBot payload must be an object")
    for field in ("id", "eventType", "targetType", "createdAt"):
        if not isinstance(event.get(field), str) or not event[field]:
            raise ReceiptError(f"OpenBot event requires {field}")
    kind = event["eventType"]
    outcome = ("refused" if kind.endswith(("_rejected", "_refused"))
               else "failed" if kind.endswith(("_failed", "_stalled"))
               else "observed")
    return session.append(source="openbot", source_event_id=event["id"],
                          action=kind, outcome=outcome, evidence=event)


def append_trace(session, provider, trace):
    """Commit to caller-supplied Opik/Helicone JSON exports (not live hooks).

    Export formats vary. Require an explicit non-empty trace id and retain the
    hash of the exact provided object; never infer grounding or success.
    """
    if provider not in ("opik", "helicone"):
        raise ReceiptError("unsupported trace provider")
    if not isinstance(trace, dict) or not isinstance(trace.get("id"), str) or not trace["id"]:
        raise ReceiptError("trace export requires a string id")
    return session.append(source=provider, source_event_id=trace["id"],
                          action="trace.exported", outcome="observed", evidence=trace)