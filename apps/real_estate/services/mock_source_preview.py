from pathlib import Path
from uuid import uuid4

from rest_framework.exceptions import ValidationError

from .mock_source_files import file_checksum, iter_workbook_rows


ALLOWED_RECORD_LIMITS = (1, 10, 100, 1000)


def preview_workbooks(company, uploads, record_limit):
    limit = _validated_limit(record_limit)
    files = [upload for upload in uploads if upload]
    if not files:
        raise ValidationError({'files': 'Select at least one .xlsx workbook.'})

    run_id = str(uuid4())
    rows = []
    summaries = []
    for file_index, upload in enumerate(files):
        summary = _preview_workbook(
            company.pk, run_id, file_index, upload, limit - len(rows),
        )
        rows.extend(summary.pop('rows'))
        summaries.append(summary)
        if len(rows) >= limit:
            break

    return {
        'import_run_id': run_id,
        'rows': rows,
        'count': len(rows),
        'files': summaries,
        'record_limit': limit,
        'truncated': len(rows) >= limit,
        'persisted': False,
    }


def _preview_workbook(company_id, run_id, file_index, upload, remaining):
    name = Path(str(upload.name)).name
    if Path(name).suffix.lower() != '.xlsx':
        raise ValidationError({'files': f'{name}: only .xlsx workbooks are supported.'})

    checksum = file_checksum(upload)
    rows = []
    sheet_indexes = set()
    for row in iter_workbook_rows(company_id, run_id, upload, name, checksum):
        row['preview_id'] = f'{run_id}:{file_index}:{row["source_sheet_index"]}:{row["source_row_number"]}'
        row['processing_notes'] = 'Preview only; not persisted.'
        row['imported_at'] = None
        rows.append(row)
        sheet_indexes.add(row['source_sheet_index'])
        if len(rows) >= remaining:
            break

    return {
        'name': name,
        'checksum': checksum,
        'sheets_scanned': len(sheet_indexes),
        'rows_returned': len(rows),
        'rows': rows,
    }


def _validated_limit(value):
    try:
        limit = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError({'record_limit': 'Choose a supported record limit.'}) from exc
    if limit not in ALLOWED_RECORD_LIMITS:
        allowed = ', '.join(str(item) for item in ALLOWED_RECORD_LIMITS)
        raise ValidationError({'record_limit': f'Choose one of: {allowed}.'})
    return limit
