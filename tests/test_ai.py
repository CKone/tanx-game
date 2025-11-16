import math

from tanx_game.core.game import Game
from tanx_game.core.world import TerrainSettings
from tanx_game.pygame.ai import ShotPlanner


def _flat_settings() -> TerrainSettings:
    return TerrainSettings(
        width=36,
        height=24,
        min_height=12.0,
        max_height=12.0,
        smoothing=0,
        detail=4,
        seed=2025,
    )


def test_shot_planner_finds_reasonable_solution() -> None:
    game = Game("Alpha", "Bravo", _flat_settings(), seed=2025)
    planner = ShotPlanner(angle_step=4, power_step=0.05, humanize=False)
    shooter = game.tanks[1]
    target = game.tanks[0]
    original_angle = shooter.turret_angle
    original_power = shooter.shot_power

    plan = planner.find_best_shot(game, shooter, [target])

    assert plan is not None, "Planner should find at least one candidate"
    assert shooter.turret_angle == original_angle
    assert math.isclose(shooter.shot_power, original_power)
    prediction = plan.prediction
    if prediction.hit_tank is target:
        assert plan.confidence >= 0.9
    else:
        assert prediction.impact_x is not None and prediction.impact_y is not None
        distance = math.hypot(target.x - prediction.impact_x, target.y - prediction.impact_y)
        assert distance < 8.0


def test_shot_planner_returns_none_without_targets() -> None:
    game = Game("Alpha", "Bravo", _flat_settings(), seed=2025)
    planner = ShotPlanner(humanize=False)
    shooter = game.tanks[1]

    plan = planner.find_best_shot(game, shooter, [])

    assert plan is None
