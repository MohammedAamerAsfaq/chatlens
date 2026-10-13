from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models


class PropertyTypeFieldDefinition(models.Model):
    TYPE_TEXT = 'text'
    TYPE_NUMBER = 'number'
    TYPE_BOOLEAN = 'boolean'
    TYPE_SELECT = 'select'
    TYPE_LIST = 'list'
    DATA_TYPE_CHOICES = [
        (TYPE_TEXT, 'Text'),
        (TYPE_NUMBER, 'Number'),
        (TYPE_BOOLEAN, 'Boolean'),
        (TYPE_SELECT, 'Selection'),
        (TYPE_LIST, 'List'),
    ]

    company = models.ForeignKey(
        'tenancy.Company', on_delete=models.CASCADE,
        related_name='real_estate_property_field_definitions',
    )
    property_type = models.ForeignKey(
        'real_estate.PropertyType', on_delete=models.CASCADE,
        related_name='field_definitions',
    )
    code = models.CharField(
        max_length=60,
        validators=[RegexValidator(
            r'^[a-z0-9]+(?:_[a-z0-9]+)*$',
            'Use lowercase letters, numbers, and underscores.',
        )],
    )
    label = models.CharField(max_length=120)
    data_type = models.CharField(max_length=20, choices=DATA_TYPE_CHOICES)
    options = models.JSONField(default=list, blank=True)
    unit_hint = models.CharField(max_length=30, blank=True)
    is_required = models.BooleanField(default=False)
    is_filterable = models.BooleanField(default=False)
    is_embeddable = models.BooleanField(default=True)
    condition_field = models.CharField(max_length=60, blank=True)
    condition_value = models.CharField(max_length=120, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'real_estate_property_type_field'
        ordering = ['sort_order', 'label', 'id']
        constraints = [models.UniqueConstraint(
            fields=['company', 'property_type', 'code'],
            name='re_property_type_field_code_uniq',
        )]

    def clean(self):
        super().clean()
        if self.property_type_id and self.property_type.company_id != self.company_id:
            raise ValidationError({'property_type': 'The property type must belong to this company.'})
        if not isinstance(self.options, list):
            raise ValidationError({'options': 'Options must be a list.'})
        if self.data_type == self.TYPE_SELECT and not self.options:
            raise ValidationError({'options': 'Selection fields require at least one option.'})

    def __str__(self):
        return f'{self.property_type.code}.{self.code}'
