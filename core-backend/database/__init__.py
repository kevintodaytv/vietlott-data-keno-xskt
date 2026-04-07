from .supabase_client import (
    get_supabase,
    save_lottery_result,
    get_recent_results,
    save_training_metrics,
    subscribe_to_results,
)

__all__ = [
    "get_supabase",
    "save_lottery_result",
    "get_recent_results",
    "save_training_metrics",
    "subscribe_to_results",
]
