# Tanx - Arcade Tank Duel

Tanx is a minimalist two-player artillery duel that now plays out in a shiny
pygame-powered window. Two tanks face off on a procedurally generated,
destructible landscape. Take turns to move, adjust your turret, and fire shells
until your opponent reaches zero health.

### Quick Feature Highlights

* Weather-aware battlefields (clear skies, rain, snowfall) with parallax skyline and moving clouds.
* Fully destructible urban structures that collapse into physics-driven rubble and persistent smoke.
* Enhanced tank presentation: suspension bounce, turret recoil, muzzle flashes, and camera shake.
* Audio-ready engine with configurable volume buckets, ambient loops, and impact SFX triggers.

## Requirements

* Python 3.9+
* `pygame` (install with `pip install pygame`)

## Running the Game

```bash
python main.py
```

To enable the optional cheat console:

```bash
python main.py --cheat
```

A window will open with the battlefield and UI overlay.

### Audio Troubleshooting

Tanx now cycles through common SDL audio backends on startup (PulseAudio, PipeWire, ALSA, CoreAudio, DirectSound, WASAPI, WinMM, and finally the silent `dummy` fallback). If no real device is available, the main menu displays a warning and the mixer runs silently.

To explicitly select a backend, launch with `SDL_AUDIODRIVER` set, e.g.:

```bash
SDL_AUDIODRIVER=pulse python main.py
```

Once a working device appears, the client retries automatically and clears the warning; reconnecting a headset is usually enough.

## Controls

* Player 1 – `A`/`D` move, `W`/`S` aim, `Space` fire, `Q`/`E` tweak shot power.
* Player 2 – `←`/`→` move, `↑`/`↓` aim, `Enter` fire, `[`/`]` tweak shot power.
* `Esc` – exit the match.
* After a victory, `R` restarts the duel.
* With `--cheat`, press `F1` for the cheat console (`1`/`2` detonate Player 1/2).

Direct hits remove 25 hit points from the target tank. Near misses chip away at
health and reshape the terrain. Use the power keys to dial in muzzle velocity so
shells follow graceful ballistic arcs to the target. First tank to reach zero
hit points loses.
