from tanx_game.core.tank import Tank


def test_move_within_bounds(flat_world):
    surface = flat_world.surface_y(5)
    assert surface is not None

    tank = Tank(name="Alpha", x=5, y=surface, facing=1)

    moved = tank.move(flat_world, 1)

    assert moved is True
    assert tank.x == 6
    assert tank.y == flat_world.surface_y(6)


def test_move_blocked_when_out_of_bounds(flat_world):
    surface = flat_world.surface_y(0)
    assert surface is not None

    tank = Tank(name="Bravo", x=0, y=surface, facing=-1)

    moved = tank.move(flat_world, -1)

    assert moved is False
    assert tank.x == 0
    assert tank.y == surface
