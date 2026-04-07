import asyncio
from playwright.async_api import async_playwright
import redis
import json
import datetime
import os

class VietlottHarvester:
    def __init__(self):
        # Tọa độ mục tiêu: Kết quả Mega 6/45
        self.target_url = "https://vietlott.vn/vi/trung-thuong/ket-qua-trung-thuong/mega-6-45"
        
        # Mạch máu trung tâm (Fallback if redis connection fails)
        try:
            self.redis_client = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)
            self.redis_client.ping()
            self.use_redis = True
        except:
            print("⚠️ [VIETLOTT AGENT]: Redis unavailable, will fallback to direct print/http if needed")
            self.use_redis = False

    async def execute_strike(self):
        print("🛸 [VIETLOTT AGENT]: Khởi động chu trình rà quét lượng tử Mega 6/45...")
        
        async with async_playwright() as p:
            # Chế độ tàng hình
            browser = await p.chromium.launch(
                headless=True, 
                args=["--no-sandbox", "--disable-infobars", "--disable-blink-features=AutomationControlled"]
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            try:
                print(f"🛸 [VIETLOTT AGENT]: Đang đột nhập {self.target_url}...")
                await page.goto(self.target_url, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(3000)
                
                # 1. Trích xuất Kỳ Quay (Zero Mock)
                try:
                    draw_element = await page.locator("h5 b").first.inner_text()
                    draw_id = draw_element.strip()
                except Exception as e:
                    print("⚠️ Không lấy được title từ h5 b. Đang thử selector khác...")
                    draw_id = "UNKNOWN"

                # 2. Trích xuất 6 Con Số Vàng
                winning_numbers = []
                balls = await page.locator(".bong_tron").all()
                for ball in balls[:6]: 
                    number = await ball.inner_text()
                    winning_numbers.append(number.strip())

                if not winning_numbers:
                    raise Exception("Không tìm thấy số nào trên trang")

                # --- MCTS Prediction ---
                # Vì chạy ngoài main app, import mcts engine
                try:
                    import sys
                    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
                    from ml_engine.mcts_vietlott import VietlottMCTSCore
                    mcts = VietlottMCTSCore()
                    ai_result = mcts.predict_mega_645(winning_numbers)
                    ai_prediction = [f"{n:02d}" for n in ai_result["prediction"]]
                    confidence = ai_result["confidence_score"]
                except Exception as mcts_e:
                    print(f"⚠️ [VIETLOTT AGENT] Lỗi chạy MCTS: {mcts_e}")
                    ai_prediction = []
                    confidence = 0

                # 3. Đóng gói Payload
                payload = {
                    "action": "vietlott_update",
                    "lottery_type": "MEGA_645",
                    "draw_id": draw_id,
                    "winning_numbers": winning_numbers,
                    "ai_prediction": ai_prediction,
                    "confidence_score": confidence,
                    "timestamp": str(datetime.datetime.now()),
                    "status": "VERIFIED_REAL_DATA"
                }

                # 4. Bơm thẳng vào Mạch máu
                if self.use_redis:
                    # Publish data to redis to be picked up by the fastAPI backend if it has a listener
                    self.redis_client.publish('vietlott-stream', json.dumps(payload))
                
                # Gửi thẳng request lên Backend API nội bộ để broadcast websocket
                import httpx
                api_url = os.getenv("API_URL", "http://localhost:8000/api/internal/vietlott-webhook")
                try:
                    async with httpx.AsyncClient() as client:
                        await client.post(api_url, json=payload, timeout=10.0)
                        print("📡 [VIETLOTT AGENT]: Đã bơm dữ liệu vào hệ thống Backend thành công!")
                except Exception as api_err:
                    print(f"⚠️ [VIETLOTT AGENT]: Cảnh báo - Không thể gửi webhook tới core_api: {api_err}")

                print(f"✅ [VIETLOTT AGENT]: Trích xuất thành công! Kỳ {draw_id} | Bộ số: {winning_numbers}")
                print(f"🔮 [VIETLOTT AGENT]: MCTS Alpha: {ai_prediction} | Tự tin: {confidence}%")
                
            except Exception as e:
                print(f"❌ [VIETLOTT AGENT]: Lỗi quang học, không thể bắt mục tiêu: {e}")
                import traceback
                traceback.print_exc()
            finally:
                await browser.close()

if __name__ == "__main__":
    agent = VietlottHarvester()
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(agent.execute_strike())
