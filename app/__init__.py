import os
import redis
from flask import Flask
from dotenv import load_dotenv
from flask_smorest import Api
from app.rate_limiter import RedisRateLimiter

load_dotenv()

redis_client = None
limiter = None


def create_app(config=None) -> Flask:
    global redis_client, limiter

    app = Flask(__name__)

    app.config["API_TITLE"] = "Redis Rate Limiter API"
    app.config["API_VERSION"] = "v1"
    app.config["OPENAPI_VERSION"] = "3.0.3"
    app.config["OPENAPI_URL_PREFIX"] = "/"
    app.config["OPENAPI_SWAGGER_UI_PATH"] = "/swagger-ui"
    app.config["OPENAPI_SWAGGER_UI_URL"] = (
        "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"
    )

    redis_url = os.getenv("REDIS_URL")

    if redis_client is None:
        redis_client = redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            protocol=2
        )
        limiter = RedisRateLimiter(redis_client)

    api = Api(app)

    from app.routes import api_bp
    api.register_blueprint(api_bp)

    return app