import os
import redis
from flask import Flask
from app.rate_limiter import RedisRateLimiter

redis_client = None
limiter = None

def create_app(config=None) -> Flask:
    global redis_client, limiter
    
    app = Flask(__name__)

    redis_url = os.getenv("REDIS_URL")

    if redis_client is None:
        redis_client = redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            protocol=2
        )
        limiter = RedisRateLimiter(redis_client)

    from app.routes import api_bp
    app.register_blueprint(api_bp)

    return app