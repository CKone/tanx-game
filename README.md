# Tanx - Arcade Tank Duel

Tanx is a minimalist two-player artillery duel that now plays out in a shiny
pygame-powered window. Two tanks face off on a procedurally generated,
destructible landscape. Take turns to move, adjust your turret, and fire shells
until your opponent reaches zero health.

## Requirements

* Python 3.9+
* `pygame` (install with `pip install pygame`)

## Running the Game

```bash
python main.py
```

A window will open with the battlefield and UI overlay.

## Controls

* Player 1 – `A`/`D` move, `W`/`S` aim, `Space` fire.
* Player 2 – `←`/`→` move, `↑`/`↓` aim, `Enter` fire.
* `Esc` or `Q` – exit the match.
* After a victory, `R` restarts the duel.

Direct hits remove 25 hit points from the target tank. Near misses chip away at
health and reshape the terrain. First tank to reach zero hit points loses.
