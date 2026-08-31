import time
from typing import Tuple, Dict, Any
from redis import Redis, ResponseError

SLIDING_WINDOW_LUA_SCRIPT = """
local key = KEYS[1]
local current_time = tonumber(ARGV[1])
local window_size_ms = tonumber(ARGV[2])
local max_limit = tonumber(ARGV[3])

local clear_before = current_time - window_size_ms

redis.call('ZREMRANGEBYSCORE', key, '-inf', clear_before)
local current_requests = redis.call('ZCARD', key)

if current_requests < max_limit then
    local seq_key = key .. ':seq'
    local seq_val = redis.call('INCR', seq_key)
    
    redis.call('ZADD', key, current_time, current_time .. ':' .. seq_val)
    
    local ttl_seconds = math.ceil(window_size_ms / 1000)
    redis.call('EXPIRE', key, ttl_seconds)
    redis.call('EXPIRE', seq_key, ttl_seconds)  -- FIX: Expire sequence key to prevent memory leak
    
    return {1, max_limit - (current_requests + 1), 0}
else
    local oldest_entry = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local oldest_time = tonumber(oldest_entry[2])
    
    local reset_ms = (oldest_time + window_size_ms) - current_time
    local retry_after = math.max(1, math.ceil(reset_ms / 1000))
    return {0, 0, retry_after}
end
"""

class RedisRateLimiter:
    
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.script = SLIDING_WINDOW_LUA_SCRIPT
        try:
            self.lua_sha = self.redis.script_load(self.script)
        except Exception:
            self.lua_sha = None

    def is_allowed(self, key: str, max_limit: int, window_size_ms: int) -> Dict[str, Any]:
        current_time_ms = int(time.time() * 1000)

        if self.lua_sha:
            try:
                status, remaining, retry_after = self.redis.evalsha(
                    self.lua_sha, 1, key, current_time_ms, window_size_ms, max_limit
                )
                return {"allowed": bool(status), "remaining": remaining, "retry_after": retry_after}
            except ResponseError as e:
                
                if "NOSCRIPT" in str(e):
                    self.lua_sha = self.redis.script_load(self.script)
                    status, remaining, retry_after = self.redis.evalsha(
                        self.lua_sha, 1, key, current_time_ms, window_size_ms, max_limit
                    )
                    return {"allowed": bool(status), "remaining": remaining, "retry_after": retry_after}
                raise e

        status, remaining, retry_after = self.redis.eval(
            self.script, 1, key, current_time_ms, window_size_ms, max_limit
        )
        return {"allowed": bool(status), "remaining": remaining, "retry_after": retry_after}

    def is_ip_banned(self, ip: str) -> bool:
        return bool(self.redis.exists(f"banned:{ip}"))

    def record_violation(self, ip: str, max_violations: int = 5, ban_ttl_sec: int = 3600) -> bool:
        violation_key = f"violations:{ip}"
        violations = self.redis.incr(violation_key)
        
        if violations == 1:
            self.redis.expire(violation_key, 300)

        if violations >= max_violations:
            ban_key = f"banned:{ip}"
            self.redis.set(ban_key, "banned", ex=ban_ttl_sec)
            self.redis.delete(violation_key)
            return True
            
        return False