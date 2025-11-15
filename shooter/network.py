"""Networking utilities for the shooter game."""

from __future__ import annotations

import json
import queue
import socket
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from .config import NETWORK_CONFIG


@dataclass
class ServerInfo:
    """Simple data container for discovered servers."""

    name: str
    host: str
    port: int
    players: int
    max_players: int


class DiscoveryClient:
    """Discovers LAN servers via UDP broadcast."""

    def __init__(self, timeout: float = 1.5) -> None:
        self.timeout = timeout

    def scan(self) -> List[ServerInfo]:
        message = b"DISCOVER\n"
        servers: Dict[str, ServerInfo] = {}
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(self.timeout)
        try:
            sock.sendto(message, ("<broadcast>", NETWORK_CONFIG.discovery_port))
            start = time.time()
            while time.time() - start < self.timeout:
                try:
                    data, addr = sock.recvfrom(1024)
                except socket.timeout:
                    break
                parts = data.decode("utf8").strip().split()
                if len(parts) != 5 or parts[0] != "SERVER":
                    continue
                _, name, port, players, max_players = parts
                servers[addr[0]] = ServerInfo(
                    name=name,
                    host=addr[0],
                    port=int(port),
                    players=int(players),
                    max_players=int(max_players),
                )
        finally:
            sock.close()
        return list(servers.values())


class NetworkClient:
    """Thread-based TCP client that communicates using JSON lines."""

    def __init__(self) -> None:
        self._socket: Optional[socket.socket] = None
        self._receiver: Optional[threading.Thread] = None
        self._messages: "queue.Queue[dict]" = queue.Queue()
        self._running = threading.Event()
        self._running.clear()
        self.player_id: Optional[str] = None

    def connect(self, host: str, port: int, name: str) -> None:
        if self._socket:
            raise RuntimeError("Client already connected")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        self._socket = sock
        self._running.set()
        self._receiver = threading.Thread(target=self._receive_loop, daemon=True)
        self._receiver.start()
        self.send({"type": "join", "name": name})

    def close(self) -> None:
        self._running.clear()
        if self._socket:
            try:
                self._socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self._socket.close()
        self._socket = None

    def _receive_loop(self) -> None:
        assert self._socket is not None
        buffer = b""
        sock = self._socket
        while self._running.is_set():
            try:
                chunk = sock.recv(4096)
            except OSError:
                break
            if not chunk:
                break
            buffer += chunk
            while b"\n" in buffer:
                raw, buffer = buffer.split(b"\n", 1)
                if not raw:
                    continue
                try:
                    message = json.loads(raw.decode("utf8"))
                except json.JSONDecodeError:
                    continue
                if message.get("type") == "welcome":
                    self.player_id = message.get("player_id")
                self._messages.put(message)
        self._running.clear()

    def send(self, payload: dict) -> None:
        if not self._socket:
            raise RuntimeError("Not connected")
        data = (json.dumps(payload) + "\n").encode("utf8")
        try:
            self._socket.sendall(data)
        except OSError as exc:
            raise RuntimeError("Failed to send data") from exc

    def poll(self) -> Iterable[dict]:
        """Yield all pending messages."""

        while True:
            try:
                yield self._messages.get_nowait()
            except queue.Empty:
                break


def generate_player_id() -> str:
    return uuid.uuid4().hex

