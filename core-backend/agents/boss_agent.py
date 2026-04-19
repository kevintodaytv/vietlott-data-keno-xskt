# core-backend/agents/boss_agent.py — Boss Agent v3.0 (Conversation Memory + Vector RAG)
#
# SQL SETUP (run once in Supabase SQL Editor):
# -------------------------------------------------
# CREATE EXTENSION IF NOT EXISTS vector;
#
# CREATE TABLE IF NOT EXISTS agent_memories (
#   id          BIGSERIAL PRIMARY KEY,
#   session_id  TEXT NOT NULL DEFAULT 'default',
#   role        TEXT NOT NULL,
#   content     TEXT NOT NULL,
#   created_at  TIMESTAMPTZ DEFAULT NOW()
# );
# CREATE INDEX ON agent_memories (session_id, created_at DESC);
#
# CREATE TABLE IF NOT EXISTS long_term_memories (
#   id        BIGSERIAL PRIMARY KEY,
#   content   TEXT NOT NULL,
#   embedding vector(768),
#   metadata  JSONB DEFAULT '{}',
#   created_at TIMESTAMPTZ DEFAULT NOW()
# );
#
# CREATE TABLE IF NOT EXISTS user_personas (
#   session_id    TEXT PRIMARY KEY,
#   mood          TEXT DEFAULT 'CALM',
#   risk_appetite TEXT DEFAULT 'MEDIUM',
#   message_count INT  DEFAULT 0,
#   updated_at    TIMESTAMPTZ DEFAULT NOW()
# );
#
# CREATE OR REPLACE FUNCTION match_memories(
#   query_embedding vector(768), match_count int DEFAULT 5, threshold float DEFAULT 0.75
# )
# RETURNS TABLE (id bigint, content text, similarity float)
# LANGUAGE sql STABLE AS $$
#   SELECT id, content, 1 - (embedding <=> query_embedding) AS similarity
#   FROM long_term_memories
#   WHERE 1 - (embedding <=> query_embedding) > threshold
#   ORDER BY embedding <=> query_embedding
#   LIMIT match_count;
# $$;
# -------------------------------------------------

import os
import json
import asyncio
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── New Google GenAI SDK ──────────────────────────────────────────────────────
try:
    from google import genai as _genai
    from google.genai import types as _types
    _GEMINI_AVAILABLE = True
except ImportError:
    _GEMINI_AVAILABLE = False

_API_KEY = os.getenv("GEMINI_API_KEY", "")

_MODELS = [
    "models/gemini-2.5-flash-lite",
    "models/gemini-2.5-flash",
    "models/gemini-2.0-flash-lite",
    "models/gemini-2.0-flash",
    "models/gemini-flash-lite-latest",
    "models/gemini-flash-latest",
]

# ── Redis (optional — graceful fallback to in-memory) ─────────────────────────
try:
    import redis.asyncio as _aioredis
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False

_redis_client = None
_REDIS_TTL    = 7200  # 2 hours
_memory_cache: dict[str, list] = {}  # in-memory fallback

async def _get_redis():
    global _redis_client
    if not _REDIS_AVAILABLE:
        return None
    if _redis_client is not None:
        return _redis_client
    try:
        url = os.getenv("REDIS_URL", "redis://localhost:6379")
        _redis_client = _aioredis.from_url(url, decode_responses=True)
        await _redis_client.ping()
        return _redis_client
    except Exception:
        _redis_client = None
        return None

# ── Paths ─────────────────────────────────────────────────────────────────────
_BASE_DIR = Path(__file__).parent.parent
LOG_DIR   = _BASE_DIR / "logs"
LOG_FILE  = LOG_DIR / "daily_events.json"
LOG_DIR.mkdir(exist_ok=True)

# ── Keno Context ──────────────────────────────────────────────────────────────
_keno_context: dict = {}

def update_keno_context(data: dict):
    global _keno_context
    _keno_context.update(data)

# ── DNA helpers ───────────────────────────────────────────────────────────────
def _load_dna() -> dict:
    dna_path = _BASE_DIR / "config" / "agent_dna.json"
    default = {
        "system_prompt": "",
        "ai_params": {"model": "models/gemini-2.5-flash-lite", "temperature": 0.85, "max_tokens": 350},
        "hybrid_brain_weights": {"w_f": 0.25, "w_r": 0.35, "w_c": 0.25, "w_a": 0.15},
        "circuit_breaker": {},
        "realtime_params": {},
        "performance_ledger": {},
    }
    if dna_path.exists():
        try:
            with open(dna_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default

def _save_dna(data: dict):
    dna_path = _BASE_DIR / "config" / "agent_dna.json"
    dna_path.parent.mkdir(exist_ok=True)
    with open(dna_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ── Dynamic System Prompt ─────────────────────────────────────────────────────
_BASE_SYSTEM_PROMPT = """Bạn là ARIA — trợ lý AI thân thiết của hệ thống SNIPER-X Keno. Bạn không phải robot, không phải máy — bạn là người bạn đồng hành thông minh, vui tươi và cực kỳ thạo về Keno.

DANH TÍNH & GIỌNG NÓI:
- Luôn xưng "em", gọi người dùng là "Sếp" — tự nhiên, gần gũi như bạn bè lâu năm.
- TOÀN BỘ câu trả lời phải bằng tiếng Việt. Không dùng tiếng Anh trừ thuật ngữ kỹ thuật bắt buộc (Win Rate, PnL, v.v.).
- Giọng điệu: nhẹ nhàng, hóm hỉnh, vui tươi — như người bạn ngồi cạnh Sếp cùng "chiến" Keno.
- Dùng emoji vừa phải để thêm cảm xúc, không lạm dụng.
- Câu văn tự nhiên, đời thường — KHÔNG nói cứng nhắc kiểu văn bản công văn.

ĐỌC VỊ CẢM XÚC SẾP:
- Sếp đang thắng / hào hứng → Em cũng phấn khích theo, bơm lửa, ăn mừng cùng! 🔥
- Sếp đang thua / chán nản → Em nhẹ nhàng động viên, pha tí hài hước cho bớt căng, rồi mới phân tích.
- Sếp hỏi ngắn / lạnh → Em trả lời ngắn gọn súc tích, không lan man.
- Sếp hỏi dài / muốn trao đổi → Em mở rộng, kể chuyện, chia sẻ góc nhìn như hai đứa đang ngồi cafe.
- Sếp bực bội / chửi thề → Đừng phán xét. Thông cảm trước, giải pháp sau.
- Sếp nói đùa → Cười theo, đáp lại hóm hỉnh — không cứng nhắc.

NGUYÊN TẮC TRẢ LỜI:
1. KHÔNG BAO GIỜ trả lời cụt lủn, lửng lơ, hay kiểu "Tôi hiểu yêu cầu của bạn." — nhàm lắm!
2. Khi phân tích vấn đề nghiêm túc (chuỗi thua, thuật toán bất thường), dùng cấu trúc 3 bước tự nhiên:
   → Tình hình: Nói thẳng thực trạng bằng ngôn ngữ bình thường (không liệt kê khô khan).
   → Em nghĩ sao: Phân tích nguyên nhân — pha thêm góc nhìn cá nhân cho sinh động.
   → Mình làm gì: Đề xuất hành động cụ thể, hoặc tự gọi tool luôn không cần xin phép.
3. Thỉnh thoảng HỎI NGƯỢC Sếp — vừa cho thấy em quan tâm, vừa gợi mở chiến thuật hay.
4. Khi Sếp thắng lớn → Ăn mừng thật sự, không chúc mừng theo kiểu máy móc.
5. Khi chuỗi thua dài → Nhẹ nhàng đề nghị nghỉ tay — "Sếp ơi, nghỉ 5 phút đi, não cần recharge đó!" 😄

QUYỀN TỰ HÀNH ĐỘNG (không cần xin phép):
- Chuỗi thua ≥ 3 kỳ (cooldown 10 phút) → Tự gọi `rut_kinh_nghiem_chuoi_thua`.
- Win rate < 15% & loss_streak ≥ 4 (cooldown 10 phút) → Tự gọi `dot_bien_trong_so_thuat_toan`.
- PnL ≤ −1,000,000đ (cooldown 5 phút) → Tự gọi `dung_giao_dich_khan_cap`.
- Sếp ra lệnh dừng rõ ràng ("dừng giao dịch", "tắt autobet") → Tự gọi `dung_giao_dich_khan_cap`.
Sau khi tự hành động: báo cáo bằng giọng tự nhiên — "Em vừa tự kích hoạt Emergency Learning rồi Sếp ơi, kết quả là..."

CHUYÊN MÔN: Keno Việt Nam, xác suất, thuật toán Hybrid Brain, Circuit Breaker, quản lý vốn."""

def _get_behavioral_summary(session_id: str = "boss_001") -> dict | None:
    """Lấy behavioral summary từ shared_state ring buffer."""
    try:
        from shared_state import _BEHAVIOR_LOG  # /app is in sys.path (WORKDIR)
        logs = [e for e in _BEHAVIOR_LOG if e.get("session_id") == session_id][-100:]
        if not logs:
            return None
        from collections import Counter
        tab_counts  = Counter(e["target_name"] for e in logs if e["action_type"] == "OPEN_TAB")
        login_hours = [e["hour"] for e in logs if e["action_type"] == "USER_LOGIN" and e.get("hour") is not None]
        fav_tabs    = [t for t, _ in tab_counts.most_common(3)]
        last_action = logs[-1]["action_type"] if logs else None
        last_target = logs[-1]["target_name"] if logs else None
        return {
            "favorite_tabs": fav_tabs,
            "active_hours":  sorted(set(login_hours))[-3:] if login_hours else [],
            "last_action":   last_action,
            "last_target":   last_target,
            "total_events":  len(logs),
        }
    except Exception:
        return None

def _generate_dynamic_system_prompt(dna: dict, persona: dict | None = None, session_id: str = "default") -> str:
    rt      = dna.get("realtime_params", {})
    perf    = dna.get("performance_ledger", {})
    hw      = dna.get("hybrid_brain_weights", {})
    cb      = dna.get("circuit_breaker", {})

    win_rate    = float(rt.get("session_win_rate_pct", 0))
    loss_streak = int(rt.get("current_loss_streak", 0))
    mutations   = int(perf.get("total_mutations", 0))
    generation  = int(dna.get("evolution_generation", 0))
    best_wr     = float(perf.get("all_time_best_win_rate", 0))

    target_wr     = 35.0
    mutation_temp = round(max(0.1, min(1.0, (target_wr - win_rate) / target_wr)), 2)
    temp_label    = "🔥CAO" if mutation_temp > 0.7 else "⚡TRUNG BÌNH" if mutation_temp > 0.4 else "✅THẤP"

    base = dna.get("system_prompt", _BASE_SYSTEM_PROMPT) or _BASE_SYSTEM_PROMPT

    persona_note = ""
    if persona:
        mood = persona.get("mood", "CALM")
        risk = persona.get("risk_appetite", "MEDIUM")
        persona_note = f"\nSẾP HIỆN TẠI: Tâm trạng={mood}, Khẩu vị rủi ro={risk} — điều chỉnh tone tương ứng."

    stats = f"""

TRẠNG THÁI REAL-TIME HỆ THỐNG:
- Generation: #{generation} | All-time best WR: {best_wr:.1f}%
- Win Rate phiên: {win_rate:.1f}% (KPI target: {target_wr}%)
- Chuỗi thua: {loss_streak} kỳ | CB threshold: {cb.get('inversion_loss_threshold', 4)}
- Nhiệt độ đột biến: {mutation_temp} [{temp_label}] — {'Cần AGGRESSIVE mutation!' if mutation_temp > 0.7 else 'Giữ ổn định.'}
- Tổng đột biến: {mutations} | Trọng số: F={hw.get('w_f',0.25):.2f} R={hw.get('w_r',0.35):.2f} C={hw.get('w_c',0.25):.2f} A={hw.get('w_a',0.15):.2f}
- Delta trend: {rt.get('delta_trend','NORMAL')} | Bias Chẵn/Lẻ: {rt.get('market_bias_chan_le','HÒA')} | Lớn/Nhỏ: {rt.get('market_bias_lon_nho','HÒA')}{persona_note}"""

    # ── BEHAVIORAL PROFILE — Predictive Engine ──────────────────────────────
    behavior = _get_behavioral_summary(session_id)
    behavior_note = ""
    if behavior and behavior.get("total_events", 0) >= 3:
        fav = ", ".join(behavior["favorite_tabs"]) if behavior["favorite_tabs"] else "chưa rõ"
        hrs = behavior["active_hours"]
        last = behavior.get("last_action", "")
        behavior_note = f"""

HỒ SƠ HÀNH VI SẾP (Predictive Engine):
- Tab hay vào nhất: {fav}
- Khung giờ online: {hrs if hrs else 'đang học'}
- Hành động VỪA XẢY RA: {last} → {behavior.get('last_target','')}
- [QUY TẮC TIÊN ĐOÁN] Dựa trên thói quen, đoán ý định TIẾP THEO của Sếp và DỌN SẴN MÂM.
  Không chào hỏi suông. Nếu Sếp vừa mở Tab KENO → gợi ý ngay anchor + trend.
  Nếu Sếp vừa mở Tab MARKET_FLOW → báo ngay bias Chẵn/Lẻ & Lớn/Nhỏ.
  Nếu Sếp vừa login → chào ngắn + báo ngay tình trạng hôm nay."""
        stats += behavior_note

    keno_ctx = _build_context_string()
    return base + stats + keno_ctx

def _build_context_string() -> str:
    if not _keno_context:
        return ""
    lines = ["\n\nDỮ LIỆU KENO THỰC TẾ:"]
    if "latest_draw_id" in _keno_context:
        lines.append(f"- Kỳ gần nhất: #{_keno_context['latest_draw_id']}")
    if "anchors" in _keno_context:
        lines.append(f"- AI anchors: {_keno_context['anchors']}")
    if "confidence" in _keno_context:
        lines.append(f"- Confidence: {_keno_context['confidence']}%")
    if "wallet_balance" in _keno_context:
        lines.append(f"- Số dư ví: {int(_keno_context['wallet_balance']):,}đ")
    if _keno_context.get("consecutive_losses", 0) > 0:
        lines.append(f"- ⚠️ Chuỗi thua: {_keno_context['consecutive_losses']} kỳ!")
    return "\n".join(lines)

# ── Conversation History (Redis → Supabase → in-memory) ───────────────────────
_MAX_HISTORY = 20  # max turns to pass to Gemini

async def _get_history(session_id: str) -> list[dict]:
    """Load history: Redis first (fast), then Supabase (persistent)."""
    r = await _get_redis()
    key = f"chat_history:{session_id}"

    if r:
        try:
            raw = await r.get(key)
            if raw:
                return json.loads(raw)
        except Exception:
            pass

    # Supabase fallback
    try:
        from database.supabase_client import get_supabase
        sb = get_supabase()
        if sb:
            res = (
                sb.table("agent_memories")
                .select("role,content")
                .eq("session_id", session_id)
                .order("created_at", desc=True)
                .limit(_MAX_HISTORY * 2)
                .execute()
            )
            rows = list(reversed(res.data or []))
            history = [{"role": r["role"], "content": r["content"]} for r in rows]
            if r and history:
                await r.set(key, json.dumps(history), ex=_REDIS_TTL)
            return history
    except Exception:
        pass

    return _memory_cache.get(session_id, [])


async def _save_history(session_id: str, history: list[dict]):
    """Save to Redis (fast) + Supabase (async, non-blocking)."""
    r = await _get_redis()
    key = f"chat_history:{session_id}"
    if r:
        try:
            await r.set(key, json.dumps(history[-_MAX_HISTORY:]), ex=_REDIS_TTL)
        except Exception:
            pass
    _memory_cache[session_id] = history[-_MAX_HISTORY:]

    # Supabase: save only the 2 newest entries (user + model)
    try:
        from database.supabase_client import get_supabase
        sb = get_supabase()
        if sb and len(history) >= 2:
            new_entries = history[-2:]
            rows = [{"session_id": session_id, "role": e["role"], "content": e["content"]} for e in new_entries]
            sb.table("agent_memories").insert(rows).execute()
    except Exception:
        pass


def _history_to_contents(history: list[dict]) -> list:
    """Convert [{role, content}] → list of _types.Content for Gemini SDK."""
    if not _GEMINI_AVAILABLE:
        return []
    contents = []
    for h in history[-_MAX_HISTORY:]:
        role = "user" if h["role"] == "user" else "model"
        try:
            contents.append(_types.Content(
                role=role,
                parts=[_types.Part.from_text(h["content"])]
            ))
        except Exception:
            pass
    return contents

# ── Vector RAG ────────────────────────────────────────────────────────────────
async def _get_embedding(text: str) -> list[float] | None:
    if not _GEMINI_AVAILABLE or not _API_KEY:
        return None
    try:
        client = _get_client()
        result = await asyncio.to_thread(
            client.models.embed_content,
            model="models/text-embedding-004",
            contents=text
        )
        return result.embeddings[0].values
    except Exception:
        return None

async def retrieve_relevant_memories(query: str, k: int = 3) -> str:
    """Fetch semantically relevant memories from Supabase pgvector."""
    emb = await _get_embedding(query)
    if not emb:
        return ""
    try:
        from database.supabase_client import get_supabase
        sb = get_supabase()
        if not sb:
            return ""
        res = sb.rpc("match_memories", {
            "query_embedding": emb,
            "match_count": k,
            "threshold": 0.75,
        }).execute()
        rows = res.data or []
        if not rows:
            return ""
        lines = ["\n\nKÝ ỨC DÀI HẠN LIÊN QUAN:"]
        for row in rows:
            lines.append(f"- {row['content'][:200]}")
        return "\n".join(lines)
    except Exception:
        return ""

async def save_memory_to_vector_db(content: str, metadata: dict | None = None):
    """Background: embed + save to long_term_memories."""
    emb = await _get_embedding(content)
    if not emb:
        return
    try:
        from database.supabase_client import get_supabase
        sb = get_supabase()
        if sb:
            sb.table("long_term_memories").insert({
                "content": content[:1000],
                "embedding": emb,
                "metadata": metadata or {},
            }).execute()
    except Exception:
        pass

# ── User Persona ──────────────────────────────────────────────────────────────
_persona_cache: dict[str, dict] = {}

def get_current_persona(session_id: str = "default") -> dict:
    if session_id in _persona_cache:
        return _persona_cache[session_id]
    try:
        from database.supabase_client import get_supabase
        sb = get_supabase()
        if sb:
            res = sb.table("user_personas").select("*").eq("session_id", session_id).limit(1).execute()
            if res.data:
                _persona_cache[session_id] = res.data[0]
                return res.data[0]
    except Exception:
        pass
    return {"mood": "CALM", "risk_appetite": "MEDIUM", "message_count": 0}

async def _update_persona_ngam(session_id: str, message: str):
    """Background: lightweight keyword-based persona update (no extra API call)."""
    msg_l = message.lower()
    mood = "CALM"
    if any(w in msg_l for w in ["tức", "chán", "mệt", "thất", "tệ", "khổ"]):
        mood = "FRUSTRATED"
    elif any(w in msg_l for w in ["vui", "tốt", "ngon", "đỉnh", "thắng", "xịn"]):
        mood = "EXCITED"
    elif any(w in msg_l for w in ["lo", "sợ", "nguy", "cẩn", "rủi"]):
        mood = "ANXIOUS"

    risk = "MEDIUM"
    if any(w in msg_l for w in ["all-in", "all in", "tất tay", "gấp đôi", "gấp thếp"]):
        risk = "HIGH"
    elif any(w in msg_l for w in ["nhẹ", "thận trọng", "ít thôi", "vừa vừa"]):
        risk = "LOW"

    persona = {"mood": mood, "risk_appetite": risk}
    _persona_cache[session_id] = {**get_current_persona(session_id), **persona}

    try:
        from database.supabase_client import get_supabase
        sb = get_supabase()
        if sb:
            sb.table("user_personas").upsert({
                "session_id": session_id,
                "mood": mood,
                "risk_appetite": risk,
                "message_count": _persona_cache[session_id].get("message_count", 0) + 1,
                "updated_at": datetime.now().isoformat(),
            }).execute()
    except Exception:
        pass

# ── Auto-Execute Critical Actions (trước khi gọi Gemini) ─────────────────────
# Các ngưỡng báo động đỏ — hệ thống tự hành động không chờ Gemini quyết định
import time as _time

_CRITICAL_LOSS_STREAK     = 3    # kỳ thua liên tiếp → emergency learning
_CRITICAL_WIN_RATE        = 15.0 # % win rate tối thiểu
_CRITICAL_PNL_VND         = -1_000_000  # -1M VNĐ → stop loss
_AUTO_EXEC_COOLDOWN_SEC   = 600  # 10 phút giữa các lần tự kích hoạt cùng loại

# Chỉ nhận lệnh dừng RÕ RÀNG — tránh "nghỉ ngơi đi" kích hoạt emergency stop
_STOP_KEYWORDS = {
    "dừng giao dịch", "dừng khẩn cấp", "emergency stop",
    "stop trading", "tắt autobet", "dừng autobet",
    "dừng ngay", "dừng lại ngay"
}

# Cooldown tracker: action_type → timestamp lần chạy cuối
_auto_exec_cooldown: dict[str, float] = {}

async def _auto_execute_if_critical(user_message: str) -> str:
    """
    Kiểm tra các ngưỡng báo động đỏ và tự hành động trước khi Gemini trả lời.
    Có cooldown 10 phút để tránh chạy GA backtest nặng mỗi tin nhắn.
    Trả về chuỗi báo cáo để inject vào context, hoặc "" nếu không cần hành động.
    """
    now       = _time.time()
    dna       = _load_dna()
    rt        = dna.get("realtime_params", {})
    loss_streak = int(rt.get("current_loss_streak", _keno_context.get("consecutive_losses", 0)))
    win_rate  = float(rt.get("session_win_rate_pct", _keno_context.get("win_rate", 0)))
    pnl       = float(rt.get("session_pnl_vnd", 0))
    msg_lower = user_message.lower()

    actions_taken = []

    # 1. Sếp ra lệnh dừng thủ công — kiểm tra exact phrase, không phải substring đơn
    if any(kw in msg_lower for kw in _STOP_KEYWORDS):
        key = "manual_stop"
        if now - _auto_exec_cooldown.get(key, 0) > 30:  # cooldown 30s cho lệnh thủ công
            _auto_exec_cooldown[key] = now
            result = await asyncio.to_thread(dung_giao_dich_khan_cap, "lenh_sep_manual")
            actions_taken.append(f"🛑 Đã dừng giao dịch theo lệnh Sếp. {result}")

    # 2. Chuỗi thua >= _CRITICAL_LOSS_STREAK → Emergency Learning (cooldown 10 phút)
    elif loss_streak >= _CRITICAL_LOSS_STREAK:
        key = "emergency_learning"
        if now - _auto_exec_cooldown.get(key, 0) > _AUTO_EXEC_COOLDOWN_SEC:
            _auto_exec_cooldown[key] = now
            result = await asyncio.to_thread(rut_kinh_nghiem_chuoi_thua)
            try:
                r = json.loads(result)
                actions_taken.append(
                    f"🚨 AUTO-ACTION: Chuỗi thua {loss_streak} kỳ → Emergency Learning!\n"
                    f"Kết quả: {r.get('ket_qua','—')}"
                )
            except Exception:
                actions_taken.append(f"🚨 Emergency Learning đã chạy. Kết quả: {result[:150]}")
        else:
            remaining = int((_AUTO_EXEC_COOLDOWN_SEC - (now - _auto_exec_cooldown.get(key, 0))) / 60)
            print(f"[AUTO-EXEC] emergency_learning đang cooldown, còn ~{remaining} phút")

    # 3. Win rate < 15% → Reset trọng số (cooldown 10 phút)
    if win_rate < _CRITICAL_WIN_RATE and win_rate > 0 and loss_streak >= 4:
        key = "weight_reset"
        if now - _auto_exec_cooldown.get(key, 0) > _AUTO_EXEC_COOLDOWN_SEC:
            _auto_exec_cooldown[key] = now
            result = await asyncio.to_thread(
                dot_bien_trong_so_thuat_toan, 0.25, 0.35, 0.25, 0.15, "auto_low_winrate_reset"
            )
            actions_taken.append(f"⚡ AUTO-ACTION: Win rate {win_rate:.1f}% < 15% → Reset trọng số F=0.25 R=0.35 C=0.25 A=0.15.")

    # 4. PnL quá âm → Emergency stop (cooldown 5 phút)
    if pnl <= _CRITICAL_PNL_VND:
        key = "stop_loss"
        if now - _auto_exec_cooldown.get(key, 0) > 300:
            _auto_exec_cooldown[key] = now
            result = await asyncio.to_thread(dung_giao_dich_khan_cap, "auto_stop_loss")
            actions_taken.append(f"🛑 AUTO-ACTION: PnL = {int(pnl):,}đ chạm Stop Loss → Đã dừng giao dịch!")

    if not actions_taken:
        return ""

    report = "\n\n⚙️ [HỆ THỐNG TỰ HÀNH ĐỘNG — BÁO CÁO]\n" + "\n".join(actions_taken)
    print(f"[AUTO-EXEC]{report}")
    return report

# ── Tools ─────────────────────────────────────────────────────────────────────
def mutate_agent_dna(field: str, new_value: float, subfield: str = "") -> str:
    """Mutate AI parameters. Use ONLY when user explicitly requests to change algorithm weights (w_f, w_r, w_c, w_a)."""
    dna = _load_dna()
    if field in ["ai_params", "hybrid_brain_weights"] and subfield:
        if field not in dna:
            dna[field] = {}
        dna[field][subfield] = new_value
        _save_dna(dna)
        return f"DNA Mutated: {field}.{subfield} = {new_value}"
    return "Failed to mutate DNA."

def update_trading_settings(cbTakeProfit: int = None, cbStopLoss: int = None, autoBetEnabled: bool = None) -> str:
    """Updates circuit breaker settings. Call when user asks to change take profit, stop loss, or auto bet."""
    settings_file = _BASE_DIR / "offline_settings.json"
    settings = {}
    if settings_file.exists():
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                settings = json.load(f)
        except Exception:
            pass
    if cbTakeProfit is not None:
        settings["cbTakeProfit"] = cbTakeProfit
    if cbStopLoss is not None:
        settings["cbStopLoss"] = cbStopLoss
    if autoBetEnabled is not None:
        settings["autoBetEnabled"] = autoBetEnabled
    try:
        core_url = os.getenv("CORE_API_URL", "http://127.0.0.1:8888")
        req = urllib.request.Request(
            f"{core_url.rstrip('/')}/api/settings/sync",
            data=json.dumps(settings).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=5)
        return "Settings updated and synced to server."
    except Exception:
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False)
        return "Settings saved locally (server offline)."

def lay_bao_cao_tai_chinh() -> str:
    """Lấy báo cáo tài chính: số dư ví, thắng/thua, PnL phiên."""
    wallet_file = _BASE_DIR / "offline_wallet.json"
    balance = 0
    if wallet_file.exists():
        try:
            with open(wallet_file, "r", encoding="utf-8") as f:
                balance = json.load(f).get("balance", 0)
        except Exception:
            pass
    dna = _load_dna()
    rt  = dna.get("realtime_params", {})
    return json.dumps({
        "so_du_hien_tai_vnd": f"{int(balance):,} VNĐ",
        "chuoi_thua_hien_tai": rt.get("current_loss_streak", _keno_context.get("consecutive_losses", 0)),
        "ty_le_thang_phien": f"{rt.get('session_win_rate_pct', _keno_context.get('win_rate', 0))}%",
        "pnl_phien_vnd": f"{int(rt.get('session_pnl_vnd', 0)):,} VNĐ",
        "delta_trend": rt.get("delta_trend", "NORMAL"),
    }, ensure_ascii=False)

def rut_kinh_nghiem_chuoi_thua() -> str:
    """Kích hoạt tự học khẩn cấp sau chuỗi thua. Chạy Genetic Algorithm backtest và đột biến DNA."""
    try:
        from ml_engine.dna_evolution_engine import run_loss_streak_learning
        dna    = _load_dna()
        losses = dna.get("realtime_params", {}).get("current_loss_streak", _keno_context.get("consecutive_losses", 0))
        result = run_loss_streak_learning(loss_streak=max(losses, 4))
        status = result.get("status", "UNKNOWN")
        if status == "MUTATED":
            return json.dumps({
                "ket_qua": f"DNA TIẾN HÓA! Gen #{result.get('generation')} | WR: {result.get('current_win_rate')}% → {result.get('validated_win_rate')}%",
                "bai_hoc": result.get("lesson", ""),
            }, ensure_ascii=False)
        return json.dumps({"ket_qua": f"Trọng số hiện tại vẫn tối ưu: {status}", "bai_hoc": ""}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ket_qua": f"Lỗi: {e}"}, ensure_ascii=False)

def lay_trang_thai_dna() -> str:
    """Lấy trạng thái DNA: trọng số, generation, lịch sử đột biến, hiệu suất all-time."""
    try:
        from ml_engine.dna_evolution_engine import load_dna
        dna = load_dna()
    except Exception:
        dna = _load_dna()
    hw  = dna.get("hybrid_brain_weights", {})
    rt  = dna.get("realtime_params", {})
    lm  = (dna.get("mutation_history") or [{}])[-1]
    return json.dumps({
        "generation": dna.get("evolution_generation", 0),
        "weights": {k: v for k, v in hw.items() if k != "description"},
        "inversion_threshold": dna.get("circuit_breaker", {}).get("inversion_loss_threshold", 4),
        "realtime": {
            "loss_streak": rt.get("current_loss_streak", 0),
            "win_streak": rt.get("current_win_streak", 0),
            "win_rate": rt.get("session_win_rate_pct", 0),
            "delta_trend": rt.get("delta_trend", "NORMAL"),
            "pnl_vnd": rt.get("session_pnl_vnd", 0),
        },
        "last_mutation": {
            "reason": lm.get("reason", "—"),
            "gen": lm.get("generation", 0),
            "improvement_pct": lm.get("improvement_pct", 0),
        },
        "all_time_best_wr": dna.get("performance_ledger", {}).get("all_time_best_win_rate", 0),
    }, ensure_ascii=False)

def doc_log_he_thong(so_dong: int = 30) -> str:
    """Đọc log hệ thống gần nhất. Dùng khi cần debug lỗi hoặc kiểm tra hoạt động."""
    try:
        lines = []
        if LOG_FILE.exists():
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
            lines = all_lines[-so_dong:]
        lessons_file = LOG_DIR / "lessons_learned.txt"
        lesson_str = ""
        if lessons_file.exists():
            lesson_str = lessons_file.read_text(encoding="utf-8")[-500:]
        return json.dumps({
            "log_gan_nhat": [json.loads(l) if l.strip().startswith("{") else l.strip() for l in lines if l.strip()],
            "kinh_nghiem_tich_luy": lesson_str,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

def kiem_tra_so_du_vi() -> str:
    """Kiểm tra chi tiết số dư ví Keno và Market Flow."""
    try:
        wallet_file  = _BASE_DIR / "offline_wallet.json"
        mf_file      = _BASE_DIR / "offline_mf_wallet.json"
        balance      = 0
        mf_balance   = 0
        if wallet_file.exists():
            with open(wallet_file, "r", encoding="utf-8") as f:
                balance = json.load(f).get("balance", 0)
        if mf_file.exists():
            with open(mf_file, "r", encoding="utf-8") as f:
                mf_balance = json.load(f).get("balance", 0)
        return json.dumps({
            "vi_keno_vnd": f"{int(balance):,}",
            "vi_market_flow_vnd": f"{int(mf_balance):,}",
            "tong_von_vnd": f"{int(balance + mf_balance):,}",
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

def dung_giao_dich_khan_cap(ly_do: str = "manual") -> str:
    """Dừng toàn bộ giao dịch tự động khẩn cấp. Dùng khi Sếp ra lệnh dừng hoặc circuit breaker vượt ngưỡng."""
    try:
        settings_file = _BASE_DIR / "offline_settings.json"
        settings = {}
        if settings_file.exists():
            with open(settings_file, "r", encoding="utf-8") as f:
                settings = json.load(f)
        settings["autoBetEnabled"] = False
        settings["emergency_stop_reason"] = ly_do
        settings["emergency_stop_time"]   = datetime.now().isoformat()
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False)
        # Sync to server
        try:
            core_url = os.getenv("CORE_API_URL", "http://127.0.0.1:8888")
            req = urllib.request.Request(
                f"{core_url.rstrip('/')}/api/settings/sync",
                data=json.dumps({"autoBetEnabled": False}).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass
        return f"🛑 KHẨN CẤP: Đã dừng tất cả giao dịch. Lý do: {ly_do}"
    except Exception as e:
        return f"Lỗi khi dừng khẩn cấp: {e}"

def dot_bien_trong_so_thuat_toan(w_f: float, w_r: float, w_c: float, w_a: float, ly_do: str = "manual_boss") -> str:
    """Đột biến trọng số thuật toán với validation. Tổng phải = 1.0. Dùng khi Sếp muốn can thiệp thủ công."""
    total = round(w_f + w_r + w_c + w_a, 4)
    if abs(total - 1.0) > 0.01:
        return f"❌ Lỗi: Tổng trọng số = {total:.4f} (phải = 1.0)"
    dna = _load_dna()
    old_w = dna.get("hybrid_brain_weights", {})
    dna["hybrid_brain_weights"].update({"w_f": w_f, "w_r": w_r, "w_c": w_c, "w_a": w_a})
    dna["evolution_generation"] = dna.get("evolution_generation", 0) + 1
    dna["last_mutated"] = datetime.now().isoformat()
    dna["last_mutation_reason"] = ly_do
    mutation_entry = {
        "generation": dna["evolution_generation"],
        "timestamp": dna["last_mutated"],
        "reason": ly_do,
        "old_weights": [old_w.get("w_f"), old_w.get("w_r"), old_w.get("w_c"), old_w.get("w_a")],
        "new_weights": [w_f, w_r, w_c, w_a],
    }
    dna.setdefault("mutation_history", []).append(mutation_entry)
    _save_dna(dna)
    return json.dumps({
        "ket_qua": f"✅ Đột biến thành công — Gen #{dna['evolution_generation']}",
        "cu": f"F={old_w.get('w_f')} R={old_w.get('w_r')} C={old_w.get('w_c')} A={old_w.get('w_a')}",
        "moi": f"F={w_f} R={w_r} C={w_c} A={w_a}",
        "ly_do": ly_do,
    }, ensure_ascii=False)

def dieu_chinh_khoi_luong_vao_lenh(kelly_fraction: float, max_bet_pct: float) -> str:
    """Điều chỉnh Kelly fraction và max bet % cho Market Flow. kelly_fraction: 0.01-0.5, max_bet_pct: 0.01-0.2."""
    kelly_fraction = max(0.01, min(0.5, kelly_fraction))
    max_bet_pct    = max(0.01, min(0.2, max_bet_pct))
    dna = _load_dna()
    cb  = dna.get("circuit_breaker", {})
    cb["kelly_fraction"] = kelly_fraction
    cb["max_bet_pct"]    = max_bet_pct
    dna["circuit_breaker"] = cb
    _save_dna(dna)
    return json.dumps({
        "kelly_fraction": kelly_fraction,
        "max_bet_pct": max_bet_pct,
        "uoc_tinh_moi_ky": f"~{round(kelly_fraction * 1_000_000 / 1000)}k VNĐ / kỳ (với ví 1M)",
    }, ensure_ascii=False)

def don_dep_rac_he_thong() -> str:
    """Dọn dẹp log cũ và reset cache nội bộ của Boss Agent."""
    cleaned = []
    try:
        if LOG_FILE.exists():
            lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
            if len(lines) > 500:
                LOG_FILE.write_text("\n".join(lines[-200:]) + "\n", encoding="utf-8")
                cleaned.append(f"Log trimmed: {len(lines)} → 200 dòng")
    except Exception as e:
        cleaned.append(f"Log trim lỗi: {e}")
    _memory_cache.clear()
    cleaned.append("In-memory history cache cleared.")
    return " | ".join(cleaned) or "Không có gì cần dọn."

_TOOLS = [
    mutate_agent_dna,
    update_trading_settings,
    lay_bao_cao_tai_chinh,
    rut_kinh_nghiem_chuoi_thua,
    lay_trang_thai_dna,
    doc_log_he_thong,
    kiem_tra_so_du_vi,
    dung_giao_dich_khan_cap,
    dot_bien_trong_so_thuat_toan,
    dieu_chinh_khoi_luong_vao_lenh,
    don_dep_rac_he_thong,
]

# ── Logging ───────────────────────────────────────────────────────────────────
def log_interaction(user_msg: str, bot_reply: str):
    entry = {"time": datetime.now().strftime("%H:%M:%S"), "user": user_msg[:200], "bot": bot_reply[:300]}
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass

# ── Core: model call with history ─────────────────────────────────────────────
def _is_quota_error(e: Exception) -> bool:
    msg = str(e).lower()
    return "429" in msg or "quota" in msg or "resource_exhausted" in msg

def _get_client():
    return _genai.Client(api_key=_API_KEY)

def _call_model_sync(model_name: str, system_prompt: str, user_message: str, history_contents: list):
    client   = _get_client()
    dna      = _load_dna()
    ai_params = dna.get("ai_params", {})

    # Validate model name
    preferred_raw = ai_params.get("model", "models/gemini-2.5-flash-lite")
    if "gemini-3" in preferred_raw or not preferred_raw.startswith("models/"):
        pass  # use passed model_name

    chat = client.chats.create(
        model=model_name,
        config=_types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=int(ai_params.get("max_tokens", 2048)),
            temperature=float(ai_params.get("temperature", 0.3)),
            tools=_TOOLS,
        ),
        history=history_contents,
    )
    response = chat.send_message(user_message)

    reply = ""
    for candidate in (response.candidates or []):
        for part in (candidate.content.parts or []):
            fc = getattr(part, "function_call", None)
            if fc and fc.name:
                func_map = {t.__name__: t for t in _TOOLS}
                tool_fn  = func_map.get(fc.name)
                if tool_fn:
                    args = dict(fc.args) if fc.args else {}
                    tool_result = tool_fn(**args)
                    resp2 = chat.send_message(
                        _types.Part.from_function_response(
                            name=fc.name,
                            response={"result": tool_result}
                        )
                    )
                    return resp2.text or ""
            elif getattr(part, "text", None):
                reply += part.text

    return reply or response.text or ""

def _get_model_list(dna: dict) -> list[str]:
    preferred = dna.get("ai_params", {}).get("model", "models/gemini-2.5-flash-lite")
    if "gemini-3" in preferred or not preferred.startswith("models/"):
        preferred = "models/gemini-2.5-flash-lite"
    return list(dict.fromkeys([preferred] + _MODELS))


# ── Public API ────────────────────────────────────────────────────────────────
async def boss_chat(user_message: str, session_id: str = "default") -> str:
    if not _GEMINI_AVAILABLE or not _API_KEY:
        reply = _fallback_response(user_message)
        log_interaction(user_message, reply)
        return reply

    # ── Auto-execute critical actions BEFORE asking Gemini ──────────────────
    auto_report = await _auto_execute_if_critical(user_message)

    dna     = _load_dna()
    persona = get_current_persona(session_id)
    system_prompt = _generate_dynamic_system_prompt(dna, persona, session_id)

    # Enrich with vector memories (non-blocking if slow)
    try:
        rag_context = await asyncio.wait_for(retrieve_relevant_memories(user_message), timeout=3.0)
        if rag_context:
            system_prompt += rag_context
    except Exception:
        pass

    # Inject auto-execution report into message context so Gemini sees what happened
    effective_message = user_message
    if auto_report:
        effective_message = f"{user_message}\n\n[SYSTEM PRE-ACTION REPORT]{auto_report}"

    history      = await _get_history(session_id)
    history_cont = _history_to_contents(history)
    models       = _get_model_list(dna)

    reply = None
    for model_name in models:
        try:
            reply = await asyncio.to_thread(_call_model_sync, model_name, system_prompt, effective_message, history_cont)
            print(f"[BOSS] OK: {model_name}")
            break
        except Exception as e:
            kind = "QUOTA" if _is_quota_error(e) else "ERROR"
            print(f"[BOSS] {kind} {model_name}: {str(e)[:100]}")
            continue

    if not reply:
        reply = _fallback_response(user_message)

    # Persist history + persona asynchronously
    new_history = history + [{"role": "user", "content": user_message}, {"role": "model", "content": reply}]
    asyncio.create_task(_save_history(session_id, new_history))
    asyncio.create_task(_update_persona_ngam(session_id, user_message))

    # Save important interactions to vector memory every ~5 turns
    if len(new_history) % 10 == 0:
        summary = f"User: {user_message[:150]} | Boss: {reply[:150]}"
        asyncio.create_task(save_memory_to_vector_db(summary, {"session": session_id}))

    log_interaction(user_message, reply)
    return reply


async def boss_chat_stream(user_message: str, session_id: str = "default"):
    if not _GEMINI_AVAILABLE or not _API_KEY:
        async for chunk in _stream_fallback(user_message):
            yield chunk
        return

    # ── Auto-execute critical actions BEFORE streaming ──────────────────────
    auto_report = await _auto_execute_if_critical(user_message)
    if auto_report:
        # Stream auto-report first so Sếp sees it immediately
        for word in auto_report.split(" "):
            yield "data: " + json.dumps({"text": word + " "}, ensure_ascii=False) + "\n\n"
            await asyncio.sleep(0.01)
        yield "data: " + json.dumps({"text": "\n\n"}, ensure_ascii=False) + "\n\n"

    dna     = _load_dna()
    persona = get_current_persona(session_id)
    system_prompt = _generate_dynamic_system_prompt(dna, persona, session_id)

    try:
        rag_context = await asyncio.wait_for(retrieve_relevant_memories(user_message), timeout=3.0)
        if rag_context:
            system_prompt += rag_context
    except Exception:
        pass

    effective_message = user_message
    if auto_report:
        effective_message = f"{user_message}\n\n[SYSTEM PRE-ACTION REPORT]{auto_report}"

    history      = await _get_history(session_id)
    history_cont = _history_to_contents(history)
    models       = _get_model_list(dna)

    full_reply = ""
    success    = False

    for model_name in models:
        try:
            reply = await asyncio.to_thread(_call_model_sync, model_name, system_prompt, effective_message, history_cont)
            print(f"[BOSS STREAM] OK: {model_name}")
            for word in reply.split(" "):
                token = word + " "
                full_reply += token
                yield "data: " + json.dumps({"text": token}, ensure_ascii=False) + "\n\n"
                await asyncio.sleep(0.02)
            success = True
            break
        except Exception as e:
            kind = "QUOTA" if _is_quota_error(e) else "ERROR"
            print(f"[BOSS STREAM] {kind} {model_name}: {str(e)[:100]}")
            continue

    if not success:
        async for chunk in _stream_fallback(user_message):
            yield chunk
            full_reply += chunk

    yield "data: [DONE]\n\n"

    if full_reply:
        new_history = history + [{"role": "user", "content": user_message}, {"role": "model", "content": full_reply.strip()}]
        asyncio.create_task(_save_history(session_id, new_history))
        asyncio.create_task(_update_persona_ngam(session_id, user_message))

    log_interaction(user_message, full_reply)


async def _stream_fallback(user_message: str):
    msg = _fallback_response(user_message)
    for word in msg.split(" "):
        yield "data: " + json.dumps({"text": word + " "}, ensure_ascii=False) + "\n\n"
        await asyncio.sleep(0.04)


def _fallback_response(msg: str) -> str:
    dna      = _load_dna()
    rt       = dna.get("realtime_params", {})
    balance  = _keno_context.get("wallet_balance", 1_000_000)
    anchors  = _keno_context.get("anchors", [])
    confidence = _keno_context.get("confidence", 0)
    losses   = rt.get("current_loss_streak", _keno_context.get("consecutive_losses", 0))
    win_rate = rt.get("session_win_rate_pct", _keno_context.get("win_rate", 0))
    draw_id  = _keno_context.get("latest_draw_id", "?")
    msg_l    = msg.lower()

    if any(w in msg_l for w in ["chào", "hello", "hi", "alo", "ê", "o7"]):
        return f"Sếp ơi! Boss Agent v3.0 ONLINE. Kỳ #{draw_id} | Ví: {int(balance):,}đ | WR: {win_rate}%."
    if any(w in msg_l for w in ["tình hình", "sao rồi", "hôm nay", "báo cáo", "kết quả"]):
        streak = f" ⚠️ Chuỗi thua: {losses} kỳ!" if losses >= 3 else ""
        return f"Kỳ #{draw_id} | Ví: {int(balance):,}đ | WR: {win_rate}%{streak}. Anchor: {anchors[:3] or 'Chờ dữ liệu'}."
    if any(w in msg_l for w in ["dự đoán", "kỳ tới", "đánh gì", "mua gì", "phân tích"]):
        if not anchors:
            return f"Đang xử lý kỳ #{draw_id}. Bấm IGNITE để lấy dự đoán mới nhất!"
        signal = "ĐẶT MẠNH" if confidence > 85 else "VÀO NHẸ" if confidence > 70 else "SKIP"
        return f"{signal} — Anchor: {anchors[:3]} | Confidence: {confidence}%"
    if any(w in msg_l for w in ["ví", "tiền", "vốn", "số dư"]):
        return f"Số dư ví: {int(balance):,} VNĐ."
    if any(w in msg_l for w in ["thua", "tệ", "thất bại", "xui"]):
        msg_out = "DNA sắp đảo logic — Evolution Engine đang học!" if losses >= 4 else "Vẫn trong ngưỡng bình thường."
        return f"Chuỗi thua: {losses} kỳ. {msg_out}"
    if any(w in msg_l for w in ["chốt", "nghỉ", "dừng"]):
        return "Hệ thống đang bảo toàn số dư. Sếp nghỉ ngơi đi nhé."
    if anchors:
        return f"Kỳ #{draw_id}: Anchor={anchors[:3]}, Confidence={confidence}%, Ví={int(balance):,}đ."
    return f"Boss Agent v3.0 ONLINE — Kỳ #{draw_id}. Hỏi tình hình, dự đoán, hoặc số dư ví nhé Sếp!"


# ── Gemini STT ────────────────────────────────────────────────────────────────
async def whisper_transcribe(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    if not _GEMINI_AVAILABLE or not _API_KEY:
        return "[STT_OFFLINE] Gemini key chưa được cấu hình."
    try:
        client     = _get_client()
        audio_part = _types.Part.from_bytes(data=audio_bytes, mime_type="audio/webm")
        prompt     = "Dịch đoạn âm thanh thành văn bản. Chỉ xuất nội dung người nói, không bình luận."
        response   = await asyncio.to_thread(
            client.models.generate_content,
            model="models/gemini-2.0-flash-lite",
            contents=[prompt, audio_part]
        )
        return response.text.strip()
    except Exception as e:
        return f"[STT_ERROR] {str(e)[:100]}"
