"""
Sistem Multi-Key Smart Router untuk AutoJurnal.
Mengelola key pool, rotasi Round-Robin, fault-tolerance, auto-retry 429/timeout,
dan failover cerdas tanpa memutus memory atau flow penulisan.
"""

import asyncio
import time
import random
import re
from typing import List, Dict, Optional, Any, Tuple


class KeyStatus:
    def __init__(self, key: str):
        self.key = key
        self.is_active = True
        self.cooldown_until: float = 0.0
        self.failure_count: int = 0
        self.success_count: int = 0
        self.last_error: Optional[str] = None
        self.last_used: float = 0.0
        self.last_latency_ms: float = 0.0

    @property
    def is_available(self) -> bool:
        return self.is_active and time.time() >= self.cooldown_until

    def mark_success(self, latency_ms: float = 0.0):
        self.success_count += 1
        self.failure_count = 0
        self.last_error = None
        self.cooldown_until = 0.0
        self.last_used = time.time()
        if latency_ms > 0:
            self.last_latency_ms = latency_ms

    def mark_rate_limited(self, cooldown_seconds: int = 60, error_msg: str = "Rate limit (429)"):
        self.failure_count += 1
        self.last_error = error_msg
        self.cooldown_until = time.time() + cooldown_seconds
        self.last_used = time.time()
        print(f"[KeyPool] Key ...{self.key[-6:] if len(self.key) > 6 else self.key} rate-limited. Cooldown for {cooldown_seconds}s")

    def mark_failed(self, error_msg: str, cooldown_seconds: int = 30):
        self.failure_count += 1
        self.last_error = error_msg
        self.cooldown_until = time.time() + cooldown_seconds
        self.last_used = time.time()
        print(f"[KeyPool] Key ...{self.key[-6:] if len(self.key) > 6 else self.key} failed: {error_msg}. Cooldown for {cooldown_seconds}s")


class KeyPool:
    """
    Mengelola kumpulan API Key untuk satu provider atau endpoint.
    Mendukung strategi: 'round-robin', 'failover', 'random'.
    """

    def __init__(self, keys: Optional[List[str] | str] = None, strategy: str = "round-robin"):
        self.strategy = strategy.lower()
        self.keys_list: List[KeyStatus] = []
        self._index: int = 0
        self._lock = asyncio.Lock()
        if keys:
            self.set_keys(keys)

    def set_keys(self, raw_keys: List[str] | str):
        """Memparsing string koma / newline / list menjadi KeyStatus pool."""
        parsed = []
        if isinstance(raw_keys, str):
            # Split by comma or newline, strip whitespace
            parts = re.split(r"[,;\n\r]+", raw_keys.strip())
            for p in parts:
                p_clean = p.strip()
                if p_clean:
                    parsed.append(p_clean)
        elif isinstance(raw_keys, (list, tuple)):
            for p in raw_keys:
                if isinstance(p, str) and p.strip():
                    parsed.append(p.strip())

        # Pertahankan data status key yang sudah ada jika key-nya sama
        existing_map = {k.key: k for k in self.keys_list}
        new_list = []
        for key_str in parsed:
            if key_str in existing_map:
                new_list.append(existing_map[key_str])
            else:
                new_list.append(KeyStatus(key_str))
        self.keys_list = new_list

    def add_key(self, key_str: str):
        k_clean = key_str.strip()
        if k_clean and not any(k.key == k_clean for k in self.keys_list):
            self.keys_list.append(KeyStatus(k_clean))

    def remove_key(self, key_str: str):
        self.keys_list = [k for k in self.keys_list if k.key != key_str]

    @property
    def total_keys(self) -> int:
        return len(self.keys_list)

    @property
    def available_keys(self) -> List[KeyStatus]:
        return [k for k in self.keys_list if k.is_available]

    async def get_next_key(self) -> Optional[KeyStatus]:
        """Mengambil key berikutnya sesuai strategi."""
        if not self.keys_list:
            return None

        async with self._lock:
            avail = self.available_keys
            if not avail:
                # Jika semua key sedang cooldown, gunakan key yang cooldown-nya paling cepat berakhir
                sorted_by_cooldown = sorted(self.keys_list, key=lambda k: k.cooldown_until)
                return sorted_by_cooldown[0]

            if self.strategy == "random":
                return random.choice(avail)

            if self.strategy == "failover":
                # Gunakan key pertama yang tersedia secara statis sampai error
                return avail[0]

            # Default: Round-Robin
            self._index = (self._index + 1) % len(avail)
            return avail[self._index]

    def get_status_summary(self) -> List[Dict[str, Any]]:
        """Mengembalikan status kesehatan setiap key untuk UI / API."""
        res = []
        now = time.time()
        for idx, k in enumerate(self.keys_list, 1):
            is_cooling = now < k.cooldown_until
            res.append({
                "index": idx,
                "key_preview": f"...{k.key[-6:]}" if len(k.key) > 6 else k.key,
                "is_active": k.is_active,
                "is_available": k.is_available,
                "is_cooling": is_cooling,
                "cooldown_remaining_sec": max(0, int(k.cooldown_until - now)),
                "success_count": k.success_count,
                "failure_count": k.failure_count,
                "last_error": k.last_error,
                "last_latency_ms": round(k.last_latency_ms, 1)
            })
        return res


class EndpointPool:
    """
    Mengelola kumpulan Base URLs (misal beberapa host Ollama atau local servers).
    """

    def __init__(self, endpoints: Optional[List[str] | str] = None):
        self.endpoints: List[str] = []
        self._index: int = 0
        self._lock = asyncio.Lock()
        if endpoints:
            self.set_endpoints(endpoints)

    def set_endpoints(self, raw: List[str] | str):
        parsed = []
        if isinstance(raw, str):
            parts = re.split(r"[,;\n\r]+", raw.strip())
            for p in parts:
                p_clean = p.strip().rstrip("/")
                if p_clean:
                    parsed.append(p_clean)
        elif isinstance(raw, (list, tuple)):
            for p in raw:
                if isinstance(p, str) and p.strip():
                    parsed.append(p.strip().rstrip("/"))
        self.endpoints = parsed or ["http://localhost:11434"]

    async def get_next_endpoint(self) -> str:
        if not self.endpoints:
            return "http://localhost:11434"
        async with self._lock:
            self._index = (self._index + 1) % len(self.endpoints)
            return self.endpoints[self._index]


def is_rate_limit_error(error: Exception) -> bool:
    """Memeriksa apakah exception adalah rate limit (429) atau kuota habis."""
    err_msg = str(error).lower()
    keywords = [
        "429", "rate limit", "ratelimit", "too many requests",
        "quota exceeded", "resource_exhausted", "credit balance",
        "insufficient_quota", "exceeded your current quota",
        "billing", "tokens per minute", "requests per minute"
    ]
    return any(k in err_msg for k in keywords)


def is_transient_error(error: Exception) -> bool:
    """Memeriksa error sementara (503, 502, timeout, connection drop)."""
    err_msg = str(error).lower()
    keywords = [
        "502", "503", "504", "bad gateway", "service unavailable",
        "gateway timeout", "timeout", "timed out", "connecterror",
        "connection reset", "connection refused", "remoteprotocolerror"
    ]
    return any(k in err_msg for k in keywords)
