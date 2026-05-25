"""
Kindle Cloud Reader テキスト抽出モジュール（Playwright使用）

ブラウザを可視状態で起動し、ログイン後にページを自動めくりしながら
テキストを抽出します。ログイン情報はブラウザプロファイルに保存されるため
2回目以降はログイン不要です。
"""

import asyncio
import hashlib
from pathlib import Path

from playwright.async_api import async_playwright

# ブラウザのログイン情報・Cookie保存先
BROWSER_DATA_DIR = Path.home() / ".kindle_tts_browser"


def _text_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


async def _extract_page_text(page) -> str:
    """現在のKindle Cloud Readerページからテキストを抽出する（複数戦略）"""

    # 戦略1: サブフレーム（Kindleはiframeを使うことがある）
    for frame in page.frames:
        if frame is page.main_frame:
            continue
        try:
            body_text = await frame.inner_text("body", timeout=1500)
            if body_text and len(body_text.strip()) > 50:
                return body_text.strip()
        except Exception:
            pass

    # 戦略2: JavaScript でKindleのコンテンツ領域を特定
    try:
        result = await page.evaluate("""
            () => {
                const selectors = [
                    '.kfre-container',
                    '#book-reader',
                    '[class*="kindleReader"]',
                    '[id*="book-reader"]',
                    '[class*="bookReader"]',
                    '[class*="content-area"]',
                    '.kr-text-content',
                    '[data-a-target="kindle-reader"]',
                ];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el && el.innerText && el.innerText.trim().length > 50) {
                        return el.innerText.trim();
                    }
                }
                // 同一オリジンのiframeを試みる
                for (const iframe of document.querySelectorAll('iframe')) {
                    try {
                        const t = iframe.contentDocument?.body?.innerText?.trim();
                        if (t && t.length > 50) return t;
                    } catch (_) {}
                }
                return null;
            }
        """)
        if result and len(result.strip()) > 50:
            return result.strip()
    except Exception:
        pass

    # 戦略3: ページ全体のテキスト（最終手段）
    try:
        text = await page.inner_text("body", timeout=2000)
        return text.strip()
    except Exception:
        return ""


async def _scrape_async(url: str, max_pages: int, navigate_key: str) -> str:
    """非同期スクレイピング本体"""
    BROWSER_DATA_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        print(f"ブラウザを起動中... (設定保存先: {BROWSER_DATA_DIR})")
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_DATA_DIR),
            headless=False,                       # Kindleは可視ブラウザが必要
            viewport={"width": 1280, "height": 800},
            locale="ja-JP",
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
        )

        page = await ctx.new_page()

        print("Kindle Cloud Reader を開いています...")
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)

        # ログイン確認
        current_url = page.url
        if any(kw in current_url for kw in ["signin", "ap/signin", "/ap/", "login"]):
            print()
            print("=" * 60)
            print("【Amazonへのログインが必要です】")
            print("開いたブラウザでAmazonにログインしてください。")
            print("本が開いた状態になったら、ここでEnterを押してください。")
            print("=" * 60)
            input("Enterキーを押す >>> ")
            await asyncio.sleep(3)

        # リーダー読み込み待ち
        print("リーダーの読み込みを待っています...")
        try:
            await page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            pass
        await asyncio.sleep(2)

        print(f"\nテキスト抽出開始 (最大 {max_pages} ページ, キー: {navigate_key})")
        print("-" * 50)

        collected: list[str] = []
        seen_hashes: set[str] = set()
        consecutive_dupes = 0

        for page_num in range(1, max_pages + 1):
            await asyncio.sleep(1.5)

            raw = await _extract_page_text(page)
            raw = raw.strip()

            if not raw or len(raw) < 20:
                print(f"  ページ {page_num:3d}: テキスト取得不可（スキップ）")
                await page.keyboard.press(navigate_key)
                continue

            h = _text_hash(raw)
            if h in seen_hashes:
                consecutive_dupes += 1
                print(f"  ページ {page_num:3d}: 重複 ({consecutive_dupes}/3)")
                if consecutive_dupes >= 3:
                    print("  → 末尾に到達（または進行不可）— 終了します")
                    break
            else:
                consecutive_dupes = 0
                seen_hashes.add(h)
                collected.append(raw)
                print(f"  ページ {page_num:3d}: {len(raw):5d} 文字 ✓")

            await page.keyboard.press(navigate_key)

        await ctx.close()

    combined = "\n\n---PAGE---\n\n".join(collected)
    print(f"\n抽出完了: {len(collected)} ページ / {len(combined)} 文字")
    return combined


def scrape_kindle_book(
    url: str,
    max_pages: int = 100,
    navigate_key: str = "ArrowLeft",
) -> str:
    """
    Kindle Cloud Reader からテキストを抽出する（同期ラッパー）。

    Args:
        url: Kindle Cloud Reader の URL (https://read.amazon.co.jp/...)
        max_pages: 最大取得ページ数
        navigate_key: ページ送りキー
                      日本語書籍（縦書き）→ "ArrowLeft"
                      英語書籍（横書き）  → "ArrowRight"

    Returns:
        ページ区切り (---PAGE---) 付きの抽出テキスト
    """
    return asyncio.run(_scrape_async(url, max_pages, navigate_key))
