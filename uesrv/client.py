"""Minimal Python client for the control + asset protocols (also the reference for the UE5 client)."""
import json
import socket
import urllib.request


class Client:
    def __init__(self, host, control_port):
        self.sock = socket.create_connection((host, control_port), timeout=30)
        self.f = self.sock.makefile("rwb")
        self.n = 0
        self.token = None

    def call(self, type_, **kw):
        self.n += 1
        self.f.write((json.dumps(dict(kw, type=type_, id=self.n, v=1)) + "\n").encode())
        self.f.flush()
        return json.loads(self.f.readline())

    def login(self, user, password, register=False):
        r = self.call("register" if register else "login", user=user, password=password)
        self.token = r.get("token")
        return r

    def fetch_asset(self, kind, did, fmt="png"):
        info = self.call("asset_info", kind=kind, did=did, fmt=fmt)
        req = urllib.request.Request(info["url"], headers={"X-Token": self.token})
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.read()

    def close(self):
        self.sock.close()
