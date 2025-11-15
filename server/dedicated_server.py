"""Dedicated server for the Python shooter game."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import socket
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional

from shooter.config import (
    BULLET_DAMAGE,
    BULLET_LIFETIME,
    BULLET_SPEED,
    NETWORK_CONFIG,
    PLAYER_RADIUS,
    RESPAWN_HEIGHT,
)

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s:%(name)s: %(message)s")
LOGGER = logging.getLogger("dedicated_server")


@dataclass
class PlayerState:
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    name: str
    position: list[float]
    rotation_y: float
    health: int = 100
    last_update: float = field(default_factory=time.time)


@dataclass
class Bullet:
    id: str
    owner_id: str
    position: list[float]
    direction: list[float]
    created_at: float


class ShooterServer:
    def __init__(self, host: str, port: int, name: str, max_players: int) -> None:
        self.host = host
        self.port = port
        self.name = name
        self.max_players = max_players
        self.players: Dict[str, PlayerState] = {}
        self.bullets: Dict[str, Bullet] = {}
        self._server: Optional[asyncio.base_events.Server] = None
        self._discovery_socket: Optional[socket.socket] = None
        self._running = False

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._handle_client, self.host, self.port)
        LOGGER.info("Server started on %s:%s", self.host, self.port)
        self._running = True
        asyncio.create_task(self._world_tick())
        asyncio.create_task(self._discovery_loop())

    async def stop(self) -> None:
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        if self._discovery_socket:
            self._discovery_socket.close()

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        addr = writer.get_extra_info("peername")
        player_id: Optional[str] = None
        LOGGER.info("Client connected from %s", addr)
        try:
            while data := await reader.readline():
                try:
                    message = json.loads(data.decode("utf8"))
                except json.JSONDecodeError:
                    continue
                msg_type = message.get("type")
                if msg_type == "join":
                    if len(self.players) >= self.max_players:
                        writer.write((json.dumps({"type": "error", "message": "Server full"}) + "\n").encode("utf8"))
                        await writer.drain()
                        break
                    player_id = uuid.uuid4().hex
                    name = message.get("name", "Player")
                    state = PlayerState(
                        reader=reader,
                        writer=writer,
                        name=name,
                        position=[0.0, RESPAWN_HEIGHT, 0.0],
                        rotation_y=0.0,
                    )
                    self.players[player_id] = state
                    LOGGER.info("Player %s joined as %s", player_id, name)
                    writer.write((json.dumps({"type": "welcome", "player_id": player_id}) + "\n").encode("utf8"))
                    await writer.drain()
                elif msg_type == "state" and player_id:
                    state = self.players.get(player_id)
                    if not state:
                        continue
                    state.position = message.get("position", state.position)
                    state.rotation_y = message.get("rotation_y", state.rotation_y)
                    state.health = message.get("health", state.health)
                    state.last_update = time.time()
                elif msg_type == "shoot" and player_id:
                    origin = message.get("origin")
                    direction = message.get("direction")
                    if origin and direction:
                        bullet_id = uuid.uuid4().hex
                        self.bullets[bullet_id] = Bullet(
                            id=bullet_id,
                            owner_id=player_id,
                            position=list(origin),
                            direction=list(direction),
                            created_at=time.time(),
                        )
        except ConnectionResetError:
            LOGGER.warning("Connection reset by %s", addr)
        finally:
            if player_id and player_id in self.players:
                LOGGER.info("Player %s disconnected", player_id)
                del self.players[player_id]
            writer.close()
            await writer.wait_closed()

    async def _world_tick(self) -> None:
        tick_interval = 1.0 / NETWORK_CONFIG.tick_rate
        while self._running:
            start = time.time()
            await self._update_bullets(tick_interval)
            await self._broadcast_state()
            elapsed = time.time() - start
            await asyncio.sleep(max(0.0, tick_interval - elapsed))

    async def _update_bullets(self, dt: float) -> None:
        to_remove = []
        for bullet_id, bullet in list(self.bullets.items()):
            bullet.position[0] += bullet.direction[0] * BULLET_SPEED * dt
            bullet.position[1] += bullet.direction[1] * BULLET_SPEED * dt
            bullet.position[2] += bullet.direction[2] * BULLET_SPEED * dt
            if time.time() - bullet.created_at > BULLET_LIFETIME:
                to_remove.append(bullet_id)
                continue
            for pid, player in self.players.items():
                if pid == bullet.owner_id:
                    continue
                if _distance_sq(bullet.position, player.position) <= PLAYER_RADIUS ** 2:
                    player.health -= BULLET_DAMAGE
                    LOGGER.info("Player %s hit for %s", pid, BULLET_DAMAGE)
                    await self._send_message(player.writer, {"type": "damage", "amount": BULLET_DAMAGE})
                    if player.health <= 0:
                        player.position = [0.0, RESPAWN_HEIGHT, 0.0]
                        player.health = 100
                    to_remove.append(bullet_id)
                    break
        for bullet_id in to_remove:
            self.bullets.pop(bullet_id, None)

    async def _broadcast_state(self) -> None:
        payload = {
            "type": "world_state",
            "players": [
                {
                    "id": pid,
                    "name": player.name,
                    "position": player.position,
                    "rotation_y": player.rotation_y,
                    "health": player.health,
                }
                for pid, player in self.players.items()
            ],
            "projectiles": [
                {"id": bullet.id, "position": bullet.position} for bullet in self.bullets.values()
            ],
        }
        message = (json.dumps(payload) + "\n").encode("utf8")
        for player in list(self.players.values()):
            try:
                player.writer.write(message)
                await player.writer.drain()
            except ConnectionResetError:
                continue

    async def _send_message(self, writer: asyncio.StreamWriter, payload: dict) -> None:
        writer.write((json.dumps(payload) + "\n").encode("utf8"))
        await writer.drain()

    async def _discovery_loop(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", NETWORK_CONFIG.discovery_port))
        self._discovery_socket = sock
        LOGGER.info("Discovery service listening on %s", NETWORK_CONFIG.discovery_port)
        loop = asyncio.get_running_loop()
        while self._running:
            data, addr = await loop.run_in_executor(None, sock.recvfrom, 512)
            if data.strip() == b"DISCOVER":
                response = f"SERVER {self.name} {self.port} {len(self.players)} {self.max_players}\n"
                sock.sendto(response.encode("utf8"), addr)


def _distance_sq(a: list[float], b: list[float]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Python Shooter dedicated server")
    parser.add_argument("--host", default=NETWORK_CONFIG.host)
    parser.add_argument("--port", type=int, default=NETWORK_CONFIG.game_port)
    parser.add_argument("--name", default="Python Server")
    parser.add_argument("--max-players", type=int, default=NETWORK_CONFIG.max_players)
    return parser.parse_args()


async def _async_main() -> None:
    args = parse_args()
    server = ShooterServer(args.host, args.port, args.name, args.max_players)
    await server.start()
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        LOGGER.info("Stopping server...")
        await server.stop()


def main() -> None:  # pragma: no cover - CLI entry
    asyncio.run(_async_main())


if __name__ == "__main__":  # pragma: no cover - CLI entry
    main()

