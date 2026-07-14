from unittest.mock import patch

import pytest

from .gossiper import event_name, publish_handler, redis_payload


class TestGossiper:
    def test_event_name_valid(self):
        assert event_name("product", "created") == "cookiexpend.product.created"

    def test_event_name_invalid(self):
        with pytest.raises(ValueError):
            event_name("invalid", "created")

    def test_event_name_invalid_action(self):
        with pytest.raises(ValueError):
            event_name("product", "invalid")

    def test_redis_payload_includes_envelope(self):
        data = {
            "id": 1,
            "name": "cookie",
            "version": 2,
            "updated_at": "2026-05-10T00:00:00Z",
        }
        payload = redis_payload(
            data,
            event="cookiexpend.product.created",
            version=2,
            updated_at="2026-05-10T00:00:00Z",
            source="test",
            model="product",
            action="created",
        )

        assert payload["data"] == data
        assert payload["version"] == 2
        assert payload["updated_at"] == "2026-05-10T00:00:00Z"
        assert payload["source"] == "test"
        assert payload["model"] == "product"
        assert payload["action"] == "created"

    def test_redis_payload_missing_fields_allows_none(self):
        data = {"id": 1, "name": "cookie"}

        payload = redis_payload(
            data,
            event="cookiexpend.product.created",
            version=None,
            updated_at=None,
            source="test",
            model="product",
            action="created",
        )

        assert payload["data"] == data
        assert payload["version"] is None
        assert payload["updated_at"] is None

    def test_publish_handler_calls_publish_on_redis(self):
        data = {
            "id": 1,
            "name": "cookie",
            "version": 2,
            "updated_at": "2026-05-10T00:00:00Z",
        }
        with patch("apps._redis.gossiper.publish_on_redis") as publish_mock:
            publish_handler("product", "created", data, "test")

        channel, payload = publish_mock.call_args.args
        assert channel == "cookiexpend.product.created"
        assert payload["event"] == "cookiexpend.product.created"
        assert payload["data"] == data
