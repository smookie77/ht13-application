"""WebSocket behaviour, including the proxy heartbeat."""

import pytest
from channels.testing import WebsocketCommunicator

from config.asgi import application

pytestmark = pytest.mark.django_db(transaction=True)

# AllowedHostsOriginValidator wraps the socket router, so a connection with no
# Origin header is refused before it ever reaches a consumer. Real browsers
# always send one; the test client has to be told to.
ORIGIN_HEADERS = [(b"origin", b"http://localhost")]


def socket(path: str) -> WebsocketCommunicator:
    return WebsocketCommunicator(application, path, headers=ORIGIN_HEADERS)


@pytest.fixture
async def availability_socket(event, ticket_type):
    communicator = socket(f"/ws/events/{event.slug}/")
    connected, _ = await communicator.connect()
    assert connected
    yield communicator
    await communicator.disconnect()


@pytest.mark.asyncio
async def test_socket_without_origin_is_refused(event, ticket_type):
    """The WebSocket equivalent of CSRF protection: another site cannot open
    one of these against a signed-in visitor."""
    communicator = WebsocketCommunicator(application, f"/ws/events/{event.slug}/")
    connected, _ = await communicator.connect()
    assert not connected
    await communicator.disconnect()


@pytest.mark.asyncio
async def test_socket_from_a_foreign_origin_is_refused(event, ticket_type):
    communicator = WebsocketCommunicator(
        application,
        f"/ws/events/{event.slug}/",
        headers=[(b"origin", b"https://evil.example")],
    )
    connected, _ = await communicator.connect()
    assert not connected
    await communicator.disconnect()


@pytest.mark.asyncio
async def test_snapshot_is_sent_on_connect(availability_socket):
    """A client connecting between two allocations must not be left staring at
    a stale number, so the current state is pushed immediately."""
    message = await availability_socket.receive_json_from(timeout=5)

    assert message["type"] == "availability.update"
    assert message["payload"]["tickets_available"] == 10
    assert "now_serving" in message["payload"]


@pytest.mark.asyncio
async def test_ping_is_answered(availability_socket):
    """Proxies drop sockets that go quiet; the client pings to stay alive."""
    await availability_socket.receive_json_from(timeout=5)  # snapshot

    await availability_socket.send_json_to({"type": "ping"})
    assert await availability_socket.receive_json_from(timeout=5) == {"type": "pong"}


@pytest.mark.asyncio
async def test_unknown_client_messages_are_ignored(availability_socket):
    """These sockets are read-only - nothing a client sends may change state."""
    await availability_socket.receive_json_from(timeout=5)  # snapshot

    await availability_socket.send_json_to({"type": "allocate_me_a_ticket"})
    await availability_socket.send_json_to({"type": "ping"})

    # Still alive, and the only reply is the pong.
    assert await availability_socket.receive_json_from(timeout=5) == {"type": "pong"}


@pytest.mark.asyncio
async def test_unknown_event_is_refused(db):
    communicator = socket("/ws/events/does-not-exist/")
    connected, _ = await communicator.connect()
    assert not connected
    await communicator.disconnect()


@pytest.mark.asyncio
async def test_anonymous_reservation_socket_is_refused(db):
    """Order state is private, so the handshake is refused outright."""
    communicator = socket("/ws/reservations/00000000-0000-0000-0000-000000000000/")
    connected, _ = await communicator.connect()
    assert not connected
    await communicator.disconnect()
