import os
import redis
from flask import Flask
from app.rate_limiter import RedisRateLimiter

redis_client = None
limiter = None

def create_app(config=None) -> Flask:
    global redis_client, limiter
    
    app = Flask(__name__)


    redis_host = os.getenv("REDIS_HOST", "redis")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    redis_db = int(os.getenv("REDIS_DB", 0))

    if redis_client is None:
        redis_client = redis.Redis(
            host=redis_host, 
            port=redis_port, 
            db=redis_db, 
            decode_responses=True,
            protocol=2  
        )
        limiter = RedisRateLimiter(redis_client)

    from app.routes import api_bp
    app.register_blueprint(api_bp)

    return app