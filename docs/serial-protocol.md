# Serial protocol v1

UTF-8 newline-delimited JSON, **256 bytes maximum including newline**, 115200 baud.
Every outbound command has `v:1`, `seq` (0..2147483647) and an explicit type:

```json
{"v":1,"seq":1,"type":"EYES","x":0.25,"y":-0.1}
{"v":1,"seq":2,"type":"JAW","open":0.65}
{"v":1,"seq":3,"type":"HEAD","pan":0.15,"tilt":0.0}
{"v":1,"seq":4,"type":"LED","effect":"red_pulse"}
{"v":1,"seq":5,"type":"STOP"}
{"v":1,"seq":6,"type":"RESET"}
{"v":1,"seq":7,"type":"PING"}
```

x/y/pan/tilt ∈ [-1,1]; open ∈ [0,1]. LED names: off, red_pulse, purple_glow.
Unknown fields/types, nonfinite/out-of-range values, duplicate keys and malformed
JSON are rejected. No arbitrary PWM values or executable commands are accepted.

```json
{"v":1,"type":"ACK","seq":1}
{"v":1,"type":"ERROR","seq":1}
```

Unidentifiable/malformed packets use ERROR with seq=-1. ACK means accepted target,
not measured physical movement. The host waits for the matching seq; timeout or ERROR
latches STOP and reconnects serial only. Initial connection and reconnect remain
stopped until explicit Resume sends RESET. Hardware defaults are intentionally inert.

Firmware buffers partial messages, discards oversize frames until the next newline,
limits traffic to 250 packets/s, interpolates at 50 Hz and stops after 500 ms without
an accepted command. The host sends coalesced current targets about every 40 ms;
ACK latency can reduce this rate. A physical driver must retain its own calibrated
pulse limits, disabled-output STOP and measured safe behavior on loss of communications.

Python framing/validation and the actual portable C parser have host tests.
FreeRTOS task scheduling, UART framing, watchdog expiry and physical reconnection
need board-level validation; portable tests do not prove those runtime properties.
