/*
 * lighting_node/main/app_main.c
 *
 * LED ノードファームウェア (ESP-IDF)
 * WS2812B × 880個 (2ストリップ × 440) を UART コマンドで制御
 *
 * 受信経路:
 *   1. UART1 (GPIO17 TX / GPIO18 RX) — 中央ノード または USB-UART アダプタ
 *   2. USB Serial/JTAG               — PC デバッグ (COM3 直結)
 *
 * フレーム形式: hub_protocol.h の UART 仕様を参照
 *   [STX 0xAA][CMD 1B][LEN 1B][PAYLOAD 0-32B][CRC8 1B][ETX 0x55]
 */

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_system.h"
#include "driver/uart.h"
#include "driver/usb_serial_jtag.h"
#include "led_strip.h"
#include "hub_protocol.h"
#include <string.h>
#include <stdint.h>

static const char *TAG = "lighting_node";

/* ============================================================
 * ピン・定数定義
 * ============================================================ */

#define GPIO_LED_STRIP1         4
#define GPIO_LED_STRIP2         5
#define LED_COUNT_PER_STRIP     440
#define SAFE_BRIGHTNESS         12    /* 白 ~5% (12/255 ≈ 4.7%) */

#define UART_PORT               UART_NUM_1
#define GPIO_UART_TX            17
#define GPIO_UART_RX            18
#define UART_BAUD_RATE          115200
#define UART_RX_BUF_SIZE        512

#define USB_RX_BUF_SIZE         512

#define HEARTBEAT_TIMEOUT_MS    3000
#define RX_ACCUM_SIZE           256
#define RX_TMP_SIZE             64

/* ============================================================
 * 状態変数
 * ============================================================ */

static led_strip_handle_t s_strip[2];
static uint8_t    s_brightness    = SAFE_BRIGHTNESS;
static uint8_t    s_color_r       = 255;
static uint8_t    s_color_g       = 255;
static uint8_t    s_color_b       = 255;
static TickType_t s_last_cmd_tick = 0;
static bool       s_hb_armed      = false;

/* ============================================================
 * LED ヘルパー
 * ============================================================ */

/* 全 LED に r/g/b × brightness を適用して送出 */
static void led_flush(uint8_t r, uint8_t g, uint8_t b, uint8_t brightness)
{
    uint8_t br = (uint8_t)((uint32_t)r * brightness / 255);
    uint8_t bg = (uint8_t)((uint32_t)g * brightness / 255);
    uint8_t bb = (uint8_t)((uint32_t)b * brightness / 255);

    for (int i = 0; i < LED_COUNT_PER_STRIP; i++) {
        led_strip_set_pixel(s_strip[0], i, br, bg, bb);
        led_strip_set_pixel(s_strip[1], i, br, bg, bb);
    }
    led_strip_refresh(s_strip[0]);
    led_strip_refresh(s_strip[1]);
}

/* ハートビートタイムアウト時のフォールバック: 白 5% */
static void led_safe_white(void)
{
    ESP_LOGW(TAG, "heartbeat timeout -> safe_white");
    s_brightness = SAFE_BRIGHTNESS;
    s_color_r = 255; s_color_g = 255; s_color_b = 255;
    led_flush(255, 255, 255, SAFE_BRIGHTNESS);
}

/* ============================================================
 * コマンドハンドラ
 * ============================================================ */

static void handle_command(const hub_uart_frame_t *frame)
{
    switch ((hub_uart_command_t)frame->cmd) {

    case HUB_UART_CMD_SET_COLOR:
        if (frame->len >= 3) {
            s_color_r = frame->payload[0];
            s_color_g = frame->payload[1];
            s_color_b = frame->payload[2];
            led_flush(s_color_r, s_color_g, s_color_b, s_brightness);
            ESP_LOGI(TAG, "SET_COLOR R=%u G=%u B=%u (brightness=%u)",
                     s_color_r, s_color_g, s_color_b, s_brightness);
        }
        break;

    case HUB_UART_CMD_SET_BRIGHTNESS:
        if (frame->len >= 1) {
            s_brightness = frame->payload[0];
            led_flush(s_color_r, s_color_g, s_color_b, s_brightness);
            ESP_LOGI(TAG, "SET_BRIGHTNESS %u", s_brightness);
        }
        break;

    case HUB_UART_CMD_STOP:
        led_strip_clear(s_strip[0]);
        led_strip_clear(s_strip[1]);
        ESP_LOGI(TAG, "STOP");
        break;

    case HUB_UART_CMD_HEARTBEAT:
        ESP_LOGD(TAG, "HEARTBEAT");
        break;

    case HUB_UART_CMD_RESET:
        ESP_LOGW(TAG, "RESET");
        esp_restart();
        break;

    default:
        ESP_LOGW(TAG, "unknown CMD 0x%02X len=%u", frame->cmd, frame->len);
        break;
    }
}

/* ============================================================
 * フレームデコーダ (線形アキュムレータ)
 *
 * buf[0..(*len-1)] のバイト列から 1 フレームを切り出す。
 * 成功時: out にフレームを書き込み、バッファを消費して 1 を返す。
 * 失敗時: 0 を返す (データ不足 or STX なし)。
 * ============================================================ */

static int try_decode_frame(uint8_t *buf, int *len, hub_uart_frame_t *out)
{
    /* STX を探す */
    int stx_pos = -1;
    for (int i = 0; i < *len; i++) {
        if (buf[i] == HUB_UART_STX) { stx_pos = i; break; }
    }
    if (stx_pos < 0) { *len = 0; return 0; }

    /* STX の前を捨てる */
    if (stx_pos > 0) {
        memmove(buf, buf + stx_pos, *len - stx_pos);
        *len -= stx_pos;
    }

    /* CMD + LEN まで揃うのを待つ */
    if (*len < 3) return 0;

    uint8_t payload_len = buf[2];
    if (payload_len > HUB_UART_PAYLOAD_MAX) {
        /* 不正な LEN → この STX を捨てて再スキャン */
        memmove(buf, buf + 1, *len - 1);
        (*len)--;
        return 0;
    }

    /* フレーム全体長: STX(1)+CMD(1)+LEN(1)+PAYLOAD+CRC8(1)+ETX(1) */
    int frame_total = 5 + payload_len;
    if (*len < frame_total) return 0;  /* データ不足 */

    /* ETX チェック */
    if (buf[frame_total - 1] != HUB_UART_ETX) {
        memmove(buf, buf + 1, *len - 1);
        (*len)--;
        return 0;
    }

    /* フレームを out に構築 */
    memset(out, 0, sizeof(*out));
    out->stx = buf[0];
    out->cmd = buf[1];
    out->len = buf[2];
    if (payload_len > 0) {
        memcpy(out->payload, buf + 3, payload_len);
    }
    out->crc8 = buf[3 + payload_len];
    out->etx  = buf[4 + payload_len];

    /* CRC 検証 */
    uint8_t calc = hub_uart_frame_calc_crc8(out);
    if (calc != out->crc8) {
        ESP_LOGW(TAG, "CRC mismatch: calc=0x%02X recv=0x%02X cmd=0x%02X",
                 calc, out->crc8, out->cmd);
        memmove(buf, buf + 1, *len - 1);
        (*len)--;
        return 0;
    }

    /* バッファからフレームを除去 */
    memmove(buf, buf + frame_total, *len - frame_total);
    *len -= frame_total;
    return 1;
}

/* ============================================================
 * 受信タスク (UART1 + USB Serial/JTAG を同一ループで処理)
 * ============================================================ */

static void rx_task(void *arg)
{
    uint8_t uart_accum[RX_ACCUM_SIZE];
    int     uart_len = 0;
    uint8_t usb_accum[RX_ACCUM_SIZE];
    int     usb_len  = 0;
    uint8_t tmp[RX_TMP_SIZE];
    hub_uart_frame_t frame;

    for (;;) {
        /* ---- UART1 受信 ---- */
        int n = uart_read_bytes(UART_PORT, tmp, sizeof(tmp), pdMS_TO_TICKS(0));
        if (n > 0) {
            int copy = (uart_len + n <= RX_ACCUM_SIZE) ? n : (RX_ACCUM_SIZE - uart_len);
            if (copy > 0) {
                memcpy(uart_accum + uart_len, tmp, copy);
                uart_len += copy;
            }
        }
        while (try_decode_frame(uart_accum, &uart_len, &frame)) {
            handle_command(&frame);
            s_last_cmd_tick = xTaskGetTickCount();
            s_hb_armed = true;
        }

        /* ---- USB Serial/JTAG 受信 ---- */
        n = usb_serial_jtag_read_bytes(tmp, sizeof(tmp), pdMS_TO_TICKS(0));
        if (n > 0) {
            int copy = (usb_len + n <= RX_ACCUM_SIZE) ? n : (RX_ACCUM_SIZE - usb_len);
            if (copy > 0) {
                memcpy(usb_accum + usb_len, tmp, copy);
                usb_len += copy;
            }
        }
        while (try_decode_frame(usb_accum, &usb_len, &frame)) {
            handle_command(&frame);
            s_last_cmd_tick = xTaskGetTickCount();
            s_hb_armed = true;
        }

        /* ---- ハートビートタイムアウト監視 ---- */
        if (s_hb_armed) {
            uint32_t elapsed_ms =
                (xTaskGetTickCount() - s_last_cmd_tick) * portTICK_PERIOD_MS;
            if (elapsed_ms >= HEARTBEAT_TIMEOUT_MS) {
                led_safe_white();
                s_hb_armed = false;
            }
        }

        vTaskDelay(pdMS_TO_TICKS(5));
    }
}

/* ============================================================
 * app_main
 * ============================================================ */

void app_main(void)
{
    ESP_LOGI(TAG, "lighting node boot v1.0 (ESP-IDF)");

    /* ---- LED ストリップ 1 初期化 (GPIO4) ---- */
    led_strip_config_t strip_cfg = {
        .strip_gpio_num   = GPIO_LED_STRIP1,
        .max_leds         = LED_COUNT_PER_STRIP,
        .led_pixel_format = LED_PIXEL_FORMAT_GRB,
        .led_model        = LED_MODEL_WS2812,
        .flags.invert_out = false,
    };
    led_strip_rmt_config_t rmt_cfg = {
        .clk_src        = RMT_CLK_SRC_DEFAULT,
        .resolution_hz  = 10 * 1000 * 1000,  /* 10 MHz */
        .flags.with_dma = false,
    };
    ESP_ERROR_CHECK(led_strip_new_rmt_device(&strip_cfg, &rmt_cfg, &s_strip[0]));

    /* ---- LED ストリップ 2 初期化 (GPIO5) ---- */
    strip_cfg.strip_gpio_num = GPIO_LED_STRIP2;
    ESP_ERROR_CHECK(led_strip_new_rmt_device(&strip_cfg, &rmt_cfg, &s_strip[1]));

    ESP_LOGI(TAG, "LED strips ready: GPIO%d x%d, GPIO%d x%d",
             GPIO_LED_STRIP1, LED_COUNT_PER_STRIP,
             GPIO_LED_STRIP2, LED_COUNT_PER_STRIP);

    /* ---- 起動時: safe_white (白 5%) ---- */
    led_flush(255, 255, 255, SAFE_BRIGHTNESS);
    ESP_LOGI(TAG, "initial state: safe_white brightness=%u", SAFE_BRIGHTNESS);

    /* ---- UART1 初期化 (GPIO17 TX / GPIO18 RX) ---- */
    uart_config_t uart_cfg = {
        .baud_rate  = UART_BAUD_RATE,
        .data_bits  = UART_DATA_8_BITS,
        .parity     = UART_PARITY_DISABLE,
        .stop_bits  = UART_STOP_BITS_1,
        .flow_ctrl  = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    ESP_ERROR_CHECK(uart_driver_install(UART_PORT, UART_RX_BUF_SIZE, 0, 0, NULL, 0));
    ESP_ERROR_CHECK(uart_param_config(UART_PORT, &uart_cfg));
    ESP_ERROR_CHECK(uart_set_pin(UART_PORT, GPIO_UART_TX, GPIO_UART_RX,
                                 UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
    ESP_LOGI(TAG, "UART1 ready: TX=GPIO%d RX=GPIO%d @ %d bps",
             GPIO_UART_TX, GPIO_UART_RX, UART_BAUD_RATE);

    /* ---- USB Serial/JTAG 初期化 (COM3 直結) ---- */
    usb_serial_jtag_driver_config_t usb_cfg = {
        .rx_buffer_size = USB_RX_BUF_SIZE,
        .tx_buffer_size = USB_RX_BUF_SIZE,
    };
    ESP_ERROR_CHECK(usb_serial_jtag_driver_install(&usb_cfg));
    ESP_LOGI(TAG, "USB Serial/JTAG ready");

    /* ---- 受信タスク起動 ---- */
    xTaskCreate(rx_task, "rx_task", 4096, NULL, 10, NULL);

    ESP_LOGI(TAG, "waiting for UART commands...");
}
