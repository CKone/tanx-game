"""Core game logic for Tanx, independent of rendering."""

from .game import Game, ShotResult
from .session import GameSession, ProjectileStep
from .tank import Tank
from .world import TerrainSettings, World

__all__ = [
    "Game",
    "GameSession",
    "ProjectileStep",
    "ShotResult",
    "Tank",
    "TerrainSettings",
    "World",
]
