# Python Shooter

A lightweight LAN-focused 3D first-person shooter written in Python using [Ursina](https://www.ursinaengine.org/).

## Features

- Fast main menu with automatic LAN server discovery.
- Dedicated authoritative server that simulates player state and projectiles.
- Multiplayer arena with hitscan-like projectile handling and health tracking.
- HUD for player feedback.

## Getting Started

### Prerequisites

- Python 3.10+
- A GPU capable of running Panda3D/Ursina applications.

Install the Python dependencies:

```bash
pip install -r requirements.txt
```

### Running the Dedicated Server

```bash
python -m server.dedicated_server --host 0.0.0.0 --port 50000 --name "My Python Server"
```

The server automatically answers LAN discovery requests so it will appear in the in-game server browser.

### Running the Game Client

```bash
python -m shooter.client
```

From the menu choose a player name, refresh the LAN server list, and join a server.

## Project Layout

```
shooter/               # Client and menu implementation
server/                # Dedicated server entry point
tests/                 # Automated tests for the server logic
```

## Testing

Run the asynchronous unit test suite:

```bash
python -m unittest discover tests
```

## Notes

- The networking stack is intentionally lightweight and designed for LAN play.
- Projectiles and player health are simulated on the server for fairness; clients only send state updates and actions.
- The discovery protocol is UDP broadcast based and will automatically discover servers running on the same local network.

