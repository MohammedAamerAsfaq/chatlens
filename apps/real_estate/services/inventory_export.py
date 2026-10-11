import csv

from django.http import StreamingHttpResponse

from apps.real_estate.services.inventory_import import CSV_FIELDS


class Echo:
    def write(self, value):
        return value


def property_export_response(queryset):
    writer = csv.writer(Echo())

    def rows():
        yield writer.writerow(CSV_FIELDS)
        for property_record in queryset.select_related('address').prefetch_related('listings'):
            address = getattr(property_record, 'address', None)
            listing = next((item for item in property_record.listings.all() if not item.is_archived), None)
            values = []
            for field in CSV_FIELDS:
                if hasattr(property_record, field):
                    value = getattr(property_record, field)
                elif address and hasattr(address, field):
                    value = getattr(address, field)
                elif listing and field == 'listing_status':
                    value = listing.status
                elif listing and field == 'status':
                    value = listing.status
                elif listing and hasattr(listing, field):
                    value = getattr(listing, field)
                else:
                    value = ''
                values.append(value if value is not None else '')
            yield writer.writerow(values)

    response = StreamingHttpResponse(rows(), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="real-estate-properties.csv"'
    return response
