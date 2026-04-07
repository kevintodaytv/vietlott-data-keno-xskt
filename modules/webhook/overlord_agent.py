"""
╔══════════════════════════════════════════════════════════════════════╗
║   OVERLORD AGENT — Master Orchestrator with Webhook Integration      ║
║   Lắng nghe sự kiện → Điều phối → Gửi báo cáo tự động              ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import asyncio
import json
import time
import logging
import signal
from datetime import datetime, timezone
from typing import Optional, Dict, Any

# Webhook module
from overlord_webhook import (
    OverlordWebhook, QAReport, WebhookConfig, BuildStatus,
    fire_overlord_report
)

log = logging.getLogger("overlord.agent")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [OVERLORD] %(levelname)s ▶ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)


class OverlordAgent:
    """
    Tướng chỉ huy tối cao của Alien-Nexus.
    
    Luồng hoạt động:
      1. Lắng nghe Event Bus (Kafka / Redis Pub/Sub / Unix Signal)
      2. Khi nhận sự kiện BUILD_COMPLETE hoặc AUDIT_REQUEST:
         a. Gọi QA Sniper để thu thập kết quả
         b. Gọi Overlord Webhook để bắn báo cáo ra kênh
      3. Ghi log và cập nhật trạng thái hệ thống
    """

    def __init__(self, webhook_config: Optional[WebhookConfig] = None):
        self.webhook_config = webhook_config or WebhookConfig()
        self.is_running     = False
        self._event_queue: asyncio.Queue = asyncio.Queue()
        log.info("🌌 Overlord Agent khởi động. Đang lắng nghe sự kiện...")

    # ──────────────────────────────────────────────────────────────────
    # LIFECYCLE
    # ──────────────────────────────────────────────────────────────────
    async def start(self):
        """Khởi động Overlord và bắt đầu vòng lặp xử lý sự kiện."""
        self.is_running = True

        # Đăng ký Unix Signal handler (khi hệ thống gửi SIGUSR1 → kích hoạt audit)
        self._register_signal_handlers()

        await asyncio.gather(
            self._event_loop(),
            self._heartbeat_loop(),
        )

    def stop(self):
        self.is_running = False
        log.info("🛑 Overlord Agent đang tắt...")

    def _register_signal_handlers(self):
        """Cho phép trigger audit từ bên ngoài qua Unix signal."""
        try:
            loop = asyncio.get_event_loop()
            loop.add_signal_handler(
                signal.SIGUSR1,
                lambda: asyncio.create_task(self.trigger_audit("SIGUSR1"))
            )
            loop.add_signal_handler(
                signal.SIGUSR2,
                lambda: asyncio.create_task(self.trigger_audit("SIGUSR2_FORCE"))
            )
            log.info("📶 Signal handlers: SIGUSR1 (audit) / SIGUSR2 (force-audit) đã đăng ký")
        except (AttributeError, NotImplementedError):
            log.warning("Unix signals không khả dụng trên Windows — bỏ qua signal handlers")

    # ──────────────────────────────────────────────────────────────────
    # EVENT HANDLING
    # ──────────────────────────────────────────────────────────────────
    async def trigger_audit(self, source: str = "manual", extra: Optional[Dict] = None):
        """Đưa sự kiện audit vào hàng đợi."""
        event = {
            "type": "AUDIT_REQUEST",
            "source": source,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "extra": extra or {}
        }
        await self._event_queue.put(event)
        log.info("📨 Sự kiện audit từ [%s] đã được thêm vào hàng đợi", source)

    async def trigger_build_complete(self, build_data: Dict):
        """Gọi sau khi docker-compose build hoàn tất."""
        event = {
            "type": "BUILD_COMPLETE",
            "source": "ci_cd",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "extra": build_data
        }
        await self._event_queue.put(event)
        log.info("🔨 BUILD_COMPLETE event: %s", json.dumps(build_data, ensure_ascii=False))

    async def _event_loop(self):
        """Vòng lặp chính xử lý sự kiện."""
        log.info("🔄 Event loop bắt đầu chạy...")

        while self.is_running:
            try:
                event = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)
                await self._handle_event(event)
                self._event_queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("❌ Lỗi event loop: %s", e)

    async def _handle_event(self, event: Dict[str, Any]):
        """Xử lý từng loại sự kiện."""
        event_type = event.get("type")
        source     = event.get("source", "unknown")
        log.info("⚡ Xử lý sự kiện: %s từ [%s]", event_type, source)

        if event_type in ("AUDIT_REQUEST", "BUILD_COMPLETE"):
            await self._run_audit_and_report(event)
        elif event_type == "MANUAL_REPORT":
            report_data = event.get("extra", {})
            await self._send_manual_report(report_data)
        else:
            log.warning("Sự kiện không xác định: %s", event_type)

    async def _run_audit_and_report(self, event: Dict):
        """
        Luồng chính: Audit → Chụp ảnh → Webhook.
        Import QA Sniper trực tiếp để chạy trong process.
        """
        log.info("👁️  Kích hoạt QA Sniper...")
        build_start = float(event.get("extra", {}).get("build_start_epoch", time.time()))

        try:
            # Import QA Sniper function
            # Trong môi trường thật, import từ module đã cài
            from qa_sniper_with_webhook import run_qa_sniper
            os.environ["BUILD_START_EPOCH"] = str(build_start)
            report = await run_qa_sniper()

            log.info(
                "✅ Audit hoàn tất | Build #%s | Status: %s",
                report.build_id, report.status.value
            )

        except ImportError:
            # Fallback: tạo báo cáo cơ bản nếu QA Sniper chưa sẵn sàng
            log.warning("QA Sniper chưa sẵn sàng — gửi báo cáo cơ bản...")
            report = QAReport(
                status      = BuildStatus.WARNING,
                notes       = "QA Sniper module chưa được tích hợp hoàn toàn. Báo cáo cơ bản.",
                triggered_by= f"overlord → {event['source']}"
            )
            await fire_overlord_report(report, self.webhook_config)

        except Exception as e:
            # Lỗi nghiêm trọng — vẫn gửi báo cáo FAILED
            log.error("❌ QA Sniper thất bại: %s", e)
            report = QAReport(
                status      = BuildStatus.FAILED,
                notes       = f"QA Sniper crash: {str(e)[:500]}",
                triggered_by= f"overlord → {event['source']}"
            )
            await fire_overlord_report(report, self.webhook_config)

    async def _send_manual_report(self, data: Dict):
        """Gửi báo cáo thủ công (được điều phối từ API endpoint)."""
        try:
            report = QAReport(
                status      = BuildStatus(data.get("status", "warning")),
                notes       = data.get("notes", "Báo cáo thủ công từ Overlord"),
                triggered_by= "overlord_manual"
            )
            await fire_overlord_report(report, self.webhook_config)
        except Exception as e:
            log.error("Manual report thất bại: %s", e)

    # ──────────────────────────────────────────────────────────────────
    # HEARTBEAT — Tự động audit định kỳ
    # ──────────────────────────────────────────────────────────────────
    async def _heartbeat_loop(self):
        """
        Tự động trigger audit mỗi X phút.
        Interval được đọc từ env var OVERLORD_HEARTBEAT_MINUTES (default: 30).
        """
        interval_min = int(os.getenv("OVERLORD_HEARTBEAT_MINUTES", "30"))
        interval_sec = interval_min * 60
        log.info("💓 Heartbeat loop: Tự động audit mỗi %d phút", interval_min)

        await asyncio.sleep(30)   # Chờ hệ thống ổn định trước

        while self.is_running:
            await self.trigger_audit(source=f"heartbeat_{interval_min}min")
            await asyncio.sleep(interval_sec)


# ──────────────────────────────────────────────────────────────────────
# FASTAPI ENDPOINT — Tích hợp vào core_api
# ──────────────────────────────────────────────────────────────────────
"""
Thêm đoạn này vào file main.py của core-backend FastAPI:

from fastapi import FastAPI, BackgroundTasks
from overlord_agent import OverlordAgent

app = FastAPI()
overlord = OverlordAgent()

@app.on_event("startup")
async def start_overlord():
    asyncio.create_task(overlord.start())

@app.post("/api/overlord/audit")
async def trigger_audit(background_tasks: BackgroundTasks):
    background_tasks.add_task(overlord.trigger_audit, source="api_call")
    return {"message": "Audit đã được kích hoạt", "status": "queued"}

@app.post("/api/overlord/build-complete")
async def notify_build_complete(data: dict, background_tasks: BackgroundTasks):
    background_tasks.add_task(overlord.trigger_build_complete, data)
    return {"message": "BUILD_COMPLETE đã được nhận", "build_data": data}
"""


# ──────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    config = WebhookConfig(
        discord_webhook_url = os.getenv("DISCORD_WEBHOOK_URL"),
        telegram_bot_token  = os.getenv("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id    = os.getenv("TELEGRAM_CHAT_ID"),
        slack_webhook_url   = os.getenv("SLACK_WEBHOOK_URL"),
        max_retries         = 3,
        retry_delay_sec     = 2.0,
    )

    agent = OverlordAgent(webhook_config=config)

    # Trigger audit ngay khi khởi động (chạy từ make ignite)
    asyncio.get_event_loop().run_until_complete(agent.trigger_audit("ignition_startup"))
    asyncio.get_event_loop().run_until_complete(agent.start())
