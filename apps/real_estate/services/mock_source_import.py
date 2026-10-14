from itertools import islice

from apps.real_estate.models import RealEstateMockSourceRecord

from .mock_source_files import file_checksum, iter_workbook_rows, resolve_workbooks


BATCH_SIZE = 1000


def import_mock_sources(company, import_run_id, file_names=None):
    workbooks = resolve_workbooks(file_names)
    before_count = RealEstateMockSourceRecord.objects.filter(company=company).count()
    rows_seen = 0
    files = []

    for file_name, path in workbooks:
        checksum = file_checksum(path)
        file_seen = 0
        row_iterator = iter_workbook_rows(
            company.pk, import_run_id, path, file_name, checksum,
        )
        while True:
            batch = list(islice(row_iterator, BATCH_SIZE))
            if not batch:
                break
            RealEstateMockSourceRecord.objects.bulk_create(
                [RealEstateMockSourceRecord(**row) for row in batch],
                batch_size=BATCH_SIZE,
                ignore_conflicts=True,
            )
            file_seen += len(batch)
            rows_seen += len(batch)
        files.append({
            'name': file_name,
            'checksum': checksum,
            'rows_seen': file_seen,
        })

    after_count = RealEstateMockSourceRecord.objects.filter(company=company).count()
    created = max(0, after_count - before_count)
    return {
        'import_run_id': str(import_run_id),
        'files_processed': len(files),
        'rows_seen': rows_seen,
        'records_created': created,
        'duplicates_skipped': max(0, rows_seen - created),
        'total_records': after_count,
        'files': files,
    }
