"""Top-level package for the Tanx tank battle game."""

from tanx_game.core import (
    Game,
    GameSession,
    ProjectileStep,
    ShotResult,
    Tank,
    TerrainSettings,
    World,
)
from tanx_game.pygame import PygameTanx, run_pygame

__all__ = [
    "Game",
    "GameSession",
    "ProjectileStep",
    "ShotResult",
    "Tank",
    "TerrainSettings",
    "World",
    "PygameTanx",
    "run_pygame",
]
