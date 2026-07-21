from sys import modules

from django.apps import AppConfig
from redis import from_url as redis_from_url

from project.config import config


class RedisConfig(AppConfig):
    name = "apps._redis"

    def ready(self):
        modules[self.name].redis_client = redis_from_url(config.REDIS_URL)
