"""Shared configuration constants for the shooter project."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class NetworkConfig:
    """Container for network related configuration."""

    host: str = "0.0.0.0"
    game_port: int = int(os.environ.get("SHOOTER_GAME_PORT", 50000))
    discovery_port: int = int(os.environ.get("SHOOTER_DISCOVERY_PORT", 50001))
    tick_rate: int = 30
    max_players: int = 8


NETWORK_CONFIG = NetworkConfig()


PLAYER_RADIUS = 0.8
BULLET_SPEED = 18.0
BULLET_LIFETIME = 3.0
BULLET_DAMAGE = 25
RESPAWN_HEIGHT = 3.0

