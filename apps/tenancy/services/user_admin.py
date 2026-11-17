"""Admin actions on a company user's login: change username, set a password, remove.

All three change the Django User itself, which is shared by every company the person
belongs to, so each one is refused when the user is also a member of another company.
Owners can only be changed by an Owner, and a Django superuser only by a superuser.

Remove never deletes rows. Deleting the User would cascade into the WhatsApp accounts
they own (chats, messages, inquiries). Instead the login is disabled, the username
becomes "<username>-deleted-<key>" and the email is cleared, so both are free for a
new user. The membership is kept and marked removed, so the person's past status
changes and audit entries still show who made them.
"""

import secrets
from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import password_validators_help_texts, validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils.timezone import now

from apps.tenancy.models import CompanyMembership
from apps.tenancy.services.authorization import bump_authorization_version
from apps.tenancy.services.ownership import active_owner_count, is_owner

DELETED_MARKER = '-deleted-'


class UserAdminError(ValueError):
    """A refused request; message is user-facing, status the HTTP status to answer with."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


@dataclass
class Actor:
    user: object
    membership: object


def password_rules():
    """The server's password rules, worded for people (shown next to password fields)."""
    return password_validators_help_texts()


def check_password_strength(password, *, username='', email='', user=None):
    """Raise UserAdminError listing every rule the password breaks."""
    if not password:
        raise UserAdminError('A password is required.')
    candidate = user or get_user_model()(username=username, email=email)
    try:
        validate_password(password, user=candidate)
    except ValidationError as exc:
        raise UserAdminError(' '.join(exc.messages)) from exc


def _guard(actor, membership):
    """Checks shared by every action that changes another person's login."""
    if membership.removed_at:
        raise UserAdminError('This user has been removed.', status=409)
    target = membership.user
    if target.is_superuser and not actor.user.is_superuser:
        raise UserAdminError('Only a platform superuser can change a superuser login.', status=403)
    if is_owner(membership) and not (actor.membership and is_owner(actor.membership)):
        raise UserAdminError('Only an Owner can change an Owner login.', status=403)
    other = CompanyMembership.objects.filter(user=target, removed_at__isnull=True).exclude(company=membership.company)
    if other.exists():
        raise UserAdminError(
            'This login is also used in another company, so it cannot be changed from here.', status=409,
        )


def change_username(actor, membership, username):
    _guard(actor, membership)
    User = get_user_model()
    username = (username or '').strip()
    if not username:
        raise UserAdminError('A username is required.')
    max_length = User._meta.get_field('username').max_length
    if len(username) > max_length:
        raise UserAdminError(f'A username can be at most {max_length} characters.')
    if DELETED_MARKER in username:
        raise UserAdminError(f'A username cannot contain "{DELETED_MARKER}".')
    try:
        User.username_validator(username)
    except ValidationError as exc:
        raise UserAdminError(' '.join(exc.messages)) from exc
    target = membership.user
    if User.objects.filter(username__iexact=username).exclude(pk=target.pk).exists():
        raise UserAdminError(f'The username {username!r} is already taken.')
    old = target.username
    target.username = username
    target.save(update_fields=['username'])
    return old


def set_password(actor, membership, password):
    _guard(actor, membership)
    target = membership.user
    check_password_strength(password, user=target)
    target.set_password(password)
    target.save(update_fields=['password'])
    # Changing the password also changes the session hash, which signs the user out of
    # every other browser. bump_authorization_version refreshes their cached permissions.
    bump_authorization_version(membership)
    return target


@transaction.atomic
def remove_user(actor, membership):
    """Disable the login and free the username/email, keeping every record. Returns the old names."""
    if actor.user.pk == membership.user_id:
        raise UserAdminError('You cannot remove yourself.')
    _guard(actor, membership)
    if membership.is_active and is_owner(membership) and active_owner_count(membership.company) <= 1:
        raise UserAdminError('A company must retain an active Owner.')

    target = membership.user
    old = {'username': target.username, 'email': target.email}
    User = get_user_model()
    max_length = User._meta.get_field('username').max_length
    while True:
        suffix = f'{DELETED_MARKER}{secrets.token_hex(4)}'
        new_username = f'{target.username[:max_length - len(suffix)]}{suffix}'
        if not User.objects.filter(username=new_username).exists():
            break
    target.username = new_username
    target.email = ''
    target.is_active = False
    target.set_unusable_password()
    target.save(update_fields=['username', 'email', 'is_active', 'password'])

    moment = now()
    membership.is_active = False
    membership.removed_at = moment
    membership.removed_by = actor.user
    membership.save(update_fields=['is_active', 'removed_at', 'removed_by'])
    bump_authorization_version(membership)

    # Sharing they took part in ends with them.
    from apps.trading.models import InquiryShare, InquirySharingRule
    InquirySharingRule.objects.filter(
        Q(owner=target) | Q(recipient=target), company=membership.company, ended_at__isnull=True,
    ).update(ended_at=moment)
    InquiryShare.objects.filter(
        recipient=target, inquiry__company=membership.company, revoked_at__isnull=True,
    ).update(revoked_at=moment)
    return old
