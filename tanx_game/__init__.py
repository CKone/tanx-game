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

__all__ = [
    "Game",
    "GameSession",
    "ProjectileStep",
    "ShotResult",
    "Tank",
    "TerrainSettings",
    "World",
]

try:
    from tanx_game.pygame import PygameTanx, run_pygame  # type: ignore[misc]
except (ImportError, RuntimeError):
    PygameTanx = None

    def run_pygame(*_args, **_kwargs):  # type: ignore[override]
        raise RuntimeError(
            "The pygame front-end requires the optional pygame dependency. "
            "Install pygame to enable graphical gameplay."
        )

    __all__.extend(["PygameTanx", "run_pygame"])
else:
    __all__.extend(["PygameTanx", "run_pygame"])
