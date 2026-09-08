/*
 * audio_node — M1: WiFi connect (M0 tone still playing as proof-of-life)
 * Board: ESP32-S3-DevKitC-1-N8R2, Amp: MAX98357A
 * 48000 Hz, 16-bit, MONO, I2S Philips std, no MCLK.
 * Pins: BCLK=4, LRC=5, DIN=6, SD=15 (HIGH = amp enabled)
 */
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include "driver/i2s_std.h"
#include "driver/gpio.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "nvs_flash.h"
#include "lwip/sockets.h"

#define PC_SERVER_IP   "<pc-ip>"
#define PC_SERVER_PORT 1234


#define PIN_BCLK   4
#define PIN_LRC    5
#define PIN_DIN    6
#define PIN_SD     15

#define SAMPLE_RATE 48000
#define TONE_HZ     1000
#define AMP         8000   /* ~25% full scale, safe for speaker */

#define WIFI_SSID   "<ssid>"
#define WIFI_PASS   "<password>"

static EventGroupHandle_t wifi_events;
#define WIFI_CONNECTED_BIT BIT0

static void wifi_event_handler(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        printf("wifi disconnected, retrying...\n");
        esp_wifi_connect();
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *evt = (ip_event_got_ip_t *)data;
        printf("GOT IP: " IPSTR "\n", IP2STR(&evt->ip_info.ip));
        xEventGroupSetBits(wifi_events, WIFI_CONNECTED_BIT);
    }
}

static void wifi_init(void)
{
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    wifi_events = xEventGroupCreate();
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &wifi_event_handler, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &wifi_event_handler, NULL));

    wifi_config_t wifi_config = {
        .sta = {
            .ssid = WIFI_SSID,
            .password = WIFI_PASS,
        },
    };
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());

    /* Power-save OFF (proven fact: required for streaming) */
    ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE));

    /* Wait for connection */
    xEventGroupWaitBits(wifi_events, WIFI_CONNECTED_BIT, pdFALSE, pdTRUE, portMAX_DELAY);
}

/* M1 check: print RSSI every 10s */
static void rssi_task(void *arg)
{
    while (1) {
        vTaskDelay(pdMS_TO_TICKS(10000));
        wifi_ap_record_t ap;
        if (esp_wifi_sta_get_ap_info(&ap) == ESP_OK) {
            printf("rssi=%d\n", ap.rssi);
        }
    }
}

static i2s_chan_handle_t tx_chan;

static void i2s_init(void)
{
    i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
    ESP_ERROR_CHECK(i2s_new_channel(&chan_cfg, &tx_chan, NULL));

    i2s_std_config_t std_cfg = {
        .clk_cfg  = I2S_STD_CLK_DEFAULT_CONFIG(SAMPLE_RATE),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_STEREO),
        .gpio_cfg = {
            .mclk = I2S_GPIO_UNUSED,
            .bclk = PIN_BCLK,
            .ws   = PIN_LRC,
            .dout = PIN_DIN,
            .din  = I2S_GPIO_UNUSED,
            .invert_flags = { .mclk_inv = false, .bclk_inv = false, .ws_inv = false },
        },
    };
    ESP_ERROR_CHECK(i2s_channel_init_std_mode(tx_chan, &std_cfg));
    ESP_ERROR_CHECK(i2s_channel_enable(tx_chan));
}

void audio_pump_task(void *arg)
{
    /* Duplicate sample to L+R slots; MAX98357A mixes to mono speaker output */
    static int16_t sine_tab[48];   /* 48000 Hz / 1000 Hz = 48 samples per cycle */
    for (int i = 0; i < 48; i++) {
        sine_tab[i] = (int16_t)(AMP * sinf(2.0f * (float)M_PI * TONE_HZ * i / SAMPLE_RATE));
    }

    static int16_t buf[2 * 256];  /* stereo interleaved, 256 frames */
    int n = 0;
    int err_printed = 0;
    size_t written = 0;
    while (1) {
        for (int i = 0; i < 256; i++) {
            int16_t s = sine_tab[n % 48];
            buf[2 * i] = s;      /* L */
            buf[2 * i + 1] = s;  /* R */
            n++;
        }
        esp_err_t ret = i2s_channel_write(tx_chan, buf, sizeof(buf), &written, portMAX_DELAY);
        if (ret != ESP_OK || written != sizeof(buf)) {
            if (err_printed++ < 5) printf("i2s write ret=%d written=%u/%u\n", ret, (unsigned)written, (unsigned)sizeof(buf));
        }
        vTaskDelay(pdMS_TO_TICKS(4));   /* rate-limit: 1024 bytes = 5.3ms audio; yield so IDLE0 feeds */
    }
}

/* M2: TCP client — board connects TO the PC (server waits in accept()) */
static void tcp_task(void *arg)
{
    while (1) {
        struct sockaddr_in dest = {0};
        dest.sin_addr.s_addr = inet_addr(PC_SERVER_IP);
        dest.sin_family = AF_INET;
        dest.sin_port = htons(PC_SERVER_PORT);

        int sock = socket(AF_INET, SOCK_STREAM, IPPROTO_IP);
        if (sock < 0) { printf("tcp: socket failed\n"); vTaskDelay(pdMS_TO_TICKS(2000)); continue; }

        printf("tcp: connecting to %s:%d ...\n", PC_SERVER_IP, PC_SERVER_PORT);
        if (connect(sock, (struct sockaddr *)&dest, sizeof(dest)) == 0) {
            printf("tcp: CONNECTED to %s:%d\n", PC_SERVER_IP, PC_SERVER_PORT);
            /* M2 scope: hold connection, log every 10s; recv drains any data */
            uint8_t tmp[512];
            int up = 0;
            while (1) {
                int len = recv(sock, tmp, sizeof(tmp), MSG_DONTWAIT);
                if (len < 0 && errno != EAGAIN && errno != EWOULDBLOCK) { printf("tcp: recv err, reconnect\n"); break; }
                if (++up >= 10) { up = 0; printf("tcp: alive\n"); }
                vTaskDelay(pdMS_TO_TICKS(1000));
            }
        } else {
            printf("tcp: connect failed (errno=%d), retry\n", errno);
        }
        close(sock);
        vTaskDelay(pdMS_TO_TICKS(2000));
    }
}

void app_main(void)
{
    printf("M1: wifi + tone test start\n");
    printf("I2S: %d Hz, 16-bit mono, BCLK=%d LRC=%d DIN=%d SD=%d\n",
           SAMPLE_RATE, PIN_BCLK, PIN_LRC, PIN_DIN, PIN_SD);

    /* Amp enable (SD HIGH) */
    ESP_ERROR_CHECK(gpio_reset_pin(PIN_SD));
    ESP_ERROR_CHECK(gpio_set_direction(PIN_SD, GPIO_MODE_OUTPUT));
    gpio_set_level(PIN_SD, 1);

    i2s_init();

    /* Pump runs in its own task: keeps app_main free (avoids task watchdog timeout) */
    xTaskCreate(audio_pump_task, "audio_pump", 4096, NULL, 5, NULL);

    /* WiFi */
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);
    wifi_init();
    printf("wifi connected, power-save OFF\n");
    xTaskCreate(rssi_task, "rssi", 3072, NULL, 3, NULL);
    xTaskCreate(tcp_task, "tcp", 4096, NULL, 4, NULL);
}
