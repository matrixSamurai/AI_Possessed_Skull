#pragma once
#include <stdbool.h>
typedef struct {
    float x, y, jaw, pan, tilt;
    float target_x, target_y, target_jaw, target_pan, target_tilt;
    bool stopped;
} motion_state;
void motion_init(motion_state *state);
void motion_stop(motion_state *state);
void motion_step(motion_state *state, float dt);
bool motion_valid(float value, float low, float high);
/* Mock actuator only. Replace behind this boundary after physical calibration. */
void actuator_mock_write(const motion_state *state);
