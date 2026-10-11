#include "motion.h"
#include <math.h>
#include <string.h>
bool motion_valid(float value, float low, float high) {
    return isfinite(value) && value >= low && value <= high;
}
void motion_stop(motion_state *s) {
    s->stopped = true;
    s->target_x = s->target_y = s->target_jaw = 0;
    s->target_pan = s->target_tilt = 0;
    /* Mock does not energize anything. Real STOP must disable actuator output. */
    s->x = s->y = s->jaw = s->pan = s->tilt = 0;
}
void motion_init(motion_state *s) {
    memset(s, 0, sizeof(*s));
    motion_stop(s);
}
static float approach(float value, float target, float step) {
    float delta = target - value;
    if (delta > step) delta = step;
    if (delta < -step) delta = -step;
    return value + delta;
}
void motion_step(motion_state *s, float dt) {
    if (s->stopped || !motion_valid(dt, 0, 0.1f)) return;
    s->x = approach(s->x, s->target_x, 2 * dt);
    s->y = approach(s->y, s->target_y, 2 * dt);
    s->jaw = approach(s->jaw, s->target_jaw, 5 * dt);
    s->pan = approach(s->pan, s->target_pan, dt);
    s->tilt = approach(s->tilt, s->target_tilt, dt);
    actuator_mock_write(s);
}
void actuator_mock_write(const motion_state *s) { (void)s; }
