"""
Events API Route
Receives EventBridge events via POST and streams them to listeners via GET (SSE).
"""

import json
import logging
import queue
import threading
import time
from datetime import datetime, timezone
from flask import Blueprint, Response, jsonify, request, stream_with_context

BP = Blueprint("events", __name__)

logger = logging.getLogger(__name__)

# ---- In-memory event store --------------------------------------------------
# Keeps the last MAX_STORED_EVENTS events for late-joining clients.
MAX_STORED_EVENTS = 100
_events: list[dict] = []
_events_lock = threading.Lock()

# Each connected SSE client gets its own Queue placed in this list.
_listeners: list[queue.Queue] = []
_listeners_lock = threading.Lock()


def _store_and_broadcast(event: dict) -> None:
    """Persist event in memory and push it to every active SSE listener."""
    with _events_lock:
        _events.append(event)
        if len(_events) > MAX_STORED_EVENTS:
            _events.pop(0)

    with _listeners_lock:
        dead = []
        for q in _listeners:
            try:
                q.put_nowait(event)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _listeners.remove(q)


def _sse_format(data: dict, event_type: str = "event") -> str:
    """Serialize a dict to the SSE wire format."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


# ---- POST /api/events -------------------------------------------------------

@BP.route("/", methods=["POST"])
def receive_event():
    """
    Receive an EventBridge (or any JSON) event payload.

    Stores the event in memory and broadcasts it to all active SSE listeners.
    """
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415

    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"error": "Invalid or empty JSON body"}), 400

    event = {
        "id": f"{time.time_ns()}",
        "receivedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "payload": payload,
    }

    _store_and_broadcast(event)
    logger.info("Event received and broadcast: id=%s source=%s",
                event["id"], payload.get("source", "unknown"))

    return jsonify({"status": "received", "eventId": event["id"]}), 202


# ---- GET /api/events --------------------------------------------------------

@BP.route("/", methods=["GET"])
def stream_events():
    """
    Server-Sent Events (SSE) stream.

    Connect with:
        const es = new EventSource('/api/events');
        es.addEventListener('event', e => console.log(JSON.parse(e.data)));

    Query parameters:
        replay (bool, default true) – send all stored events on connect before
                                      switching to live streaming.
    """
    replay = request.args.get("replay", "true").lower() != "false"
    client_queue: queue.Queue = queue.Queue(maxsize=50)

    with _listeners_lock:
        _listeners.append(client_queue)

    def generate():
        # Replay buffered events first so the client catches up.
        if replay:
            with _events_lock:
                buffered = list(_events)
            for ev in buffered:
                yield _sse_format(ev)

        # Stream new events as they arrive.
        try:
            while True:
                try:
                    ev = client_queue.get(timeout=25)
                    yield _sse_format(ev)
                except queue.Empty:
                    # Send a keep-alive comment so the connection stays open.
                    yield ": keep-alive\n\n"
        except GeneratorExit:
            pass
        finally:
            with _listeners_lock:
                if client_queue in _listeners:
                    _listeners.remove(client_queue)
            logger.info("SSE client disconnected")

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering if behind a proxy
        },
    )
