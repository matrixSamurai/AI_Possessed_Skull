# Under-skull lighting preview

The desktop preview includes a diffused light strip beneath the skull, a soft floor
pool, upward haze and reflected light on the lower face. Color follows the active eye
preset (including agent-selected styles). Brightness eases with eye intensity;
ordinary modes breathe slowly while inferno has a smooth ember pulse. Emergency
stop switches the simulated light off immediately. It restarts gently after resume.

![Under-skull lighting preview](under-skull-lighting-preview.png)

## Future physical LEDs

`UnderLighting` is independent of Qt. Its `LightingFrame` output contains:

- `rgb`: three integer color channels, each 0–255.
- `brightness`: normalized brightness, 0–1.
- `effect`: active preset name, or `off` during emergency stop.

A later LED controller can consume the same state at a suitable update rate and map
it to the selected strip or lamp. Preview intensity is not a calibrated physical
brightness measurement. LED type, wiring, power and protocol are not assumed. This
change sends no new serial commands and does not drive physical LEDs yet.
