# core-backend/database/supabase_client.py
# ══════════════════════════════════════════════════════════
#   SUPABASE CLIENT — Sniper-X Hub Database Layer
#   Real-time PostgreSQL + Auth + Storage via Supabase
# ══════════════════════════════════════════════════════════
import os
from supabase import create_client, Client
from typing import Optional
import logging

logger = logging.getLogger("supabase_client")

# ── Singleton pattern ──────────────────────────────────────
_supabase_client: Optional[Client] = None


def get_supabase() -> Optional[Client]:
    """
    Trả về Supabase client singleton.
    Trả về None nếu chưa config SUPABASE_URL / SUPABASE_KEY.
    """
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    url  = os.getenv("SUPABASE_URL")
    key  = os.getenv("SUPABASE_ANON_KEY")

    if not url or not key:
        logger.warning(
            "[SUPABASE] SUPABASE_URL hoặc SUPABASE_ANON_KEY chưa được set. "
            "Hệ thống sẽ chạy không có Supabase."
        )
        return None

    try:
        _supabase_client = create_client(url, key)
        logger.info("[SUPABASE] ✅ Kết nối thành công!")
        return _supabase_client
    except Exception as e:
        logger.error(f"[SUPABASE] ❌ Kết nối thất bại: {e}")
        return None


# ── Helper: Lưu kết quả xổ số ─────────────────────────────
async def save_lottery_result(
    numbers: list[int],
    provider: str,
    draw_type: str = "mega6x45",
    confidence: float = 0.0,
    ai_prediction: list[int] = None,
) -> dict | None:
    """Lưu một kết quả xổ số vào bảng lottery_results."""
    sb = get_supabase()
    if not sb:
        return None

    try:
        data = {
            "numbers":       numbers,
            "provider":      provider,
            "draw_type":     draw_type,
            "confidence":    confidence,
            "ai_prediction": ai_prediction or [],
        }
        res = sb.table("lottery_results").insert(data).execute()
        logger.info(f"[SUPABASE] Saved lottery result: {numbers}")
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"[SUPABASE] save_lottery_result error: {e}")
        return None


# ── Helper: Lấy lịch sử dự đoán ───────────────────────────
async def get_recent_results(limit: int = 20, draw_type: str = "mega6x45") -> list:
    """Lấy các kết quả gần nhất từ Supabase."""
    sb = get_supabase()
    if not sb:
        return []

    try:
        res = (
            sb.table("lottery_results")
            .select("*")
            .eq("draw_type", draw_type)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.error(f"[SUPABASE] get_recent_results error: {e}")
        return []


# ── Helper: Lưu AI training metrics ───────────────────────
async def save_training_metrics(
    model_name: str,
    accuracy: float,
    loss: float,
    epoch: int,
    metadata: dict = None,
) -> dict | None:
    """Lưu metrics sau mỗi lần train model AI."""
    sb = get_supabase()
    if not sb:
        return None

    try:
        data = {
            "model_name": model_name,
            "accuracy":   accuracy,
            "loss":       loss,
            "epoch":      epoch,
            "metadata":   metadata or {},
        }
        res = sb.table("ai_training_metrics").insert(data).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"[SUPABASE] save_training_metrics error: {e}")
        return None


# ── Helper: Realtime subscription (websocket) ──────────────
def subscribe_to_results(callback):
    """
    Subscribe realtime vào bảng lottery_results.
    callback(payload) sẽ được gọi mỗi khi có row mới.
    
    Dùng trong background worker, KHÔNG dùng trong async route.
    """
    sb = get_supabase()
    if not sb:
        logger.warning("[SUPABASE] Realtime subscription bị bỏ qua — client chưa init.")
        return None

    channel = (
        sb.channel("lottery-stream")
        .on(
            "postgres_changes",
            event="INSERT",
            schema="public",
            table="lottery_results",
            callback=callback,
        )
        .subscribe()
    )
    logger.info("[SUPABASE] 📡 Realtime channel 'lottery-stream' đã subscribe.")
    return channel
