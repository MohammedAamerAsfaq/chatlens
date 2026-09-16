'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  classifyDestination,
  normalizeGroupMetadata,
} = require('../src/outbound/destination-classifier');

test('classifies supported and blocked destination JIDs', () => {
  assert.equal(classifyDestination('971500000001@s.whatsapp.net'), 'direct_contact');
  assert.equal(classifyDestination('123@lid'), 'direct_contact');
  assert.equal(classifyDestination('120001@g.us'), 'standard_group');
  assert.equal(classifyDestination('123@newsletter'), 'channel');
  assert.equal(classifyDestination('status@broadcast'), 'status');
  assert.equal(classifyDestination('list@broadcast'), 'broadcast');
  assert.equal(classifyDestination('invalid'), 'unknown');
});

test('classifies community group variants from live metadata', () => {
  assert.equal(
    classifyDestination('120001@g.us', { isCommunity: true }),
    'community',
  );
  assert.equal(
    classifyDestination('120002@g.us', { isCommunityAnnounce: true }),
    'community_announcement',
  );
  assert.equal(
    classifyDestination('120003@g.us', { linkedParent: '120001@g.us' }),
    'community_subgroup',
  );
});

test('normalizes account role and permits an admin in an announcement group', () => {
  const result = normalizeGroupMetadata({
    id: '120004@g.us',
    subject: 'Announcements',
    isCommunity: true,
    isCommunityAnnounce: true,
    announce: true,
    participants: [
      { id: '99111@lid', jid: '971500000001@s.whatsapp.net', admin: 'admin' },
      { id: '99222@lid', jid: '971500000002@s.whatsapp.net' },
    ],
  }, '971500000001:14@s.whatsapp.net');

  assert.equal(result.account_is_participant, true);
  assert.equal(result.account_participant_role, 'admin');
  assert.equal(result.can_send, true);
  assert.equal(result.send_block_reason, '');
  assert.equal(result.metadata_complete, true);
});

test('blocks member-only access to announcement group and community umbrella', () => {
  const member = normalizeGroupMetadata({
    id: '120005@g.us',
    announce: true,
    participants: [{ id: '971500000001@s.whatsapp.net' }],
  }, '971500000001@s.whatsapp.net');
  assert.equal(member.can_send, false);
  assert.equal(member.send_block_reason, 'group_admin_required');

  const community = normalizeGroupMetadata({
    id: '120006@g.us',
    isCommunity: true,
    participants: [{ id: '971500000001@s.whatsapp.net', admin: 'superadmin' }],
  }, '971500000001@s.whatsapp.net');
  assert.equal(community.can_send, false);
  assert.equal(community.send_block_reason, 'community_send_blocked');
});
