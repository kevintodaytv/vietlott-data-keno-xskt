# core-backend/database/supabase_client.py
# ══════════════════════════════════════════════════════════
#   SUPABASE CLIENT — Sniper-X Hub Database Layer
#   OFFLINE-RESILIENT: Không crash khi thiếu module/config
# ══════════════════════════════════════════════════════════
import os
import logging
from typing import Optional

logger = logging.getLogger("supabase_client")

# ── Singleton pattern ──────────────────────────────────────
_supabase_client = None  # Không type-hint để tránh import lỗi
_supabase_available = False

def get_supabase():
    """
    Trả về Supabase client singleton.
    Trả về None nếu chưa config hoặc module lỗi.
    """
    global _supabase_client, _supabase_attempted
    
    if _supabase_client is not None:
        return _supabase_client
    
    if getattr(get_supabase, "attempted", False):
        return None
        
    get_supabase.attempted = True

    url  = os.getenv("SUPABASE_URL")
    key  = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY")

    if not url or not key:
        print(
            f"[SUPABASE-ERROR] SUPABASE_URL ({url}) hoặc SUPABASE_ANON_KEY ({key}) chưa được set. "
            "Hệ thống sẽ chạy không có Supabase."
        )
        _supabase_available = False
        return None

    try:
        from supabase import create_client
        _supabase_client = create_client(url, key)
        _supabase_available = True
        print("[SUPABASE] ✅ Kết nối thành công!")
        return _supabase_client
    except ImportError as e:
        print(f"[SUPABASE-ERROR] ❌ Module lỗi (websockets/realtime): {e}")
        _supabase_available = False
        return None
    except Exception as e:
        print(f"[SUPABASE-ERROR] ❌ Kết nối thất bại: {e}")
        _supabase_available = False
        return None


# ── Helper: Lưu kết quả xổ số ─────────────────────────────
async def save_lottery_result(
    numbers: list,
    provider: str,
    draw_type: str = "mega6x45",
    confidence: float = 0.0,
    ai_prediction: list = None,
) -> dict:
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
) -> dict:
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

    try:
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
    except Exception as e:
        logger.error(f"[SUPABASE] Realtime subscription error: {e}")
        return None


# ── Evolution Log Helpers ──────────────────────────────────────────
def save_evolution_log(
    phase: str,
    strategy_name: str,
    confidence_score: float,
    win_rate: float,
    lesson_learned: str,
    weights: dict,
    draws_analyzed: int,
) -> dict:
    """Lưu bài học vào bảng keno_evolution_log."""
    sb = get_supabase()
    if not sb:
        logger.warning("[SUPABASE] save_evolution_log: client offline")
        return None
    try:
        data = {
            "phase":            phase,
            "strategy_name":    strategy_name,
            "confidence_score": round(float(confidence_score), 2),
            "win_rate":         round(float(win_rate), 2),
            "lesson_learned":   lesson_learned,
            "weights":          weights,
            "draws_analyzed":   int(draws_analyzed),
        }
        res = sb.table("keno_evolution_log").insert(data).execute()
        logger.info(f"[SUPABASE] Evolution log saved — phase={phase} win_rate={win_rate:.1f}%")
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"[SUPABASE] save_evolution_log error: {e}")
        return None


def get_evolution_log(limit: int = 50) -> list:
    """Lấy các bài học gần nhất từ Supabase."""
    sb = get_supabase()
    if not sb:
        return []
    try:
        res = (
            sb.table("keno_evolution_log")
            .select("*")
            .order("timestamp", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.error(f"[SUPABASE] get_evolution_log error: {e}")
        return []


def get_morning_brief_today() -> dict:
    """Lấy Morning Brief được tạo gần nhất (phase=MORNING_BRIEF)."""
    sb = get_supabase()
    if not sb:
        return {}
    try:
        res = (
            sb.table("keno_evolution_log")
            .select("*")
            .eq("phase", "MORNING_BRIEF")
            .order("timestamp", desc=True)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else {}
    except Exception as e:
        logger.error(f"[SUPABASE] get_morning_brief_today error: {e}")
        return {}


def save_proactive_ping(ping: dict) -> dict:
    """Lưu proactive ping vào bảng orbis_proactive_log."""
    sb = get_supabase()
    if not sb:
        return None
    try:
        data = {
            "ping_type":  ping.get("type", "UNKNOWN"),
            "priority":   ping.get("priority", "NORMAL"),
            "message":    ping.get("message", ""),
            "trigger":    ping.get("trigger", ""),
            "payload":    ping.get("data", {}),
            "ping_id":    ping.get("ping_id", 0),
        }
        res = sb.table("orbis_proactive_log").insert(data).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"[SUPABASE] save_proactive_ping error: {e}")
        return None


def get_evolution_kpis() -> dict:
    """Tính các KPI tiến hóa từ bảng keno_evolution_log."""
    sb = get_supabase()
    if not sb:
        return {"evolution_count": 0, "lessons_stored": 0, "proactive_pings": 0}
    try:
        # Tổng bài học
        lessons_res = sb.table("keno_evolution_log").select("id", count="exact").execute()
        lessons_count = lessons_res.count or 0

        # Số lần tiến hóa (phase=DEPLOY hoặc EVOLVE)
        evolve_res = (
            sb.table("keno_evolution_log")
            .select("id", count="exact")
            .in_("phase", ["DEPLOY", "EVOLVE"])
            .execute()
        )
        evolution_count = evolve_res.count or 0

        # Tổng proactive pings
        try:
            pings_res = sb.table("orbis_proactive_log").select("id", count="exact").execute()
            pings_count = pings_res.count or 0
        except Exception:
            pings_count = 0

        return {
            "evolution_count":  evolution_count,
            "lessons_stored":   lessons_count,
            "proactive_pings":  pings_count,
        }
    except Exception as e:
        logger.error(f"[SUPABASE] get_evolution_kpis error: {e}")
        return {"evolution_count": 0, "lessons_stored": 0, "proactive_pings": 0}
