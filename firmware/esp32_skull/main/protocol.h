#pragma once
#include <stddef.h>
#include "motion.h"
/* Return true for accepted command, seq=-1 for malformed/unidentifiable packet. */
bool protocol_apply(const char *packet, motion_state *state, int *seq);
