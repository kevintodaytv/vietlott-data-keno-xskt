import asyncio
import os
import sys
import json
import re
from playwright.async_api import async_playwright

# Xử lý import đường dẫn tương đối (vào thư mục chứa vault_db.py)
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from vault_db import SessionLocal, VietlottRealData

class VietlottHarvester:
    def __init__(self):
        # BẺ MŨI NGẮM SANG TỌA ĐỘ MỚI (Tránh Cloudflare)
        self.target_url = "https://www.minhngoc.net.vn/ket-qua-xo-so/dien-toan-vietlott/mega-6x45.html"

    async def execute_strike(self):
        print("🛸 [VIETLOTT AGENT]: Kích hoạt Giao thức Đột kích Đường vòng (Optical Regex)...")
        
        async with async_playwright() as p:
            # Bật chế độ tàng hình với User-Agent chuẩn của Google Chrome
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            try:
                # Ép thời gian chờ để tải toàn bộ DOM
                await page.goto(self.target_url, wait_until="networkidle", timeout=30000)
                
                # Trích xuất toàn bộ text được render trên màn hình để xuyên qua các lớp obfuscation
                page_text = await page.evaluate('document.body.innerText')
                with open('debug_regex.txt', 'w', encoding='utf-8') as f: f.write(page_text)
                print(f"DEBUG FIRST 200 CHARS OF KET QUA: {page_text[page_text.find('KẾT QUẢ'):page_text.find('KẾT QUẢ')+300]}")
                
                # Dùng Regex để quét dữ liệu văn bản thuần túy
                match = re.search(r'KẾT QUẢ XỔ SỐ MEGA 6/45 - NGÀY:? (\d{2}/\d{2}/\d{4})[\s\S]*?Kỳ vé: #\s*(\d+)[\s\S]*?((?:\d{2}\s+){5}\d{2})', page_text)
                
                if match:
                    date = match.group(1)
                    raw_id = match.group(2)
                    draw_id = f"KỲ_{date}".replace("/", "") # VD: KỲ_05042026
                    winning_numbers = match.group(3).split()

                    print(f"✅ [VIETLOTT AGENT]: Trích xuất thành công! {draw_id} (Kỳ #{raw_id}) | Bộ số: {winning_numbers}")
                    
                    session = SessionLocal()
                    try:
                        exists = session.query(VietlottRealData).filter_by(draw_id=draw_id).first()
                        if not exists:
                            new_record = VietlottRealData(
                                lottery_type="MEGA_645",
                                draw_id=draw_id,
                                winning_numbers=winning_numbers
                            )
                            session.add(new_record)
                            session.commit()
                            print(f"💾 [VAULT]: Đã khóa chặt {draw_id} vào Két Sắt Vĩnh Cửu!")
                        else:
                            print(f"⚠️ [VAULT]: Dữ liệu {draw_id} đã tồn tại. Không ghi đè.")
                    finally:
                        session.close()
                else:
                    print("❌ [VIETLOTT AGENT]: Radar nhiễu sóng! Không gom đủ 6 số.")
                    print(">> Dùng fallback CSS .result-number...")
                    try:
                        result_nums = await page.locator(".result-number").first.text_content()
                        clean = [n.strip() for n in result_nums.split() if n.strip().isdigit()]
                        if len(clean) >= 6:
                            draw_id = "LATEST_FALLBACK"
                            print(f"✅ [VIETLOTT AGENT] FALLBACK extracted: {clean[:6]}")
                            session = SessionLocal()
                            exists = session.query(VietlottRealData).filter_by(draw_id=draw_id).first()
                            if not exists:
                                session.add(VietlottRealData(lottery_type="MEGA_645", draw_id=draw_id, winning_numbers=clean[:6]))
                                session.commit()
                                print(f"💾 [VAULT]: Đã khóa chặt FALLBACK vào Két Sắt!")
                            session.close()
                    except Exception as e2:
                        print(f"❌ FALLBACK cũng thất bại: {e2}")
                
            except Exception as e:
                print(f"❌ [VIETLOTT AGENT]: Lỗi quang học/Kết nối: {e}")
            finally:
                await browser.close()

if __name__ == "__main__":
    agent = VietlottHarvester()
    asyncio.run(agent.execute_strike())
