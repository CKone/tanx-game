# Audio, UX, and Testing Roadmap

## Audio Upgrade

- **SFX Palette**
  - Explosions: layered low-end boom + metallic shrapnel transient (multiple variants to avoid repetition).
  - Terrain/rubble impacts: short debris clatter and dirt puff.
  - Superpowers: bomber fly-over loop, whistle and detonation sequence, squad volley burst.
  - UI feedback: menu move/confirm/cancel, weather toggle, match end sting.
  - Ambient loops per weather: subtle wind, rain patter, distant city hum.

- **Implementation Notes**
  - Use `pygame.mixer` with 44.1 kHz stereo; keep channels pooled to avoid clipping.
  - Soundscape manager now wraps mixer with category-aware playback and ambient loops; extend with ducking and cross-fades.
  - Procedural placeholder tones cover missing assets so CI and local dev can exercise the mixer without shipping heavy files.
  - Allow weather + match style to influence mix (e.g., rain muffles high frequencies, urban adds distant sirens).
  - Add settings menu sliders for master/SFX/ambient volume plus a mute toggle persisted in user settings.
  - Settings menu options now respond to ←/→ for per-category volume adjustments and play UI navigation audio cues.

## UX Enhancements

- Settings copy already includes map/weather descriptions; extend Options with:
  - `Weather` selector (done) and `Audio` sliders (pending).
  - Quick help overlay explaining new destructible cover/controls.
  - Post-round highlight reel prompt (optional screenshot key binding).

## Testing Strategy

- **Automated**
  - Extend unit tests (pytest) to cover weather persistence, skyline state regeneration, and smoke/rubble decay functions.
  - Build snapshot-based regression check using headless pygame + `pygame.surfarray` to compare hash of critical frames (tolerance-based to allow minor pixel drift).
  - Audio smoke test: instantiate `Soundscape`, load stub WAV, verify volume and channel management without emitting sound in CI (use dummy audio driver). ✅ Placeholder-tone coverage landed in `tests/test_soundscape.py`.

- **Manual QA Checklist**
  - Validate audio mix at different weather states and during simultaneous explosions.
  - Confirm volume sliders persist between runs and mute works.
  - Verify camera shake + recoil + weather overlays remain smooth at 60 FPS on baseline hardware.
