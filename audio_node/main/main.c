/*
 * audio_node — WiFi audio streamer (M4)
 * Board: ESP32-S3-DevKitC-1-N8R2, Amp: MAX98357A
 * 48000 Hz, 16-bit, MONO, I2S Philips std, no MCLK.
 * Pins: BCLK=4, LRC=5, DIN=6, SD=15 (HIGH = amp enabled), RGB LED=48
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
#include "lwip/inet.h"
#include "esp_heap_caps.h"
#include "esp_timer.h"
#include "led_strip.h"
#include "esp_http_server.h"
#include "esp_system.h"
#include <stdlib.h>

/* P1: RTP L16 over UDP — 48 kHz, 16-bit, mono, 20 ms frames (960 samples / 1920 bytes) */
#define UDP_PORT     1234
#define RTP_PT        96   /* dynamic payload type for L16/48k/mono */
#define FRAME_SAMPLES 960
#define FRAME_BYTES  (FRAME_SAMPLES * 2)   /* 16-bit = 2 bytes/sample */

/* Configured server IP for source-IP whitelist. 0 = accept any (set by NVS in P3). */
static uint32_t configured_server_ip = 0;

/* M3: raw PCM streaming — recv → PSRAM ring buffer → I2S pump.
 * Modes: TONE (no stream), STREAM (connected), SILENCE (stream ended, until next connect) */
#define RING_SIZE (256 * 1024)   /* ~2.7s of 48k/16b/stereo audio, in PSRAM */

static uint8_t *ring_buf = NULL;
static volatile int ring_head = 0, ring_tail = 0;   /* head=write, tail=read */
static SemaphoreHandle_t ring_mutex;
static volatile int play_mode = 0;  /* 0=tone, 1=stream, 2=silence */
static volatile uint32_t pump_chunks = 0;  /* diag: pump loop iterations */

static inline int ring_used(void) { int d = ring_head - ring_tail; if (d < 0) d += RING_SIZE; return d; }
static inline int ring_free(void) { return RING_SIZE - 1 - ring_used(); }

static int ring_write(const uint8_t *src, int len)
{
    int written = 0;
    xSemaphoreTake(ring_mutex, portMAX_DELAY);
    while (written < len) {
        int f = ring_free();
        if (f == 0) { xSemaphoreGive(ring_mutex); return written; }
        int n = len - written; if (n > f) n = f;
        int until_end = RING_SIZE - ring_head; if (n > until_end) n = until_end;
        memcpy(ring_buf + ring_head, src + written, n);
        ring_head = (ring_head + n) % RING_SIZE;
        written += n;
    }
    xSemaphoreGive(ring_mutex);
    return written;
}

static int ring_read(uint8_t *dst, int len)
{
    int r = 0;
    xSemaphoreTake(ring_mutex, portMAX_DELAY);
    int avail = ring_used();
    if (len > avail) len = avail;
    while (r < len) {
        int until_end = RING_SIZE - ring_tail; int n = len - r; if (n > until_end) n = until_end;
        memcpy(dst + r, ring_buf + ring_tail, n);
        ring_tail = (ring_tail + n) % RING_SIZE;
        r += n;
    }
    xSemaphoreGive(ring_mutex);
    return r;
}

#define PIN_BCLK   4
#define PIN_LRC    5
#define PIN_DIN    6
#define PIN_SD     15
#define PIN_RGB    48   /* onboard WS2812 RGB LED */

/* LED state: RGB shows connection state when idle, audio VU when streaming */
static led_strip_handle_t rgb_led = NULL;
static volatile uint8_t vu_level = 0;    /* smoothed audio level 0..255 */
static volatile int net_state = 0;       /* 0=wifi down, 1=waiting, 2=streaming */

#define SAMPLE_RATE 48000
#define TONE_HZ     1000
#define AMP         8000   /* ~25% full scale, safe for speaker */

/* Digital gain for streamed PCM (SD pin at VDD = amp's 3dB minimum gain).
   x2 = +6dB. Sender decodes at -7dB headroom, so x2 lands near full scale
   without clipping. */
#define PCM_GAIN    2

static inline int16_t gain_clip(int32_t s)
{
    s *= PCM_GAIN;
    if (s > 32767) s = 32767;
    if (s < -32768) s = -32768;
    return (int16_t)s;
}

/* ── P2+P3: NVS config, setup AP + captive portal, STA mode + failover ── */
#define CFG_NS          "cfg"
#define CFG_BLOB_KEY    "wifi"
#define AP_SSID         "AudioNode-Setup"
#define AP_GATEWAY      "192.168.4.1"
#define STA_FAIL_TIMEOUT_MS 30000       /* no IP in 30 s => revert to setup AP */

/* Persisted config blob (SSID, password, server ip/port) */
typedef struct {
    char ssid[33];
    char password[64];
    char server_ip[16];
    uint16_t server_port;
    uint8_t has_server;   /* 1 = server ip/port configured by user */
} node_cfg_t;

static node_cfg_t node_cfg;
static volatile int cfg_loaded = 0;
static volatile int ap_active = 0;      /* 1 = setup AP running */

static EventGroupHandle_t wifi_events;
#define WIFI_CONNECTED_BIT BIT0

static esp_err_t cfg_save(void)
{
    nvs_handle_t h;
    if (nvs_open(CFG_NS, NVS_READWRITE, &h) != ESP_OK) return ESP_FAIL;
    esp_err_t e = nvs_set_blob(h, CFG_BLOB_KEY, &node_cfg, sizeof(node_cfg));
    if (e == ESP_OK) e = nvs_commit(h);
    nvs_close(h);
    if (e == ESP_OK) cfg_loaded = 1;
    return e;
}

static esp_err_t cfg_load(void)
{
    nvs_handle_t h;
    if (nvs_open(CFG_NS, NVS_READONLY, &h) != ESP_OK) return ESP_FAIL;
    size_t len = sizeof(node_cfg);
    esp_err_t e = nvs_get_blob(h, CFG_BLOB_KEY, &node_cfg, &len);
    nvs_close(h);
    if (e == ESP_OK) cfg_loaded = 1;
    return e;
}

static void wifi_event_handler(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        printf("wifi disconnected, retrying...\n");
        net_state = 0;
        if (ap_active) return;          /* don't fight AP mode */
        esp_wifi_connect();
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *evt = (ip_event_got_ip_t *)data;
        printf("GOT IP: " IPSTR "\n", IP2STR(&evt->ip_info.ip));
        net_state = 1;                  /* waiting for server */
        xEventGroupSetBits(wifi_events, WIFI_CONNECTED_BIT);
    }
}

/* Pull server IP out of NVS config into the udp_task whitelist. */
static void cfg_apply_server_whitelist(void)
{
    if (node_cfg.has_server && node_cfg.server_ip[0]) {
        struct in_addr a;
        if (inet_pton(AF_INET, node_cfg.server_ip, &a) == 1) {
            configured_server_ip = a.s_addr;
            printf("cfg: server whitelist %s\n", node_cfg.server_ip);
            return;
        }
    }
    configured_server_ip = 0;           /* accept any */
}

/* Standing STA-mode connect using saved config (non-blocking). */
static esp_err_t sta_mode_start(void)
{
    wifi_config_t wc = { 0 };
    memcpy(wc.sta.ssid, node_cfg.ssid, sizeof(wc.sta.ssid) - 1);
    memcpy(wc.sta.password, node_cfg.password, sizeof(wc.sta.password) - 1);
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wc));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE));   /* proven: needed for streaming */
    ap_active = 0;
    printf("STA: joining %s\n", node_cfg.ssid);
    return ESP_OK;
}

/* ── P2: Setup AP + captive portal ─────────────────────────────── */
static esp_err_t portal_get_handler(httpd_req_t *req)
{
    char *html =
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>AudioNode Setup</title>"
        "<style>body{font-family:sans-serif;max-width:360px;margin:40px auto;}input{width:100%;"
        "padding:8px;margin:6px 0;box-sizing:border-box;}"
        "button{width:100%;padding:10px;background:#157;color:#fff;border:0;}</style>"
        "</head><body><h2>AudioNode Setup</h2>"
        "<form method='POST' action='/save'>"
        "<label>WiFi SSID</label><input name='ssid' required>"
        "<label>WiFi Password</label><input type='password' name='password'>"
        "<label>Server IP (RTP sender)</label><input name='server_ip' placeholder='192.168.1.100'>"
        "<label>Server Port</label><input name='server_port' value='1234'>"
        "<button type='submit'>Save &amp; Connect</button></form>"
        "</body></html>";
    httpd_resp_set_type(req, "text/html");
    httpd_resp_send(req, html, strlen(html));
    return ESP_OK;
}

/* url-decode a single form value into out (returns count written). */
static size_t url_decode(const char *src, char *out, size_t max)
{
    size_t o = 0;
    for (size_t i = 0; src[i] && o < max - 1; i++) {
        if (src[i] == '%' && i + 2 < strlen(src)) {
            int hi = isxdigit(src[i+1]) ? (isdigit(src[i+1]) ? src[i+1]-'0' :
                  (src[i+1]|0x20)-'a'+10) : 0;
            int lo = isxdigit(src[i+2]) ? (isdigit(src[i+2]) ? src[i+2]-'0' :
                  (src[i+2]|0x20)-'a'+10) : 0;
            out[o++] = (char)((hi << 4) | lo);
            i += 2;
        } else if (src[i] == '+') {
            out[o++] = ' ';
        } else {
            out[o++] = src[i];
        }
    }
    out[o] = '\0';
    return o;
}

static esp_err_t portal_save_handler(httpd_req_t *req)
{
    static char *keys[] = { "ssid", "password", "server_ip", "server_port", NULL };
    char vals[4][64] = {{0}};

    /* Read request body (form-encoded), bounded. */
    char body[1024];
    int off = 0;
    while (off < (int)sizeof(body)) {
        int n = httpd_req_recv(req, body + off, 1);
        if (n <= 0) break;
        off += n;
    }
    if (off <= 0) {
        httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "empty body");
        return ESP_OK;
    }
    body[off] = '\0';

    /* Split on '&', decode each known k=v. */
    char *tok = body, *save = NULL;
    while ((tok = strtok_r(tok, "&", &save)) != NULL) {
        const char *eq = strchr(tok, '=');
        if (!eq) continue;
        size_t klen = eq - tok;
        for (int k = 0; k < 4; k++) {
            if (keys[k] && strlen(keys[k]) == klen && strncmp(tok, keys[k], klen) == 0) {
                url_decode(eq + 1, vals[k], sizeof(vals[k]));
                break;
            }
        }
        tok = save;
    }

    if (!vals[0][0]) {
        httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "missing ssid");
        return ESP_OK;
    }
    snprintf(node_cfg.ssid, sizeof(node_cfg.ssid), "%.32s", vals[0]);
    if (vals[1][0]) snprintf(node_cfg.password, sizeof(node_cfg.password), "%.63s", vals[1]);
    if (vals[2][0]) snprintf(node_cfg.server_ip, sizeof(node_cfg.server_ip), "%.15s", vals[2]);
    if (vals[3][0]) node_cfg.server_port = (uint16_t)atoi(vals[3]);
    node_cfg.has_server = (vals[2][0] != 0) ? 1 : 0;

    if (cfg_save() != ESP_OK) {
        httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "nvs write failed");
        return ESP_OK;
    }
    printf("cfg: saved via portal (SSID=%s server=%s:%u)\n",
           node_cfg.ssid, node_cfg.server_ip, (unsigned)node_cfg.server_port);

    httpd_resp_sendstr(req, "Saved. Rebooting into STA mode...");
    vTaskDelay(pdMS_TO_TICKS(300));
    esp_restart();
    return ESP_OK;
}

static void setup_ap_start(void)
{
    ap_active = 1;
    net_state = 0;
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_AP));
    wifi_config_t ap = {
        .ap = { .ssid = AP_SSID, .ssid_len = strlen(AP_SSID),
                .channel = 1, .authmode = WIFI_AUTH_OPEN, .max_connection = 4 },
    };
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &ap));
    ESP_ERROR_CHECK(esp_wifi_start());

    /* Static 192.168.4.1 gateway for the AP. */
    esp_netif_ip_info_t ip;
    ip.ip.addr      = ESP_IP4TOADDR(192, 168, 4, 1);
    ip.netmask.addr = ESP_IP4TOADDR(255, 255, 255, 0);
    ip.gw           = ip.ip;
    esp_netif_t *ap_if = esp_netif_get_handle_from_ifkey("WIFI_AP_DEF");
    /* DHCP server is already running (default AP netif): stop -> set IP -> restart */
    ESP_ERROR_CHECK(esp_netif_dhcps_stop(ap_if));
    ESP_ERROR_CHECK(esp_netif_set_ip_info(ap_if, &ip));
    ESP_ERROR_CHECK(esp_netif_dhcps_start(ap_if));
    esp_netif_dns_info_t dns;
    dns.ip = (esp_ip_addr_t)ESP_IP4ADDR_INIT(192, 168, 4, 1);   /* captive dns */
    esp_netif_set_dns_info(ap_if, ESP_NETIF_DNS_MAIN, &dns);

    /* Captive portal: HTTP server on :80 */
    httpd_handle_t hd = NULL;
    httpd_config_t hcfg = HTTPD_DEFAULT_CONFIG();
    if (httpd_start(&hd, &hcfg) != ESP_OK) {
        printf("setup ap: httpd failed\n");
    } else {
        httpd_uri_t get_uri  = { .uri = "/", .method = HTTP_GET,  .handler = portal_get_handler };
        httpd_uri_t save_uri = { .uri = "/save", .method = HTTP_POST, .handler = portal_save_handler };
        httpd_register_uri_handler(hd, &get_uri);
        httpd_register_uri_handler(hd, &save_uri);
    }
    printf("setup ap: running 'AudioNode-Setup' open AP, portal http://%s/\n", AP_GATEWAY);
}

/* ── P3: failover — STA no IP in 30 s → return to setup AP (keep NVS) ── */
static void failover_task(void *arg)
{
    int64_t sta_start = 0;
    while (1) {
        vTaskDelay(pdMS_TO_TICKS(1000));
        if (ap_active) continue;               /* already in setup AP */
        if (net_state >= 1) { sta_start = 0; continue; }  /* got IP, all good */
        if (sta_start == 0) sta_start = esp_timer_get_time();   /* us */
        if (esp_timer_get_time() - sta_start > (int64_t)STA_FAIL_TIMEOUT_MS * 1000) {
            printf("failover: no IP in %d ms, opening setup AP (NVS kept)\n",
                   STA_FAIL_TIMEOUT_MS);
            esp_wifi_stop();
            setup_ap_start();
            sta_start = 0;
        }
    }
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

    static int16_t buf[2 * 1024];  /* stereo interleaved, up to 1024 frames (21.3ms) */
    int n = 0;
    int err_printed = 0;
    size_t written = 0;
    while (1) {
        int mode = play_mode;
        int frames = 0;
        if (mode == 0) {
            for (int i = 0; i < 1024; i++) {
                int16_t s = sine_tab[n % 48];
                buf[2 * i] = s;      /* L */
                buf[2 * i + 1] = s;  /* R */
                n++;
            }
            frames = 1024;
            /* power-on tone limited to ~2s (user request), then silence
               until the stream connects. tcp_task switches back to mode 1. */
            static int tone_ms = 0;
            tone_ms += 1024 * 1000 / SAMPLE_RATE;   /* 21.3ms per chunk */
            if (tone_ms >= 2000 && play_mode == 0) play_mode = 2;
        } else if (mode == 1) {
            /* stream: pull up to 1024 frames from ring, apply digital gain, dup L/R */
            static int16_t mono[1024];
            xSemaphoreTake(ring_mutex, portMAX_DELAY);
            int avail = ring_used() & ~1;   /* even bytes only */
            xSemaphoreGive(ring_mutex);
            if (avail >= 2048) {
                ring_read((uint8_t *)mono, 2048);
                frames = 1024;
            } else if (avail >= 512) {
                int bytes = (avail > 2048) ? 2048 : avail;
                bytes &= ~1;
                ring_read((uint8_t *)mono, bytes);
                frames = bytes / 2;
            } else {
                /* starved: emit ~5ms of SILENCE instead of leaving the DMA
                   replaying the last buffer (= harsh buzzing noise) */
                memset(buf, 0, 256 * 4);
                frames = 256;
                i2s_channel_write(tx_chan, buf, frames * 4, &written, portMAX_DELAY);
                vTaskDelay(pdMS_TO_TICKS(2));
                continue;
            }
            for (int i = 0; i < frames; i++) {
                int16_t s = gain_clip(mono[i]);
                buf[2 * i] = s;
                buf[2 * i + 1] = s;
            }
            memset(&buf[2 * frames], 0, sizeof(buf) - frames * 4);
        } else {
            memset(buf, 0, sizeof(buf));
            frames = 1024;
        }
        /* VU level for RGB LED: peak of written audio, fast attack / slow decay */
        {
            int peak = 0;
            for (int i = 0; i < frames; i++) {
                int a = buf[2 * i]; if (a < 0) a = -a;
                if (a > peak) peak = a;
            }
            int lvl = peak / 128; if (lvl > 255) lvl = 255;
            if (lvl > vu_level) vu_level = (uint8_t)lvl;
            else if (vu_level > 8) vu_level -= 8; else vu_level = 0;
        }
        esp_err_t ret = i2s_channel_write(tx_chan, buf, frames * 4, &written, portMAX_DELAY);
        if (ret != ESP_OK || written != (size_t)frames * 4) {
            if (err_printed++ < 5) printf("i2s write ret=%d written=%u/%u\n", ret, (unsigned)written, (unsigned)frames * 4);
        }
        /* pacing = DMA backpressure alone: i2s_channel_write blocks until the
           DMA has drained one chunk (21.3ms). A fixed sleep here adds a 4ms
           deficit per chunk → periodic dry gaps → glitch/buzz on buffer replay. */
        pump_chunks++;
    }
}

/* RGB LED: idle → connection state (red=wifi down, blue breathing=waiting);
   streaming → VU meter (green=quiet → red=loud), driven by smoothed peak */
static void rgb_init(void)
{
    led_strip_config_t strip_cfg = { .strip_gpio_num = PIN_RGB, .max_leds = 1 };
    led_strip_rmt_config_t rmt_cfg = { .resolution_hz = 10 * 1000 * 1000 };
    if (led_strip_new_rmt_device(&strip_cfg, &rmt_cfg, &rgb_led) == ESP_OK) {
        led_strip_clear(rgb_led);
    } else {
        printf("rgb: init failed, LED disabled\n");
        rgb_led = NULL;
    }
}

static void led_task(void *arg)
{
    int phase = 0;
    while (1) {
        if (rgb_led == NULL) { vTaskDelay(pdMS_TO_TICKS(100)); continue; }
        if (net_state == 2) {
            /* VU: quadratic red + inverse green = green quiet → red loud */
            int v = vu_level;
            uint8_t r = (uint8_t)((v * v) >> 8);
            uint8_t g = (uint8_t)(255 - ((v * v) >> 8));
            led_strip_set_pixel(rgb_led, 0, r, g, 0);
        } else if (net_state == 1) {
            /* blue breathing: 0..255..0 over ~3s */
            int ph = phase = (phase + 1) % 100;
            int b = ph < 50 ? ph * 5 : (100 - ph) * 5;
            led_strip_set_pixel(rgb_led, 0, 0, 0, (uint8_t)b);
        } else {
            /* wifi down: solid dim red */
            led_strip_set_pixel(rgb_led, 0, 60, 0, 0);
        }
        led_strip_refresh(rgb_led);
        vTaskDelay(pdMS_TO_TICKS(30));
    }
}

/* P1: RTP L16 over UDP receiver — board is a UDP listener (server sends TO the board).
   Replaces the TCP client transport. The board listens on UDP 1234;
   the sender sends RTP datagrams (PT=96, 48kHz/16-bit/mono, 20ms frames) to
   board_ip:1234. Every datagram is validated before feeding PCM to the ring.
   Missing packets -> silence fill; never block I2S on a lost UDP packet. */
static void udp_task(void *arg)
{
    /* UDP socket bound to port 1234 */
    int sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (sock < 0) {
        printf("udp: socket failed (errno=%d)\n", errno);
        vTaskDelay(pdMS_TO_TICKS(2000));
        return;
    }

    struct sockaddr_in local = {0};
    local.sin_family = AF_INET;
    local.sin_addr.s_addr = INADDR_ANY;
    local.sin_port = htons(UDP_PORT);

    int opt = 1;
    setsockopt(sock, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    if (bind(sock, (struct sockaddr *)&local, sizeof(local)) < 0) {
        printf("udp: bind failed (errno=%d)\n", errno);
        close(sock);
        return;
    }

    printf("udp: listening on 0.0.0.0:%d, waiting for RTP L16 (PT=%d)...\n",
           UDP_PORT, RTP_PT);

    static uint8_t rx_buf[2048];            /* RTP hdr (12) + PCM (1920) = 1932 */
    struct sockaddr_in peer;
    socklen_t peer_len = sizeof(peer);
    uint16_t last_seq = 0;
    int first_packet = 1;
    uint64_t total = 0;
    uint32_t pkts = 0, dropped = 0;
    int64_t last_log = 0;

    while (1) {
        int len = recvfrom(sock, rx_buf, sizeof(rx_buf), 0,
                           (struct sockaddr *)&peer, &peer_len);
        if (len < 0) {
            printf("udp: recvfrom err=%d\n", errno);
            continue;
        }
        if (ring_buf == NULL) {
            vTaskDelay(pdMS_TO_TICKS(10));
            continue;
        }

        /* --- RTP header validation (before touching the ring) --- */
        if (len < 12) continue;                              /* no RTP header */
        if ((rx_buf[0] >> 6) != 2) continue;                  /* version != 2  */
        if ((rx_buf[1] & 0x7F) != RTP_PT) continue;           /* PT != 96       */

        uint16_t seq = (rx_buf[2] << 8) | rx_buf[3];
        (void)rx_buf;  /* ts parsed below but not used for diagnostics */

        /* Source-IP whitelist (0 = accept any; set by NVS in P3) */
        if (configured_server_ip &&
            peer.sin_addr.s_addr != configured_server_ip) {
            continue;
        }

        int payload_len = len - 12;
        if (payload_len < FRAME_BYTES) continue;             /* too short */

        /* --- Sequence / gap detection --- */
        if (!first_packet) {
            uint16_t expected = (last_seq + 1) & 0xFFFF;
            if (seq != expected && seq != last_seq) {        /* not next, not dup */
                uint16_t gap = (seq - expected) & 0xFFFF;
                if (gap > 64) gap = 1;  /* cap runaway gap */
                dropped += gap;
                /* fill missing frames with silence */
                uint8_t silence[FRAME_BYTES];
                memset(silence, 0, FRAME_BYTES);
                for (uint16_t g = 0; g < gap; g++) {
                    (void)ring_write(silence, FRAME_BYTES);
                }
            }
        }
        first_packet = 0;
        last_seq = seq;

        /* --- Write validated PCM payload to ring --- */
        int w = ring_write(rx_buf + 12, FRAME_BYTES);
        total += w;
        pkts++;

        play_mode = 1;
        net_state = 2;   /* streaming */

        int64_t now = esp_timer_get_time();
        if (now - last_log > 5000000) {
            printf("udp: pkts=%lu dropped=%lu ring=%d pcm=%llu bytes (t=%lld ms)\n",
                   (unsigned long)pkts, (unsigned long)dropped, ring_used(),
                   (unsigned long long)total, (long long)(now / 1000));
            last_log = now;
        }
    }
    close(sock);
}

void app_main(void)
{
    printf("audio_node: WiFi streamer start\n");
    printf("I2S: %d Hz, 16-bit mono, BCLK=%d LRC=%d DIN=%d SD=%d RGB=%d\n",
           SAMPLE_RATE, PIN_BCLK, PIN_LRC, PIN_DIN, PIN_SD, PIN_RGB);

    /* Amp enable (SD HIGH) */
    ESP_ERROR_CHECK(gpio_reset_pin(PIN_SD));
    ESP_ERROR_CHECK(gpio_set_direction(PIN_SD, GPIO_MODE_OUTPUT));
    gpio_set_level(PIN_SD, 1);

    i2s_init();

    /* RGB LED (WS2812 on GPIO48): connection state + audio VU */
    rgb_init();
    xTaskCreate(led_task, "led", 3072, NULL, 2, NULL);

    /* PSRAM ring buffer for jitter buffering */
    ring_buf = heap_caps_malloc(RING_SIZE, MALLOC_CAP_SPIRAM);
    if (ring_buf == NULL) {
        ring_buf = malloc(64 * 1024);   /* internal-RAM fallback */
        if (ring_buf) printf("ring: PSRAM failed, using 64KB internal\n");
    }
    if (ring_buf == NULL) printf("ERROR: no ring buffer, streaming disabled\n");
    ring_mutex = xSemaphoreCreateMutex();

    /* Pump runs in its own task: keeps app_main free (avoids task watchdog timeout) */
    xTaskCreate(audio_pump_task, "audio_pump", 4096, NULL, 5, NULL);

    /* ── WiFi: init stack once, then decide STA vs setup-AP from NVS ── */
    /* NVS partition MUST be ready before esp_wifi_init (wifi stores its own data there). */
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();
    esp_netif_create_default_wifi_ap();
    {
        wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
        ESP_ERROR_CHECK(esp_wifi_init(&cfg));
    }
    wifi_events = xEventGroupCreate();
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &wifi_event_handler, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &wifi_event_handler, NULL));

    /* Load config; none in NVS (first boot / factory reset) -> zeroed cfg ->
       ssid empty -> setup AP (documented spec: first boot runs AudioNode-Setup) */
    if (cfg_load() != ESP_OK) {
        printf("cfg: none in NVS (first boot / factory reset)\n");
    }
    cfg_apply_server_whitelist();

    if (node_cfg.ssid[0]) {
        sta_mode_start();
        printf("wifi: STA mode, power-save OFF, listening on :%d\n", UDP_PORT);
    } else {
        printf("wifi: no SSID configured, starting setup AP\n");
        setup_ap_start();
    }

    xTaskCreate(rssi_task, "rssi", 3072, NULL, 3, NULL);
    xTaskCreate(failover_task, "failover", 3072, NULL, 2, NULL);
    xTaskCreate(udp_task, "udp", 8192, NULL, 4, NULL);
}
