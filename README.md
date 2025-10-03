# Tanx - Text-Based Tank Duel

Tanx is a minimalist two-player artillery duel played in the terminal. Two tanks
face off on a procedurally generated, destructible landscape. Take turns to move,
adjust your turret, and fire shells until your opponent reaches zero health.

## Requirements

* Python 3.9+

## Running the Game

```bash
python main.py
```

The game starts immediately and prompts each player for commands on their turns.

## Controls

* `left` / `right` – drive the tank horizontally.
* `up` / `down` – tilt the turret up or down.
* `fire` – launch a shell at your opponent.
* `status` – display tank information.
* `help` – show the list of commands.
* `quit` – exit the game early.

Direct hits remove 25 hit points from the target tank. Near misses chip away at
health and reshape the terrain. First tank to reach zero hit points loses.

