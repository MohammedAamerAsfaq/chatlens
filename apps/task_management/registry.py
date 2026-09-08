from dataclasses import dataclass


class TaskRegistrationError(RuntimeError):
    pass


class UnsupportedTaskPayload(ValueError):
    pass


@dataclass(frozen=True)
class TaskDefinition:
    key: str
    version: int
    default_queue: str
    payload_validator: object
    idempotency_required: bool
    retry_safe: bool
    handler: object


class TaskRegistry:
    def __init__(self):
        self._definitions = {}

    def register(self, definition):
        key = (definition.key, definition.version)
        if key in self._definitions:
            raise TaskRegistrationError(f'Task handler already registered: {key[0]} v{key[1]}')
        self._definitions[key] = definition
        return definition.handler

    def get(self, key, version=1):
        try:
            return self._definitions[(key, version)]
        except KeyError as exc:
            raise TaskRegistrationError(f'No task handler registered for {key} v{version}') from exc


task_registry = TaskRegistry()


def task_handler(*, key, version=1, default_queue, payload_validator, idempotency_required=True, retry_safe=True):
    def decorator(handler):
        task_registry.register(TaskDefinition(
            key=key, version=version, default_queue=default_queue,
            payload_validator=payload_validator, idempotency_required=idempotency_required,
            retry_safe=retry_safe, handler=handler,
        ))
        return handler
    return decorator


def validate_versioned_message_payload(payload):
    if not isinstance(payload, dict) or payload.get('version') != 1:
        raise UnsupportedTaskPayload('Payload version 1 is required.')
    if not isinstance(payload.get('message_id'), int) or payload['message_id'] <= 0:
        raise UnsupportedTaskPayload('message_id must be a positive integer.')


def validate_recovery_payload(payload):
    if not isinstance(payload, dict) or payload.get('version') != 1:
        raise UnsupportedTaskPayload('Payload version 1 is required.')
    if not isinstance(payload.get('account_id'), int) or not payload.get('lid_jid') or not payload.get('phone_jid'):
        raise UnsupportedTaskPayload('account_id, lid_jid, and phone_jid are required.')


def validate_any_v1_payload(payload):
    if not isinstance(payload, dict) or payload.get('version') != 1:
        raise UnsupportedTaskPayload('Payload version 1 is required.')
