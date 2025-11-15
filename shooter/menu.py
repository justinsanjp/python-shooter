"""Main menu and server browser for the shooter game."""

from __future__ import annotations

from typing import Callable, Optional

from ursina import Button, Color, Entity, InputField, Text, Ursina

from .network import DiscoveryClient, ServerInfo


class ServerEntry(Entity):
    """Represents a single server entry in the browser."""

    def __init__(self, server_info: ServerInfo, on_join: Callable[[ServerInfo], None], y: float) -> None:
        super().__init__()
        label = f"{server_info.name} - {server_info.players}/{server_info.max_players} players"
        self.button = Button(
            text=label,
            color=Color.gray,
            origin=(-0.5, 0),
            position=(-0.45, y),
            scale=(0.9, 0.08),
            on_click=lambda: on_join(server_info),
            parent=self,
        )

    def disable(self) -> None:  # pragma: no cover - UI cleanup
        self.button.disable()
        super().disable()


class MainMenu:
    """Main menu flow controller."""

    def __init__(self, app: Ursina, on_start_game: Callable[[ServerInfo, str], None]) -> None:
        self.app = app
        self.discovery = DiscoveryClient()
        self.on_start_game = on_start_game
        self._active_entries: list[ServerEntry] = []
        self.empty_label: Optional[Text] = None
        self.root = Entity()
        self.title = Text(text="Python 3D Shooter", scale=2, position=(-0.25, 0.45), parent=self.root)
        self.name_field = InputField(default_value="Player", limit=16, position=(-0.3, 0.2), scale=(0.6, 0.07), parent=self.root)
        self.refresh_button = Button(
            text="Refresh Servers",
            position=(-0.3, 0.1),
            scale=(0.6, 0.08),
            color=Color.azure,
            on_click=self.refresh_servers,
            parent=self.root,
        )
        self.quit_button = Button(
            text="Quit",
            position=(-0.3, -0.4),
            scale=(0.6, 0.08),
            color=Color.red,
            on_click=app.quit,
            parent=self.root,
        )
        self._server_list_origin = 0.0
        self.server_label = Text(text="Servers:", position=(-0.95, 0.05), parent=self.root)
        self.refresh_servers()

    def refresh_servers(self) -> None:
        if self.empty_label:
            self.empty_label.disable()
            self.empty_label = None
        for entry in self._active_entries:
            entry.disable()
        self._active_entries.clear()
        servers = self.discovery.scan()
        y = -0.05
        if not servers:
            self.empty_label = Text(
                text="No servers found",
                position=(-0.45, -0.05),
                origin=(-0.5, 0),
                color=Color.light_gray,
                parent=self.root,
            )
            return
        for server in servers:
            entry = ServerEntry(server, self._join_server, y)
            self._active_entries.append(entry)
            y -= 0.09

    def _join_server(self, server_info: ServerInfo) -> None:
        name = self.name_field.text.strip() or "Player"
        self.on_start_game(server_info, name)

    def hide(self) -> None:
        for entry in self._active_entries:
            entry.disable()
        self.name_field.disable()
        self.refresh_button.disable()
        self.quit_button.disable()
        self.server_label.disable()
        self.title.disable()
        if self.empty_label:
            self.empty_label.disable()


__all__ = ["MainMenu"]

