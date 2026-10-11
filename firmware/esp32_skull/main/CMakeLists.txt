idf_component_register(SRCS "main.c" "motion.c" "protocol.c" INCLUDE_DIRS "." REQUIRES json esp_driver_uart esp_timer)
