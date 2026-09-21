"""
Modul Checkpoint & Session Persistence untuk AutoJurnal.
Menyimpan snapshot berkala (setiap bab/section selesai) ke file JSON,
memungkinkan resume generasi jika koneksi internet terputus atau server restart.
"""

import os
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

CHECKPOINT_DIR = Path(__file__).resolve().parent / "data" / "checkpoints"
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)


def get_checkpoint_path(session_id: str) -> Path:
    # Sanitize session_id for filesystem safety
    safe_id = "".join(c for c in session_id if c.isalnum() or c in ("-", "_")).strip()
    return CHECKPOINT_DIR / f"{safe_id}.json"


def save_checkpoint(session_id: str, data: Dict[str, Any]) -> str:
    """
    Menyimpan snapshot status generasi ke disk secara aman.
    """
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    file_path = get_checkpoint_path(session_id)
    payload = {
        **data,
        "session_id": session_id,
        "last_updated": time.time(),
        "last_updated_human": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
    }
    # Atomic write via temp file
    temp_path = file_path.with_suffix(".tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    temp_path.replace(file_path)
    print(f"[Checkpoint] Saved snapshot for session '{session_id}' (Step: {data.get('current_step', 0)}/{data.get('total_steps', 0)})")
    return session_id


def load_checkpoint(session_id: str) -> Optional[Dict[str, Any]]:
    """Memuat snapshot checkpoint berdasarkan session_id."""
    file_path = get_checkpoint_path(session_id)
    if not file_path.exists():
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Checkpoint] Failed to load checkpoint '{session_id}': {e}")
        return None


def get_latest_active_checkpoint() -> Optional[Dict[str, Any]]:
    """
    Mencari checkpoint terbaru yang berstatus 'in_progress' dan belum selesai.
    """
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    candidates = []
    for f in CHECKPOINT_DIR.glob("*.json"):
        try:
            with open(f, "r", encoding="utf-8") as cp_file:
                data = json.load(cp_file)
                if data.get("status") in ("in_progress", "interrupted"):
                    candidates.append((data.get("last_updated", 0), data))
        except Exception:
            continue

    if not candidates:
        return None

    # Urutkan berdasarkan waktu modifikasi terbaru
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def mark_checkpoint_completed(session_id: str):
    """Menandai checkpoint sebagai selesai dan menghapusnya atau mengarsipkannya."""
    file_path = get_checkpoint_path(session_id)
    if file_path.exists():
        try:
            file_path.unlink()
            print(f"[Checkpoint] Cleaned up completed session '{session_id}'")
        except Exception as e:
            print(f"[Checkpoint] Error removing completed checkpoint: {e}")


def delete_checkpoint(session_id: str) -> bool:
    """Menghapus checkpoint yang dibatalkan oleh pengguna."""
    file_path = get_checkpoint_path(session_id)
    if file_path.exists():
        try:
            file_path.unlink()
            print(f"[Checkpoint] Deleted checkpoint '{session_id}'")
            return True
        except Exception as e:
            print(f"[Checkpoint] Error deleting checkpoint: {e}")
    return False


def list_checkpoints() -> List[Dict[str, Any]]:
    """Mendaftar semua checkpoint yang tersimpan."""
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    result = []
    for f in CHECKPOINT_DIR.glob("*.json"):
        try:
            with open(f, "r", encoding="utf-8") as cp_file:
                data = json.load(cp_file)
                result.append({
                    "session_id": data.get("session_id"),
                    "theme": data.get("theme"),
                    "mode": data.get("mode"),
                    "provider": data.get("provider"),
                    "current_step": data.get("current_step", 0),
                    "total_steps": data.get("total_steps", 0),
                    "status": data.get("status"),
                    "last_updated": data.get("last_updated"),
                    "last_updated_human": data.get("last_updated_human"),
                })
        except Exception:
            continue
    result.sort(key=lambda x: x.get("last_updated", 0), reverse=True)
    return result
