from django.test import SimpleTestCase

from apps.whatsapp_bridge.outbound.policy import (
    CAP_AVAILABLE,
    CAP_EXHAUSTED,
    CAP_NOT_APPLICABLE,
    CAP_UNKNOWN,
    new_chat_cap_state,
)


class NewChatCapStateTests(SimpleTestCase):
    def test_zero_sentinel_for_non_eligible_account_is_not_a_reached_cap(self):
        state = new_chat_cap_state({
            'state': 'available',
            'total_quota': 0,
            'used_quota': 0,
            'remaining_quota': 0,
            'capping_status': 'NONE',
            'ote_status': 'NOT_ELIGIBLE',
            'mv_status': 'NOT_ELIGIBLE',
        })

        self.assertEqual(state, CAP_NOT_APPLICABLE)

    def test_explicit_capped_status_is_exhausted(self):
        self.assertEqual(new_chat_cap_state({'capping_status': 'CAPPED'}), CAP_EXHAUSTED)

    def test_positive_quota_uses_remaining_capacity(self):
        self.assertEqual(new_chat_cap_state({
            'total_quota': 10, 'used_quota': 10, 'remaining_quota': 0,
        }), CAP_EXHAUSTED)
        self.assertEqual(new_chat_cap_state({
            'total_quota': 10, 'used_quota': 4, 'remaining_quota': 6,
        }), CAP_AVAILABLE)

    def test_ambiguous_zero_quota_remains_unknown(self):
        self.assertEqual(new_chat_cap_state({
            'state': 'available',
            'total_quota': 0,
            'used_quota': 0,
            'remaining_quota': 0,
            'capping_status': 'NONE',
        }), CAP_UNKNOWN)
