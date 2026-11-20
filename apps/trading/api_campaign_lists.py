"""Saved campaign lists: reusable contact, group and product lists for campaigns.

Anyone who can view campaigns can see and use the lists; creating, renaming, deleting
and changing members needs campaigns.audiences.manage. Applying a list to a campaign is
a campaign change (see the add-list / add-product-list actions on the campaign viewsets).
"""
from django.db import transaction
from django.db.models import Count
from django.utils.timezone import now
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.tenancy.api_permissions import CompanyPermissionRequired
from apps.tenancy.services.access import default_company_for_user

from .models import CampaignList, CampaignListContact, CampaignListGroup, CampaignListKind, CampaignListProduct
from .services.campaign_lists import (
    eligible_for,
    member_field,
    member_rows,
    search_eligible,
    spec,
    visible_member_rows,
)

CANDIDATE_PAGE_SIZE = 25
ROW_MODELS = {
    CampaignListKind.CONTACTS: CampaignListContact,
    CampaignListKind.GROUPS: CampaignListGroup,
    CampaignListKind.PRODUCTS: CampaignListProduct,
}
CANDIDATE_ORDER = {
    CampaignListKind.CONTACTS: 'display_name',
    CampaignListKind.GROUPS: 'name',
    CampaignListKind.PRODUCTS: 'name',
}
NOT_ELIGIBLE = {
    CampaignListKind.CONTACTS: "contacts are not phone-number contacts on this company's accounts you can see",
    CampaignListKind.GROUPS: "groups are not sendable groups on this company's accounts you can see",
    CampaignListKind.PRODUCTS: "products are not active products of this company",
}


def _account_name(account):
    return account.display_name or account.phone_number or f'Account {account.pk}'


def _contact_entry(contact):
    return {
        'id': contact.pk,
        'name': contact.display_name or contact.push_name or contact.phone_number or contact.wa_contact_id,
        'detail': contact.phone_number or contact.wa_contact_id,
        'account_name': _account_name(contact.account),
    }


def _group_entry(group):
    return {
        'id': group.pk,
        'name': group.name or group.wa_group_id,
        'detail': group.wa_group_id,
        'account_name': _account_name(group.account),
    }


def _product_entry(product):
    price = f'{product.sale_price} {product.currency}'.strip() if product.sale_price is not None else 'No price'
    return {
        'id': product.pk,
        'name': product.name,
        'detail': f'{price} · Qty {product.qty}',
        'account_name': product.brand or product.category or '',
    }


ENTRIES = {
    CampaignListKind.CONTACTS: _contact_entry,
    CampaignListKind.GROUPS: _group_entry,
    CampaignListKind.PRODUCTS: _product_entry,
}


class CampaignListSerializer(serializers.ModelSerializer):
    member_count = serializers.SerializerMethodField()
    created_by = serializers.CharField(source='created_by.username', read_only=True, default=None)

    class Meta:
        model = CampaignList
        fields = ['id', 'kind', 'name', 'description', 'member_count', 'created_by', 'created_at', 'updated_at']
        read_only_fields = ['id', 'member_count', 'created_by', 'created_at', 'updated_at']

    def get_member_count(self, obj):
        return getattr(obj, f"{spec(obj)['rows']}_count")

    def validate_name(self, value):
        value = (value or '').strip()
        if not value:
            raise ValidationError('Name is required.')
        return value

    def validate(self, attrs):
        if self.instance:
            if 'kind' in attrs and attrs['kind'] != self.instance.kind:
                raise ValidationError({'kind': 'A list cannot change its kind.'})
            kind = self.instance.kind
        else:
            kind = attrs.get('kind')
            if kind not in CampaignListKind.values:
                raise ValidationError({'kind': 'Choose a contact, group or product list.'})
        name = attrs.get('name', self.instance.name if self.instance else '')
        clash = CampaignList.objects.filter(company=self.context['company'], kind=kind, name__iexact=name)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise ValidationError({'name': 'A list with this name already exists.'})
        return attrs


class CampaignListViewSet(viewsets.ModelViewSet):
    serializer_class = CampaignListSerializer
    permission_classes = [IsAuthenticated, CompanyPermissionRequired]
    pagination_class = None
    http_method_names = ['get', 'post', 'patch', 'delete']

    def permission_code_for(self, request):
        if request.method in permissions.SAFE_METHODS:
            return 'campaigns.campaigns.view'
        return 'campaigns.audiences.manage'

    def _company(self):
        return default_company_for_user(self.request.user)

    def get_queryset(self):
        qs = (
            CampaignList.objects.filter(company=self._company())
            .select_related('created_by', 'company')
            .annotate(
                contacts_count=Count('contacts', distinct=True),
                groups_count=Count('groups', distinct=True),
                products_count=Count('products', distinct=True),
            )
        )
        if self.action != 'list':
            # ?search= on candidates searches for members, not list names.
            return qs
        kind = self.request.query_params.get('kind')
        if kind:
            qs = qs.filter(kind=kind)
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(name__icontains=search)
        return qs

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'company': self._company()}

    def perform_create(self, serializer):
        serializer.save(company=self._company(), created_by=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(self._detail(self.get_queryset().get(pk=serializer.instance.pk)), status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        return Response(self._detail(self.get_object()))

    def partial_update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(self._detail(self.get_queryset().get(pk=serializer.instance.pk)))

    def _detail(self, campaign_list):
        """The list with the members the user may see; recipients on accounts the user
        can't see are counted, not shown."""
        target = spec(campaign_list)['target']
        related = f'{target}__account' if spec(campaign_list)['account_scoped'] else target
        shown = list(visible_member_rows(campaign_list, self.request.user).select_related(related))
        usable = set(eligible_for(campaign_list, self.request.user).filter(
            pk__in=[getattr(row, f'{target}_id') for row in shown],
        ).values_list('pk', flat=True))
        entry = ENTRIES[campaign_list.kind]
        members = []
        for row in shown:
            item = getattr(row, target)
            members.append({**entry(item), 'id': row.pk, f'{target}_id': item.pk, 'usable': item.pk in usable})
        data = self.get_serializer(campaign_list).data
        data['members'] = members
        data['hidden_member_count'] = data['member_count'] - len(members)
        return data

    @action(detail=True, methods=['get'], url_path='candidates')
    def candidates(self, request, pk=None):
        """What can be added to the list, excluding current members."""
        campaign_list = self.get_object()
        qs = eligible_for(campaign_list, request.user).exclude(
            pk__in=member_rows(campaign_list).values(member_field(campaign_list)),
        )
        qs = search_eligible(qs, campaign_list.kind, request.query_params.get('search'))
        qs = qs.order_by(CANDIDATE_ORDER[campaign_list.kind], 'pk')
        try:
            page = max(1, int(request.query_params.get('page') or 1))
        except ValueError:
            page = 1
        total = qs.count()
        start = (page - 1) * CANDIDATE_PAGE_SIZE
        entry = ENTRIES[campaign_list.kind]
        return Response({
            'count': total,
            'page': page,
            'page_size': CANDIDATE_PAGE_SIZE,
            'results': [entry(item) for item in qs[start:start + CANDIDATE_PAGE_SIZE]],
        })

    @action(detail=True, methods=['post'], url_path='add-members')
    def add_members(self, request, pk=None):
        """Add the given ids, or with all_matching every eligible one matching search.
        Fails as a whole if any given id cannot go on the list."""
        campaign_list = self.get_object()
        eligible = eligible_for(campaign_list, request.user)
        if request.data.get('all_matching'):
            ids = list(search_eligible(eligible, campaign_list.kind, request.data.get('search')).values_list('pk', flat=True))
        else:
            ids = request.data.get('ids')
            if not isinstance(ids, list) or not ids or not all(isinstance(pk, int) for pk in ids):
                raise ValidationError({'ids': 'Choose at least one to add.'})
            found = set(eligible.filter(pk__in=ids).values_list('pk', flat=True))
            missing = [pk for pk in ids if pk not in found]
            if missing:
                raise ValidationError({'ids': f'{len(missing)} of the selected {NOT_ELIGIBLE[campaign_list.kind]}.'})
        field = member_field(campaign_list)
        existing = set(member_rows(campaign_list).values_list(field, flat=True))
        new_ids = list(dict.fromkeys(pk for pk in ids if pk not in existing))
        row_model = ROW_MODELS[campaign_list.kind]
        with transaction.atomic():
            row_model.objects.bulk_create(
                [row_model(campaign_list=campaign_list, added_by=request.user, **{field: pk}) for pk in new_ids],
                ignore_conflicts=True,
            )
            CampaignList.objects.filter(pk=campaign_list.pk).update(updated_at=now())
        return Response({
            'added': len(new_ids),
            'skipped': len(ids) - len(new_ids),
            'list': self._detail(self.get_queryset().get(pk=campaign_list.pk)),
        })

    @action(detail=True, methods=['post'], url_path='remove-members')
    def remove_members(self, request, pk=None):
        campaign_list = self.get_object()
        ids = request.data.get('ids')
        if not isinstance(ids, list) or not ids:
            raise ValidationError({'ids': 'Choose at least one to remove.'})
        with transaction.atomic():
            removed, _ = visible_member_rows(campaign_list, request.user).filter(pk__in=ids).delete()
            CampaignList.objects.filter(pk=campaign_list.pk).update(updated_at=now())
        return Response({'removed': removed, 'list': self._detail(self.get_queryset().get(pk=campaign_list.pk))})
