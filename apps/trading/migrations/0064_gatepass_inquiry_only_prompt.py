from django.db import migrations

GATE_KEY = 'inquiry_gate_v2'

OLD_BODY = (
    'Classify this WhatsApp message for a wholesale trading desk. Return ONLY JSON:\n'
    '{"decision":"buy"|"sell"|"not_inquiry"}.\n'
    'Use business intent, not merely literal WTB/WTS tokens. Greetings, links, logistics,\n'
    'and unrelated messages are not_inquiry. Do not extract products or explain reasoning.'
)

NEW_BODY = (
    'Decide whether this WhatsApp message is a trade inquiry for a wholesale trading desk.\n'
    'Return ONLY JSON: {"decision":"inquiry"|"not_inquiry"}.\n'
    'An inquiry offers products for sale or asks to buy products. Do not decide whether it is\n'
    'buying or selling. Greetings, links, logistics, and unrelated messages are not_inquiry.\n'
    'Do not extract products or explain reasoning.'
)


def forwards(apps, schema_editor):
    # Only stored copies of the old default; customised prompts are left for the owner.
    PromptConfig = apps.get_model('trading', 'PromptConfig')
    PromptConfig.objects.filter(key=GATE_KEY, body=OLD_BODY).update(body=NEW_BODY)


def backwards(apps, schema_editor):
    PromptConfig = apps.get_model('trading', 'PromptConfig')
    PromptConfig.objects.filter(key=GATE_KEY, body=NEW_BODY).update(body=OLD_BODY)


class Migration(migrations.Migration):
    dependencies = [('trading', '0063_inquiryforwardingrule_condition_logic_and_more')]

    operations = [migrations.RunPython(forwards, backwards)]
