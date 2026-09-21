import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)
sys.path.insert(0, os.path.dirname(backend_dir))

import asyncio
import time
from backend.providers.router import KeyPool, is_rate_limit_error
from backend.providers.catalog import get_catalog_list, get_catalog_entry, AI_CATALOG
from backend.checkpoint import save_checkpoint, load_checkpoint, get_latest_active_checkpoint, delete_checkpoint, mark_checkpoint_completed


async def test_keypool_parsing_and_round_robin():
    # Test parsing comma and newline separated keys
    raw_keys = "key1, key2\nkey3,  key4  "
    pool = KeyPool(raw_keys, strategy="round-robin")
    assert pool.total_keys == 4

    # Test round robin rotation
    k1 = await pool.get_next_key()
    k2 = await pool.get_next_key()
    k3 = await pool.get_next_key()
    k4 = await pool.get_next_key()
    k5 = await pool.get_next_key()

    assert k1.key == "key2"
    assert k2.key == "key3"
    assert k3.key == "key4"
    assert k4.key == "key1"
    assert k5.key == "key2"


async def test_keypool_rate_limit_cooldown():
    raw_keys = ["keyA", "keyB", "keyC"]
    pool = KeyPool(raw_keys, strategy="round-robin")

    # Mark keyA as rate limited
    pool.keys_list[0].mark_rate_limited(cooldown_seconds=10)
    assert not pool.keys_list[0].is_available

    # Next keys returned should skip keyA while it's in cooldown
    avail_keys = pool.available_keys
    assert len(avail_keys) == 2
    assert "keyA" not in [k.key for k in avail_keys]


def test_ai_catalog_entries():
    # Ensure NVIDIA NIM, Xiaomi MiMo, DeepSeek, Qwen, Gemini exist in catalog
    assert "nvidia" in AI_CATALOG
    assert "xiaomi_mimo" in AI_CATALOG
    assert "deepseek" in AI_CATALOG
    assert "qwen" in AI_CATALOG
    assert "gemini" in AI_CATALOG

    nv = get_catalog_entry("nvidia")
    assert "integrate.api.nvidia.com" in nv["default_base_url"]

    mimo = get_catalog_entry("xiaomi_mimo")
    assert "mimo" in mimo["default_model"]


def test_checkpoint_lifecycle():
    session_id = f"test-sess-{int(time.time())}"
    data = {
        "theme": "Artificial Intelligence in ERP",
        "mode": "textbook",
        "current_step": 3,
        "total_steps": 14,
        "completed_count": 3,
        "all_content": "## Bab 1\nKonten Bab 1\n\n## Bab 2\nKonten Bab 2\n\n## Bab 3\nKonten Bab 3",
        "chapters": ["Bab 1", "Bab 2", "Bab 3", "Bab 4"],
        "status": "in_progress"
    }

    # 1. Save checkpoint
    save_checkpoint(session_id, data)

    # 2. Load checkpoint
    loaded = load_checkpoint(session_id)
    assert loaded is not None
    assert loaded["current_step"] == 3
    assert "Bab 2" in loaded["all_content"]

    # 3. Active checkpoint detection
    active = get_latest_active_checkpoint()
    assert active is not None
    assert active["session_id"] == session_id

    # 4. Clean up
    mark_checkpoint_completed(session_id)
    assert load_checkpoint(session_id) is None


if __name__ == "__main__":
    asyncio.run(test_keypool_parsing_and_round_robin())
    asyncio.run(test_keypool_rate_limit_cooldown())
    test_ai_catalog_entries()
    test_checkpoint_lifecycle()
    print("All tests in test_router_and_checkpoints.py passed successfully!")
