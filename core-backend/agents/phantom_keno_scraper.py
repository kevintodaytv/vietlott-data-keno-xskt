"""
╔══════════════════════════════════════════════════════════════╗
║  PHANTOM KENO SCRAPER — Sniper-X Hub v11.0 CONFIRMED API    ║
║  Source: xoso.com.vn/Keno/GetKetQuaMore (VERIFIED HTTP)     ║
║  API: /Keno/AjaxTrucTiep → live_ky, next_ky, live_date     ║
╚══════════════════════════════════════════════════════════════╝
"""

import asyncio
import sys
import os
import re
from datetime import datetime, timezone

# Windows asyncio fix
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Fix encoding
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from vault_db import SessionLocal, KenoRealData

import httpx

# ─────────────────────────────────────────────────────────────────────────────
# VERIFIED APIs từ xoso.com.vn (KHÔNG cần browser, HTTP thuần túy)
# ─────────────────────────────────────────────────────────────────────────────
XOSO_BASE = "https://xoso.com.vn"
XOSO_LIVE_API  = f"{XOSO_BASE}/Keno/AjaxTrucTiep"      # JSON: live_ky, live_date, next_ky
XOSO_KQ_API    = f"{XOSO_BASE}/Keno/GetKetQuaMore"      # HTML: kết quả các kỳ gần nhất
XOSO_KENO_PAGE = f"{XOSO_BASE}/ket-qua-xs-keno.html"   # HTML: trang chính

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/json,*/*;q=0.9",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
    "Referer": f"{XOSO_BASE}/ket-qua-xs-keno.html",
}


async def get_live_status(client: httpx.AsyncClient) -> dict | None:
    """
    Gọi /Keno/AjaxTrucTiep để lấy kỳ hiện tại.
    Returns: {"live_ky": "276728", "live_date": "2026-04-08 10:16:00", ...}
    """
    try:
        import time
        resp = await client.get(
            XOSO_LIVE_API,
            params={"t": int(time.time() * 1000) % 100000},
            headers=HEADERS,
            timeout=15,
        )
        if resp.status_code == 200:
            import json
            raw = resp.text.strip().strip('"')
            # API trả về JSON string escaped: "\u0022live_ky\u0022:..."
            raw = raw.replace('\\u0022', '"').replace('\\"', '"')
            data = json.loads(raw)
            print(f"[LIVE API] live_ky={data.get('live_ky')} | live_date={data.get('live_date')}")
            print(f"[LIVE API] next_ky={data.get('next_ky')} | next_date={data.get('next_date')}")
            return data
    except Exception as e:
        print(f"[LIVE API] ✗ {e}")
    return None


async def get_keno_results_html(client: httpx.AsyncClient) -> dict | None:
    """
    Gọi /Keno/GetKetQuaMore để lấy HTML kết quả.
    Parse ra: draw_id, draw_time, winning_numbers
    """
    try:
        resp = await client.get(XOSO_KQ_API, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            print(f"[KQ API] HTTP {resp.status_code}")
            return None
        
        html = resp.text
        
        # Parse kỳ: <a class=span-row href=/ket-qua-keno-ky-276728.html ...>Kỳ: <strong>#276728</strong></a>
        ky_match = re.search(r'Kỳ:\s*<strong>#(\d+)</strong>', html)
        if not ky_match:
            # Fallback: tìm trong URL
            ky_match = re.search(r'keno-ky-(\d+)\.html', html)
        
        if not ky_match:
            print(f"[KQ API] ✗ Không tìm được số kỳ!")
            print(f"[KQ API] HTML preview: {html[:300]}")
            return None
        
        draw_id = ky_match.group(1)
        
        # Parse thời gian: <span class=span-row> 08/04/2026 10:16</span>
        time_match = re.search(r'<span[^>]*>\s*(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})\s*</span>', html)
        if time_match:
            dt_str = time_match.group(1).strip()
            try:
                draw_time = datetime.strptime(dt_str, "%d/%m/%Y %H:%M")
                draw_time = draw_time.replace(tzinfo=timezone.utc)
            except:
                draw_time = datetime.now(timezone.utc)
        else:
            draw_time = datetime.now(timezone.utc)
        
        # Parse numbers: <span class=btn-number-kq>01</span>
        numbers_raw = re.findall(r'class=btn-number-kq[^>]*>(\d{1,2})<', html)
        if not numbers_raw:
            numbers_raw = re.findall(r'class=["\']btn-number-kq["\'][^>]*>(\d{1,2})<', html)
        
        numbers = [int(n) for n in numbers_raw if n.strip().isdigit() and 1 <= int(n) <= 80]
        
        if len(numbers) >= 10:
            # Lấy chỉ 20 số của kỳ đầu tiên (mỗi kỳ 20 số)
            winning = numbers[:20]
            print(f"[KQ API] ✓ Kỳ {draw_id} | {draw_time.strftime('%d/%m/%Y %H:%M')} | {len(winning)} số: {winning}")
            return {
                "draw_id": draw_id,
                "draw_time": draw_time.isoformat(),
                "winning_numbers": winning,
                "source": "xoso_kq_api"
            }
        else:
            print(f"[KQ API] ✗ Chỉ lấy được {len(numbers)} số (cần >= 10)")
            print(f"[KQ API] Raw numbers found: {numbers_raw[:10]}")
            return None
            
    except Exception as e:
        print(f"[KQ API] ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


async def get_keno_from_main_page(client: httpx.AsyncClient) -> dict | None:
    """
    Fallback: Parse trang chính xoso.com.vn/ket-qua-xs-keno.html
    """
    try:
        resp = await client.get(XOSO_KENO_PAGE, headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            return None
        
        html = resp.text
        
        # Tìm kỳ mới nhất từ trang chính
        # Pattern: href=/ket-qua-keno-ky-276728.html
        ky_matches = re.findall(r'keno-ky-(\d+)\.html', html)
        if not ky_matches:
            return None
        
        draw_id = ky_matches[0]  # Kỳ đầu tiên = mới nhất
        
        # Parse numbers theo class btn-number-kq trong context của kỳ đầu tiên
        # Tìm vị trí kỳ đầu tiên trong HTML
        first_ky_pos = html.find(f'keno-ky-{draw_id}')
        if first_ky_pos < 0:
            return None
        
        # Lấy đoạn HTML của kỳ đầu tiên (~500 chars)
        section = html[first_ky_pos:first_ky_pos + 800]
        
        numbers_raw = re.findall(r'btn-number-kq[^>]*>(\d{1,2})<', section)
        if not numbers_raw:
            numbers_raw = re.findall(r'>(\d{2})<', section)
        
        numbers = [int(n) for n in numbers_raw if n.strip().isdigit() and 1 <= int(n) <= 80]
        
        # Thời gian
        time_match = re.search(r'(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})', section)
        draw_time = datetime.now(timezone.utc)
        if time_match:
            try:
                draw_time = datetime.strptime(time_match.group(1), "%d/%m/%Y %H:%M").replace(tzinfo=timezone.utc)
            except:
                pass
        
        if len(numbers) >= 10:
            print(f"[MAIN PAGE] ✓ Kỳ {draw_id}: {numbers[:20]}")
            return {
                "draw_id": draw_id,
                "draw_time": draw_time.isoformat(),
                "winning_numbers": numbers[:20],
                "source": "xoso_main_page"
            }
    except Exception as e:
        print(f"[MAIN PAGE] ✗ {e}")
    return None


async def scrape_keno_once() -> dict | None:
    """Tổng hợp: Thử lần lượt các nguồn đã verified."""
    print(f"\n[PHANTOM] 🕷  Đột kích kho số {datetime.now().strftime('%H:%M:%S')}...")
    
    async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
        
        # 1. Lấy live status để biết kỳ hiện tại
        live = await get_live_status(client)
        
        # 2. Scrape kết quả từ /Keno/GetKetQuaMore
        result = await get_keno_results_html(client)
        if result:
            return result
        
        # 3. Fallback: trang chính
        print("[PHANTOM] GetKetQuaMore thất bại, thử trang chính...")
        result = await get_keno_from_main_page(client)
        if result:
            return result
    
    print("[PHANTOM] ✗ Tất cả nguồn thất bại.")
    return None


async def push_to_vault(data: dict) -> bool:
    """Đẩy dữ liệu vào PostgreSQL Vault."""
    session = SessionLocal()
    try:
        exists = session.query(KenoRealData).filter_by(draw_id=str(data['draw_id'])).first()
        if not exists:
            new_record = KenoRealData(
                draw_id=str(data['draw_id']),
                draw_time=datetime.fromisoformat(data['draw_time']) if 'draw_time' in data else datetime.now(timezone.utc),
                winning_numbers=data['winning_numbers']
            )
            session.add(new_record)
            session.commit()
            print(f"[VAULT] ✓ Đã khóa kỳ {data['draw_id']} vào Két Sắt! ({len(data['winning_numbers'])} số: {data['winning_numbers']})")
            
            # Gửi tín hiệu refresh cho Backend
            try:
                print(f"[SCRAPER] Triggering realtime update via API...")
                import requests
                requests.post("http://localhost:8888/api/trigger-refresh", timeout=2)
                print("[⚡] TÍN HIỆU ĐÃ GỬI TỚI THE CORE (8888)")
            except Exception:
                pass
        else:
            print(f"[VAULT] Kỳ {data['draw_id']} đã tồn tại, bỏ qua.")
            
        return True
    except Exception as e:
        session.rollback()
        print(f"[VAULT] ✗ Lỗi lưu DB: {e}")
        return False
    finally:
        session.close()


async def overclock_loop():
    """Vòng lặp chính: scrape mỗi 3 phút (Keno ra 10'/lần, poll nhanh để không miss)."""
    print("╔══════════════════════════════════════════════════════════╗")
    print("║   PHANTOM KENO SCRAPER v11 — XOSO.COM.VN ENGINE        ║")
    print("║   Source: /Keno/GetKetQuaMore + /Keno/AjaxTrucTiep     ║")
    print("║   Chu kỳ: 3 phút | Target: Kỳ mới nhất mỗi 10 phút    ║")
    print("╚══════════════════════════════════════════════════════════╝")

    cycle = 0
    while True:
        cycle += 1
        print(f"\n[PHANTOM] ══ CHU KỲ #{cycle} | {datetime.now().strftime('%H:%M:%S')} ══")

        data = await scrape_keno_once()
        if data:
            await push_to_vault(data)
        else:
            print("[PHANTOM] Không có dữ liệu. Chờ chu kỳ tiếp theo...")

        print(f"[PHANTOM] ⏳ Nghỉ 3 phút đến chu kỳ #{cycle + 1}...")
        await asyncio.sleep(180)  # 3 phút


async def test_once():
    """Test scrape 1 lần không lưu DB."""
    print("=== TEST MODE — 1 lần scrape ===")
    result = await scrape_keno_once()
    if result:
        print(f"\n✓ SUCCESS: {result}")
    else:
        print("\n✗ FAILED: Không lấy được dữ liệu")
    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        asyncio.run(test_once())
    else:
        asyncio.run(overclock_loop())
