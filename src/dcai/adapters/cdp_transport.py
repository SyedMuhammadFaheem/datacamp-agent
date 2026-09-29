"""Minimal Chrome DevTools Protocol transport: HTTP target discovery plus a
WebSocket JSON-RPC session. No Playwright/Selenium/Puppeteer — this talks
the CDP wire protocol directly against a browser the user already launched
and is authenticated in.
"""

import itertools
import json
import queue
import threading
import time
import urllib.request

import websocket


class CDPError(Exception):
    pass


def list_targets(port: int) -> list[dict]:
    with urllib.request.urlopen(f"http://localhost:{port}/json/list", timeout=5) as resp:
        return json.load(resp)


def open_new_tab(port: int, url: str) -> dict:
    # Chrome requires PUT here (GET was deprecated and now 405s).
    req = urllib.request.Request(f"http://localhost:{port}/json/new?{url}", method="PUT")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.load(resp)


class CDPSession:
    """One WebSocket connection to a single browser target (tab), with
    blocking request/response matching by id and a background-drained
    queue of async protocol events."""

    def __init__(self, ws_url: str):
        self._ws = websocket.create_connection(ws_url, timeout=20)
        self._id_counter = itertools.count(1)
        self._results: dict[int, dict] = {}
        self._results_lock = threading.Lock()
        self._events: "queue.Queue[dict]" = queue.Queue()
        self._stop = threading.Event()
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def _read_loop(self) -> None:
        while not self._stop.is_set():
            try:
                raw = self._ws.recv()
            except Exception:
                return
            if not raw:
                continue
            msg = json.loads(raw)
            if "id" in msg:
                with self._results_lock:
                    self._results[msg["id"]] = msg
            else:
                self._events.put(msg)

    def send(self, method: str, params: dict | None = None, timeout_s: float = 15) -> dict:
        msg_id = next(self._id_counter)
        self._ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            with self._results_lock:
                result = self._results.pop(msg_id, None)
            if result is not None:
                if "error" in result:
                    raise CDPError(f"{method} failed: {result['error']}")
                return result.get("result", {})
            time.sleep(0.02)
        raise CDPError(f"{method} timed out after {timeout_s}s")

    def next_event(self, timeout_s: float = 1.0) -> dict | None:
        try:
            return self._events.get(timeout=timeout_s)
        except queue.Empty:
            return None

    def close(self) -> None:
        self._stop.set()
        try:
            self._ws.close()
        except Exception:
            pass
