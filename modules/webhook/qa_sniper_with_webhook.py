"""
╔══════════════════════════════════════════════════════════════════════╗
║   QA SNIPER AGENT — Enhanced with Overlord Webhook Integration       ║
║   Tự động chụp ảnh Dashboard, kiểm tra health, bắn báo cáo         ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import asyncio
import time
import json
import httpx
from pathlib import Path
from datetime import datetime, timezone
from playwright.async_api import async_playwright, Page, Browser

from overlord_webhook import (
    OverlordWebhook, QAReport, WebhookConfig, BuildStatus,
    fire_overlord_report
)

# ─── Cấu hình ──────────────────────────────────────────────────────────
AUDIT_TARGETS = [
    {"name": "nexus_ui",    "url": "http://localhost:3000",            "expect_status": 200},
    {"name": "core_api",    "url": "http://localhost:8000/api/health", "expect_status": 200},
    {"name": "vault_check", "url": "http://localhost:8000/api/vault",  "expect_status": 200},
]

SCREENSHOT_DIR = Path(os.getenv("QA_SCREENSHOT_DIR", "/tmp/qa_screenshots"))
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

PRIMARY_UI_URL   = os.getenv("AUDIT_UI_URL", "http://localhost:3000")
BUILD_START_TIME = float(os.getenv("BUILD_START_EPOCH", str(time.time())))


# ──────────────────────────────────────────────────────────────────────
# HELPER — Kiểm tra health endpoint
# ──────────────────────────────────────────────────────────────────────
async def check_service_health(client: httpx.AsyncClient, name: str, url: str, expected: int) -> dict:
    t0 = time.monotonic()
    try:
        resp = await client.get(url, timeout=10.0)
        ms   = (time.monotonic() - t0) * 1000
        ok   = resp.status_code == expected
        return {"name": name, "healthy": ok, "status_code": resp.status_code, "ms": ms}
    except Exception as e:
        return {"name": name, "healthy": False, "error": str(e), "ms": 0}


# ──────────────────────────────────────────────────────────────────────
# PLAYWRIGHT — Chụp ảnh giao diện và kiểm tra UI
# ──────────────────────────────────────────────────────────────────────
async def capture_ui_screenshots(url: str) -> list[str]:
    """Dùng Playwright chụp toàn trang và từng section quan trọng."""
    screenshots = []
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    async with async_playwright() as pw:
        browser: Browser = await pw.chromium.launch(headless=True)
        ctx  = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page: Page = await ctx.new_page()

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000)   # Chờ animation 3D khởi động

            # ── Chụp toàn trang ─────────────────────────────────────
            full_path = str(SCREENSHOT_DIR / f"full_dashboard_{ts}.png")
            await page.screenshot(path=full_path, full_page=True)
            screenshots.append(full_path)

            # ── Chụp Hero Section (Lồng cầu 3D) ────────────────────
            hero_el = await page.query_selector("#hero-section, .hero, canvas")
            if hero_el:
                hero_path = str(SCREENSHOT_DIR / f"hero_3d_{ts}.png")
                await hero_el.screenshot(path=hero_path)
                screenshots.append(hero_path)

            # ── Chụp Data Panel (Amber Glow Dashboard) ──────────────
            panel_el = await page.query_selector("#data-panel, .glass-card, .matrix-grid")
            if panel_el:
                panel_path = str(SCREENSHOT_DIR / f"amber_glow_panel_{ts}.png")
                await panel_el.screenshot(path=panel_path)
                screenshots.append(panel_path)

            # ── Kiểm tra Console Errors ──────────────────────────────
            errors = []
            page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
            await page.wait_for_timeout(500)

            if errors:
                print(f"⚠️  QA Sniper phát hiện {len(errors)} console error(s): {errors[:3]}")

        except Exception as e:
            print(f"❌ QA Sniper capture thất bại: {e}")
            # Chụp ảnh lỗi nếu có thể
            try:
                err_path = str(SCREENSHOT_DIR / f"error_state_{ts}.png")
                await page.screenshot(path=err_path)
                screenshots.append(err_path)
            except:
                pass

        finally:
            await browser.close()

    return screenshots


# ──────────────────────────────────────────────────────────────────────
# MAIN — Luồng thực thi chính của QA Sniper
# ──────────────────────────────────────────────────────────────────────
async def run_qa_sniper() -> QAReport:
    print("\n👁️  QA SNIPER — Khóa mục tiêu...\n" + "─"*50)

    start = time.monotonic()

    # 1. Kiểm tra tất cả services song song
    async with httpx.AsyncClient(follow_redirects=True) as client:
        health_tasks = [
            check_service_health(client, t["name"], t["url"], t["expect_status"])
            for t in AUDIT_TARGETS
        ]
        health_results = await asyncio.gather(*health_tasks)

    healthy_services = [r["name"] for r in health_results if r["healthy"]]
    failed_services  = [r["name"] for r in health_results if not r["healthy"]]
    avg_response_ms  = sum(r["ms"] for r in health_results) / max(len(health_results), 1)

    for r in health_results:
        icon = "✅" if r["healthy"] else "❌"
        print(f"  {icon}  {r['name']:<20} | {r.get('status_code', 'ERR')} | {r['ms']:.0f}ms")

    # 2. Chụp ảnh UI (chạy song song với health check đã xong)
    print("\n📸 QA Sniper đang chụp ảnh giao diện...")
    screenshot_paths = await capture_ui_screenshots(PRIMARY_UI_URL)
    print(f"  📷 Đã chụp {len(screenshot_paths)} ảnh → {SCREENSHOT_DIR}")

    # 3. Xác định trạng thái build tổng thể
    if not failed_services:
        status = BuildStatus.SUCCESS
        notes  = f"Tất cả {len(healthy_services)} services hoạt động tốt. Giao diện render thành công."
    elif len(failed_services) < len(AUDIT_TARGETS) / 2:
        status = BuildStatus.DEGRADED
        notes  = f"Cảnh báo: {len(failed_services)} service(s) lỗi: {', '.join(failed_services)}"
    else:
        status = BuildStatus.FAILED
        notes  = f"CRITICAL: Đa số services không phản hồi. Failed: {', '.join(failed_services)}"

    build_duration = time.monotonic() - start + (time.time() - BUILD_START_TIME)

    # 4. Đóng gói QAReport
    report = QAReport(
        status            = status,
        services_checked  = [t["name"] for t in AUDIT_TARGETS],
        services_healthy  = healthy_services,
        services_failed   = failed_services,
        screenshot_paths  = screenshot_paths,
        audit_url         = PRIMARY_UI_URL,
        response_time_ms  = avg_response_ms,
        build_duration_sec= build_duration,
        ai_confidence_score= (len(healthy_services) / max(len(AUDIT_TARGETS), 1)) * 100,
        notes             = notes,
        triggered_by      = "qa_sniper_agent → overlord"
    )

    print(f"\n📋 Tổng kết: {status.value.upper()} | "
          f"Healthy: {len(healthy_services)} | Failed: {len(failed_services)}")

    # 5. Bắn báo cáo qua Overlord Webhook
    print("\n🚀 Bắn báo cáo tới Overlord Webhook...")
    webhook_results = await fire_overlord_report(report)
    print("📡 Kết quả phát tán:", json.dumps(webhook_results, indent=2, ensure_ascii=False))

    return report


if __name__ == "__main__":
    final_report = asyncio.run(run_qa_sniper())
    print(f"\n✅ QA Sniper hoàn tất. Build ID: #{final_report.build_id}")
