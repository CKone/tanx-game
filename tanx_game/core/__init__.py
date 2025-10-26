"""Core game logic for Tanx, independent of rendering."""

from tanx_game.core.game import Game, ShotResult
from tanx_game.core.session import GameSession, ProjectileStep
from tanx_game.core.tank import Tank
from tanx_game.core.world import (
    Building,
    BuildingFloor,
    RubbleSegment,
    TerrainSettings,
    World,
)

__all__ = [
    "Game",
    "GameSession",
    "ProjectileStep",
    "ShotResult",
    "Tank",
    "TerrainSettings",
    "World",
    "Building",
    "BuildingFloor",
    "RubbleSegment",
]
