"""Minimal tests covering the dedicated server logic."""

from __future__ import annotations

import asyncio
from time import time
import unittest

from server.dedicated_server import Bullet, PlayerState, ShooterServer


class DummyWriter:
    def __init__(self) -> None:
        self.written = []

    def write(self, data: bytes) -> None:
        self.written.append(data)

    async def drain(self) -> None:  # pragma: no cover - trivial
        await asyncio.sleep(0)

    def close(self) -> None:  # pragma: no cover - compatibility
        pass


class ServerLogicTest(unittest.IsolatedAsyncioTestCase):
    async def test_bullet_deals_damage(self) -> None:
        server = ShooterServer("127.0.0.1", 0, "Test", max_players=4)
        reader = asyncio.StreamReader()
        writer = DummyWriter()
        target = PlayerState(reader=reader, writer=writer, name="Target", position=[0.0, 0.0, 0.0], rotation_y=0.0)
        shooter = PlayerState(reader=reader, writer=writer, name="Shooter", position=[5.0, 0.0, 0.0], rotation_y=0.0)
        server.players = {
            "target": target,
            "shooter": shooter,
        }
        bullet = Bullet(
            id="bullet",
            owner_id="shooter",
            position=[0.2, 0.0, 0.0],
            direction=[-1.0, 0.0, 0.0],
            created_at=time(),
        )
        server.bullets = {"bullet": bullet}

        await server._update_bullets(0.01)
        self.assertLess(target.health, 100)
        self.assertNotIn("bullet", server.bullets)
        self.assertTrue(writer.written)


if __name__ == "__main__":  # pragma: no cover - manual execution
    unittest.main()

