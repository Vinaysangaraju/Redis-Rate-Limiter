import pytest
import fakeredis
from app import create_app
from app.rate_limiter import RedisRateLimiter

@pytest.fixture
def client():
    fake_redis = fakeredis.FakeStrictRedis(decode_responses=True, protocol=2)
    
    import app
    app.redis_client = fake_redis
    app.limiter = RedisRateLimiter(fake_redis)

    flask_app = create_app()
    flask_app.config['TESTING'] = True
    
    with flask_app.test_client() as client:
        yield client

def test_role_tiering_limits(client):
    
    anon_headers = {"X-Forwarded-For": "192.168.1.1"}
    res = client.get('/api/tier-endpoint', headers=anon_headers)
    assert res.headers["X-RateLimit-Limit"] == "5"

    user_headers = {"Authorization": "Bearer regular-user-token", "X-Forwarded-For": "192.168.1.2"}
    res = client.get('/api/tier-endpoint', headers=user_headers)
    assert res.headers["X-RateLimit-Limit"] == "50"

    admin_headers = {"Authorization": "Bearer admin-secret-token", "X-Forwarded-For": "192.168.1.3"}
    res = client.get('/api/tier-endpoint', headers=admin_headers)
    assert res.headers["X-RateLimit-Limit"] == "500"

def test_circuit_breaker_ip_blacklisting(client):
    ip_headers = {"X-Forwarded-For": "10.0.0.99"}

    for _ in range(5):
        res = client.get('/api/tier-endpoint', headers=ip_headers)
        assert res.status_code == 200

    for i in range(5):
        res = client.get('/api/tier-endpoint', headers=ip_headers)
        assert res.status_code == 429

    res = client.get('/api/tier-endpoint', headers=ip_headers)
    assert res.status_code == 403
    assert res.json["error"] == "Forbidden"
    assert "IP temporarily blocked" in res.json["message"]