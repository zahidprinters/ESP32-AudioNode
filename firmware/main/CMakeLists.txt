idf_component_register(SRCS "main.c"
                       INCLUDE_DIRS "."
                       REQUIRES driver esp_wifi nvs_flash esp_event esp_netif lwip esp_timer led_strip esp_driver_i2s esp_http_server esp_system
                       PRIV_REQUIRES esp_driver_gpio)
