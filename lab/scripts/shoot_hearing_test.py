#!/usr/bin/env python3
"""Visual QA harness: screenshot each tab of the hearing-test page.

Drives the real tab clicks via Chrome DevTools Protocol over WebSocket
(the page's tabs are JS-driven, so a fragment URL would not switch them).
Outputs PNGs to lab/shots/.
"""
from __future__ import annotations

import base64
import json
import pathlib
import subprocess
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lab" / "pylibs"))
PAGE = ROOT / "products" / "hearing-test.html"
OUT = ROOT / "lab" / "shots"
PORT = 9333

CASES = [
    ("setup", 'document.querySelector(\'button[data-tab="setup"]\').click()', "校准与音量（默认）"),
    ("threshold", 'document.querySelector(\'button[data-tab="threshold"]\').click()', "频段听阈"),
    # 进入盲测并点一下 A 槽播放，验证播放态脉冲 + 轮次进度条
    ("blind", '(document.querySelector(\'button[data-tab="blind"]\').click(),'
              'document.getElementById("blStart").click(),'
              'document.querySelector("#blSlots .slot button").click())', "码率盲测(播放态)"),
    ("report", 'document.querySelector(\'button[data-tab="report"]\').click()', "结果与导出"),
]

PAGE_JS = "document.documentElement.setAttribute('data-theme','light');"


def wait_devtools(timeout=20):
    url = f"http://127.0.0.1:{PORT}/json/list"
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1) as r:
                pages = json.loads(r.read())
            # 选真正在跑被测页面的那个 target(Chrome 会带出若干辅助 target)
            target = next((p for p in pages
                           if p.get("type") == "page" and "hearing-test" in p.get("url", "")),
                          None)
            if target:
                return target["webSocketDebuggerUrl"]
        except Exception:
            pass
        time.sleep(0.3)
    raise RuntimeError("devtools did not come up")


def main() -> int:
    try:
        import websocket  # websocket-client
    except ImportError:
        print("需要 websocket-client: pip install websocket-client", file=sys.stderr)
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [
            "google-chrome-stable",
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            "--hide-scrollbars",
            "--window-size=920,2400",
            f"--remote-debugging-port={PORT}",
            "--user-data-dir=/tmp/chrome-ht-qa",
            f"file://{PAGE}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        ws_url = wait_devtools()
        ws = websocket.create_connection(ws_url, timeout=30, suppress_origin=True)
        msg_id = 0

        def send(method, params=None):
            nonlocal msg_id
            msg_id += 1
            ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
            while True:
                resp = json.loads(ws.recv())
                if resp.get("id") == msg_id:
                    return resp.get("result", {})

        def evaluate(expr):
            return send("Runtime.evaluate", {
                "expression": expr, "awaitPromise": True, "returnByValue": True
            })

        time.sleep(1.0)
        evaluate(PAGE_JS)

        for name, click_js, desc in CASES:
            res = evaluate(click_js)
            exc = res.get("exceptionDetails")
            if exc:
                print(f"WARN {name}: eval error: "
                      f"{exc.get('exception', {}).get('description', exc)}", file=sys.stderr)
            time.sleep(1.2)
            shot = send("Page.captureScreenshot", {"format": "png"})
            data = base64.b64decode(shot["data"])
            out = OUT / f"{name}.png"
            out.write_bytes(data)
            print(f"shot {name} ({desc}): {len(data)} bytes -> {out}")
        ws.close()
    finally:
        proc.terminate()
        proc.wait(timeout=10)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
