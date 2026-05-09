import os
import sys
import logging
from dotenv import load_dotenv

# Load .env dari root folder (naik dua level dari scripts/)
load_dotenv(
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", ".env"
    )
)

# Tambahkan root folder ke sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.supabase_store import SupabaseStore
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_api_keys():
    """
    Memasukkan API Keys ke database sesuai aturan Zero Hacker (No .env).
    Karena Redis mati, kita masukkan ke tabel konfigurasi di Supabase.
    """
    db = SupabaseStore()

    # Buat tabel config jika belum ada agar konfigurasi runtime bisa dibaca service lain.

    keys = {
        "BINANCE_API_KEY": "oIwwep4aciogDQJeCFWI0MFMQ7Ec62pH8P8nfFOPIyX0Wth2LEVJSH3txF1e0V0K",
        "BINANCE_SECRET_KEY": "1wFGYTcHV0ettSZXtlFC9Wfg9dnxkHIwhzL18f9RVX3Susko2xCW6BG2UM7Bb0qt",
        "TOKOCRYPTO_API_KEY": "cfDC92B191b9B3Ca3D842Ae0e01108CBKI6BqEW6xr4NrPus3hoZ9Ze9YrmWwPFV",
        "TOKOCRYPTO_SECRET_KEY": "f9AbA6a8AD6bC2a97294a212244dda04ETfl0kc4BSUGOtL7m7rNELpt3Jh25SiP",
        "TELEGRAM_BOT_TOKEN": "YOUR_TELEGRAM_BOT_TOKEN_HERE",
        "TELEGRAM_CHAT_ID": "YOUR_TELEGRAM_CHAT_ID_HERE",
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "your_email@gmail.com",
        "SMTP_PASS": "your_app_password",
        "NVIDIA_API_KEY": "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",
        "LLM_MODEL_NAME": "nvidia/nv-embedcode-7b-v1",
    }

    try:
        with db.engine.connect() as conn:
            # Drop table jika schema lama tidak sesuai (e.g. beda kolom)
            # Karena ini script seeding, kita ingin memastikan schema yang benar.
            conn.execute(text("DROP TABLE IF EXISTS system_configs"))

            # Buat ulang tabel config
            conn.execute(
                text(
                    """
                CREATE TABLE system_configs (
                    "key" VARCHAR(100) PRIMARY KEY,
                    "value" TEXT NOT NULL,
                    "updated_at" TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """
                )
            )

            for k, v in keys.items():
                conn.execute(
                    text(
                        """
                    INSERT INTO system_configs ("key", "value")
                    VALUES (:key, :value)
                    ON CONFLICT ("key") DO UPDATE SET
                        "value" = EXCLUDED."value",
                        "updated_at" = CURRENT_TIMESTAMP
                """
                    ),
                    {"key": k, "value": v},
                )

            conn.commit()
            logger.info(
                "✅ API Keys berhasil diamankan ke Supabase (system_configs table)."
            )
    except Exception as e:
        logger.error(f"❌ Gagal melakukan seeding: {e}")


if __name__ == "__main__":
    seed_api_keys()
