"""
╔══════════════════════════════════════════════════════════════╗
║  PHANTOM KENO SCRAPER — Sniper-X Hub v9.5 OVERCLOCK         ║
║  Mission: Scrape Keno 10min/lần → Push → Supabase Vault      ║
║  Target : minhngoc.net.vn/keno                               ║
╚══════════════════════════════════════════════════════════════╝
"""

import asyncio
import sys
import os
from datetime import datetime, timezone

# Windows asyncio fix
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Fix encoding
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

from playwright.async_api import async_playwright
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

KENO_URL = "https://www.minhngoc.net.vn/ket-qua-xo-so/vietlott/keno.html"

async def scrape_keno_once() -> dict | None:
    """Đột kích nguồn, lấy kết quả Keno mới nhất."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars"
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )

        # Stealth injection
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'languages', {get: () => ['vi-VN', 'vi', 'en']});
            window.chrome = {runtime: {}};
        """)

        page = await context.new_page()

        try:
            print(f"[PHANTOM] 🕷  Đột kích {KENO_URL}")
            await page.goto(KENO_URL, timeout=90000, wait_until="networkidle")
            
            # Chờ bảng số xuất hiện (Selector sạch)
            await page.wait_for_selector(".box_kq_vietlott", timeout=15000)
            
            # Lấy kỳ quay gần nhất
            draw_id_raw = await page.eval_on_selector(".ky_ve", "el => el.innerText")
            draw_id = int(''.join(filter(str.isdigit, draw_id_raw))) if draw_id_raw else int(datetime.now(timezone.utc).timestamp())
            
            # Lấy 20 con số vàng
            numbers_raw = await page.eval_on_selector_all(".so_lo", "elements => elements.map(el => el.innerText)")
            winning_numbers = [int(n) for n in numbers_raw if n.strip().isdigit()]
            
            if not winning_numbers or len(winning_numbers) < 10:
                print(f"[PHANTOM] ✗ Không đủ số ({len(winning_numbers)}). Hoãn tác chiến.")
                await browser.close()
                return None

            result = {
                "draw_id": draw_id,
                "draw_time": datetime.now(timezone.utc).isoformat(),
                "winning_numbers": winning_numbers[:20],
                "source": "minhngoc"
            }

            print(f"[PHANTOM] ✓ Kỳ {draw_id}: {winning_numbers}")
            await browser.close()
            return result

        except Exception as e:
            print(f"[PHANTOM] ✗ Lỗi scrape: {e}")
            try:
                await page.screenshot(path="keno_debug.png")
            except:
                pass
            await browser.close()
            return None


async def push_to_vault(data: dict) -> bool:
    """Đẩy dữ liệu vào Supabase Vault."""
    try:
        res = supabase.table("keno_results").upsert(
            data,
            on_conflict="draw_id"
        ).execute()
        print(f"[VAULT] ✓ Đã lưu kỳ {data['draw_id']} vào The Vault.")
        
        # Gửi tín hiệu đánh chặn cho Backend
        import requests
        try:
            requests.post("http://localhost:8888/api/trigger-refresh", timeout=5)
            print("[⚡] ĐÃ KÍCH HOẠT WEBSOCKET: DASHBOARD ĐANG CẬP NHẬT...")
        except Exception as e:
            print(f"[!] KHÔNG THỂ GỬI TÍN HIỆU: {e}")

        return True
    except Exception as e:
        print(f"[VAULT] ✗ Lỗi lưu DB: {e}")
        return False


async def overclock_loop():
    """Vòng lặp chính: scrape mỗi 10 phút."""
    print("╔══════════════════════════════════════════╗")
    print("║   PHANTOM KENO SCRAPER — OVERCLOCK MODE  ║")
    print("║   Chu kỳ: 10 phút | Target: 80 số        ║")
    print("╚══════════════════════════════════════════╝")
    print(f"[PHANTOM] Supabase: {SUPABASE_URL[:40]}...")

    cycle = 0
    while True:
        cycle += 1
        print(f"\n[PHANTOM] ══ CHU KỲ TÁC CHIẾN #{cycle} | {datetime.now().strftime('%H:%M:%S')} ══")

        data = await scrape_keno_once()
        if data:
            await push_to_vault(data)
        else:
            print("[PHANTOM] Không có dữ liệu. Chờ chu kỳ tiếp theo...")

        print(f"[PHANTOM] ⏳ Nghỉ 10 phút đến chu kỳ #{cycle + 1}...")
        await asyncio.sleep(600)  # 10 phút


if __name__ == "__main__":
    asyncio.run(overclock_loop())
