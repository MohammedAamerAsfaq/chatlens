from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models


class PropertyType(models.Model):
    CATEGORY_CHOICES = [
        ('residential', 'Residential'),
        ('commercial', 'Commercial'),
        ('land', 'Land'),
        ('other', 'Other'),
    ]

    company = models.ForeignKey(
        'tenancy.Company', on_delete=models.CASCADE, related_name='real_estate_property_types',
    )
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='children',
    )
    name = models.CharField(max_length=100)
    code = models.CharField(
        max_length=50,
        validators=[RegexValidator(r'^[a-z0-9]+(?:_[a-z0-9]+)*$', 'Use lowercase letters, numbers, and underscores.')],
    )
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    description = models.CharField(max_length=255, blank=True)
    aliases = models.JSONField(default=list, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'real_estate_property_type'
        ordering = ['sort_order', 'name', 'id']
        constraints = [
            models.UniqueConstraint(fields=['company', 'code'], name='re_property_type_company_code_uniq'),
            models.UniqueConstraint(fields=['company', 'name'], name='re_property_type_company_name_uniq'),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        self.name = self.name.strip()
        self.code = self.code.strip().lower()
        if not self.name:
            raise ValidationError({'name': 'Property type name is required.'})
        if not isinstance(self.aliases, list):
            raise ValidationError({'aliases': 'Aliases must be a list.'})
        self.aliases = list(dict.fromkeys(
            str(value).strip() for value in self.aliases if str(value).strip()
        ))
        if self.parent_id:
            if self.parent_id == self.pk:
                raise ValidationError({'parent': 'A property type cannot be its own parent.'})
            if self.parent.company_id != self.company_id:
                raise ValidationError({'parent': 'The parent type must belong to this company.'})
            ancestor = self.parent
            visited = set()
            while ancestor:
                if ancestor.pk == self.pk or ancestor.pk in visited:
                    raise ValidationError({'parent': 'The property type hierarchy cannot contain a cycle.'})
                visited.add(ancestor.pk)
                ancestor = ancestor.parent
