# LearningProcessing プロジェクト

## このプロジェクトについて

GmailのメルマガやKindle本をポッドキャストMP3に変換するシステム。
Edge TTS / OpenAI TTS で音声化し、GitHub Releases に保存、RSSフィードで配信。

---

## 引き継ぎ作業（2025-05-25時点）

### 今やりたいこと

**Kindle Cloud Reader (read.amazon.co.jp) の本をポッドキャスト化する**

`kindle_book_tts/` モジュールを作成済み。Mac でのセットアップと実行が必要。

### 次のステップ

```bash
# 1. 依存インストール（初回のみ）
cd ~/LearningProcessing/kindle_book_tts
pip install -r requirements.txt
playwright install chromium

# 2. 実行
# まずSafari/ChromeでKindle Cloud Readerを開き、本のURLをコピーしてから：
python main.py \
  --url "https://read.amazon.co.jp/reader/..." \
  --title "インザメガチャーチ" \
  --max-pages 50
```

初回はChromiumが開いてAmazonログイン画面が出る → ログイン後Enterを押す。

---

## ディレクトリ構成

```
LearningProcessing/
├── gmail_newsletter_tts/     # メルマガ→ポッドキャスト（稼働中）
│   ├── main.py               # メインエントリポイント
│   ├── gmail_client.py       # Gmail取得
│   ├── tts_client.py         # TTS（Edge/OpenAI）
│   ├── github_client.py      # GitHub Releasesアップロード
│   ├── podcast_feed.py       # RSS feed生成・push
│   ├── script_converter.py   # Claude APIで読み上げ最適化
│   ├── config.py             # 設定（Keychain / .env）
│   └── ...
└── kindle_book_tts/          # Kindle本→ポッドキャスト（新規・要セットアップ）
    ├── main.py               # エントリポイント（章分割→TTS→upload→feed）
    ├── kindle_scraper.py     # Playwrightでページめくり&テキスト抽出
    ├── requirements.txt      # playwright のみ追加（他はgmail側を共有）
    └── README.md
```

## 共有設定

`kindle_book_tts/main.py` は `gmail_newsletter_tts/` の以下を `sys.path` 経由で共有：
- `config.py` — OPENAI_API_KEY, ANTHROPIC_API_KEY, GITHUB_TOKEN 等（Keychain）
- `tts_client.py` — TTS生成
- `github_client.py` — MP3アップロード
- `podcast_feed.py` — feed.xml更新
- `script_converter.py` — Claude APIで読み上げスクリプト変換

## トラブルシューティング

| 症状 | 対処 |
|---|---|
| ページが進まない | `--navigate ArrowRight` を追加 |
| テキスト抽出が空 | ブラウザで本が開いているか確認 |
| TTS失敗 | `_extracted.txt` が保存済み → `--text-file` で再実行 |
