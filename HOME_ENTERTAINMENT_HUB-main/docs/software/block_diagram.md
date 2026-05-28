# ソフトブロック図

> **最終更新**: 2026-04-xx（初版）｜**参照時点**: 2026-05-02 現在も有効

```mermaid
flowchart TD
    MIC[Microphone Input] --> IM[Input Manager]
    EXT[AudioLINKCORE Input] --> IM
    IM --> AA[Audio Analyzer]
    IM --> ER[External Control Receiver]
    AA --> SE[Scene Engine]
    ER --> SE
    UI[Local UI] --> SE
    CFG[Config Store] --> SE
    CAT[Asset Catalog] --> SE
    SE --> UARTD[Local UART Dispatcher]
    SE --> WD[Wi-Fi Dispatcher]
    UARTD --> RX0[Local LED Node Receiver]
    WD --> RX1[Satellite Receiver]
    WD --> RX2[Satellite Receiver]
    RX0 --> PARSE0[Command Parser]
    RX1 --> PARSE1[Command Parser]
    RX2 --> PARSE2[Command Parser]
    PARSE0 --> ASSET0[Asset Loader]
    PARSE1 --> ASSET1[Asset Loader]
    PARSE2 --> ASSET2[Asset Loader]
    SD0[microSD via SDMMC] --> ASSET0
    SD1[microSD via SDMMC] --> ASSET1
    SD2[microSD via SDMMC] --> ASSET2
    ASSET0 --> FX0[Effect Renderer]
    ASSET1 --> FX1[Effect Renderer]
    ASSET2 --> FX2[Effect Renderer]
    FX0 --> LED0[LED Driver]
    FX1 --> LED1[LED Driver]
    FX2 --> LED2[LED Driver]
```

## 設計意図

- 中央ノードは入力源を吸収して、UART と Wi-Fi の両方へ同じ論理コマンドを配る。
- 照明ノードは解析負荷を持たず、ローカル microSD 上の演出データを参照して描画する。
- 将来のサテライトノードは ESP32 と microSD を核にした共通ノード化を前提にする。
