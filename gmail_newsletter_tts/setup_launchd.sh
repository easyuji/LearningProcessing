#!/bin/bash
# launchd タイマーをインストールするセットアップスクリプト
# 使い方: bash gmail_newsletter_tts/setup_launchd.sh

set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT_DIR="$REPO_DIR/gmail_newsletter_tts"
HOME_DIR="$HOME"
PLIST_NAME="com.easyuji.newsletter-tts.plist"
PLIST_SRC="$SCRIPT_DIR/$PLIST_NAME"
PLIST_DST="$HOME_DIR/Library/LaunchAgents/$PLIST_NAME"

echo "📂 リポジトリ: $REPO_DIR"
echo "🏠 ホーム:     $HOME_DIR"

# run.sh に実行権限を付与
chmod +x "$SCRIPT_DIR/run.sh"

# plist のプレースホルダーを実際のパスに置換して LaunchAgents にコピー
sed \
    -e "s|__REPO_DIR__|$REPO_DIR|g" \
    -e "s|__HOME__|$HOME_DIR|g" \
    "$PLIST_SRC" > "$PLIST_DST"

echo "📄 plist を配置: $PLIST_DST"

# 既存のジョブをアンロード（エラーは無視）
launchctl unload "$PLIST_DST" 2>/dev/null || true

# 登録
launchctl load "$PLIST_DST"

echo ""
echo "✅ 完了！毎朝7時に自動実行されます。"
echo ""
echo "📋 確認コマンド:   launchctl list | grep newsletter"
echo "📝 ログ確認:       tail -f ~/newsletter-tts.log"
echo "🧪 今すぐテスト:   bash $SCRIPT_DIR/run.sh"
echo "🗑  削除するには:   launchctl unload $PLIST_DST && rm $PLIST_DST"
