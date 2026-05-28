#include <stdio.h>
#include <string.h>

#include "driver/i2c.h"
#include "driver/uart.h"
#include "esp_err.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "hub_protocol.h"

static const char *TAG = "controller";

/* XIAO ESP32S3 (USB-first bring-up) default pin plan */
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

static void uart_send_set_color(uint8_t r, uint8_t g, uint8_t b)
{
    hub_uart_frame_t frame;
    uint8_t bytes[HUB_UART_FRAME_MAX_LEN] = {0};

    hub_uart_frame_set_color(&frame, r, g, b);
    int len = hub_uart_frame_encode(&frame, bytes, sizeof(bytes));
    if (len <= 0) {
        ESP_LOGE(TAG, "SET_COLOR encode failed");
        return;
    }

    uart_write_bytes(UART_PORT, (const char *)bytes, len);
    ESP_LOGI(TAG, "UART SET_COLOR sent rgb=(%u,%u,%u) len=%d", r, g, b, len);
}

static void uart_send_heartbeat(void)
{
    hub_uart_frame_t frame;
    uint8_t bytes[HUB_UART_FRAME_MAX_LEN] = {0};

    hub_uart_frame_heartbeat(&frame);
    int len = hub_uart_frame_encode(&frame, bytes, sizeof(bytes));
    if (len <= 0) {
        ESP_LOGE(TAG, "HEARTBEAT encode failed");
        return;
    }

    uart_write_bytes(UART_PORT, (const char *)bytes, len);
}

static void link_task(void *arg)
{
    uint8_t step = 0;

    while (1) {
        switch (step % 3) {
            case 0:
                uart_send_set_color(255, 0, 0);
                break;
            case 1:
                uart_send_set_color(0, 255, 0);
                break;
            default:
                uart_send_set_color(0, 0, 255);
                break;
        }
        step++;

        uart_send_heartbeat();
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

void app_main(void)
{
    ESP_LOGI(TAG, "controller boot (XIAO USB-first bring-up)");

    esp_err_t err = i2c_master_init();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "I2C init failed: %s", esp_err_to_name(err));
        return;
    }

    i2c_scan_bus();
    bh1750_read_once();
    ina228_probe();

    err = uart_link_init();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "UART init failed: %s", esp_err_to_name(err));
        return;
    }
    ESP_LOGI(TAG, "UART1 ready TX=%d RX=%d baud=%d", UART_TX_GPIO, UART_RX_GPIO, UART_BAUD);

    xTaskCreate(link_task, "link_task", 4096, NULL, 5, NULL);
}
