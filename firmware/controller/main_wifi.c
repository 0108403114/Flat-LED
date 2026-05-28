/*
 * firmware/controller/main_wifi.c
 *
 * 中央ノードファームウェア (ESP-IDF) - Wi-Fi 受信対応版
 * 
 * 受信経路:
 *   1. Wi-Fi UDP (ポート 5000) - PC / スマホ制御
 *   2. UART1 (GPIO43 TX / GPIO44 RX) - LED ノードへの配信
 *
 * Wi-Fi 設定:
 *   SSID: FXC-5G-E25OZX
 *   Password: cu4nm3s4
 *
 * フレーム形式: hub_protocol.h の UART 仕様を参照
 *   [STX 0xAA][CMD 1B][LEN 1B][PAYLOAD 0-32B][CRC8 1B][ETX 0x55]
 */

#include <stdio.h>
#include <string.h>

#include "driver/i2c.h"
#include "driver/uart.h"
#include "esp_err.h"
#include "esp_log.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include "lwip/sockets.h"
#include "lwip/netdb.h"

#include "hub_protocol.h"

static const char *TAG = "controller";

/* ============================================================
 * Wi-Fi & ネットワーク設定
 * ============================================================ */

#define WIFI_SSID           "FXC-5G-E25OZX"
#define WIFI_PASS           "cu4nm3s4"
#define WIFI_MAXIMUM_RETRY  5
#define UDP_PORT            5000

static EventGroupHandle_t s_wifi_event_group;
#define WIFI_CONNECTED_BIT BIT0
#define WIFI_FAIL_BIT      BIT1

static int s_retry_num = 0;

/* ============================================================
 * ピン・定数定義
 * ============================================================ */

#define I2C_PORT            I2C_NUM_0
#define I2C_SDA_GPIO        1   /* XIAO D0 */
#define I2C_SCL_GPIO        2   /* XIAO D1 */
#define I2C_FREQ_HZ         100000

#define UART_PORT           UART_NUM_1
#define UART_TX_GPIO        43  /* XIAO D6 */
#define UART_RX_GPIO        44  /* XIAO D7 */
#define UART_BAUD           115200

#define BH1750_ADDR         0x23
#define INA228_ADDR         0x40

#define INA228_REG_MANUF_ID 0x3E
#define INA228_REG_DEVICE_ID 0x3F
#define INA228_REG_VBUS     0x05
#define INA228_REG_POWER    0x08

/* ============================================================
 * Wi-Fi イベントハンドラ
 * ============================================================ */

static void wifi_event_handler(void* arg, esp_event_base_t event_base,
                               int32_t event_id, void* event_data)
{
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        if (s_retry_num < WIFI_MAXIMUM_RETRY) {
            esp_wifi_connect();
            s_retry_num++;
            ESP_LOGI(TAG, "retry to connect to the AP");
        } else {
            xEventGroupSetBits(s_wifi_event_group, WIFI_FAIL_BIT);
        }
        ESP_LOGI(TAG, "connect to the AP fail");
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t* event = (ip_event_got_ip_t*) event_data;
        ESP_LOGI(TAG, "got ip:" IPSTR, IP2STR(&event->ip_info.ip));
        s_retry_num = 0;
        xEventGroupSetBits(s_wifi_event_group, WIFI_CONNECTED_BIT);
    }
}

static void wifi_init_sta(void)
{
    s_wifi_event_group = xEventGroupCreate();

    ESP_ERROR_CHECK(esp_netif_init());

    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    esp_event_handler_instance_t instance_any_id;
    esp_event_handler_instance_t instance_got_ip;
    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT,
                                                        ESP_EVENT_ANY_ID,
                                                        &wifi_event_handler,
                                                        NULL,
                                                        &instance_any_id));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT,
                                                        IP_EVENT_STA_GOT_IP,
                                                        &wifi_event_handler,
                                                        NULL,
                                                        &instance_got_ip));

    wifi_config_t wifi_config = {
        .sta = {
            .ssid = WIFI_SSID,
            .password = WIFI_PASS,
            .threshold.authmode = WIFI_AUTH_WPA2_PSK,
            .sae_pwe_h2e = WPA3_SAE_PWE_BOTH,
        },
    };
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA) );
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config) );
    ESP_ERROR_CHECK(esp_wifi_start() );

    ESP_LOGI(TAG, "wifi_init_sta finished.");

    EventBits_t bits = xEventGroupWaitBits(s_wifi_event_group,
            WIFI_CONNECTED_BIT | WIFI_FAIL_BIT,
            pdFALSE,
            pdFALSE,
            portMAX_DELAY);

    if (bits & WIFI_CONNECTED_BIT) {
        ESP_LOGI(TAG, "connected to ap SSID:%s password:%s", WIFI_SSID, WIFI_PASS);
    } else if (bits & WIFI_FAIL_BIT) {
        ESP_LOGI(TAG, "Failed to connect to SSID:%s, password:%s", WIFI_SSID, WIFI_PASS);
    } else {
        ESP_LOGE(TAG, "UNEXPECTED EVENT");
    }
}

/* ============================================================
 * I2C 関連（既存コードと同じ）
 * ============================================================ */

static esp_err_t i2c_master_init(void)
{
    i2c_config_t conf = {
        .mode = I2C_MODE_MASTER,
        .sda_io_num = I2C_SDA_GPIO,
        .scl_io_num = I2C_SCL_GPIO,
        .sda_pullup_en = GPIO_PULLUP_ENABLE,
        .scl_pullup_en = GPIO_PULLUP_ENABLE,
        .master.clk_speed = I2C_FREQ_HZ,
        .clk_flags = 0,
    };

    esp_err_t err = i2c_param_config(I2C_PORT, &conf);
    if (err != ESP_OK) {
        return err;
    }
    return i2c_driver_install(I2C_PORT, conf.mode, 0, 0, 0);
}

static void i2c_scan_bus(void)
{
    ESP_LOGI(TAG, "I2C scan start (SDA=%d SCL=%d)", I2C_SDA_GPIO, I2C_SCL_GPIO);
    int found = 0;

    for (uint8_t addr = 1; addr < 0x78; addr++) {
        i2c_cmd_handle_t cmd = i2c_cmd_link_create();
        i2c_master_start(cmd);
        i2c_master_write_byte(cmd, (addr << 1) | I2C_MASTER_WRITE, true);
        i2c_master_stop(cmd);
        esp_err_t ret = i2c_master_cmd_begin(I2C_PORT, cmd, pdMS_TO_TICKS(30));
        i2c_cmd_link_delete(cmd);

        if (ret == ESP_OK) {
            ESP_LOGI(TAG, "I2C device found: 0x%02X", addr);
            found++;
        }
    }
    ESP_LOGI(TAG, "I2C scan done, found=%d", found);
}

static esp_err_t i2c_read_reg16(uint8_t dev_addr, uint8_t reg, uint16_t *out)
{
    uint8_t data[2] = {0};
    esp_err_t err = i2c_master_write_read_device(
        I2C_PORT,
        dev_addr,
        &reg,
        1,
        data,
        sizeof(data),
        pdMS_TO_TICKS(100));
    if (err != ESP_OK) {
        return err;
    }

    *out = ((uint16_t)data[0] << 8) | data[1];
    return ESP_OK;
}

static esp_err_t i2c_read_reg24(uint8_t dev_addr, uint8_t reg, uint32_t *out)
{
    uint8_t data[3] = {0};
    esp_err_t err = i2c_master_write_read_device(
        I2C_PORT,
        dev_addr,
        &reg,
        1,
        data,
        sizeof(data),
        pdMS_TO_TICKS(100));
    if (err != ESP_OK) {
        return err;
    }

    *out = ((uint32_t)data[0] << 16) | ((uint32_t)data[1] << 8) | data[2];
    return ESP_OK;
}

static void bh1750_read_once(void)
{
    uint8_t cmd = 0x20;  /* One-time H-resolution mode */
    uint8_t data[2] = {0};

    esp_err_t err = i2c_master_write_to_device(I2C_PORT, BH1750_ADDR, &cmd, 1, pdMS_TO_TICKS(100));
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "BH1750 write failed: %s", esp_err_to_name(err));
        return;
    }

    vTaskDelay(pdMS_TO_TICKS(180));

    err = i2c_master_read_from_device(I2C_PORT, BH1750_ADDR, data, sizeof(data), pdMS_TO_TICKS(100));
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "BH1750 read failed: %s", esp_err_to_name(err));
        return;
    }

    uint16_t raw = ((uint16_t)data[0] << 8) | data[1];
    float lux = raw / 1.2f;
    ESP_LOGI(TAG, "BH1750 raw=%u lux=%.1f", raw, lux);
}

static void ina228_probe(void)
{
    uint16_t manuf = 0;
    uint16_t device = 0;
    uint32_t vbus_raw = 0;
    uint32_t power_raw = 0;

    esp_err_t err_m = i2c_read_reg16(INA228_ADDR, INA228_REG_MANUF_ID, &manuf);
    esp_err_t err_d = i2c_read_reg16(INA228_ADDR, INA228_REG_DEVICE_ID, &device);
    esp_err_t err_v = i2c_read_reg24(INA228_ADDR, INA228_REG_VBUS, &vbus_raw);
    esp_err_t err_p = i2c_read_reg24(INA228_ADDR, INA228_REG_POWER, &power_raw);

    if (err_m == ESP_OK && err_d == ESP_OK) {
        ESP_LOGI(TAG, "INA228 ID manuf=0x%04X device=0x%04X", manuf, device);
    } else {
        ESP_LOGW(TAG, "INA228 ID read failed: manuf=%s device=%s",
                 esp_err_to_name(err_m), esp_err_to_name(err_d));
    }

    if (err_v == ESP_OK) {
        ESP_LOGI(TAG, "INA228 VBUS raw=0x%06lX", (unsigned long)vbus_raw);
    } else {
        ESP_LOGW(TAG, "INA228 VBUS read failed: %s", esp_err_to_name(err_v));
    }

    if (err_p == ESP_OK) {
        ESP_LOGI(TAG, "INA228 POWER raw=0x%06lX", (unsigned long)power_raw);
    } else {
        ESP_LOGW(TAG, "INA228 POWER read failed: %s", esp_err_to_name(err_p));
    }
}

/* ============================================================
 * UART 関連
 * ============================================================ */

static esp_err_t uart_link_init(void)
{
    const uart_config_t cfg = {
        .baud_rate = UART_BAUD,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };

    esp_err_t err = uart_driver_install(UART_PORT, 1024, 0, 0, NULL, 0);
    if (err != ESP_OK) {
        return err;
    }

    err = uart_param_config(UART_PORT, &cfg);
    if (err != ESP_OK) {
        return err;
    }

    return uart_set_pin(UART_PORT, UART_TX_GPIO, UART_RX_GPIO, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);
}

static void uart_send_frame(const hub_uart_frame_t *frame)
{
    uint8_t bytes[HUB_UART_FRAME_MAX_LEN] = {0};
    int len = hub_uart_frame_encode(frame, bytes, sizeof(bytes));
    if (len <= 0) {
        ESP_LOGE(TAG, "frame encode failed");
        return;
    }

    uart_write_bytes(UART_PORT, (const char *)bytes, len);
}

static void uart_send_set_color(uint8_t r, uint8_t g, uint8_t b)
{
    hub_uart_frame_t frame;
    hub_uart_frame_set_color(&frame, r, g, b);
    uart_send_frame(&frame);
    ESP_LOGI(TAG, "UART SET_COLOR sent rgb=(%u,%u,%u)", r, g, b);
}

static void uart_send_heartbeat(void)
{
    hub_uart_frame_t frame;
    hub_uart_frame_heartbeat(&frame);
    uart_send_frame(&frame);
}

/* ============================================================
 * UDP 受信タスク
 * ============================================================ */

static void udp_rx_task(void *arg)
{
    int sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (sock < 0) {
        ESP_LOGE(TAG, "Unable to create socket: %d", errno);
        vTaskDelete(NULL);
        return;
    }

    struct sockaddr_in addr;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_family = AF_INET;
    addr.sin_port = htons(UDP_PORT);

    if (bind(sock, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        ESP_LOGE(TAG, "socket bind failed: %d", errno);
        close(sock);
        vTaskDelete(NULL);
        return;
    }

    ESP_LOGI(TAG, "UDP socket listening on port %d", UDP_PORT);

    uint8_t rx_buffer[512];
    struct sockaddr_in source_addr;

    while (1) {
        socklen_t socklen = sizeof(source_addr);
        int len = recvfrom(sock, rx_buffer, sizeof(rx_buffer) - 1, 0,
                          (struct sockaddr *)&source_addr, &socklen);

        if (len < 0) {
            ESP_LOGE(TAG, "recvfrom failed: %d", errno);
            continue;
        }

        ESP_LOGI(TAG, "Received %d bytes from %s:%d", len,
                inet_ntoa(source_addr.sin_addr), ntohs(source_addr.sin_port));

        /* フレームデコード（hub_protocol を使用） */
        hub_uart_frame_t frame;
        memset(&frame, 0, sizeof(frame));

        /* 簡易デコード: payload が RGB データと仮定 */
        if (len >= 3) {
            uart_send_set_color(rx_buffer[0], rx_buffer[1], rx_buffer[2]);
        }

        vTaskDelay(pdMS_TO_TICKS(100));
    }

    close(sock);
    vTaskDelete(NULL);
}

/* ============================================================
 * link_task (定期的に LED を循環させる)
 * ============================================================ */

static void link_task(void *arg)
{
    uint8_t step = 0;

    while (1) {
        switch (step % 3) {
            case 0:
                uart_send_set_color(255, 0, 0);  /* Red */
                break;
            case 1:
                uart_send_set_color(0, 255, 0);  /* Green */
                break;
            default:
                uart_send_set_color(0, 0, 255);  /* Blue */
                break;
        }
        step++;

        uart_send_heartbeat();
        vTaskDelay(pdMS_TO_TICKS(3000));  /* 3秒ごと */
    }
}

/* ============================================================
 * app_main
 * ============================================================ */

void app_main(void)
{
    ESP_LOGI(TAG, "controller boot (Wi-Fi enabled)");

    /* I2C 初期化 */
    esp_err_t err = i2c_master_init();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "I2C init failed: %s", esp_err_to_name(err));
        return;
    }

    i2c_scan_bus();
    bh1750_read_once();
    ina228_probe();

    /* UART 初期化 */
    err = uart_link_init();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "UART init failed: %s", esp_err_to_name(err));
        return;
    }
    ESP_LOGI(TAG, "UART1 ready TX=%d RX=%d baud=%d", UART_TX_GPIO, UART_RX_GPIO, UART_BAUD);

    /* Wi-Fi 初期化 */
    wifi_init_sta();

    /* UDP 受信タスク起動 */
    xTaskCreate(udp_rx_task, "udp_rx_task", 4096, NULL, 5, NULL);

    /* LED 循環タスク起動 */
    xTaskCreate(link_task, "link_task", 4096, NULL, 5, NULL);

    ESP_LOGI(TAG, "all tasks started");
}
