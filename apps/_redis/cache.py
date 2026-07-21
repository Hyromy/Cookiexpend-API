from logging import getLogger

import apps._redis as redis_infra

logger = getLogger(__name__)


def set_in_cache(key: str, value: str, /, *, ttl: int = 600) -> bool:
    """Set a key-value pair in Redis cache with an optional time-to-live (TTL). Returns True if successful, False otherwise."""

    try:
        redis_infra.redis_client.setex(key, ttl, value)
        return True

    except Exception as e:
        logger.error(f"Failed to set key {key} in Redis cache", exc_info=e)
        return False


def get_from_cache(key: str, /) -> str | None:
    """Retrieve a value from Redis cache by key. Returns the value if found, None otherwise."""

    try:
        value = redis_infra.redis_client.get(key)
        return value.decode("utf-8") if value else None

    except Exception as e:
        logger.error(f"Failed to get key {key} from Redis cache", exc_info=e)
        return None


def delete_from_cache(key: str, /) -> bool:
    """Delete a key-value pair from Redis cache. Returns True if the key was deleted, False otherwise."""

    try:
        result = redis_infra.redis_client.delete(key)
        return result > 0

    except Exception as e:
        logger.error(f"Failed to delete key {key} from Redis cache", exc_info=e)
        return False
