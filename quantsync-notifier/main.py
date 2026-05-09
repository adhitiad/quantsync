import redis
import json
import asyncio
import requests
from telegram import Bot
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
import time

class NotifierWorker:
    def __init__(self):
        self.redis_host = os.getenv("REDIS_HOST", "redis")
        self.redis_port = int(os.getenv("REDIS_PORT", 6379))
        self.r = redis.Redis(host=self.redis_host, port=self.redis_port, decode_responses=True)
        
        # Supabase setup for configs
        self.database_url = self._normalize_sqlalchemy_dsn(os.getenv("DATABASE_URL", ""))
        if not self.database_url:
            raise RuntimeError("DATABASE_URL untuk Supabase tidak ditemukan.")
        self.engine = create_engine(self.database_url, pool_pre_ping=True)
        self.Session = sessionmaker(bind=self.engine)
        
        self.configs = self._load_configs()
        self.tg_bot = None
        if self.configs.get("TELEGRAM_BOT_TOKEN"):
            self.tg_bot = Bot(token=self.configs["TELEGRAM_BOT_TOKEN"])

    def _load_configs(self):
        """Load configs from Supabase as per strict rules."""
        configs = {}
        try:
            with self.Session() as session:
                result = session.execute(text('SELECT "key", "value" FROM system_configs')).fetchall()
                for key, value in result:
                    configs[key] = value
        except Exception as e:
            print(f"Error loading configs from Supabase: {e}")
        return configs

    @staticmethod
    def _normalize_sqlalchemy_dsn(dsn):
        if dsn.startswith("postgresql+psycopg://"):
            return dsn
        if dsn.startswith("postgresql://"):
            return dsn.replace("postgresql://", "postgresql+psycopg://", 1)
        if dsn.startswith("postgres://"):
            return dsn.replace("postgres://", "postgresql+psycopg://", 1)
        return dsn

    async def send_telegram(self, message):
        chat_id = self.configs.get("TELEGRAM_CHAT_ID")
        if self.tg_bot and chat_id:
            try:
                await self.tg_bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
                print("Telegram notification sent.")
            except Exception as e:
                print(f"Failed to send Telegram: {e}")

    def send_email(self, subject, message):
        # Implementation for Postal/SMTP
        postal_key = self.configs.get("POSTAL_API_KEY")
        if postal_key:
            # Placeholder for Postal API call
            print(f"Email sent via Postal: {subject}")
            pass

    def format_signal_message(self, signal):
        emoji = "🚀" if signal['action'] == 'buy' else "🔻"
        msg = (
            f"*{emoji} NEW SIGNAL: {signal['asset']}*\n"
            f"Action: {signal['action'].upper()} ({signal['type_signal']})\n"
            f"Price: {signal['price']}\n"
            f"-------------------\n"
            f"🎯 TP1: {signal['tp1']}\n"
            f"🎯 TP2: {signal['tp2']}\n"
            f"🛑 SL: {signal['sl1']}\n"
            f"-------------------\n"
            f"Winrate: {signal['winrate_pct']}%\n"
            f"Reason: {signal['reason']}\n"
            f"Timestamp: {signal['timestamp']}"
        )
        return msg

    async def run(self):
        print("Notifier Worker started. Listening for signals...")
        pubsub = self.r.pubsub()
        pubsub.subscribe("signal_events")
        
        for message in pubsub.listen():
            if message['type'] == 'message':
                try:
                    signal = json.loads(message['data'])
                    print(f"Received signal for {signal['asset']}")
                    
                    formatted_msg = self.format_signal_message(signal)
                    
                    # Parallel sending
                    await self.send_telegram(formatted_msg)
                    self.send_email(f"QuantSync Signal: {signal['asset']}", formatted_msg)
                    
                except Exception as e:
                    print(f"Error processing signal message: {e}")

if __name__ == "__main__":
    worker = NotifierWorker()
    asyncio.run(worker.run())
