from apps.task_management.models import BackgroundTask
from apps.task_management.registry import UnsupportedTaskPayload, task_handler


def validate_mock_import_payload(payload):
    if not isinstance(payload, dict) or payload.get('version') != 1:
        raise UnsupportedTaskPayload('Payload version 1 is required.')
    if not isinstance(payload.get('company_id'), int) or payload['company_id'] <= 0:
        raise UnsupportedTaskPayload('company_id must be a positive integer.')
    if not isinstance(payload.get('import_run_id'), str) or not payload['import_run_id']:
        raise UnsupportedTaskPayload('import_run_id is required.')
    file_names = payload.get('file_names')
    if file_names is not None and (
        not isinstance(file_names, list)
        or not file_names
        or any(not isinstance(name, str) or not name for name in file_names)
    ):
        raise UnsupportedTaskPayload('file_names must be a non-empty string list or null.')


def validate_mock_inquiry_payload(payload):
    if not isinstance(payload, dict) or payload.get('version') != 1:
        raise UnsupportedTaskPayload('Payload version 1 is required.')
    if not isinstance(payload.get('company_id'), int) or payload['company_id'] <= 0:
        raise UnsupportedTaskPayload('company_id must be a positive integer.')
    if not isinstance(payload.get('run_id'), str) or not payload['run_id']:
        raise UnsupportedTaskPayload('run_id is required.')


@task_handler(
    key='real_estate.import_mock_sources',
    default_queue='real_estate_imports',
    payload_validator=validate_mock_import_payload,
    retry_safe=True,
)
def import_mock_sources(payload, context):
    from apps.real_estate.services.mock_source_import import import_mock_sources as run_import
    from apps.tenancy.models import Company

    task_company_id = BackgroundTask.objects.values_list(
        'company_id', flat=True,
    ).get(pk=context.task_id)
    if task_company_id != payload['company_id']:
        raise ValueError('Task company does not match import payload company.')
    company = Company.objects.get(pk=payload['company_id'])
    if company.industry_type != Company.INDUSTRY_REAL_ESTATE:
        raise ValueError('Task company is not configured for Real Estate.')
    return run_import(
        company,
        payload['import_run_id'],
        payload.get('file_names'),
    )


@task_handler(
    key='real_estate.generate_mock_inquiries',
    default_queue='real_estate_imports',
    payload_validator=validate_mock_inquiry_payload,
    retry_safe=True,
)
def generate_mock_inquiries(payload, context):
    from apps.real_estate.models import RealEstateMockInquiryRun
    from apps.real_estate.services.mock_inquiry_generation import generate_mock_inquiries as run_generation

    task_company_id = BackgroundTask.objects.values_list(
        'company_id', flat=True,
    ).get(pk=context.task_id)
    if task_company_id != payload['company_id']:
        raise ValueError('Task company does not match mock inquiry company.')
    run = RealEstateMockInquiryRun.objects.get(pk=payload['run_id'])
    if run.company_id != payload['company_id']:
        raise ValueError('Mock inquiry run belongs to another company.')
    return run_generation(run.pk)
