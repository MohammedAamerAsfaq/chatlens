from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.real_estate.models import (
    ActivityType, ClassificationStatus, InventorySourceType, Listing,
    OpportunityItem, OwnershipEligibility, Party, Property, PropertyAddress,
    PropertyCandidate, PropertyDevelopment, PropertyRequirement,
    PropertyPartyAssociation, RealEstateOpportunity, TenureType,
)
from apps.integrations.models import AdministrativeArea, City, Country, Locality
from apps.real_estate.services.candidate_service import promote_candidate
from apps.real_estate.services.extraction_projection import project_extraction
from apps.tenancy.models import Company, CompanyMembership
from apps.real_estate.services.property_types import seed_default_property_types
from apps.real_estate.services.property_types import resolve_property_type
from apps.task_management.models import BackgroundTask


class RealEstateInventoryTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Estate A', slug='estate-a', industry_type='real_estate')
        self.other = Company.objects.create(name='Estate B', slug='estate-b', industry_type='real_estate')
        self.types = {item.code: item for item in seed_default_property_types(self.company)}
        self.other_types = {item.code: item for item in seed_default_property_types(self.other)}
        self.user = get_user_model().objects.create_user('estate-owner')
        CompanyMembership.objects.create(
            company=self.company, user=self.user, role=CompanyMembership.ROLE_SUPER_USER,
        )

    def opportunity(self, activity):
        return RealEstateOpportunity.objects.create(
            company=self.company,
            activity_type=activity,
            classification_status=ClassificationStatus.CLASSIFIED,
            first_seen_at=timezone.now(),
        )

    def test_cross_company_listing_is_rejected(self):
        foreign_property = Property.objects.create(
            company=self.other, title='Foreign villa', property_type=self.other_types['villa'],
        )
        listing = Listing(
            company=self.company, property=foreign_property, listing_type='sale',
            asking_price=1000000, is_verified=True,
        )
        with self.assertRaises(ValidationError):
            listing.full_clean()

    def test_database_prevents_conflicting_active_listings(self):
        property_record = Property.objects.create(
            company=self.company, title='Marina flat', property_type=self.types['apartment'],
        )
        values = dict(
            company=self.company, property=property_record, listing_type='sale',
            asking_price=1000000, is_verified=True, status='active',
        )
        Listing.objects.create(**values)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Listing.objects.create(**values)

    def test_property_hierarchy_is_optional_and_tracks_children(self):
        parent = Property.objects.create(
            company=self.company, title='Plot 14', property_type=self.types['plot'],
        )
        child = Property.objects.create(
            company=self.company, title='Building A', property_type=self.types['building'],
            parent=parent,
        )

        self.assertEqual(child.parent, parent)
        self.assertEqual(list(parent.children.all()), [child])

    def test_property_hierarchy_rejects_cross_company_parent_and_cycles(self):
        foreign = Property.objects.create(
            company=self.other, title='Foreign plot', property_type=self.other_types['plot'],
        )
        child = Property(
            company=self.company, title='Invalid child', property_type=self.types['building'],
            parent=foreign,
        )
        with self.assertRaises(ValidationError):
            child.full_clean()

        parent = Property.objects.create(
            company=self.company, title='Local plot', property_type=self.types['plot'],
        )
        child = Property.objects.create(
            company=self.company, title='Local building', property_type=self.types['building'],
            parent=parent,
        )
        parent.parent = child
        with self.assertRaises(ValidationError):
            parent.full_clean()

    def test_property_party_association_is_company_scoped(self):
        property_record = Property.objects.create(
            company=self.company, title='Owned villa', property_type=self.types['villa'],
        )
        owner = Party.objects.create(company=self.company, first_name='Fatima', last_name='Ali')
        association = PropertyPartyAssociation(
            company=self.company, property=property_record, party=owner,
            relationship_type='current_owner',
        )
        association.full_clean()
        association.save()
        self.assertEqual(property_record.party_associations.get().party, owner)

        foreign_party = Party.objects.create(company=self.other, first_name='Foreign')
        invalid = PropertyPartyAssociation(
            company=self.company, property=property_record, party=foreign_party,
            relationship_type='broker',
        )
        with self.assertRaises(ValidationError):
            invalid.full_clean()

    def test_demand_projects_to_requirement_only(self):
        opportunity = self.opportunity(ActivityType.BUYING)
        projected = project_extraction(opportunity, {
            'confidence': 0.9,
            'property': {
                'property_type': 'apartment', 'locations': ['Dubai Marina'],
                'bedrooms': 2, 'budget': {'max': '2500000', 'currency': 'AED'},
            },
        })
        self.assertIsInstance(projected, PropertyRequirement)
        self.assertEqual(projected.acceptable_locations, ['Dubai Marina'])
        self.assertFalse(PropertyCandidate.objects.filter(opportunity=opportunity).exists())
        self.assertFalse(Property.objects.filter(company=self.company).exists())
        item = opportunity.items.get()
        self.assertEqual(item.item_kind, OpportunityItem.KIND_DEMAND)
        self.assertEqual(item.legacy_requirement, projected)

    def test_multiple_extracted_properties_create_separate_opportunity_items(self):
        opportunity = self.opportunity(ActivityType.BUYING)

        project_extraction(opportunity, {
            'summary': 'Buyer wants either of two distinct units.',
            'properties': [
                {'property_type': 'apartment', 'location': 'Dubai Marina', 'bedrooms': 2},
                {'property_type': 'villa', 'location': 'Arabian Ranches', 'bedrooms': 4},
            ],
            'property': {
                'property_type': 'apartment', 'location': 'Dubai Marina', 'bedrooms': 2,
            },
        })

        items = list(opportunity.items.order_by('sequence'))
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].location_raw, 'Dubai Marina')
        self.assertEqual(items[1].location_raw, 'Arabian Ranches')
        self.assertFalse(Property.objects.filter(company=self.company).exists())

    def test_requirement_projection_enqueues_one_embedding_task(self):
        opportunity = self.opportunity(ActivityType.BUYING)
        with self.captureOnCommitCallbacks(execute=True):
            requirement = project_extraction(opportunity, {
                'property': {'property_type': 'apartment', 'locations': ['Dubai Marina']},
            })

        self.assertEqual(BackgroundTask.objects.filter(
            task_key='real_estate.embed_requirement',
            payload__object_id=requirement.pk,
        ).count(), 1)

    def test_supply_projects_to_candidate_then_explicit_promotion(self):
        opportunity = self.opportunity(ActivityType.LEASING_OFFER)
        candidate = project_extraction(opportunity, {
            'summary': 'Two-bedroom apartment for rent',
            'property': {
                'property_type': 'apartment', 'location': 'Business Bay',
                'bedrooms': 2, 'asking_price': 120000, 'currency': 'AED',
            },
        })
        self.assertIsInstance(candidate, PropertyCandidate)
        self.assertFalse(Property.objects.filter(company=self.company).exists())

        property_record, listing = promote_candidate(candidate, self.user)
        candidate.refresh_from_db()
        self.assertEqual(candidate.review_status, 'promoted')
        self.assertEqual(listing.property, property_record)
        self.assertEqual(listing.listing_type, 'lease')
        self.assertEqual(listing.status, 'draft')
        self.assertTrue(listing.is_verified)

    def test_candidate_projection_enqueues_one_embedding_task(self):
        opportunity = self.opportunity(ActivityType.SELLING)
        with self.captureOnCommitCallbacks(execute=True):
            candidate = project_extraction(opportunity, {
                'property': {'property_type': 'villa', 'location': 'Dubai Islands'},
            })

        self.assertEqual(BackgroundTask.objects.filter(
            task_key='real_estate.embed_candidate',
            payload__object_id=candidate.pk,
        ).count(), 1)

    def test_company_taxonomy_seeds_aliases_and_type_fields(self):
        apartment = self.types['apartment']
        self.assertEqual(resolve_property_type(self.company, 'flat'), apartment)
        self.assertTrue(apartment.field_definitions.filter(code='floor').exists())
        self.assertEqual(resolve_property_type(self.company, 'land').code, 'plot')

    def test_resolve_property_type_falls_back_on_empty_value_not_just_unmatched_text(self):
        # fallback=True must apply when there's no text to match at all, not only when
        # there's text that fails to match - an empty/missing extraction is exactly the
        # case a caller most needs the "Other" default for.
        self.assertIsNone(resolve_property_type(self.company, ''))
        self.assertEqual(resolve_property_type(self.company, '', fallback=True).code, 'other')
        self.assertEqual(resolve_property_type(self.company, None, fallback=True).code, 'other')

    def test_supply_item_with_no_extracted_property_type_falls_back_to_other_and_can_create_property(self):
        from apps.real_estate.models import RealEstateSettings
        from apps.real_estate.services.opportunity_item_projection import sync_extracted_items
        from apps.real_estate.services.opportunity_item_service import create_property_from_item

        opportunity = self.opportunity(ActivityType.SELLING)
        settings_row, _ = RealEstateSettings.objects.get_or_create(company=self.company)
        parsed = {
            'summary': 'Unit 101 for sale',
            'properties': [{'title': 'Unit 101', 'price': {'amount': 500000}}],
        }
        items = sync_extracted_items(opportunity, parsed, settings_row)
        item = items[0]
        self.assertEqual(item.property_type_id, self.types['other'].id)

        linked_item, property_record = create_property_from_item(item, self.user)
        self.assertEqual(property_record.property_type_id, self.types['other'].id)
        self.assertEqual(linked_item.match_status, OpportunityItem.MATCH_LINKED)

    def test_inventory_source_and_tracking_are_independent(self):
        property_record = Property.objects.create(
            company=self.company,
            title='Authorized tracked villa',
            property_type=self.types['villa'],
            inventory_source_type=InventorySourceType.AUTHORIZED,
            is_tracked=True,
            ownership_eligibility=OwnershipEligibility.GCC_ONLY,
            tenure_type=TenureType.LONG_LEASE,
        )
        self.assertEqual(property_record.inventory_source_type, 'authorized')
        self.assertTrue(property_record.is_tracked)
        self.assertFalse(hasattr(property_record, 'authorized_for_sale'))

    def test_property_type_schema_rejects_unknown_attributes(self):
        property_record = Property(
            company=self.company,
            title='Typed apartment',
            property_type=self.types['apartment'],
            attributes={'floor': '12', 'not_configured': 'value'},
        )
        with self.assertRaises(ValidationError):
            property_record.full_clean()

    def test_candidate_projection_and_promotion_preserve_inventory_contract(self):
        opportunity = self.opportunity(ActivityType.SELLING)
        candidate = project_extraction(opportunity, {
            'summary': 'Authorized office offer',
            'property': {
                'property_type': 'office',
                'ownership_eligibility': 'locals_only',
                'tenure_type': 'freehold',
                'attributes': {'floor': 17, 'parking': 2},
                'asking_price': 2500000,
            },
        })
        self.assertEqual(candidate.inventory_source_type, InventorySourceType.FLOATING)
        self.assertEqual(candidate.ownership_eligibility, OwnershipEligibility.LOCALS_ONLY)
        self.assertEqual(candidate.attributes['floor'], '17')
        candidate.is_tracked = True
        candidate.save(update_fields=['is_tracked'])

        property_record, _ = promote_candidate(candidate, self.user)
        self.assertEqual(property_record.inventory_source_type, InventorySourceType.FLOATING)
        self.assertTrue(property_record.is_tracked)
        self.assertEqual(property_record.tenure_type, TenureType.FREEHOLD)
        self.assertEqual(property_record.attributes['parking'], '2')

    def test_property_address_accepts_consistent_canonical_hierarchy(self):
        country, area, city, locality = self._geography()
        project = PropertyDevelopment.objects.create(
            company=self.company, locality=locality, development_type='project',
            name='Marina Heights', normalized_name='marina heights',
        )
        property_record = Property.objects.create(
            company=self.company, title='Marina apartment', property_type=self.types['apartment'],
        )
        address = PropertyAddress(
            company=self.company, property=property_record, country_master=country,
            administrative_area_master=area, city_master=city, locality_master=locality,
            development_master=project, community='Original imported community',
        )

        address.full_clean()
        self.assertEqual(address.community, 'Original imported community')

    def test_property_address_rejects_locality_from_another_city(self):
        country, area, city, locality = self._geography()
        other_city = City.objects.create(
            country=country, administrative_area=area, name='Hatta', normalized_name='hatta',
            geoname_id=290112, feature_code='PPLA3', latitude=24.8000, longitude=56.1200,
        )
        property_record = Property.objects.create(
            company=self.company, title='Invalid hierarchy', property_type=self.types['apartment'],
        )
        address = PropertyAddress(
            company=self.company, property=property_record, country_master=country,
            administrative_area_master=area, city_master=other_city, locality_master=locality,
        )

        with self.assertRaises(ValidationError):
            address.full_clean()

    def test_development_parent_must_be_same_company_project(self):
        _, _, _, locality = self._geography()
        foreign_project = PropertyDevelopment.objects.create(
            company=self.other, locality=locality, development_type='project',
            name='Foreign project', normalized_name='foreign project',
        )
        building = PropertyDevelopment(
            company=self.company, locality=locality, parent=foreign_project,
            development_type='building', name='Tower A', normalized_name='tower a',
        )

        with self.assertRaises(ValidationError):
            building.full_clean()

    def _geography(self):
        country, _ = Country.objects.get_or_create(
            iso2='AE', defaults={'name': 'United Arab Emirates', 'normalized_name': 'united arab emirates'},
        )
        area, _ = AdministrativeArea.objects.get_or_create(
            geoname_id=292224,
            defaults={'country': country, 'name': 'Dubai', 'normalized_name': 'dubai'},
        )
        city, _ = City.objects.get_or_create(
            geoname_id=292223,
            defaults={
                'country': country, 'administrative_area': area, 'name': 'Dubai',
                'normalized_name': 'dubai', 'feature_code': 'PPLA',
                'latitude': 25.0773, 'longitude': 55.3093,
            },
        )
        locality, _ = Locality.objects.get_or_create(
            geoname_id=1200001,
            defaults={
                'country': country, 'administrative_area': area, 'city': city,
                'name': 'Dubai Marina', 'normalized_name': 'dubai marina',
                'feature_code': 'PPLX', 'latitude': 25.0805, 'longitude': 55.1403,
                'mapping_status': Locality.MAPPING_MAPPED,
            },
        )
        return country, area, city, locality
