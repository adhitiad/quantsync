import logging
import os
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_milvus import Milvus
from langchain_core.prompts import ChatPromptTemplate
from database.redis_config import get_redis_config
from database.milvus_client import get_milvus_connection
from storage.vector_db import get_nvidia_embeddings

logger = logging.getLogger(__name__)

class SignalReasoner:
    def __init__(self):
        self.redis_cfg = get_redis_config()
        self.api_key = self.redis_cfg.get_config("NVIDIA_API_KEY") or os.getenv("NVIDIA_API_KEY")
        
        # FIX: Gunakan model Chat yang benar, bukan Reranker
        # Model 'meta/llama-3.1-8b-instruct' atau 'nvidia/nemotron-4-340b-instruct' adalah pilihan yang baik
        self.model_name = self.redis_cfg.get_config("LLM_MODEL_NAME", "meta/llama-3.1-8b-instruct")

        if self.api_key:
            try:
                self.llm = ChatNVIDIA(
                    nvidia_api_key=self.api_key, 
                    model=self.model_name, 
                    temperature=0.2
                )

                # Setup Milvus for RAG (Zilliz Cloud) via LangChain
                get_milvus_connection() 

                self.nv_embeddings = get_nvidia_embeddings()

                uri = self.redis_cfg.get_config("MILVUS_URI") or os.getenv("MILVUS_URI")
                token = self.redis_cfg.get_config("MILVUS_TOKEN") or os.getenv("MILVUS_TOKEN")
                db_name = self.redis_cfg.get_config("MILVUS_DB_NAME") or os.getenv("MILVUS_DB_NAME", "db_4799fccdb5b249f")

                if not uri: uri = "https://in03-4799fccdb5b249f.serverless.aws-eu-central-1.cloud.zilliz.com"
                if not token: token = "15241b309c6c0f22329449dd10860bed04d792e588a0232b22aebb0a391170e16585ea1b6a68b8559348a1ef1a2a7afa60c39ea0"

                self.vector_store = Milvus(
                    embedding_function=self.nv_embeddings,
                    connection_args={
                        "uri": uri,
                        "token": token,
                        "db_name": db_name,
                        "secure": True,
                        "alias": "default"
                    },
                    collection_name="quantsync_market_sentiment",
                    auto_id=True,
                )
                logger.info("✅ [Reasoner] Terhubung ke Milvus/Zilliz Cloud via LangChain")
            except Exception as e:
                logger.error(f"Gagal inisialisasi Reasoner: {e}")
                self.llm = None
                self.vector_store = None
        else:
            logger.warning("NVIDIA_API_KEY tidak ditemukan. Reasoner menggunakan mock responses.")
            self.llm = None
            self.vector_store = None

    def _query_market_context(self, asset: str) -> str:
        if not self.vector_store:
            return ""
        try:
            docs = self.vector_store.similarity_search(f"market sentiment for {asset}", k=2)
            return "\n".join([doc.page_content for doc in docs])
        except Exception as e:
            logger.error(f"Error searching Milvus via LangChain: {e}")
            return ""

    def generate_reason(self, asset, action, probability, winrate, context_docs=""):
        if not self.llm:
            return f"Aksi {action.upper()} untuk {asset} disarankan dengan probabilitas {probability}% dan winrate {winrate}%."

        market_context = self._query_market_context(asset)

        prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "Anda adalah Senior Market Analyst di QuantSync. Tugas Anda adalah memformulasikan "
                "alasan trading (reason) yang profesional, terukur, dan mudah dipahami dalam Bahasa Indonesia. "
                "Gunakan data teknis (Action, Probability, Winrate) dan konteks berita yang diberikan. "
                "Output harus singkat (maksimal 2-3 kalimat) dan memberikan keyakinan kepada trader."
            )),
            ("human", (
                f"Asset: {asset}\n"
                f"Action: {action.upper()}\n"
                f"Probability: {probability}%\n"
                f"Winrate: {winrate}%\n"
                f"Market Context: {market_context or context_docs}\n"
                "Tolong buatkan alasan trading yang solid."
            )),
        ])

        chain = prompt | self.llm

        try:
            response = chain.invoke({})
            return response.content.strip()
        except Exception as e:
            logger.error(f"Error generating reason with ChatNVIDIA: {e}")
            return f"Aksi {action.upper()} disarankan berdasarkan analisis model PPO ({probability}% probabilitas) dan sinyal teknikal pendukung."

_reasoner = None

def get_reasoner():
    global _reasoner
    if _reasoner is None:
        _reasoner = SignalReasoner()
    return _reasoner
