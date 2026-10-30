"""Minimal client for the Chrome DevTools Protocol: starts headless Edge and talks to a page over a WebSocket.

Standard library only, nothing to install.
"""
import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import time
import urllib.request

EDGE = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
PROFILE = r"C:\AI\tmp\leon-promo-edge"          # Latin path: the user profile folder has Cyrillic in it
PORT = 9337


class Socket:
    def __init__(self, url):
        host, path = url.replace("ws://", "").split("/", 1)
        name, port = host.split(":")
        self.s = socket.create_connection((name, int(port)), timeout=300)
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall((f"GET /{path} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                        f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        head = b""
        while b"\r\n\r\n" not in head:
            head += self.s.recv(1)
        if b" 101 " not in head.split(b"\r\n")[0]:
            raise RuntimeError(head.decode(errors="replace"))

    def _exact(self, n):
        buf = bytearray()
        while len(buf) < n:
            part = self.s.recv(min(1 << 20, n - len(buf)))
            if not part:
                raise ConnectionError("browser closed the socket")
            buf += part
        return bytes(buf)

    def _frame(self, op, data):
        mask = os.urandom(4)
        head = bytes([0x80 | op])
        n = len(data)
        if n < 126:
            head += bytes([0x80 | n])
        elif n < 65536:
            head += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            head += bytes([0x80 | 127]) + struct.pack(">Q", n)
        body = bytes(b ^ mask[i & 3] for i, b in enumerate(data))
        self.s.sendall(head + mask + body)

    def send(self, text):
        self._frame(1, text.encode("utf-8"))

    def recv(self):
        out = bytearray()
        while True:
            b0, b1 = self._exact(2)
            n = b1 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._exact(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._exact(8))[0]
            data = self._exact(n)
            op = b0 & 0x0F
            if op == 9:                               # ping
                self._frame(10, data)
                continue
            if op in (0, 1, 2):
                out += data
                if b0 & 0x80:
                    return out.decode("utf-8")


class Page:
    def __init__(self, ws_url):
        self.ws = Socket(ws_url)
        self.n = 0
        self.events = []

    def call(self, method, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})
            self.events.append(msg)

    def wait_event(self, name, timeout=60):
        end = time.time() + timeout
        while time.time() < end:
            for i, e in enumerate(self.events):
                if e.get("method") == name:
                    return self.events.pop(i)
            self.events.append(json.loads(self.ws.recv()))
        raise TimeoutError(name)

    def js(self, expr):
        """Evaluates an expression in the page, waits for its promise and returns its value."""
        r = self.call("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
        if "exceptionDetails" in r:
            d = r["exceptionDetails"]
            raise RuntimeError(d.get("exception", {}).get("description") or d.get("text"))
        return r["result"].get("value")

    def shot(self, fmt="jpeg", quality=93):
        args = {"format": fmt}
        if fmt == "jpeg":
            args["quality"] = quality
        return base64.b64decode(self.call("Page.captureScreenshot", **args)["data"])


def start_edge():
    edge = next(p for p in EDGE if os.path.exists(p))
    shutil.rmtree(PROFILE, ignore_errors=True)
    os.makedirs(PROFILE, exist_ok=True)
    proc = subprocess.Popen([
        edge, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--remote-debugging-port={PORT}",
        f"--user-data-dir={PROFILE}", "--no-first-run", "--disable-extensions", "--disable-sync",
        "--disable-background-timer-throttling", "--disable-renderer-backgrounding",
        "--disable-backgrounding-occluded-windows", "--window-size=1200,2000", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(100):
        try:
            with opener.open(f"http://127.0.0.1:{PORT}/json", timeout=2) as r:
                pages = [t for t in json.load(r) if t["type"] == "page"]
            if pages:
                return proc, Page(pages[0]["webSocketDebuggerUrl"])
        except OSError:
            pass
        time.sleep(0.2)
    proc.kill()
    raise RuntimeError("Edge did not start")
