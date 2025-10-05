import pytest

from tanx_game.core.world import TerrainSettings, World


@pytest.fixture
def flat_settings() -> TerrainSettings:
    """Provide deterministic flat terrain for gameplay tests."""

    return TerrainSettings(
        width=24,
        height=24,
        min_height=12.0,
        max_height=12.0,
        detail=4,
        smoothing=0,
        seed=1234,
    )


@pytest.fixture
def flat_world(flat_settings: TerrainSettings) -> World:
    return World(flat_settings)
