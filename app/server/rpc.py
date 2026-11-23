"""Requests from the app on stdin, one JSON object per line: {"id": n, "method": "...", "params": {...}}. The answer
goes to the stdout the process started with, one line: {"id": n, "result": ...} or {"id": n, "error": "..."}. Anything
else the process prints goes to stderr, so it cannot break an answer. When stdin closes, the process exits: it does not
outlive the app, also when the app is killed."""

import json
import os
import sys
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor


def claim_stdout():
    """The stdout for the answers; from now on, prints go to stderr. Call it before anything prints."""
    out = os.fdopen(os.dup(1), "w", buffering=1, encoding="utf-8")
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    return out


def serve(methods: dict[str, Callable], out) -> None:
    """Answers the requests in a thread; a slow method (a check) does not hold the others."""
    lock = threading.Lock()
    pool = ThreadPoolExecutor(4)

    def answer(request):
        try:
            message = {"id": request["id"], "result": methods[request["method"]](**request.get("params") or {})}
        except Exception as e:  # the app shows it; the server keeps running
            message = {"id": request.get("id"), "error": f"{type(e).__name__}: {e}"}
        # default=str: Decimal exactly, dates in ISO, beancount's positions and inventories as it prints them
        line = json.dumps(message, default=str, ensure_ascii=False)
        with lock:
            out.write(line + "\n")

    def read():
        for line in sys.stdin:
            try:
                pool.submit(answer, json.loads(line))
            except ValueError:
                print(f"rpc: not a request: {line[:200]!r}", file=sys.stderr)
        os._exit(0)

    threading.Thread(target=read, daemon=True).start()
