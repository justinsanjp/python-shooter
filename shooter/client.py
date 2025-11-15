"""Client entry point for the Python 3D shooter."""

from __future__ import annotations

import sys
from typing import Optional

from ursina import Ursina

from .game import build_game
from .menu import MainMenu
from .network import NetworkClient, ServerInfo


class GameApplication:
    """Wraps the Ursina lifecycle and scene transitions."""

    def __init__(self) -> None:
        self.app = Ursina()
        self.menu: Optional[MainMenu] = None
        self.client: Optional[NetworkClient] = None
        self.game = None
        self._setup_menu()

    def _setup_menu(self) -> None:
        self.menu = MainMenu(self.app, self._start_game)

    def _start_game(self, server_info: ServerInfo, player_name: str) -> None:
        if self.menu:
            self.menu.hide()
        self.client = NetworkClient()
        self.client.connect(server_info.host, server_info.port, player_name)
        self.game = build_game(self.app, self.client, player_name)

        def update():
            self.game.update()

        def input_handler(key: str) -> None:
            self.game.input(key)

        self.app.update = update
        self.app.input = input_handler

    def run(self) -> None:  # pragma: no cover - launches GUI
        self.app.run()


def main() -> int:  # pragma: no cover - CLI entry
    GameApplication().run()
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    sys.exit(main())

