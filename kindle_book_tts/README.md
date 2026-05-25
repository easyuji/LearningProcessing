# Kindle本 → ポッドキャスト変換ツール

Kindle Cloud Reader (read.amazon.co.jp) で開いた本のテキストを自動抽出し、
メルマガと同じパイプラインでポッドキャストMP3に変換します。

## 仕組み

```
Kindle Cloud Reader
        ↓ Playwright（ブラウザ自動操作）
    テキスト抽出
        ↓
    章ごとに分割
        ↓
   Claude API でスクリプト変換（読み上げ最適化）
        ↓
  Edge TTS / OpenAI TTS で MP3 生成
        ↓
  GitHub Releases にアップロード
        ↓
  podcast/feed.xml に追加 → ポッドキャストアプリで聴ける
```

## セットアップ（初回のみ）

```bash
cd kindle_book_tts

# Playwrightをインストール
pip install -r requirements.txt
playwright install chromium
```

## 使い方

### ステップ1: Kindle Cloud Reader で本のURLを取得

1. Mac の Safari / Chrome で [read.amazon.co.jp](https://read.amazon.co.jp) を開く
2. 読みたい本をクリックして開く
3. アドレスバーの URL をコピー

### ステップ2: 実行

```bash
python main.py \
  --url "https://read.amazon.co.jp/reader/..." \
  --title "インザメガチャーチ"
```

**初回のみ**: ブラウザが開いてAmazonのログイン画面が表示されます。  
ログインして本が開いた状態になったらターミナルで Enter を押してください。  
（2回目以降はログイン不要）

### オプション一覧

| オプション | 説明 | デフォルト |
|---|---|---|
| `--url URL` | Kindle Cloud Reader の URL | ※ --text-file と二択 |
| `--title TEXT` | 本のタイトル（ポッドキャストのエピソード名になる） | **必須** |
| `--max-pages N` | 最大取得ページ数 | `100` |
| `--navigate KEY` | ページ送りキー | `ArrowLeft` |
| `--text-file FILE` | 抽出済みテキストファイルを使用 | - |
| `--chunk-size N` | 章検出失敗時の分割文字数 | `15000` |

### ページ送りキーについて

| 書籍の種類 | 推奨キー |
|---|---|
| 日本語書籍（縦書き・右から左） | `ArrowLeft`（デフォルト） |
| 英語書籍（横書き・左から右） | `ArrowRight` |

ページが進まない場合は逆のキーをお試しください：
```bash
python main.py --url "..." --title "..." --navigate ArrowRight
```

## 抽出テキストの再利用

スクレイピング成功時に `<タイトル>_extracted.txt` が保存されます。  
TTS設定を変えて再実行したい場合はこれを使うことでスクレイピングを省略できます：

```bash
python main.py \
  --text-file in-the-megachurch_extracted.txt \
  --title "インザメガチャーチ"
```

## 注意事項

- このツールは**個人の私的利用**を目的としています
- 抽出したテキストは著作権で保護されています。配布・転載は行わないでください
- Amazon の利用規約上、自動化アクセスは推奨されていません。過度な高速アクセスはお控えください
