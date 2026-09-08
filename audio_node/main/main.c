/*
 * audio_node — M0: serial tone test (I2S only, no network)
 * Board: ESP32-S3-DevKitC-1-N8R2, Amp: MAX98357A
 * 48000 Hz, 16-bit, MONO, I2S Philips std, no MCLK.
 * Pins: BCLK=4, LRC=5, DIN=6, SD=15 (HIGH = amp enabled)
 */
#include <stdio.h>
#include <math.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/i2s_std.h"
#include "driver/gpio.h"
#include "freertos/semphr.h"


#define PIN_BCLK   4
#define PIN_LRC    5
#define PIN_DIN    6
#define PIN_SD     15

#define SAMPLE_RATE 48000
#define TONE_HZ     1000
#define AMP         8000   /* ~25% full scale, safe for speaker */

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

void app_main(void)
{
    printf("M0: serial tone test start\n");
    printf("I2S: %d Hz, 16-bit mono, BCLK=%d LRC=%d DIN=%d SD=%d\n",
           SAMPLE_RATE, PIN_BCLK, PIN_LRC, PIN_DIN, PIN_SD);

    /* Amp enable (SD HIGH) */
    ESP_ERROR_CHECK(gpio_reset_pin(PIN_SD));
    ESP_ERROR_CHECK(gpio_set_direction(PIN_SD, GPIO_MODE_OUTPUT));
    gpio_set_level(PIN_SD, 1);

    i2s_init();

    /* Pump runs in its own task: keeps app_main free (avoids task watchdog timeout) */
    xTaskCreate(audio_pump_task, "audio_pump", 4096, NULL, 5, NULL);
}
