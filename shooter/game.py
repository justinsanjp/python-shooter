"""Client side game logic using Ursina."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

from ursina import (
    Camera,
    Color,
    DirectionalLight,
    Entity,
    FirstPersonController,
    Sky,
    Text,
    Ursina,
    Vec3,
    camera,
)

from .config import NETWORK_CONFIG, RESPAWN_HEIGHT
from .network import NetworkClient


@dataclass
class RemotePlayer:
    entity: Entity
    name_tag: Text
    health_bar: Entity
    last_seen: float = field(default_factory=lambda: time.time())


class ProjectilePool:
    """Manages projectile entities to reduce allocations."""

    def __init__(self) -> None:
        self._pool: Dict[str, Entity] = {}

    def update_projectiles(self, projectiles: Dict[str, Dict[str, float]]) -> None:
        seen = set(projectiles.keys())
        # Update existing projectiles or create new ones
        for bullet_id, data in projectiles.items():
            entity = self._pool.get(bullet_id)
            if entity is None:
                entity = Entity(model="sphere", scale=0.2, color=Color.yellow)
                self._pool[bullet_id] = entity
            else:
                entity.enable()
            entity.position = Vec3(*data["position"])
        # Remove expired projectiles
        to_remove = [bullet_id for bullet_id in self._pool if bullet_id not in seen]
        for bullet_id in to_remove:
            self._pool[bullet_id].disable()
            del self._pool[bullet_id]


class ShooterGame:
    """Manages the running game scene."""

    def __init__(self, app: Ursina, client: NetworkClient, player_name: str) -> None:
        self.app = app
        self.client = client
        self.player_name = player_name
        self.player: Optional[FirstPersonController] = None
        self.remote_players: Dict[str, RemotePlayer] = {}
        self.projectiles = ProjectilePool()
        self.health = 100
        self.last_state_sent = time.time()
        self.state_interval = 1.0 / NETWORK_CONFIG.tick_rate
        self._setup_scene()

    # ------------------------------------------------------------------
    # Scene setup
    def _setup_scene(self) -> None:
        Sky()
        ground = Entity(model="plane", scale=(40, 1, 40), color=Color.dark_gray)
        ground.collider = "box"

        wall = Entity(model="cube", scale=(10, 5, 1), position=(0, 2.5, 5), color=Color.gray)
        wall.collider = "box"

        DirectionalLight(y=2, z=3, shadows=True)
        Camera.clip_far = 100

        self.player = FirstPersonController(model="cube", scale_y=2, origin_y=-0.5)
        self.player.cursor.enabled = True
        self.player.speed = 7
        self.player.gravity = 0.6
        self.player.jump_height = 2.5
        self.player.position = (0, RESPAWN_HEIGHT, 0)
        self.player.health_bar = Text(text="HP: 100", position=(-0.85, 0.45), origin=(0, 0), parent=camera.ui)

        Text(
            text="WASD to move, Space to jump, Left Click to fire",
            position=(-0.75, -0.45),
            origin=(0, 0),
            color=Color.light_gray,
            parent=camera.ui,
        )

        # Register input events
        self.player.on_destroy = self._shutdown

    # ------------------------------------------------------------------
    def _shutdown(self) -> None:
        self.client.close()

    # ------------------------------------------------------------------
    def update(self) -> None:
        assert self.player is not None
        now = time.time()
        for message in self.client.poll():
            self._handle_message(message)

        if now - self.last_state_sent >= self.state_interval:
            self._send_state()
            self.last_state_sent = now

        if self.player.position.y < -20:
            self.player.position = (0, RESPAWN_HEIGHT, 0)

    # ------------------------------------------------------------------
    def input(self, key: str) -> None:  # pragma: no cover - direct event
        if key == "left mouse down":
            self._fire_weapon()

    # ------------------------------------------------------------------
    def _fire_weapon(self) -> None:
        assert self.player is not None
        cam_forward = Vec3(
            math.sin(math.radians(self.player.camera_pivot.rotation_y)),
            0,
            math.cos(math.radians(self.player.camera_pivot.rotation_y)),
        )
        origin = self.player.position + Vec3(0, 1.5, 0) + cam_forward * 0.5
        direction = cam_forward.normalized()
        self.client.send(
            {
                "type": "shoot",
                "origin": [origin.x, origin.y, origin.z],
                "direction": [direction.x, direction.y, direction.z],
            }
        )
        # Audio assets were removed; hook left for future sound integration.

    # ------------------------------------------------------------------
    def _send_state(self) -> None:
        assert self.player is not None
        rotation_y = self.player.camera_pivot.rotation_y
        self.client.send(
            {
                "type": "state",
                "position": [self.player.position.x, self.player.position.y, self.player.position.z],
                "rotation_y": rotation_y,
                "health": self.health,
            }
        )

    # ------------------------------------------------------------------
    def _handle_message(self, message: dict) -> None:
        msg_type = message.get("type")
        if msg_type == "world_state":
            self._update_world(message)
        elif msg_type == "damage":
            amount = message.get("amount", 0)
            self.health = max(0, self.health - amount)
            if self.health <= 0:
                self.player.position = (0, RESPAWN_HEIGHT, 0)
                self.health = 100
            self.player.health_bar.text = f"HP: {self.health}"
        elif msg_type == "welcome":
            # Already handled when polled; update HUD name
            if self.player:
                self.player.health_bar.text = f"HP: {self.health}"

    # ------------------------------------------------------------------
    def _update_world(self, message: dict) -> None:
        players = message.get("players", [])
        assert self.player is not None
        my_id = self.client.player_id
        for player_data in players:
            player_id = player_data["id"]
            if player_id == my_id:
                continue
            remote = self.remote_players.get(player_id)
            if remote is None:
                entity = Entity(model="cube", color=Color.azure, scale_y=2, origin_y=-0.5)
                entity.collider = "box"
                name_tag = Text(text=player_data["name"], world_parent=entity, position=(0, 1.6, 0))
                health_bar = Entity(parent=entity, model="cube", color=Color.red, scale=(0.5, 0.05, 0.05), position=(0, 1.4, 0))
                remote = RemotePlayer(entity=entity, name_tag=name_tag, health_bar=health_bar)
                self.remote_players[player_id] = remote
            entity = remote.entity
            entity.position = Vec3(*player_data["position"])
            entity.rotation_y = player_data.get("rotation_y", 0)
            health = player_data.get("health", 100)
            remote.health_bar.scale_x = max(0.1, health / 100 * 0.5)
            remote.last_seen = time.time()

        # Remove stale players
        stale_ids = [player_id for player_id, remote in self.remote_players.items() if time.time() - remote.last_seen > 5]
        for player_id in stale_ids:
            remote = self.remote_players[player_id]
            remote.entity.disable()
            remote.name_tag.disable()
            del self.remote_players[player_id]

        projectile_data = {
            proj["id"]: proj for proj in message.get("projectiles", [])
        }
        self.projectiles.update_projectiles(projectile_data)


def build_game(app: Ursina, client: NetworkClient, player_name: str) -> ShooterGame:
    return ShooterGame(app, client, player_name)

