from apps.task_management.models import BackgroundTask
from apps.task_management.registry import UnsupportedTaskPayload, task_handler


def validate_company_payload(payload):
    if not isinstance(payload, dict) or payload.get('version') != 1:
        raise UnsupportedTaskPayload('Payload version 1 is required.')
    if not isinstance(payload.get('company_id'), int) or payload['company_id'] <= 0:
        raise UnsupportedTaskPayload('company_id must be a positive integer.')


def validate_reminder_payload(payload):
    validate_company_payload(payload)
    if not isinstance(payload.get('reminder_id'), int) or payload['reminder_id'] <= 0:
        raise UnsupportedTaskPayload('reminder_id must be a positive integer.')


def validate_activity_payload(payload):
    validate_company_payload(payload)
    if not isinstance(payload.get('message_id'), int) or payload['message_id'] <= 0:
        raise UnsupportedTaskPayload('message_id must be a positive integer.')


def _validate_task_company(context, company_id):
    task_company_id = BackgroundTask.objects.values_list('company_id', flat=True).get(pk=context.task_id)
    if task_company_id != company_id:
        raise ValueError('Task company does not match payload company.')


@task_handler(
    key='clientpulse.scan_due_reminders', default_queue='clientpulse',
    payload_validator=validate_company_payload, retry_safe=True,
)
def scan_due_reminders_task(payload, context):
    from apps.clientpulse.services.reminder_service import scan_due_reminders
    _validate_task_company(context, payload['company_id'])
    return scan_due_reminders(payload['company_id'])


@task_handler(
    key='clientpulse.deliver_reminder', default_queue='clientpulse',
    payload_validator=validate_reminder_payload, retry_safe=True,
)
def deliver_reminder_task(payload, context):
    from apps.clientpulse.services.reminder_service import deliver_reminder
    _validate_task_company(context, payload['company_id'])
    return deliver_reminder(payload['reminder_id'], payload['company_id'])


@task_handler(
    key='clientpulse.project_activity', default_queue='clientpulse',
    payload_validator=validate_activity_payload, retry_safe=True,
)
def project_activity_task(payload, context):
    from apps.clientpulse.services.activity_projection import project_message_activity
    _validate_task_company(context, payload['company_id'])
    return project_message_activity(payload['message_id'], payload['company_id'])
