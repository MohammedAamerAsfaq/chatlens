from django.utils import timezone

from apps.real_estate.models import MarketScope, RealEstateOpportunity
from apps.real_estate.services.classification_contract import outcome_for_decision


def persist_opportunity(message, company, parsed):
    outcome = outcome_for_decision(parsed['decision'])
    defaults = {
        'company': company,
        'account': message.account,
        'contact': message.contact,
        'source_chat': message.chat,
        'activity_type': outcome.activity_type,
        'market_scope': _market_scope((parsed.get('property') or {}).get('market_scope')),
        'classification_status': outcome.status,
        'summary': parsed.get('summary', ''),
        'original_message': message.message_text or '',
        'status': _workflow_status(outcome.status),
        'confidence': parsed.get('confidence'),
        'matching_complete': False,
        'deduplication_key': f'whatsapp-message:{message.pk}',
        'first_seen_at': message.message_time or timezone.now(),
    }
    opportunity, _ = RealEstateOpportunity.objects.update_or_create(
        source_message=message,
        defaults=defaults,
    )
    return opportunity


def persist_gate_rejection(message, company):
    return persist_opportunity(message, company, {
        'decision': 'not_real_estate',
        'summary': 'Rejected by enforced Real Estate GatePass.',
        'confidence': None,
    })


def _workflow_status(classification_status):
    if classification_status == 'not_real_estate':
        return RealEstateOpportunity.STATUS_IRRELEVANT
    return RealEstateOpportunity.STATUS_NEW


def _market_scope(value):
    normalized = str(value or '').strip().lower()
    return normalized if normalized in MarketScope.values else MarketScope.LOCAL
