"""Top-level package for the Tanx tank battle game."""

from .game import Game
from .pygame_game import PygameTanx, run_pygame

__all__ = ["Game", "PygameTanx", "run_pygame"]
