from __future__ import annotations

import math

import hypothesis.strategies as st
import pytest
from hypothesis import assume, given, settings

from tanx_game.core.game import Game
from tanx_game.core.world import TerrainSettings


@pytest.mark.property
@settings(max_examples=25, deadline=None)
@given(
    width=st.integers(min_value=24, max_value=64),
    height=st.integers(min_value=24, max_value=48),
    min_height_base=st.integers(min_value=6, max_value=24),
    max_height_offset=st.integers(min_value=1, max_value=10),
    smoothing=st.integers(min_value=0, max_value=6),
    detail=st.integers(min_value=4, max_value=8),
    seed=st.integers(min_value=0, max_value=5_000),
    style=st.sampled_from(["classic", "urban"]),
)
def test_spawn_positions_are_valid(
    width: int,
    height: int,
    min_height_base: int,
    max_height_offset: int,
    smoothing: int,
    detail: int,
    seed: int,
    style: str,
) -> None:
    """Ensure procedurally generated worlds always spawn tanks on solid ground."""

    min_height = float(min(min_height_base, height - 3))
    max_candidate = min_height + max_height_offset
    max_upper_bound = float(min(height - 2, math.ceil(max_candidate)))
    assume(max_upper_bound > min_height)

    terrain_settings = TerrainSettings(
        width=width,
        height=height,
        min_height=min_height,
        max_height=max_upper_bound,
        smoothing=smoothing,
        detail=detail,
        seed=seed,
        style=style,
    )

    game = Game(settings=terrain_settings, seed=seed)
    world = game.world

    for tank in game.tanks:
        assert 0 <= tank.x < world.width
        surface = world.surface_y(tank.x)
        assert surface is not None, f"No surface found beneath {tank.name} at column {tank.x}"
        assert surface == tank.y, f"{tank.name} stands at {tank.y} but surface is {surface}"
        assert not world.is_column_blocked(tank.x), f"{tank.name} spawned inside a blocked column"

    left, right = game.tanks
    assert left.x < right.x, "Tanks should face each other from distinct positions"
