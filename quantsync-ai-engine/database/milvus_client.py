import os
import logging
from pymilvus import connections

logger = logging.getLogger(__name__)

def get_milvus_connection():
    """
    Menginisialisasi koneksi ke Milvus (Zilliz Cloud).
    Kredensial diambil dari Redis atau Environment Variables.
    """
    from database.redis_config import get_redis_config
    redis_cfg = get_redis_config()
    
    uri = redis_cfg.get_config("MILVUS_URI")
    token = redis_cfg.get_config("MILVUS_TOKEN")
    db_name = redis_cfg.get_config("MILVUS_DB_NAME")
    
    # Fallback ke env
    if not uri: uri = os.getenv("MILVUS_URI")
    if not token: token = os.getenv("MILVUS_TOKEN")
    if not db_name or db_name == "default": 
        db_name = os.getenv("MILVUS_DB_NAME", "db_4799fccdb5b249f")

    # Hardcoded fallback from User instructions if still empty
    if not uri:
        uri = "https://in03-4799fccdb5b249f.serverless.aws-eu-central-1.cloud.zilliz.com"
    if not token:
        token = "15241b309c6c0f22329449dd10860bed04d792e588a0232b22aebb0a391170e16585ea1b6a68b8559348a1ef1a2a7afa60c39ea0"

    try:
        # Check if already connected
        if connections.has_connection("default"):
            return connections

        logger.info(f"Connecting to Milvus/Zilliz at {uri} (DB: {db_name})...")
        connections.connect(
            alias="default",
            uri=uri,
            token=token,
            db_name=db_name,
            secure=True
        )
        logger.info(f"✅ [Vector DB] Berhasil terhubung ke Milvus/Zilliz (Alias: default, DB: {db_name})")
        return connections
    except Exception as e:
        logger.error(f"Gagal terhubung ke Milvus/Zilliz: {e}")
        # Final safety check for threading
        if connections.has_connection("default"):
            return connections
        raise SystemExit(f"Milvus Connection Error: {e}")
