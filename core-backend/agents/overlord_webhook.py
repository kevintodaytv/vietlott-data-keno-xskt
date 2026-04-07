# core-backend/agents/overlord_webhook.py
import asyncio
import aiohttp
import os
import json
from typing import List

class OverlordWebhook:
    def __init__(self):
        self.discord_url = os.getenv("DISCORD_WEBHOOK_URL")
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.slack_url = os.getenv("SLACK_WEBHOOK_URL")

    async def _phoenix_retry(self, coro_func, channel_name: str, *args, **kwargs):
        """Exponential backoff retry (Tối đa 3 lần)"""
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                await coro_func(*args, **kwargs)
                print(f"✅ [OVERLORD] Báo cáo đã đến {channel_name}.")
                return True
            except Exception as e:
                print(f"⚠️ [PHOENIX] Lỗi {channel_name} (Lần {attempt}/{max_retries}): {e}")
                if attempt == max_retries:
                    return False
                await asyncio.sleep(2 ** attempt)

    async def _send_discord(self, message: str, image_paths: List[str]):
        if not self.discord_url: return
        async with aiohttp.ClientSession() as session:
            await session.post(self.discord_url, json={"content": message})

    async def _send_telegram(self, message: str, image_paths: List[str]):
        if not self.telegram_token or not self.telegram_chat_id: return
        base_url = f"https://api.telegram.org/bot{self.telegram_token}"
        async with aiohttp.ClientSession() as session:
            payload = {"chat_id": self.telegram_chat_id, "text": message, "parse_mode": "HTML"}
            await session.post(f"{base_url}/sendMessage", json=payload)

    async def broadcast(self, message: str, image_paths: List[str] = []):
        """Kích nổ bắn tin song song"""
        tasks = [
            self._phoenix_retry(self._send_discord, "Discord", message, image_paths),
            self._phoenix_retry(self._send_telegram, "Telegram", message, image_paths)
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

# Khởi tạo Singleton dùng chung cho toàn bộ Backend
overlord_bot = OverlordWebhook()
