#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "driver/uart.h"
#include "esp_timer.h"
#include "motion.h"
#include "protocol.h"
#define PACKET_MAX 256
#define WATCHDOG_US 500000
static motion_state state;
static SemaphoreHandle_t lock;
static int64_t last_command;
static void reply(int seq, bool accepted) {
    char text[96];
    int n = snprintf(text,sizeof(text),"{\"v\":1,\"type\":\"%s\",\"seq\":%d}\n",
                     accepted ? "ACK" : "ERROR",seq);
    uart_write_bytes(UART_NUM_0,text,n);
}
static void serial_task(void *arg) {
    (void)arg;
    char packet[PACKET_MAX];
    size_t length = 0;
    bool discard = false;
    int64_t rate_window = 0;
    unsigned count = 0;
    for (;;) {
        unsigned char byte;
        if (uart_read_bytes(UART_NUM_0,&byte,1,pdMS_TO_TICKS(20)) != 1) continue;
        if (byte == '\n') {
            if (discard) { reply(-1,false); }
            else if (length) {
                packet[length] = 0;
                int seq = -1;
                int64_t now = esp_timer_get_time();
                if (now-rate_window >= 1000000) { rate_window = now; count = 0; }
                xSemaphoreTake(lock,portMAX_DELAY);
                bool accepted = protocol_apply(packet,&state,&seq);
                /* STOP always works; rate abuse latches stop for every other command. */
                if (++count > 250 && !state.stopped) { motion_stop(&state); accepted = false; }
                if (accepted) last_command = now;
                xSemaphoreGive(lock);
                reply(seq,accepted);
            }
            length = 0; discard = false;
        } else if (!discard) {
            if (length >= PACKET_MAX-1 || byte == 0) { discard = true; length = 0; }
            else packet[length++] = byte;
        }
    }
}
static void motion_task(void *arg) {
    (void)arg;
    TickType_t previous = xTaskGetTickCount();
    for (;;) {
        xSemaphoreTake(lock,portMAX_DELAY);
        if (esp_timer_get_time()-last_command > WATCHDOG_US) motion_stop(&state);
        motion_step(&state,.02f);
        xSemaphoreGive(lock);
        vTaskDelayUntil(&previous,pdMS_TO_TICKS(20));
    }
}
void app_main(void) {
    motion_init(&state);
    lock = xSemaphoreCreateMutex();
    configASSERT(lock);
    uart_config_t config = {.baud_rate=115200,.data_bits=UART_DATA_8_BITS,
        .parity=UART_PARITY_DISABLE,.stop_bits=UART_STOP_BITS_1,
        .flow_ctrl=UART_HW_FLOWCTRL_DISABLE,.source_clk=UART_SCLK_DEFAULT};
    ESP_ERROR_CHECK(uart_param_config(UART_NUM_0,&config));
    ESP_ERROR_CHECK(uart_driver_install(UART_NUM_0,1024,1024,0,NULL,0));
    last_command = esp_timer_get_time();
    configASSERT(xTaskCreate(serial_task,"serial",4096,NULL,5,NULL)==pdPASS);
    configASSERT(xTaskCreate(motion_task,"motion",2048,NULL,4,NULL)==pdPASS);
}
