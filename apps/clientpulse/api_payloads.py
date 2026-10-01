def user_payload(user):
    return None if not user else {
        'id': user.pk, 'username': user.username, 'email': user.email,
    }


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
        'last_contacted_at': profile.last_contacted_at,
        'last_inbound_at': profile.last_inbound_at,
        'next_follow_up_at': profile.next_follow_up_at,
        'do_not_contact': profile.do_not_contact,
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
                'account_id': item.account_id,
                'account_name': item.account.display_name,
            } for item in contact.whatsapp_contacts.select_related('account')],
        })
    return data


def note_payload(note):
    return {
        'id': note.pk, 'body': note.body, 'is_pinned': note.is_pinned,
        'created_by': user_payload(note.created_by),
        'created_at': note.created_at, 'updated_at': note.updated_at,
    }


def activity_payload(activity):
    return {
        'id': activity.pk, 'activity_type': activity.activity_type,
        'occurred_at': activity.occurred_at, 'title': activity.title,
        'summary': activity.summary, 'channel': activity.channel,
        'direction': activity.direction, 'metadata': activity.metadata,
        'created_by': user_payload(activity.created_by),
    }
