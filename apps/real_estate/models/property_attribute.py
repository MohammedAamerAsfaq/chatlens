from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models


class PropertyAttributeDefinition(models.Model):
    TYPE_TEXT = 'text'
    TYPE_NUMBER = 'number'
    TYPE_BOOLEAN = 'boolean'
    TYPE_SELECT = 'select'
    TYPE_LIST = 'list'
    DATA_TYPE_CHOICES = [
        (TYPE_TEXT, 'Text'), (TYPE_NUMBER, 'Number'),
        (TYPE_BOOLEAN, 'Boolean'), (TYPE_SELECT, 'Selection'), (TYPE_LIST, 'List'),
    ]
    MATCH_EXACT = 'exact'
    MATCH_NUMERIC = 'numeric_distance'
    MATCH_TAXONOMY = 'taxonomy'
    MATCH_SEMANTIC = 'semantic'
    MATCHING_CHOICES = [
        (MATCH_EXACT, 'Exact'), (MATCH_NUMERIC, 'Numeric distance'),
        (MATCH_TAXONOMY, 'Taxonomy'), (MATCH_SEMANTIC, 'Semantic'),
    ]

    company = models.ForeignKey(
        'tenancy.Company', on_delete=models.CASCADE,
        related_name='real_estate_attribute_definitions',
    )
    code = models.CharField(max_length=60, validators=[RegexValidator(
        r'^[a-z0-9]+(?:_[a-z0-9]+)*$', 'Use lowercase letters, numbers, and underscores.',
    )])
    label = models.CharField(max_length=120)
    data_type = models.CharField(max_length=20, choices=DATA_TYPE_CHOICES)
    matching_strategy = models.CharField(
        max_length=30, choices=MATCHING_CHOICES, default=MATCH_EXACT,
    )
    unit_hint = models.CharField(max_length=30, blank=True)
    allow_multiple = models.BooleanField(default=False)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'real_estate_property_attribute_definition'
        ordering = ['sort_order', 'label', 'id']
        constraints = [models.UniqueConstraint(
            fields=['company', 'code'], name='re_attribute_definition_company_code_uniq',
        )]

    def clean(self):
        self.code = self.code.strip().lower()
        self.label = self.label.strip()

    def __str__(self):
        return self.label


class PropertyAttributeOption(models.Model):
    company = models.ForeignKey(
        'tenancy.Company', on_delete=models.CASCADE,
        related_name='real_estate_attribute_options',
    )
    definition = models.ForeignKey(
        PropertyAttributeDefinition, on_delete=models.CASCADE, related_name='options',
    )
    code = models.CharField(max_length=80, validators=[RegexValidator(
        r'^[a-z0-9]+(?:_[a-z0-9]+)*$', 'Use lowercase letters, numbers, and underscores.',
    )])
    label = models.CharField(max_length=120)
    numeric_value = models.DecimalField(max_digits=16, decimal_places=4, null=True, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'real_estate_property_attribute_option'
        ordering = ['sort_order', 'label', 'id']
        constraints = [models.UniqueConstraint(
            fields=['company', 'definition', 'code'], name='re_attribute_option_definition_code_uniq',
        )]

    def clean(self):
        self.code = self.code.strip().lower()
        self.label = self.label.strip()
        if self.definition_id and self.definition.company_id != self.company_id:
            raise ValidationError({'definition': 'The definition must belong to this company.'})

    def __str__(self):
        return f'{self.definition.code}: {self.label}'


class PropertyAttributeAlias(models.Model):
    company = models.ForeignKey(
        'tenancy.Company', on_delete=models.CASCADE,
        related_name='real_estate_attribute_aliases',
    )
    definition = models.ForeignKey(
        PropertyAttributeDefinition, on_delete=models.CASCADE, related_name='aliases',
    )
    option = models.ForeignKey(
        PropertyAttributeOption, null=True, blank=True, on_delete=models.CASCADE,
        related_name='aliases',
    )
    alias = models.CharField(max_length=160)
    normalized_alias = models.CharField(max_length=160, editable=False)
    locale = models.CharField(max_length=12, blank=True, default='')
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'real_estate_property_attribute_alias'
        ordering = ['normalized_alias', 'id']
        constraints = [models.UniqueConstraint(
            fields=['company', 'definition', 'normalized_alias'],
            name='re_attribute_alias_definition_value_uniq',
        )]

    def clean(self):
        self.alias = self.alias.strip()
        self.normalized_alias = normalize_alias(self.alias)
        if self.definition_id and self.definition.company_id != self.company_id:
            raise ValidationError({'definition': 'The definition must belong to this company.'})
        if self.option_id and (
            self.option.company_id != self.company_id
            or self.option.definition_id != self.definition_id
        ):
            raise ValidationError({'option': 'The option must belong to this definition and company.'})

    def save(self, *args, **kwargs):
        self.normalized_alias = normalize_alias(self.alias)
        super().save(*args, **kwargs)

    @staticmethod
    def normalize(value):
        return normalize_alias(value)


def normalize_alias(value):
    return ' '.join(str(value or '').strip().casefold().replace('_', ' ').split())
