def user_payload(user):
    return None if not user else {
        'id': user.pk, 'username': user.username, 'email': user.email,
    }


def _communication_accounts(contact):
    accounts = {}
    for item in contact.whatsapp_contacts.all():
        account = item.account
        accounts[account.pk] = {
            'id': account.pk,
            'name': account.display_name or account.phone_number or f'Account #{account.pk}',
            'phone_number': account.phone_number,
            'session_status': account.session_status,
        }
    return list(accounts.values())


def profile_payload(profile, *, detail=False):
    contact = profile.contact
    data = {
        'id': profile.pk,
        'company_contact_id': contact.pk,
        'display_name': contact.display_name,
        'legal_name': contact.legal_name,
        'contact_type': contact.contact_type,
        'category': contact.category,
        'lifecycle_stage': profile.lifecycle_stage,
        'status': profile.status,
        'priority': profile.priority,
        'source': profile.source,
        'owner': None if not profile.owner else {
            'id': profile.owner_id,
            'user': user_payload(profile.owner.user),
        },
        'preferred_channel': profile.preferred_channel,
        'company_name': profile.company_name,
        'job_title': profile.job_title,
        'last_contacted_at': profile.last_contacted_at,
        'last_inbound_at': profile.last_inbound_at,
        'next_follow_up_at': profile.next_follow_up_at,
        'do_not_contact': profile.do_not_contact,
        'communication_accounts': _communication_accounts(contact),
        'tags': [{
            'id': item.tag_id, 'name': item.tag.name, 'color': item.tag.color,
        } for item in profile.tag_assignments.all()],
        'updated_at': profile.updated_at,
    }
    if detail:
        data.update({
            'first_name': contact.first_name,
            'middle_name': contact.middle_name,
            'last_name': contact.last_name,
            'notes': contact.notes,
            'preferred_language': profile.preferred_language,
            'timezone': profile.timezone,
            'website': profile.website,
            'address_line1': profile.address_line1,
            'address_line2': profile.address_line2,
            'city': profile.city,
            'state_region': profile.state_region,
            'postal_code': profile.postal_code,
            'country': profile.country,
            'do_not_contact_reason': profile.do_not_contact_reason,
            'created_at': profile.created_at,
            'identities': [{
                'id': identity.pk,
                'identity_type': identity.identity_type,
                'value': identity.value,
                'label': identity.label,
                'is_primary': identity.is_primary,
                'is_verified': identity.is_verified,
                'source_type': identity.source_type,
            } for identity in contact.identities.filter(is_active=True)],
            'whatsapp_contacts': [{
                'id': item.pk,
                'display_name': item.display_name,
                'phone_number': item.phone_number,
                'wa_contact_id': item.wa_contact_id,
                'is_existing_chat': item.is_existing_chat,
                'account_id': item.account_id,
                'account_name': item.account.display_name,
                'session_status': item.account.session_status,
                'sending_enabled': item.account.outbound_sending_enabled,
                'direct_sending_enabled': item.account.direct_sending_enabled,
                'image_sending_enabled': item.account.image_sending_enabled,
            } for item in contact.whatsapp_contacts.select_related('account')],
        })
    return data


def note_payload(note):
    return {
        'id': note.pk, 'body': note.body, 'is_pinned': note.is_pinned,
        'created_by': user_payload(note.created_by),
        'created_at': note.created_at, 'updated_at': note.updated_at,
    }


def activity_payload(activity, outbound=None):
    data = {
        'id': activity.pk, 'activity_type': activity.activity_type,
        'occurred_at': activity.occurred_at, 'title': activity.title,
        'summary': activity.summary, 'channel': activity.channel,
        'direction': activity.direction, 'metadata': activity.metadata,
        'created_by': user_payload(activity.created_by),
    }
    if outbound:
        data['outbound'] = {
            'id': outbound.pk, 'status': outbound.status,
            'status_reason': outbound.status_reason,
            'content_type': outbound.content_type,
            'account_name': outbound.whatsapp_account.display_name or outbound.whatsapp_account.phone_number,
            'requested_at': outbound.requested_at,
            'provider_accepted_at': outbound.provider_accepted_at,
            'delivered_at': outbound.delivered_at,
            'read_at': outbound.read_at,
        }
    return data
