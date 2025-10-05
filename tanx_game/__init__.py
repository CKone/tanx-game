"""Top-level package for the Tanx tank battle game."""

from .core import (
    Game,
    GameSession,
    ProjectileStep,
    ShotResult,
    Tank,
    TerrainSettings,
    World,
)
from .pygame import PygameTanx, run_pygame

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
