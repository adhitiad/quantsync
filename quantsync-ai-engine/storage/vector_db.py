import os
import logging
import gc
import torch
from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings
from langchain_milvus import Milvus
from database.milvus_client import get_milvus_connection

logger = logging.getLogger(__name__)

def get_nvidia_embeddings() -> NVIDIAEmbeddings:
    """Menginisialisasi NVIDIA Embeddings dari Environment Variables."""
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
         from database.redis_config import get_redis_config
         api_key = get_redis_config().get_config("NVIDIA_API_KEY")
         
    if not api_key:
         logger.error("Fatal: NVIDIA_API_KEY tidak ditemukan!")
         raise SystemExit("Missing NVIDIA API Key")
         
    # Menggunakan model spesifik sesuai permintaan arsitek
    return NVIDIAEmbeddings(
        model="nvidia/nv-embedcode-7b-v1",
        api_key=api_key,
        truncate="NONE" 
    )

class VectorStore:
    def __init__(self):
        """
        Menginisialisasi VectorStore menggunakan Milvus (Zilliz Cloud) dan NVIDIA AI Endpoints.
        """
        try:
            # Pastikan koneksi terjalin secara global
            get_milvus_connection()
            self.nv_embeddings = get_nvidia_embeddings()
            
            # Konfigurasi Milvus
            from database.redis_config import get_redis_config
            redis_cfg = get_redis_config()
            
            uri = redis_cfg.get_config("MILVUS_URI") or os.getenv("MILVUS_URI")
            token = redis_cfg.get_config("MILVUS_TOKEN") or os.getenv("MILVUS_TOKEN")
            db_name = redis_cfg.get_config("MILVUS_DB_NAME") or os.getenv("MILVUS_DB_NAME", "db_4799fccdb5b249f")
            
            if not uri: uri = "https://in03-4799fccdb5b249f.serverless.aws-eu-central-1.cloud.zilliz.com"
            if not token: token = "15241b309c6c0f22329449dd10860bed04d792e588a0232b22aebb0a391170e16585ea1b6a68b8559348a1ef1a2a7afa60c39ea0"

            # Gunakan Milvus wrapper dengan connection_args yang benar
            self.vector_store = Milvus(
                embedding_function=self.nv_embeddings,
                connection_args={
                    "uri": uri,
                    "token": token,
                    "db_name": db_name,
                    "secure": True,
                    "alias": "default" # Pastikan menggunakan alias yang sama
                },
                collection_name="quantsync_market_sentiment",
                auto_id=False
            )
            
            logger.info("✅ [RAG] NVIDIA Embeddings berhasil disambungkan dengan Milvus/Zilliz Cloud")
        except Exception as e:
            logger.error(f"Gagal inisialisasi VectorStore: {e}")
            self.vector_store = None

    def add_documents(self, documents):
        if not self.vector_store:
            return
            
        try:
            texts = [d["document"] for d in documents]
            metadatas = [d["metadata"] for d in documents]
            ids = [d["id"] for d in documents]
            
            self.vector_store.add_texts(texts=texts, metadatas=metadatas, ids=ids)
            logger.info(f"Berhasil menambahkan {len(texts)} dokumen ke Milvus.")
            
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception as e:
            logger.error(f"Gagal menambahkan dokumen ke VectorStore: {e}")

    def query_sentiment(self, asset_name, n_results=3):
        if not self.vector_store:
            return "Vector DB not initialized."

        try:
            query = f"current market sentiment and news analysis for {asset_name}"
            docs = self.vector_store.similarity_search(query, k=n_results)
            
            if not docs:
                return "No relevant market context found."
                
            context = " ".join([doc.page_content for doc in docs])
            return context
        except Exception as e:
            logger.error(f"Gagal query sentimen dari VectorStore: {e}")
            return "Error retrieving market context."

def init_vector_store():
    return VectorStore()
