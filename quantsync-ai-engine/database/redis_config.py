import redis
import os
import logging
from dotenv import load_dotenv

# Load .env dari root folder (naik dua level dari database/)
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", ".env"))

logger = logging.getLogger(__name__)


class RedisConfig:
    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedisConfig, cls).__new__(cls)

            # Detect if running inside Docker
            is_docker = (
                os.path.exists("/.dockerenv") or os.getenv("IS_DOCKER") == "true"
            )

            try:
                # Try REDIS_URL first so cloud and docker URL forms are both supported.
                redis_url = os.getenv("REDIS_URL")

                if redis_url:
                    logger.info(
                        f"[Redis] Using URL-based connection ({'Upstash' if 'upstash' in redis_url else 'External'})"
                    )
                    cls._client = redis.Redis.from_url(
                        redis_url, decode_responses=True, socket_connect_timeout=5
                    )
                else:
                    redis_host = os.getenv("REDIS_HOST")
                    redis_port = int(os.getenv("REDIS_PORT", 6379))
                    if is_docker and redis_host:
                        logger.info(
                            f"[Redis] Docker mode detected, using {redis_host}:{redis_port}"
                        )
                    else:
                        redis_host = redis_host or "localhost"
                        logger.warning(
                            f"[Redis] REDIS_URL tidak ada, fallback ke {redis_host}:{redis_port}"
                        )
                    cls._client = redis.Redis(
                        host=redis_host,
                        port=redis_port,
                        decode_responses=True,
                        socket_connect_timeout=5,
                    )

                cls._client.ping()
                logger.info("✅ [Redis] Connection verified successfully")
            except Exception as e:
                logger.error(f"❌ [Redis] CRITICAL ERROR: {e}")
                # Don't set to None, allow lazy retry if needed or handle gracefully
                cls._client = None
        return cls._instance

    def get_config(self, key: str, default=None) -> str:
        if self._client:
            val = self._client.get(f"config:{key}")
            return val if val is not None else default
        return default


def get_redis_config():
    return RedisConfig()
