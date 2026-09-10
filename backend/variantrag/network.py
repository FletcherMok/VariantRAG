"""Bounded, cached HTTP with per-service pacing; cache contains successful responses only."""

import hashlib
import json
import random
import threading
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .io import read_json, write_json

_locks = defaultdict(threading.Lock)
_last = defaultdict(float)


class CachedHTTP:
    def __init__(self, cache, transport=None):
        self.cache = Path(cache)
        self.client = httpx.Client(timeout=30, transport=transport)

    def close(self):
        self.client.close()

    def get(self, url, params=None, ttl=86400, response_format="json"):
        key = hashlib.sha256(json.dumps([url, params, response_format], sort_keys=True).encode()).hexdigest()
        path = self.cache / (key + ".json")
        if path.exists():
            cached = read_json(path)
            if time.time() - cached["time"] < ttl:
                return cached["value"]
        host = urlsplit(url).netloc
        for attempt in range(4):
            with _locks[host]:
                time.sleep(max(0, 0.4 - (time.monotonic() - _last[host])))
                _last[host] = time.monotonic()
                try:
                    response = self.client.get(url, params=params)
                except httpx.TransportError:
                    if attempt == 3:
                        raise
                    time.sleep(2**attempt + random.random() / 4)
                    continue
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == 3:
                    response.raise_for_status()
                retry = response.headers.get("Retry-After", "")
                delay = float(retry) if retry.isdigit() else 2**attempt
                time.sleep(min(30, delay) + random.random() / 4)
                continue
            response.raise_for_status()
            value = response.json() if response_format == "json" else response.text
            write_json(path, {"time": time.time(), "value": value})
            return value
        raise RuntimeError("Request retry budget exhausted")
