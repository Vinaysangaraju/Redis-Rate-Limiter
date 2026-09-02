from functools import wraps

from flask import jsonify, request, make_response
from flask_smorest import Blueprint

from app import limiter
from app.schema import (
    TierResponseSchema,
    RateLimitErrorSchema,
    ForbiddenErrorSchema,
)


api_bp = Blueprint(
    "api",
    __name__,
    url_prefix="/api",
    description="Redis Rate Limiter API",
)


ROLE_TIERS = {
    "anonymous": {
        "limit": 5,
        "window_sec": 60,
    },
    "user": {
        "limit": 50,
        "window_sec": 60,
    },
    "admin": {
        "limit": 500,
        "window_sec": 60,
    },
}


def resolve_client_context() -> tuple[str, str, str]:
    """
    Extract client identity and role from request headers.

    Returns:
        (identifier, client_ip, role)
    """

    auth_header = request.headers.get("Authorization", "")
    role_header = request.headers.get("X-User-Role", "").lower()

    if request.headers.getlist("X-Forwarded-For"):
        client_ip = request.headers.getlist(
            "X-Forwarded-For"
        )[0].split(",")[0].strip()
    else:
        client_ip = request.remote_addr or "127.0.0.1"

    if role_header in ROLE_TIERS:
        role = role_header
        identifier = f"{role}:{auth_header or client_ip}"

    elif auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "").strip()

        role = "admin" if token.startswith("admin-") else "user"
        identifier = f"user:{token}"

    else:
        role = "anonymous"
        identifier = f"ip:{client_ip}"

    return identifier, client_ip, role


def rate_limit(custom_limit: int = None, custom_window: int = None):
    """
    Rate-limit decorator with dynamic role tiers
    and IP circuit-breaker protection.
    """

    def decorator(f):

        @wraps(f)
        def wrapped(*args, **kwargs):

            identifier, client_ip, role = resolve_client_context()

            # Check whether the IP has been temporarily banned.
            if limiter.is_ip_banned(client_ip):
                response = make_response(
                    jsonify({
                        "error": "Forbidden",
                        "message": (
                            "IP temporarily blocked due to malicious "
                            "activity. Try again later."
                        ),
                    }),
                    403,
                )

                response.headers["X-RateLimit-Limit"] = "0"
                response.headers["X-RateLimit-Remaining"] = "0"

                return response

            # Get rate-limit configuration for the user's role.
            tier_config = ROLE_TIERS.get(
                role,
                ROLE_TIERS["anonymous"],
            )

            limit = (
                custom_limit
                if custom_limit is not None
                else tier_config["limit"]
            )

            window_sec = (
                custom_window
                if custom_window is not None
                else tier_config["window_sec"]
            )

            window_ms = window_sec * 1000

            # Redis key is unique per endpoint and client.
            key = f"rate_limit:{request.endpoint}:{identifier}"

            result = limiter.is_allowed(
                key,
                max_limit=limit,
                window_size_ms=window_ms,
            )

            headers = {
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": str(result["remaining"]),
            }

            # Rate limit exceeded.
            if not result["allowed"]:

                headers["Retry-After"] = str(
                    result["retry_after"]
                )

                limiter.record_violation(
                    client_ip,
                    max_violations=5,
                    ban_ttl_sec=3600,
                )

                response = make_response(
                    jsonify({
                        "error": "Too Many Requests",
                        "message": (
                            f"Rate limit exceeded for {role} tier."
                        ),
                    }),
                    429,
                )

                response.headers.update(headers)

                return response

            # Request allowed.
            response = make_response(
                f(*args, **kwargs)
            )

            response.headers.update(headers)

            return response

        return wrapped

    return decorator


@api_bp.route(
    "/tier-endpoint",
    methods=["GET"],
)
@api_bp.response(
    200,
    TierResponseSchema,
    description="Request allowed",
)
@api_bp.alt_response(
    429,
    schema=RateLimitErrorSchema,
    description="Rate limit exceeded",
)
@api_bp.alt_response(
    403,
    schema=ForbiddenErrorSchema,
    description="IP temporarily blocked",
)
@rate_limit()
def tier_endpoint():
    """
    Test endpoint protected by the Redis rate limiter.
    """

    return {
        "message": "Access granted to tiered endpoint."
    }, 200