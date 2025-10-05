from tanx_game.core.game import Game


def test_step_projectile_direct_hit(flat_settings):
    game = Game(settings=flat_settings)
    shooter, target = game.tanks

    # Position tanks on level terrain for a predictable shot
    shooter.x = 4
    shooter_surface = game.world.surface_y(shooter.x)
    assert shooter_surface is not None
    shooter.y = shooter_surface
    shooter.facing = 1

    target.x = 8
    target_surface = game.world.surface_y(target.x)
    assert target_surface is not None
    target.y = target_surface
    target.facing = -1
    target.hp = 100

    game.gravity = 0.0
    shooter.turret_angle = 0
    shooter.shot_power = 0.6

    result = game.step_projectile(shooter)

    assert result.hit_tank is target
    assert target.hp == 75
    assert result.fatal_hit is False
