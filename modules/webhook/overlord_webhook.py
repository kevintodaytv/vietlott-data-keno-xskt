"""
╔══════════════════════════════════════════════════════════════════════╗
║        OVERLORD WEBHOOK MODULE — ALIEN-NEXUS ECOSYSTEM               ║
║        Version: 3.0.0 | Codename: "Absolute Eye"                    ║
║                                                                       ║
║  ✦ Multi-channel: Discord Rich Embed + Telegram Album + Slack Blocks ║
║  ✦ Phoenix Protocol: Exponential backoff retry (3 lần / kênh)        ║
║  ✦ asyncio.gather() — 3 kênh bắn SONG SONG, không blocking           ║
║  ✦ Trigger System:                                                    ║
║      [1] FastAPI POST /api/overlord/audit                             ║
║      [2] Heartbeat tự động mỗi N phút                                ║
║      [3] UNIX Signal SIGUSR1 — kích hoạt tức thì từ Host             ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import time
import signal
import asyncio
import hashlib
import logging
import aiohttp
import aiofiles
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum

from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ──────────────────────────────────────────────────────────────────────
# LOG — Alien-Nexus Format
# ──────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] OVERLORD ▶ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("overlord.webhook")


# ──────────────────────────────────────────────────────────────────────
# ENUMS & CONSTANTS
# ──────────────────────────────────────────────────────────────────────
class BuildStatus(Enum):
    SUCCESS  = "success"
    FAILED   = "failed"
    WARNING  = "warning"
    DEGRADED = "degraded"


class Channel(Enum):
    DISCORD  = "discord"
    TELEGRAM = "telegram"
    SLACK    = "slack"


STATUS_COLORS: Dict[BuildStatus, int] = {
    BuildStatus.SUCCESS:  0x00FF88,   # Neon Green
    BuildStatus.FAILED:   0xFF2244,   # Neon Red
    BuildStatus.WARNING:  0xFFAA00,   # Amber
    BuildStatus.DEGRADED: 0xFF6600,   # Orange
}

STATUS_EMOJI: Dict[BuildStatus, str] = {
    BuildStatus.SUCCESS:  "🟢",
    BuildStatus.FAILED:   "🔴",
    BuildStatus.WARNING:  "🟡",
    BuildStatus.DEGRADED: "🟠",
}


# ──────────────────────────────────────────────────────────────────────
# DATA SCHEMAS
# ──────────────────────────────────────────────────────────────────────
@dataclass
class QAReport:
    """Kết quả đầy đủ từ QA Sniper Agent sau mỗi lần audit."""
    timestamp:           str            = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    build_id:            str            = field(default_factory=lambda: hashlib.md5(str(time.time()).encode()).hexdigest()[:8].upper())
    status:              BuildStatus    = BuildStatus.SUCCESS
    services_checked:    List[str]      = field(default_factory=list)
    services_healthy:    List[str]      = field(default_factory=list)
    services_failed:     List[str]      = field(default_factory=list)
    screenshot_paths:    List[str]      = field(default_factory=list)
    audit_url:           str            = "http://localhost:3000"
    response_time_ms:    float          = 0.0
    build_duration_sec:  float          = 0.0
    ai_confidence_score: Optional[float] = None
    notes:               str            = ""
    environment:         str            = field(default_factory=lambda: os.getenv("DEPLOY_ENV", "production"))
    triggered_by:        str            = "overlord_agent"


@dataclass
class WebhookConfig:
    """Cấu hình toàn bộ kênh và hành vi retry."""
    discord_webhook_url: Optional[str]  = field(default_factory=lambda: os.getenv("DISCORD_WEBHOOK_URL"))
    telegram_bot_token:  Optional[str]  = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN"))
    telegram_chat_id:    Optional[str]  = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID"))
    slack_webhook_url:   Optional[str]  = field(default_factory=lambda: os.getenv("SLACK_WEBHOOK_URL"))
    max_retries:         int            = 3
    retry_delay_sec:     float          = 2.0
    screenshot_dir:      str            = field(default_factory=lambda: os.getenv("QA_SCREENSHOT_DIR", "/tmp/qa_screenshots"))
    enabled_channels:    List[Channel]  = field(default_factory=lambda: [Channel.DISCORD, Channel.TELEGRAM, Channel.SLACK])
    heartbeat_minutes:   int            = field(default_factory=lambda: int(os.getenv("OVERLORD_HEARTBEAT_MINUTES", "30")))


# ──────────────────────────────────────────────────────────────────────
# CORE CLASS — OverlordWebhook
# ──────────────────────────────────────────────────────────────────────
class OverlordWebhook:
    """
    Bộ máy phát tán báo cáo tác chiến của Overlord Agent.

    Hai cách sử dụng:
      1. Async context manager (khuyến nghị, dùng shared session):
            async with OverlordWebhook(config) as wh:
                await wh.dispatch_report(report)

      2. Hàm broadcast nhanh (dữ liệu thô, không cần QAReport):
            wh = OverlordWebhook(config)
            await wh.broadcast("Tin nhắn nhanh", ["/tmp/screen.png"])
    """

    def __init__(self, config: Optional[WebhookConfig] = None):
        self.config = config or WebhookConfig()
        self._session: Optional[aiohttp.ClientSession] = None
        log.info(
            "🌌 Overlord Webhook v3.0 khởi động | Kênh: %s",
            [c.value for c in self.config.enabled_channels],
        )

    # ── Session lifecycle ──────────────────────────────────────────────
    async def __aenter__(self):
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"User-Agent": "OverlordAgent/3.0 AlienNexus"},
        )
        return self

    async def __aexit__(self, *_):
        if self._session:
            await self._session.close()

    def _ensure_session(self) -> aiohttp.ClientSession:
        """Trả về session hiện tại hoặc tạo mới (dùng trong mode không có context manager)."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={"User-Agent": "OverlordAgent/3.0 AlienNexus"},
            )
        return self._session

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  PUBLIC API — 2 điểm vào dữ liệu
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def dispatch_report(self, report: QAReport) -> Dict[str, Any]:
        """
        [API chính] Nhận QAReport đầy đủ → Đóng gói Rich Embed → Bắn song song.
        Gọi từ QA Sniper, CI/CD, hoặc Heartbeat.
        """
        log.info("📡 Phát tán báo cáo Build #%s [%s]", report.build_id, report.status.value.upper())
        self._ensure_session()

        tasks, channel_names = self._build_dispatch_tasks(report)
        if not tasks:
            log.warning("⚠️  Không có kênh nào được cấu hình. Bỏ qua phát tán.")
            return {}

        outcomes = await asyncio.gather(*tasks, return_exceptions=True)
        results  = {}
        for name, outcome in zip(channel_names, outcomes):
            if isinstance(outcome, Exception):
                log.error("❌ Kênh [%s] thất bại: %s", name, outcome)
                results[name] = {"status": "failed", "error": str(outcome)}
            else:
                results[name] = outcome

        self._log_summary(report, results)
        return results

    async def broadcast(self, message: str, image_paths: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        [API nhanh] Gửi tin nhắn văn bản + ảnh tuỳ chọn mà không cần tạo QAReport.
        Tương đương với lệnh: overlord_bot.broadcast("Tin nhắn", ["ảnh.png"])
        Dùng cho trigger thủ công, alert nhanh.
        """
        log.info("📢 broadcast() được gọi")
        self._ensure_session()
        image_paths = image_paths or []

        tasks = [
            self._phoenix_retry(self._broadcast_discord,  "Discord",  message, image_paths),
            self._phoenix_retry(self._broadcast_telegram, "Telegram", message, image_paths),
            self._phoenix_retry(self._broadcast_slack,    "Slack",    message, image_paths),
        ]
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)

        results = {}
        for ch, outcome in zip(["discord", "telegram", "slack"], outcomes):
            results[ch] = {"status": "ok"} if outcome is True else {"status": "failed", "error": str(outcome)}
        return results

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  PHOENIX PROTOCOL — Exponential Backoff Retry
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def _phoenix_retry(self, coro_func, channel_name: str, *args, **kwargs) -> bool:
        """
        Phoenix Protocol: Tối đa 3 lần thử với exponential backoff (2s → 4s → 8s).
        Nếu kênh sập hoàn toàn → return False, không crash toàn hệ thống.
        """
        for attempt in range(1, self.config.max_retries + 1):
            try:
                await coro_func(*args, **kwargs)
                log.info("✅ [Phoenix] %s gửi thành công (lần %d)", channel_name, attempt)
                return True
            except Exception as e:
                log.warning("⚠️  [Phoenix] %s thất bại (lần %d/%d): %s",
                            channel_name, attempt, self.config.max_retries, e)
                if attempt == self.config.max_retries:
                    log.error("❌ [Phoenix] Bỏ cuộc kênh %s sau %d lần.", channel_name, self.config.max_retries)
                    return False
                wait = self.config.retry_delay_sec * (2 ** (attempt - 1))   # 2s, 4s, 8s
                log.info("   ↳ [Phoenix] Đợi %.0fs rồi thử lại...", wait)
                await asyncio.sleep(wait)
        return False

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  DISCORD — Rich Embed + multipart image attach
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _build_dispatch_tasks(self, report: QAReport):
        """Tạo danh sách task và tên kênh theo config."""
        tasks, names = [], []
        cfg = self.config

        if Channel.DISCORD in cfg.enabled_channels and cfg.discord_webhook_url:
            tasks.append(self._phoenix_retry(self._send_discord_report, "Discord", report))
            names.append("discord")

        if Channel.TELEGRAM in cfg.enabled_channels and cfg.telegram_bot_token:
            tasks.append(self._phoenix_retry(self._send_telegram_report, "Telegram", report))
            names.append("telegram")

        if Channel.SLACK in cfg.enabled_channels and cfg.slack_webhook_url:
            tasks.append(self._phoenix_retry(self._send_slack_report, "Slack", report))
            names.append("slack")

        return tasks, names

    async def _send_discord_report(self, report: QAReport):
        """Discord: Rich Embed màu + ảnh đính kèm multipart/form-data."""
        emoji = STATUS_EMOJI[report.status]
        color = STATUS_COLORS[report.status]

        healthy_str = "\n".join([f"✅ `{s}`" for s in report.services_healthy]) or "_Không có_"
        failed_str  = "\n".join([f"❌ `{s}`" for s in report.services_failed])  or "_Không có_"

        embed: Dict[str, Any] = {
            "title": f"{emoji} OVERLORD MISSION REPORT — Build #{report.build_id}",
            "description": (
                f"**Trạng thái:** `{report.status.value.upper()}`\n"
                f"**Môi trường:** `{report.environment}`\n"
                f"**URL kiểm toán:** {report.audit_url}\n"
                f"**Kích hoạt bởi:** `{report.triggered_by}`"
            ),
            "color": color,
            "fields": [
                {"name": "⏱️ Build Time",    "value": f"`{report.build_duration_sec:.1f}s`",  "inline": True},
                {"name": "🏓 Response",       "value": f"`{report.response_time_ms:.0f}ms`",   "inline": True},
                {"name": "🤖 AI Confidence", "value": f"`{report.ai_confidence_score:.1f}%`" if report.ai_confidence_score else "`N/A`", "inline": True},
                {"name": "🟢 Healthy",        "value": healthy_str, "inline": True},
                {"name": "🔴 Failed",         "value": failed_str,  "inline": True},
            ],
            "footer": {"text": f"Alien-Nexus QA Sniper • {report.timestamp[:19].replace('T',' ')} UTC"},
            "timestamp": report.timestamp,
        }

        if report.notes:
            embed["fields"].append({
                "name": "📝 Ghi chú",
                "value": f"```{report.notes[:1000]}```",
                "inline": False,
            })

        valid_paths = [Path(p) for p in report.screenshot_paths if Path(p).exists()]

        if valid_paths:
            await self._discord_multipart(embed, valid_paths)
        else:
            await self._discord_json({"embeds": [embed], "username": "Overlord Agent 🌌"})

    async def _discord_json(self, payload: dict):
        url = self.config.discord_webhook_url
        async with self._session.post(url, json=payload) as resp:
            if resp.status not in (200, 204):
                raise RuntimeError(f"Discord {resp.status}: {await resp.text()}")
            log.info("✅ Discord: Embed gửi thành công (text-only)")

    async def _discord_multipart(self, embed: dict, valid_paths: List[Path]):
        """Đính kèm ảnh vào embed qua multipart/form-data."""
        url = self.config.discord_webhook_url + "?wait=true"

        # Nhúng ảnh đầu tiên vào embed, thumbnail = ảnh thứ 2
        embed["image"]     = {"url": f"attachment://{valid_paths[0].name}"}
        if len(valid_paths) > 1:
            embed["thumbnail"] = {"url": f"attachment://{valid_paths[1].name}"}

        payload_json = json.dumps({"embeds": [embed], "username": "Overlord Agent 🌌"})

        form = aiohttp.FormData()
        form.add_field("payload_json", payload_json, content_type="application/json")

        for i, p in enumerate(valid_paths[:4]):   # Discord max 10 files
            async with aiofiles.open(p, "rb") as f:
                form.add_field(f"file{i}", await f.read(), filename=p.name, content_type="image/png")

        async with self._session.post(url, data=form) as resp:
            if resp.status not in (200, 204):
                raise RuntimeError(f"Discord multipart {resp.status}: {await resp.text()}")
            log.info("✅ Discord: Embed + %d ảnh gửi thành công", len(valid_paths[:4]))

    # ── broadcast() helper cho Discord (văn bản thô) ──────────────────
    async def _broadcast_discord(self, message: str, image_paths: List[str]):
        if not self.config.discord_webhook_url:
            return
        valid = [Path(p) for p in image_paths if Path(p).exists()]
        payload_json = json.dumps({"content": message, "username": "Overlord Agent 🌌"})

        if valid:
            form = aiohttp.FormData()
            form.add_field("payload_json", payload_json, content_type="application/json")
            for i, p in enumerate(valid[:4]):
                async with aiofiles.open(p, "rb") as f:
                    form.add_field(f"file{i}", await f.read(), filename=p.name, content_type="image/png")
            async with self._session.post(self.config.discord_webhook_url, data=form) as resp:
                resp.raise_for_status()
        else:
            async with self._session.post(self.config.discord_webhook_url,
                                          json={"content": message}) as resp:
                resp.raise_for_status()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  TELEGRAM — sendPhoto + sendMediaGroup (album)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def _send_telegram_report(self, report: QAReport):
        """Telegram: Ảnh đầu tiên kèm HTML caption, ảnh còn lại gửi album."""
        base  = f"https://api.telegram.org/bot{self.config.telegram_bot_token}"
        emoji = STATUS_EMOJI[report.status]
        conf  = f"{report.ai_confidence_score:.1f}%" if report.ai_confidence_score else "N/A"

        healthy = " | ".join([f"✅{s}" for s in report.services_healthy]) or "–"
        failed  = " | ".join([f"❌{s}" for s in report.services_failed])  or "–"

        text = (
            f"{emoji} <b>OVERLORD MISSION REPORT</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 Build: <code>#{report.build_id}</code>\n"
            f"📊 Status: <b>{report.status.value.upper()}</b>\n"
            f"🌐 Env: <code>{report.environment}</code>\n"
            f"🔗 <a href=\"{report.audit_url}\">{report.audit_url}</a>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏱ Build: <code>{report.build_duration_sec:.1f}s</code>  "
            f"🏓 Ping: <code>{report.response_time_ms:.0f}ms</code>\n"
            f"🧠 AI Score: <code>{conf}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🟢 Healthy: {healthy}\n"
            f"🔴 Failed:  {failed}\n"
        )
        if report.notes:
            text += f"━━━━━━━━━━━━━━━━━━━━━━\n📝 {report.notes[:500]}\n"
        text += f"\n<i>🕒 {report.timestamp[:19].replace('T',' ')} UTC • Alien-Nexus</i>"

        valid = [p for p in report.screenshot_paths if Path(p).exists()]

        if valid:
            await self._telegram_send_photo(base, self.config.telegram_chat_id, valid[0], text)
            if len(valid) > 1:
                await self._telegram_send_media_group(base, self.config.telegram_chat_id, valid[1:4])
        else:
            await self._telegram_send_text(base, self.config.telegram_chat_id, text)

    async def _telegram_send_photo(self, base: str, chat_id: str, photo_path: str, caption: str):
        p = Path(photo_path)
        form = aiohttp.FormData()
        form.add_field("chat_id",    chat_id)
        form.add_field("caption",    caption[:1024])
        form.add_field("parse_mode", "HTML")
        async with aiofiles.open(p, "rb") as f:
            form.add_field("photo", await f.read(), filename=p.name, content_type="image/png")
        async with self._session.post(f"{base}/sendPhoto", data=form) as resp:
            body = await resp.json()
            if not body.get("ok"):
                raise RuntimeError(f"Telegram sendPhoto: {body}")
            log.info("✅ Telegram: Đã gửi ảnh chính")

    async def _telegram_send_media_group(self, base: str, chat_id: str, paths: List[str]):
        """
        Gửi album nhiều ảnh qua sendMediaGroup.
        ⚠️  Telegram API spec: caption CHỈ được gán vào media_item[0],
        các ảnh còn lại KHÔNG được có caption — tránh lỗi 400 Bad Request.
        Tất cả file và metadata nằm trong CÙNG 1 FormData request.
        """
        media_list: List[Dict] = []
        files_to_upload: Dict[str, Path] = {}

        for i, path in enumerate(paths):
            p = Path(path)
            if not p.exists():
                continue
            attach_key = f"photo{i}"                          # dùng "photo" prefix như code mới
            media_item: Dict[str, Any] = {
                "type":  "photo",
                "media": f"attach://{attach_key}",
            }
            # Caption + parse_mode CHỈ cho ảnh đầu tiên (i == 0)
            if i == 0 and len(paths) > 1:                     # album context → không cần caption ở đây
                pass                                           # caption đã gửi qua sendPhoto trước đó
            media_list.append(media_item)
            files_to_upload[attach_key] = p

        if not media_list:
            return

        form = aiohttp.FormData()
        form.add_field("chat_id", chat_id)
        form.add_field("media",   json.dumps(media_list))    # JSON array trong cùng FormData

        for attach_key, p in files_to_upload.items():
            async with aiofiles.open(p, "rb") as f:
                form.add_field(
                    attach_key, await f.read(),
                    filename=p.name, content_type="image/png"
                )

        async with self._session.post(f"{base}/sendMediaGroup", data=form) as resp:
            body = await resp.json()
            if body.get("ok"):
                log.info("✅ Telegram: Album %d ảnh phụ gửi thành công", len(media_list))
            else:
                raise RuntimeError(f"Telegram sendMediaGroup: {body}")

    async def _telegram_send_text(self, base: str, chat_id: str, text: str):
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                   "disable_web_page_preview": True}
        async with self._session.post(f"{base}/sendMessage", json=payload) as resp:
            body = await resp.json()
            if not body.get("ok"):
                raise RuntimeError(f"Telegram sendMessage: {body}")
            log.info("✅ Telegram: Text-only gửi thành công")

    # ── broadcast() helper cho Telegram (văn bản thô) ─────────────────
    async def _broadcast_telegram(self, message: str, image_paths: List[str]):
        if not self.config.telegram_bot_token or not self.config.telegram_chat_id:
            return
        base  = f"https://api.telegram.org/bot{self.config.telegram_bot_token}"
        valid = [p for p in image_paths if Path(p).exists()]

        if len(valid) == 1:
            await self._telegram_send_photo(base, self.config.telegram_chat_id, valid[0], message[:1024])
        elif len(valid) > 1:
            await self._telegram_send_photo(base, self.config.telegram_chat_id, valid[0], message[:1024])
            await self._telegram_send_media_group(base, self.config.telegram_chat_id, valid[1:])
        else:
            await self._telegram_send_text(base, self.config.telegram_chat_id, message)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  SLACK — Block Kit message
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def _send_slack_report(self, report: QAReport):
        """Slack: Block Kit structured message."""
        emoji   = STATUS_EMOJI[report.status]
        status  = report.status.value.upper()
        healthy = ", ".join(report.services_healthy) or "–"
        failed  = ", ".join(report.services_failed)  or "–"

        blocks: List[Dict] = [
            {"type": "header",
             "text": {"type": "plain_text", "text": f"{emoji} Overlord Report — Build #{report.build_id}"}},
            {"type": "divider"},
            {"type": "section",
             "fields": [
                 {"type": "mrkdwn", "text": f"*Status:*\n`{status}`"},
                 {"type": "mrkdwn", "text": f"*Env:*\n`{report.environment}`"},
                 {"type": "mrkdwn", "text": f"*Build Time:*\n`{report.build_duration_sec:.1f}s`"},
                 {"type": "mrkdwn", "text": f"*Response:*\n`{report.response_time_ms:.0f}ms`"},
                 {"type": "mrkdwn", "text": f"*✅ Healthy:*\n{healthy}"},
                 {"type": "mrkdwn", "text": f"*❌ Failed:*\n{failed}"},
             ]},
        ]

        if report.notes:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*📝 Notes:*\n```{report.notes[:600]}```"},
            })

        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn",
                          "text": f"🕒 {report.timestamp[:19].replace('T',' ')} UTC • Alien-Nexus QA Sniper"}],
        })

        url = self.config.slack_webhook_url
        async with self._session.post(url, json={"blocks": blocks, "username": "Overlord Agent"}) as resp:
            if resp.status not in (200, 204):
                raise RuntimeError(f"Slack {resp.status}: {await resp.text()}")
            log.info("✅ Slack: Block Kit gửi thành công")

    async def _broadcast_slack(self, message: str, image_paths: List[str]):
        """broadcast() helper cho Slack (Block Kit đơn giản)."""
        if not self.config.slack_webhook_url:
            return
        blocks = [{"type": "section",
                   "text": {"type": "mrkdwn", "text": f"*BÁO CÁO TỪ OVERLORD*\n{message}"}}]
        async with self._session.post(self.config.slack_webhook_url,
                                      json={"blocks": blocks}) as resp:
            resp.raise_for_status()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  LOG SUMMARY
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def _log_summary(self, report: QAReport, results: Dict):
        ok_count   = sum(1 for v in results.values() if isinstance(v, dict) and v.get("status") == "ok")
        fail_count = len(results) - ok_count
        log.info(
            "📋 Phát tán hoàn tất | Build #%s | ✅ %d/%d kênh OK | Status: %s",
            report.build_id, ok_count, len(results), report.status.value.upper(),
        )
        if fail_count:
            log.warning("⚠️  %d kênh thất bại — Phoenix sẽ ghi log để tái thử.", fail_count)


# ──────────────────────────────────────────────────────────────────────
# SINGLETON — Dùng chung toàn bộ ứng dụng
# ──────────────────────────────────────────────────────────────────────
_default_config   = WebhookConfig()
overlord_bot      = OverlordWebhook(_default_config)


# ──────────────────────────────────────────────────────────────────────
# FACTORY FUNCTION — Gọi nhanh từ bất kỳ module nào
# ──────────────────────────────────────────────────────────────────────
async def fire_overlord_report(report: QAReport, config: Optional[WebhookConfig] = None) -> Dict:
    """
    Hàm tiện ích: Khởi tạo session → phát tán → đóng session.
    Dùng trong QA Sniper hoặc CI script:
        from overlord_webhook import fire_overlord_report, QAReport, BuildStatus
        await fire_overlord_report(QAReport(status=BuildStatus.SUCCESS, ...))
    """
    async with OverlordWebhook(config) as wh:
        return await wh.dispatch_report(report)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  FASTAPI APP — Buồng lái Trigger System
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
app = FastAPI(title="Overlord Nexus API", version="3.0.0")


async def perform_audit_and_report(source: str = "api"):
    """
    Hàm logic audit chính: Chụp ảnh Dashboard → Phân tích → Bắn báo cáo.
    Gọi bởi cả 3 trigger: API, Heartbeat, SIGUSR1.
    """
    log.info("🔍 [OVERLORD] Bắt đầu Audit từ nguồn: [%s]", source)

    # ── Cố gắng gọi QA Sniper nếu module tồn tại ────────────────────
    try:
        from qa_sniper_with_webhook import run_qa_sniper
        report = await run_qa_sniper()
        log.info("✅ [QA Sniper] Audit thành công | Build #%s", report.build_id)
        return report

    except ImportError:
        # Fallback khi QA Sniper chưa cài — gửi báo cáo cơ bản
        log.warning("[OVERLORD] QA Sniper chưa tích hợp — gửi báo cáo cơ bản")
        # ⚠️  Kiểm tra file tồn tại trước khi đưa vào evidence (tránh FileNotFoundError)
        evidence_path = "/app/shared_data/audit_evidence.png"
        evidence     = [evidence_path] if os.path.exists(evidence_path) else []
        html_message = (
            f"<b>🚨 OVERLORD AUDIT REPORT</b>\n"
            f"Nguồn trigger: <code>{source}</code>\n"
            f"Hệ thống Tech-Oracle đang chạy.\n"
            f"<i>{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC</i>"
        )
        await overlord_bot.broadcast(html_message, evidence)

    except Exception as e:
        log.error("❌ [OVERLORD] Audit crash: %s", e)
        fallback = QAReport(
            status       = BuildStatus.FAILED,
            notes        = f"Audit crash: {str(e)[:400]}",
            triggered_by = f"overlord → {source}",
        )
        async with OverlordWebhook() as wh:
            await wh.dispatch_report(fallback)


# ──────────────────────────────────────────────────────────────────────
# TRIGGER 1: FastAPI HTTP Endpoint
# ──────────────────────────────────────────────────────────────────────
@app.post("/api/overlord/audit", summary="Kích hoạt Audit thủ công")
async def manual_audit_trigger(background_tasks: BackgroundTasks):
    """
    Kích hoạt QA Sniper + Overlord Webhook ngay lập tức.
    Chạy trong BackgroundTasks để không block HTTP response.

    curl -X POST http://localhost:8000/api/overlord/audit
    """
    background_tasks.add_task(perform_audit_and_report, "http_api")
    return JSONResponse({
        "status":  "ACK",
        "message": "🚀 Strike Protocol đã được kích hoạt. Kiểm tra Discord/Telegram trong vài giây.",
        "source":  "http_api",
    })


# Pydantic model đảm bảo type-safe và tự sinh OpenAPI docs
class BroadcastRequest(BaseModel):
    message:     str
    image_paths: Optional[List[str]] = []


@app.post("/api/overlord/broadcast", summary="Gửi tin nhắn broadcast nhanh")
async def quick_broadcast(payload: BroadcastRequest, background_tasks: BackgroundTasks):
    """
    Gửi tin nhắn thủ công mà không cần audit.
    Dùng Pydantic model → FastAPI tự validate + sinh docs.

    curl -X POST http://localhost:8000/api/overlord/broadcast \\
         -H "Content-Type: application/json" \\
         -d '{"message": "Deploy thành công!", "image_paths": []}'
    """
    # Lọc chỉ các path thực sự tồn tại (tránh FileNotFoundError ở broadcast())
    valid_images = [p for p in (payload.image_paths or []) if os.path.exists(p)]
    background_tasks.add_task(overlord_bot.broadcast, payload.message, valid_images)
    return JSONResponse({
        "status":  "ACK",
        "message": "Broadcast đã được gửi vào hàng đợi.",
        "images_queued": len(valid_images),
    })


@app.get("/api/overlord/status", summary="Kiểm tra trạng thái Overlord")
async def overlord_status():
    """Health check cho chính Overlord Agent."""
    return {
        "agent":    "Overlord Webhook v3.0",
        "status":   "operational",
        "channels": [c.value for c in _default_config.enabled_channels],
        "time_utc": datetime.now(timezone.utc).isoformat(),
    }


# ──────────────────────────────────────────────────────────────────────
# TRIGGER 2: Heartbeat Loop (Tự động mỗi N phút)
# ──────────────────────────────────────────────────────────────────────
async def heartbeat_loop():
    """
    Tự động audit định kỳ. Interval đọc từ env OVERLORD_HEARTBEAT_MINUTES.
    Chạy như asyncio.Task song song với uvicorn event loop.
    """
    interval_min = _default_config.heartbeat_minutes
    interval_sec = interval_min * 60
    log.info("💓 Heartbeat loop khởi động: Tự động audit mỗi %d phút", interval_min)

    await asyncio.sleep(30)   # Chờ hệ thống ổn định trước lần đầu

    while True:
        log.info("💓 [HEARTBEAT] Kích hoạt audit định kỳ...")
        await perform_audit_and_report(source=f"heartbeat_{interval_min}min")
        await asyncio.sleep(interval_sec)


# ──────────────────────────────────────────────────────────────────────
# TRIGGER 3: UNIX Signal SIGUSR1
# ──────────────────────────────────────────────────────────────────────
def _handle_sigusr1(signum, frame):
    """
    Bắt tín hiệu SIGUSR1 từ Host/Shell.

    Cách kích hoạt từ bên ngoài container:
        docker exec -it core_api kill -USR1 $(pgrep -f "uvicorn")

    Hoặc từ trong container:
        kill -USR1 $(pgrep -f "uvicorn")
    """
    log.info("⚡ [SIGUSR1] Nhận tín hiệu từ Kỹ sư trưởng! Chạy Audit ngay lập tức...")
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(perform_audit_and_report(source="sigusr1_signal"))
    except RuntimeError:
        # Fallback nếu không có running loop
        asyncio.run(perform_audit_and_report(source="sigusr1_signal"))


# ──────────────────────────────────────────────────────────────────────
# FastAPI STARTUP — Kích hoạt tất cả hệ thống khi server bật
# ──────────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_events():
    # Gắn SIGUSR1 handler (Linux/Mac only)
    try:
        signal.signal(signal.SIGUSR1, _handle_sigusr1)
        signal.signal(signal.SIGUSR2, lambda s, f: asyncio.get_running_loop().create_task(
            perform_audit_and_report("sigusr2_force")
        ))
        log.info("📶 Signal handlers: SIGUSR1 (audit), SIGUSR2 (force-audit) đã đăng ký")
    except (AttributeError, OSError):
        log.warning("Unix signals không khả dụng trên Windows — bỏ qua")

    # Khởi động heartbeat
    asyncio.create_task(heartbeat_loop())

    log.info("🌌 [OVERLORD WEBHOOK] Đã lên mạng lưới. Sẵn sàng nhận lệnh từ mọi trigger.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CLI ENTRY — Chạy trực tiếp để test webhook (không cần FastAPI)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if __name__ == "__main__":
    demo = QAReport(
        status            = BuildStatus.SUCCESS,
        services_checked  = ["core_api", "nexus_ui", "vault_memory", "message_bus"],
        services_healthy  = ["core_api", "nexus_ui", "vault_memory"],
        services_failed   = [],
        screenshot_paths  = [
            "/tmp/qa_screenshots/dashboard_audit.png",
            "/tmp/qa_screenshots/amber_glow_ui.png",
        ],
        audit_url          = "http://103.82.25.23:3000",
        response_time_ms   = 142.5,
        build_duration_sec = 47.8,
        ai_confidence_score= 91.3,
        notes              = (
            "QA Sniper xác nhận: Giao diện Amber Glow render đúng. "
            "Dữ liệu Minh Chính đồng bộ 100%. Không có lỗi nghiêm trọng."
        ),
        environment        = "production",
        triggered_by       = "make ignite → qa_sniper → overlord",
    )

    print("\n🌌 OVERLORD WEBHOOK v3.0 — TEST FIRE\n" + "═" * 52)
    results = asyncio.run(fire_overlord_report(demo))
    print("\n📊 Kết quả phát tán:")
    print(json.dumps(results, indent=2, ensure_ascii=False))
    print("═" * 52)
