from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redis import Redis

redis_client: "Redis" = None
