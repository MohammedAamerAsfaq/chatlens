"""Hard wall-clock execution boundaries for external AI provider calls."""
import multiprocessing
import traceback


class ProviderCallTimeout(TimeoutError):
    """Raised after terminating a provider call that exceeded its deadline."""


class ProviderCallFailed(RuntimeError):
    """Wrap an exception raised in the isolated provider process."""


def _run_provider_call(connection, config_id, messages, kwargs):
    """Child-process target. Keep Django imports inside the spawned process."""
    try:
        import django

        # Windows spawn starts a clean interpreter without the parent's app registry.
        django.setup()
        from django.db import close_old_connections

        from .manager import build_provider
        from .models import AIProviderConfig

        close_old_connections()
        config = AIProviderConfig.objects.get(pk=config_id)
        response = build_provider(config).chat(messages, **kwargs)
        connection.send(('ok', response))
    except Exception as exc:
        connection.send(('error', str(exc), traceback.format_exc()))
    finally:
        try:
            close_old_connections()
        except Exception:
            pass
        connection.close()


def call_provider_with_deadline(config_id, messages, *, timeout_seconds, **kwargs):
    """Execute one provider request and terminate it at a strict deadline.

    ``requests`` timeouts govern socket inactivity, not total wall-clock time.
    A dedicated process gives the worker an enforceable deadline on Windows and
    prevents a stalled provider call from retaining a concurrency reservation.
    """
    context = multiprocessing.get_context('spawn')
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(
        target=_run_provider_call,
        args=(sender, config_id, messages, kwargs),
        daemon=False,
    )
    process.start()
    sender.close()
    process.join(timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join()
        receiver.close()
        raise ProviderCallTimeout(f'AI provider exceeded the {timeout_seconds}-second request timeout.')

    if not receiver.poll():
        receiver.close()
        raise ProviderCallFailed(f'AI provider process exited without a response (exit code {process.exitcode}).')
    outcome = receiver.recv()
    receiver.close()
    if outcome[0] == 'ok':
        return outcome[1]
    detail = outcome[2] if len(outcome) > 2 else ''
    raise ProviderCallFailed(f'{outcome[1]}\n{detail}'.strip())
