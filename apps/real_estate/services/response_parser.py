import json

from apps.real_estate.models import ClassificationDecision


def parse_json_object(raw_response):
    if isinstance(raw_response, dict):
        return raw_response
    text = str(raw_response or '').strip()
    if text.startswith('```'):
        lines = text.splitlines()
        if lines and lines[0].startswith('```'):
            lines = lines[1:]
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        text = '\n'.join(lines).strip()
    start, end = text.find('{'), text.rfind('}')
    if start < 0 or end < start:
        raise ValueError('AI response did not contain a JSON object.')
    parsed = json.loads(text[start:end + 1])
    if not isinstance(parsed, dict):
        raise ValueError('AI response must be a JSON object.')
    return parsed


def parse_gate_response(raw_response):
    parsed = parse_json_object(raw_response)
    decision = str(parsed.get('decision') or '').strip().lower()
    allowed = {'real_estate', 'not_real_estate', 'needs_review'}
    if decision not in allowed:
        raise ValueError(f'Unsupported Real Estate gate decision: {decision!r}')
    return decision


def parse_extraction_response(raw_response):
    parsed = parse_json_object(raw_response)
    decision = str(parsed.get('decision') or '').strip().lower()
    if decision not in ClassificationDecision.values:
        raise ValueError(f'Unsupported Real Estate extraction decision: {decision!r}')
    parsed['decision'] = decision
    parsed['summary'] = str(parsed.get('summary') or '').strip()
    parsed['confidence'] = _confidence(parsed.get('confidence'))
    supplied = parsed.get('properties')
    if isinstance(supplied, list):
        properties = [item for item in supplied if isinstance(item, dict)]
    else:
        legacy = parsed.get('property')
        properties = [legacy] if isinstance(legacy, dict) and legacy else []
    parsed['properties'] = properties
    # Keep the old contract available while legacy projections are retired.
    parsed['property'] = properties[0] if properties else {}
    return parsed


def _confidence(value):
    if value in (None, ''):
        return None
    numeric = float(value)
    if not 0 <= numeric <= 1:
        raise ValueError('confidence must be between 0 and 1.')
    return numeric
