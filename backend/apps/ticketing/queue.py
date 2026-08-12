"""The Redis side of the fair queue.

Design in one paragraph: an HTTP request does one INSERT and one RPUSH, then
returns. A single allocator process pops with BLPOP, so requests are served in
exactly the order they arrived - fairness comes from having one consumer, not
from database locks, which is what lets the web tier absorb a spike.

Two counters per event make the queue observable:
  `queue:<id>:seq`    incremented on enqueue  -> the buyer's ticket number
  `queue:<id>:served` incremented on pop      -> how far the line has moved
A buyer's position is `sequence - served`, so one broadcast value updates
everybody's position without a message per person.
"""

import redis
from django.conf import settings

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client


def queue_key(event_id: int) -> str:
    return f"queue:event:{event_id}"


def sequence_key(event_id: int) -> str:
    return f"queue:event:{event_id}:seq"


def served_key(event_id: int) -> str:
    return f"queue:event:{event_id}:served"


def enqueue(event_id: int, reservation_public_id: str) -> int:
    """Append to the line and return the buyer's ticket number.

    The INCR and the RPUSH go out in one pipeline so the sequence a buyer is
    told matches the order the allocator will actually see.
    """
    client = get_redis()
    pipe = client.pipeline()
    pipe.incr(sequence_key(event_id))
    pipe.rpush(queue_key(event_id), reservation_public_id)
    sequence, _ = pipe.execute()
    return int(sequence)


def pop_blocking(event_id: int, timeout: int = 5) -> str | None:
    """Take the next buyer in line, waiting up to `timeout` seconds."""
    result = get_redis().blpop(queue_key(event_id), timeout=timeout)
    return result[1] if result else None


def mark_served(event_id: int) -> int:
    return int(get_redis().incr(served_key(event_id)))


def get_served(event_id: int) -> int:
    return int(get_redis().get(served_key(event_id)) or 0)


def queue_length(event_id: int) -> int:
    return int(get_redis().llen(queue_key(event_id)))


def position_for(
    sequence: int | None,
    served: int | None = None,
    event_id: int | None = None,
) -> int | None:
    """How many people are still ahead, including the one being served."""
    if sequence is None:
        return None
    if served is None:
        served = get_served(event_id) if event_id is not None else 0
    return max(0, sequence - served)


def reset_queue(event_id: int) -> None:
    """Clear the line. Used by tests and between load-test runs."""
    client = get_redis()
    client.delete(queue_key(event_id), sequence_key(event_id), served_key(event_id))
