import pytest
import fakeredis
from app import create_app
from app.rate_limiter import RedisRateLimiter

@pytest.fixture
def client():
    fake_redis = fakeredis.FakeStrictRedis(decode_responses=True, protocol=2)
    fake_redis.flushall()

    import app
    app.redis_client = fake_redis
    app.limiter = RedisRateLimiter(fake_redis)

    flask_app = create_app()
    flask_app.config['TESTING'] = True
    
    with flask_app.test_client() as client:
        yield client

def test_tier_endpoint_anonymous_limit(client):
    headers = {"X-Forwarded-For": "192.168.1.100"}
    for i in range(5):
        res = client.get('/api/tier-endpoint', headers=headers)
        assert res.status_code == 200
        assert res.headers["X-RateLimit-Limit"] == "5"
        assert res.headers["X-RateLimit-Remaining"] == str(5 - (i + 1))

    res = client.get('/api/tier-endpoint', headers=headers)
    assert res.status_code == 429
    assert res.headers["X-RateLimit-Remaining"] == "0"
    assert "Retry-After" in res.headers
    assert res.json["error"] == "Too Many Requests"

def test_tier_endpoint_user_scope(client):
    headers = {
        "Authorization": "Bearer unique-user-token-99",
        "X-Forwarded-For": "192.168.1.101"
    }
    
    res1 = client.get('/api/tier-endpoint', headers=headers)
    assert res1.status_code == 200
    assert res1.headers["X-RateLimit-Limit"] == "50"
    assert res1.headers["X-RateLimit-Remaining"] == "49"