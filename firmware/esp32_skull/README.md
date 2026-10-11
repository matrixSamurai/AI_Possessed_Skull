# ESP32-S3 mock firmware

Target ESP-IDF **5.4.x**. No servos, LEDs, I2C or PWM outputs are energized.
This is a protocol/FreeRTOS foundation, not a finished PCA9685 driver.
`actuator_mock_write()` is the replacement boundary for a calibrated physical driver.

With ESP-IDF installed through Espressif's official installer:

```sh
cd firmware/esp32_skull
. "$IDF_PATH/export.sh"
idf.py set-target esp32s3
idf.py build
# Only when you own a board:
idf.py -p /dev/cu.usbserial-YOURPORT flash
```

UART0 uses the board's console routing at 115200 baud. ESP32-S3 default UART0
pins are TX GPIO43 and RX GPIO44; verify your board's schematic. Use a **3.3V**
USB/UART bridge. Native USB CDC is a future transport adaptation, not enabled here.
Disable application logs on the protocol UART. Boot ROM messages may appear before
startup; the host intentionally rejects unexpected replies and stays stopped.

Two tasks: serial parsing and 50 Hz motion interpolation. Strict versioned JSON,
256-byte packet bound, partial-frame support, ACK/ERROR, 250 packets/s limit,
500 ms communication watchdog, and a latched STOP. Only explicit RESET releases STOP.
At startup, reconnect, invalid host reply, or watchdog expiry, motion remains stopped.
Python sends normalized targets, never arbitrary PWM values or executable commands.
No sequence deduplication is implemented; absolute target commands are idempotent.

Host tests compile the portable motion module and the parser against upstream cJSON.
The full ESP-IDF build and board behavior must be validated separately; ESP-IDF is
not installed in the cloud prototype environment.

Before replacing the mock: measure linkage travel, choose servo models, enforce
pulse bounds locally, install a separately regulated servo supply, share ground,
include a physical power cutoff, and test one unloaded servo at a time. Do not use
Pi or ESP32 supply pins to power servos. STOP should disable actuator outputs;
returning under power to a neutral pose is only safe after mechanical validation.
