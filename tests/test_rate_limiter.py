import time
import pytest
import fakeredis
from app.rate_limiter import RedisRateLimiter

@pytest.fixture
def fake_redis_limiter():
    """Provides a RedisRateLimiter instance connected to an in-memory Fake Redis."""
    fake_client = fakeredis.FakeStrictRedis(decode_responses=True, protocol=2)
    return RedisRateLimiter(fake_client)

def test_sliding_window_rate_limiter(fake_redis_limiter):
    key = "rate_limit:test_client"
    max_limit = 5
    window_ms = 60000

    for i in range(1, 6):
        res = fake_redis_limiter.is_allowed(key, max_limit, window_ms)
        assert res["allowed"] is True
        assert res["remaining"] == (max_limit - i)

    res = fake_redis_limiter.is_allowed(key, max_limit, window_ms)
    assert res["allowed"] is False
    assert res["remaining"] == 0
    assert res["retry_after"] > 0

def test_sliding_window_expiration(fake_redis_limiter):
    key = "rate_limit:expiration_client"
    max_limit = 2
    window_ms = 1000

    assert fake_redis_limiter.is_allowed(key, max_limit, window_ms)["allowed"] is True
    assert fake_redis_limiter.is_allowed(key, max_limit, window_ms)["allowed"] is True
    
    assert fake_redis_limiter.is_allowed(key, max_limit, window_ms)["allowed"] is False

    time.sleep(1.1)

    res = fake_redis_limiter.is_allowed(key, max_limit, window_ms)
    assert res["allowed"] is True
    assert res["remaining"] == 1