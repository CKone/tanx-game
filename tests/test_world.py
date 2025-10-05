from tanx_game.core.world import World


def test_surface_aligns_with_solid_cells(flat_world: World):
    x = 7
    surface = flat_world.surface_y(x)
    assert surface is not None

    assert flat_world.is_solid(x, surface) is False
    assert flat_world.is_solid(x, surface + 1) is True


def test_sample_sdf_signs(flat_world: World):
    x = 4
    surface = flat_world.surface_y(x)
    assert surface is not None

    assert flat_world.sample_sdf(x + 0.25, surface - 2) > 0
    assert flat_world.sample_sdf(x + 0.25, surface + 2) < 0
