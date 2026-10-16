"""
Live event bus over Redis pub/sub.

Producers (decoders, capture jobs, alerts) call publish(); the SSE endpoint
subscribes and forwards events to browsers. A second channel carries control
commands (e.g. "stop session X") so any API process can stop a decoder owned
by another process.
"""

import json
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Iterator, Optional

from redis_client import get_redis

logger = logging.getLogger(__name__)

EVENT_CHANNEL = 'radiomoni:events'
CONTROL_CHANNEL = 'radiomoni:control'


def publish(event_type: str, data: dict[str, Any]) -> None:
    """Publish an event. Never raises — live updates are best effort."""
    message = {
        'type': event_type,
        'time': datetime.now(timezone.utc).isoformat(),
        'data': data,
    }
    try:
        get_redis().publish(EVENT_CHANNEL, json.dumps(message, default=str))
    except Exception as e:
        logger.debug(f"Event publish failed ({event_type}): {e}")


def sse_stream(types: Optional[set[str]] = None, heartbeat: float = 15.0) -> Iterator[str]:
    """
    Yield Server-Sent-Event frames for events on the bus.

    Emits a comment line every `heartbeat` seconds so proxies keep the
    connection open and dead clients are detected.
    """
    pubsub = get_redis().pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(EVENT_CHANNEL)
    try:
        yield 'retry: 3000\n\n'
        while True:
            message = pubsub.get_message(timeout=heartbeat)
            if message is None:
                yield ': keepalive\n\n'
                continue
            raw = message.get('data')
            if not isinstance(raw, str):
                continue
            try:
                event = json.loads(raw)
            except ValueError:
                continue
            if types and event.get('type') not in types:
                continue
            yield f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"
    finally:
        try:
            pubsub.close()
        except Exception:
            pass


def send_control(command: str, **kwargs: Any) -> None:
    """Broadcast a control command to all API processes."""
    get_redis().publish(CONTROL_CHANNEL, json.dumps({'command': command, **kwargs}))


def start_control_listener(handler: Callable[[dict[str, Any]], None]) -> threading.Thread:
    """Run `handler(command_dict)` for every control message in a daemon thread."""

    def _loop() -> None:
        while True:
            try:
                pubsub = get_redis().pubsub(ignore_subscribe_messages=True)
                pubsub.subscribe(CONTROL_CHANNEL)
                for message in pubsub.listen():
                    raw = message.get('data')
                    if not isinstance(raw, str):
                        continue
                    try:
                        handler(json.loads(raw))
                    except Exception as e:
                        logger.error(f"Control handler failed: {e}", exc_info=True)
            except Exception as e:
                logger.warning(f"Control listener reconnecting after error: {e}")
                threading.Event().wait(5)

    thread = threading.Thread(target=_loop, name='control-listener', daemon=True)
    thread.start()
    return thread
