"""Control server (JSON lines over TCP) + asset server (HTTP) for the UE5 client.

Control message: one JSON object per line, {"v": 1, "type": ..., "id": ..., ...}; replies echo "id".
  hello {}                          -> {type: "hello", protocol, server}
  register/login {user, password}   -> {type: "session", token, profile}   (register creates the account)
  profile {}                        -> {type: "profile", profile}            (needs login)
  asset_info {kind, did, fmt}       -> {type: "asset_info", url, fmt}        (needs login)
Assets: GET /asset/<kind>/<did hex>.<fmt> with header X-Token (or ?t=token).
"""
import hashlib
import hmac
import json
import os
import secrets
import socketserver
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .assets import AssetStore


class Accounts:
    def __init__(self, path):
        self.path, self.lock = path, threading.Lock()
        self.data = {}
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                self.data = json.load(f)

    def _save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=1)

    @staticmethod
    def _hash(password, salt):
        return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 120000).hex()

    def register(self, user, password):
        with self.lock:
            if not user or len(password or "") < 4 or user.lower() in self.data:
                return None
            salt = secrets.token_hex(16)
            self.data[user.lower()] = {"name": user, "salt": salt, "hash": self._hash(password, salt),
                                       "created": int(time.time()), "level": 30}
            self._save()
            return self.data[user.lower()]

    def check(self, user, password):
        acc = self.data.get((user or "").lower())
        if acc and hmac.compare_digest(acc["hash"], self._hash(password or "", acc["salt"])):
            return acc
        return None


class Server:
    def __init__(self, cfg):
        u = cfg["uesrv"]
        self.cfg, self.u = cfg, u
        self.accounts = Accounts(cfg.resolve(u["accounts"]))
        self.assets = AssetStore(os.path.join(cfg.game_dir, "rp"), cfg.resolve(u["cache_dir"]))
        self.tokens = {}          # token -> account key
        self.control = self.http = None

    def profile(self, acc):
        return {"name": acc["name"], "level": acc.get("level", 30)}

    def start(self):
        srv, host = self, self.u["host"]

        class Control(socketserver.StreamRequestHandler):
            def handle(self):
                token = None
                for line in self.rfile:
                    msg = {}
                    try:
                        msg = json.loads(line)
                        reply = srv.dispatch(msg, token)
                    except Exception as e:      # bad JSON etc.: report and keep the connection
                        reply = {"type": "error", "error": "bad_request", "detail": str(e)}
                    if reply.get("type") == "session":
                        token = reply["token"]
                    reply.update(v=srv.u["protocol"], id=msg.get("id") if isinstance(msg, dict) else None)
                    self.wfile.write((json.dumps(reply) + "\n").encode())

        class Http(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                path, _, query = self.path.partition("?")
                token = self.headers.get("X-Token") or dict(
                    p.split("=", 1) for p in query.split("&") if "=" in p).get("t")
                if token not in srv.tokens:
                    return self.send_error(401)
                try:
                    parts = path.strip("/").split("/")
                    kind, (name, _, fmt) = parts[1], parts[2].partition(".")
                    res = parts[0] == "asset" and srv.assets.get(kind, int(name, 16), fmt)
                except (IndexError, ValueError):
                    return self.send_error(400)
                if not res:
                    return self.send_error(404)
                body, ctype = res
                etag = '"%s"' % srv.assets.etag(body)
                if self.headers.get("If-None-Match") == etag:
                    self.send_response(304)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("ETag", etag)
                self.end_headers()
                self.wfile.write(body)

        socketserver.ThreadingTCPServer.allow_reuse_address = True
        self.control = socketserver.ThreadingTCPServer((host, self.u["control_port"]), Control)
        self.http = ThreadingHTTPServer((host, self.u["asset_port"]), Http)
        self.control.daemon_threads = self.http.daemon_threads = True
        for s in (self.control, self.http):
            threading.Thread(target=s.serve_forever, daemon=True).start()

    def stop(self):
        for s in (self.control, self.http):
            if s:
                s.shutdown()
                s.server_close()

    def dispatch(self, msg, token):
        t = msg.get("type")
        if t == "hello":
            return {"type": "hello", "protocol": self.u["protocol"], "server": "uesrv"}
        if t in ("register", "login"):
            acc = (self.accounts.register if t == "register" else self.accounts.check)(
                msg.get("user"), msg.get("password"))
            if not acc:
                return {"type": "error", "error": "register_failed" if t == "register" else "login_failed"}
            tok = secrets.token_hex(16)
            self.tokens[tok] = acc["name"].lower()
            return {"type": "session", "token": tok, "profile": self.profile(acc)}
        if token not in self.tokens:
            return {"type": "error", "error": "not_logged_in"}
        acc = self.accounts.data[self.tokens[token]]
        if t == "profile":
            return {"type": "profile", "profile": self.profile(acc)}
        if t == "asset_info":
            kind, fmt = msg.get("kind"), msg.get("fmt", "png")
            did = int(msg.get("did"))
            return {"type": "asset_info", "url": "http://%s:%d/asset/%s/%08x.%s" % (
                self.u["host"], self.u["asset_port"], kind, did, fmt), "fmt": fmt}
        return {"type": "error", "error": "unknown_type"}
