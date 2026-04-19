# shared_state.py — Trạng thái dùng chung giữa main.py và boss_agent.py
# Tránh circular import: cả hai module cùng import từ đây.

from typing import Any

# ── Predictive Telemetry ring buffer ────────────────────────────────────────
_BEHAVIOR_LOG: list[dict[str, Any]] = []
_MAX_BEHAVIOR_LOG = 500
