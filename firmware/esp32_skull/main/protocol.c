#include "protocol.h"
#include "cJSON.h"
#include <math.h>
#include <string.h>

static bool number(cJSON *root, const char *name, float low, float high, float *value) {
    cJSON *item = cJSON_GetObjectItemCaseSensitive(root, name);
    if (!cJSON_IsNumber(item) || !motion_valid(item->valuedouble, low, high)) return false;
    *value = item->valuedouble;
    return true;
}
static bool keys(cJSON *root, const char *a, const char *b) {
    const cJSON *item;
    int count = 0;
    cJSON_ArrayForEach(item, root) {
        if (!item->string) return false;
        const char *key = item->string;
        if (strcmp(key,"v") && strcmp(key,"seq") && strcmp(key,"type") &&
            (!a || strcmp(key,a)) && (!b || strcmp(key,b))) return false;
        /* Reject duplicate fields. */
        for (const cJSON *other = item->next; other; other = other->next)
            if (other->string && !strcmp(key,other->string)) return false;
        ++count;
    }
    return count == 3 + (a != NULL) + (b != NULL);
}
bool protocol_apply(const char *packet, motion_state *s, int *seq) {
    *seq = -1;
    const char *end = NULL;
    cJSON *root = cJSON_ParseWithOpts(packet, &end, true);
    if (!cJSON_IsObject(root)) { cJSON_Delete(root); return false; }
    cJSON *version = cJSON_GetObjectItemCaseSensitive(root,"v");
    cJSON *sequence = cJSON_GetObjectItemCaseSensitive(root,"seq");
    cJSON *type = cJSON_GetObjectItemCaseSensitive(root,"type");
    bool ok = false;
    if (!cJSON_IsNumber(version) || version->valuedouble != 1 ||
        !cJSON_IsNumber(sequence) || !isfinite(sequence->valuedouble) ||
        sequence->valuedouble < 0 || sequence->valuedouble > 2147483647.0 ||
        floor(sequence->valuedouble) != sequence->valuedouble || !cJSON_IsString(type)) goto done;
    *seq = sequence->valueint;
    const char *name = type->valuestring;
    if (!strcmp(name,"STOP") && keys(root,NULL,NULL)) {
        motion_stop(s); ok = true; goto done;
    }
    if (!strcmp(name,"RESET") && keys(root,NULL,NULL)) {
        motion_init(s); s->stopped = false; ok = true; goto done;
    }
    if (!strcmp(name,"PING") && keys(root,NULL,NULL)) { ok = true; goto done; }
    if (s->stopped) goto done;
    float x, y;
    if (!strcmp(name,"EYES") && keys(root,"x","y") &&
        number(root,"x",-1,1,&x) && number(root,"y",-1,1,&y)) {
        s->target_x = x; s->target_y = y; ok = true;
    } else if (!strcmp(name,"JAW") && keys(root,"open",NULL) && number(root,"open",0,1,&x)) {
        s->target_jaw = x; ok = true;
    } else if (!strcmp(name,"HEAD") && keys(root,"pan","tilt") &&
        number(root,"pan",-1,1,&x) && number(root,"tilt",-1,1,&y)) {
        s->target_pan = x; s->target_tilt = y; ok = true;
    } else if (!strcmp(name,"LED") && keys(root,"effect",NULL)) {
        cJSON *effect = cJSON_GetObjectItemCaseSensitive(root,"effect");
        ok = cJSON_IsString(effect) && (!strcmp(effect->valuestring,"off") ||
             !strcmp(effect->valuestring,"red_pulse") || !strcmp(effect->valuestring,"purple_glow"));
        /* Mock LED: accepts a named effect, performs no physical output. */
    }
done:
    cJSON_Delete(root);
    return ok;
}
