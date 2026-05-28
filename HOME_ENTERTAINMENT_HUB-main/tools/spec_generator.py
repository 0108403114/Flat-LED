from pathlib import Path


JP_CONTENT = """# HOME_ENTERTAINMENT_HUB 仕様書

## 使用シーン

1. ライブ映像視聴時に音に合わせてリビングをライブ空間化する。
2. 就寝前に音楽に合わせてヒーリング空間を作る。

## 初期版方針

- 主音声入力はマイク
- PC 再生時は AudioLINKCORE の制御信号を利用
- 照明ノードは Wi-Fi で演出パラメータを受信
"""


EN_CONTENT = """# HOME_ENTERTAINMENT_HUB Specification

## Usage Scenes

1. Turn the living room into a live venue while watching concert videos.
2. Turn the living room into a healing space before sleep.

## Initial Version

- Primary audio input is a microphone
- AudioLINKCORE provides external control data for PC playback
- Lighting nodes receive effect parameters over Wi-Fi
"""


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    specs_dir = root / "docs" / "specifications"
    write_file(specs_dir / "HOME_ENTERTAINMENT_HUB_Spec_JP.generated.md", JP_CONTENT)
    write_file(specs_dir / "HOME_ENTERTAINMENT_HUB_Spec_EN.generated.md", EN_CONTENT)
    print("generated markdown files")


if __name__ == "__main__":
    main()