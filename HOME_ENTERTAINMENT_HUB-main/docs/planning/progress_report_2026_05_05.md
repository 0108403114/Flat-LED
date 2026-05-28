# 作業申し送りメモ

## 最終更新: 2026-05-05

---

## 本日（2026-05-05）の作業内容

### TouchDesigner × GitHub Copilot MCP 連携環境セットアップ

#### 完了したこと

1. **Node.js v24.15.0 LTS インストール**
   - インストーラー: `node-v24.15.0-x64.msi`
   - `node --version` → `v24.15.0`
   - `npx --version` → `11.12.1`

2. **TouchDesigner 側セットアップ**
   - `touchdesigner-mcp-td.zip` をダウンロード・展開
   - 配置場所: `C:\Projects\02_HomeLiveHall_Trial01\touchdesigner-mcp-td\`
     ```
     touchdesigner-mcp-td/
     ├── mcp_webserver_base.tox   ← TDにインポートするコンポーネント
     ├── import_modules.py
     └── modules/                 ← tox と同階層に必須（相対パス参照）
         ├── mcp/
         ├── utils/
         └── td_server/
     ```
   - TouchDesigner Python Console で以下を実行してインポート成功：
     ```python
     op('/project1').loadTox(r'C:\Projects\02_HomeLiveHall_Trial01\touchdesigner-mcp-td\mcp_webserver_base.tox')
     ```
   - HTTP Server が `http://127.0.0.1:9981` で起動（ポート 9981）
   - ログ確認: `HTTP SERVER STARTED` / API Version: 1.4.3

3. **VS Code（GitHub Copilot）側セットアップ**
   - `.vscode/mcp.json`（プロジェクト固有）を作成済み:
     ```json
     {
       "servers": {
         "touchdesigner": {
           "type": "stdio",
           "command": "npx",
           "args": ["-y", "touchdesigner-mcp-server@latest", "--stdio"]
         }
       }
     }
     ```
   - User `settings.json`（全プロジェクト共通）にも追加済み:
     `C:\Users\shin_\AppData\Roaming\Code\User\settings.json`
     ```json
     "mcp": {
         "servers": {
             "touchdesigner": {
                 "type": "stdio",
                 "command": "npx",
                 "args": ["-y", "touchdesigner-mcp-server@latest", "--stdio"]
             }
         }
     }
     ```

4. **動作確認済み**
   - GitHub Copilot Agent モードのツール一覧に `touchdesigner` が表示
   - `get_td_info` で TouchDesigner サーバー情報を正常取得:
     - TouchDesigner Version: 099.2025.32050
     - API Server Version: 1.4.3
     - MCP Server Version: 1.4.7
     - OS: Windows 10

---

## 次回作業時の注意点

### TouchDesigner MCP を使う際の毎回の手順

1. **TouchDesigner を起動**
2. **Python Console で `mcp_webserver_base.tox` をインポート**（プロジェクト保存していない場合）
   ```python
   op('/project1').loadTox(r'C:\Projects\02_HomeLiveHall_Trial01\touchdesigner-mcp-td\mcp_webserver_base.tox')
   ```
3. Textport で `HTTP SERVER STARTED` が表示されていることを確認
4. **VS Code を開いて GitHub Copilot Agent モードで利用開始**

> **重要**: `mcp_webserver_base.tox` と `modules/` フォルダは必ず同じディレクトリに置くこと。フォルダ構成を変えるとモジュールが見つからずエラーになる。

### TDプロジェクトを永続化したい場合

- TouchDesigner で **File → Save As** でプロジェクト（`.toe`）を保存しておけば、次回起動時に `mcp_webserver_base` が自動的に読み込まれる
- 保存推奨パス: `C:\Projects\02_HomeLiveHall_Trial01\touchdesigner-mcp-td\`

---

## 利用可能な MCP ツール一覧

| ツール名 | 説明 |
|---|---|
| `create_td_node` | ノードの作成 |
| `delete_td_node` | ノードの削除 |
| `exec_node_method` | ノードのPythonメソッド実行 |
| `execute_python_script` | TDで任意のPythonスクリプト実行 |
| `get_td_info` | サーバー情報取得 |
| `get_td_nodes` | ノード一覧取得 |
| `get_td_node_parameters` | ノードパラメータ取得 |
| `update_td_node_parameters` | ノードパラメータ更新 |
| `get_td_node_errors` | ノードエラー確認 |
| `get_td_classes` | TDのPythonクラス一覧 |
| `get_td_class_details` | TDのPythonクラス詳細 |
| `get_td_module_help` | Pythonモジュールヘルプ取得 |

---

## 次のステップ候補

- [ ] TouchDesigner から ESP32（COM3）経由で `hub_protocol` UARTフレームを送出する検証（Phase E）
- [ ] TouchDesigner プロジェクトを `.toe` ファイルとして保存し、起動時に自動ロードされるよう設定
- [ ] LED ビジュアライザーなど具体的な演出の TouchDesigner → ESP32 連携実装
