# ハードブロック図

> **最終更新**: 2026-04-xx（初版）｜**参照時点**: 2026-05-02 現在も有効

```mermaid
flowchart LR
    MIC[I2S Mic] --> CTRL[Central Node ESP32-S3]
    TFT[TFT Display] --> CTRL
    BTN[Buttons] --> CTRL
    ALC[AudioLINKCORE via USB or Serial] --> CTRL
    CTRL -->|UART Preset Commands| LNODE[Local LED Node]
    CTRL -->|Wi-Fi Preset Commands| NODE1[Satellite LED Node A]
    CTRL -->|Wi-Fi Preset Commands| NODE2[Satellite LED Node B]
    CTRL -->|Wi-Fi Preset Commands| NODE3[Satellite LED Node N]
    PSU1[5V Power] --> CTRL
    PSU0[5V Power] --> LNODE
    PSU2[5V Power] --> NODE1
    PSU3[5V Power] --> NODE2
    LNODE --> SDL[microSD via SDMMC]
    LNODE --> LED0[WS2812 Matrix]
    NODE1 --> SD1[microSD via SDMMC]
    NODE2 --> SD2[microSD via SDMMC]
    NODE3 --> SD3[microSD via SDMMC]
    NODE1 --> LED1[WS2812 Matrix]
    NODE2 --> LED2[WS2812 Matrix]
    NODE3 --> LED3[WS2812 Matrix]
```

## ブロック要点

- 中央ノードは入力集約と演出配信を担当する。
- ローカル LED ノードは中央ノードと UART 直結し、同じ論理コマンドを低遅延で受ける。
- サテライト LED ノードは Wi-Fi で同じ論理コマンドを受け、microSD 上のローカルデータを参照しながら描画を行う。
- 音声データはノードへ直接配信しない。
- 大容量イルミネーションデータは各照明ノードの microSD に保持する。
