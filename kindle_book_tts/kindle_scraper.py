"""
Kindle Cloud Reader (read.amazon.co.jp) からテキストを抽出する。

- Playwright の persistent context を使い、既存のサインイン状態を引き継ぐ
- ページ送りは ArrowRight キー（Kindle Cloud Reader の標準）
- テキストレイヤーは複数のセレクタを試してフォールバック
- デバッグ用スクリーンショットを screenshots/ に保存
"""

import asyncio
import time
from pathlib import Path
from playwright.async_api import async_playwright, Page, BrowserContext

import config

# ── Kindle テキストレイヤーのセレクタ候補（DOM変更に備えて複数用意） ──
_TEXT_SELECTORS = [
    "div.textLayer span",          # 現在の主セレクタ
    "div.KindleReaderPage span",   # 旧形式
    "span.a-text",                 # 別バリアント
    "div[class*='text'] span",     # クラス名が変わった場合の grep
    "div[id*='page'] span",        # page ID ベース
]

_SCREENSHOT_DIR = Path(__file__).parent / "screenshots"
_SCREENSHOT_DIR.mkdir(exist_ok=True)


async def _wait_for_page_load(page: Page, timeout: float = 5.0):
    """ページ遷移後のテキスト描画を待つ。"""
    await asyncio.sleep(timeout)


async def _extract_text_from_page(page: Page) -> str:
    """現在表示中のページからテキストを取得する。複数セレクタを試す。"""
    for selector in _TEXT_SELECTORS:
        try:
            elements = await page.query_selector_all(selector)
            if elements:
                texts = [await el.inner_text() for el in elements]
                combined = " ".join(t.strip() for t in texts if t.strip())
                if combined:
                    return combined
        except Exception:
            continue
    return ""


async def _turn_page(page: Page) -> None:
    """次のページへ進む。ArrowRight が標準。"""
    await page.keyboard.press("ArrowRight")


async def scrape_kindle_book(
    url: str,
    max_pages: int = 50,
    debug: bool = True,
) -> str:
    """
    Kindle Cloud Reader のURLからテキストを抽出して返す。

    Parameters
    ----------
    url : str
        read.amazon.co.jp の本のURL
    max_pages : int
        最大取得ページ数
    debug : bool
        True にすると各ページのスクリーンショットを screenshots/ に保存

    Returns
    -------
    str
        全ページを結合したテキスト
    """
    all_texts: list[str] = []
    prev_text = ""
    consecutive_empty = 0
    consecutive_same = 0

    async with async_playwright() as pw:
        # persistent context でサインイン状態を維持
        ctx: BrowserContext = await pw.chromium.launch_persistent_context(
            user_data_dir=config.KINDLE_PROFILE_DIR,
            headless=False,  # Kindle は headless だとブロックされることがある
            args=[
                "--window-position=-32000,-32000",  # 画面外に配置
                "--disable-blink-features=AutomationControlled",
            ],
            viewport={"width": 1280, "height": 800},
        )

        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        print(f"[scraper] Opening: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)

        # ページが完全に読み込まれるまで待機（Kindle は JS 依存）
        await _wait_for_page_load(page, timeout=8.0)

        if debug:
            await page.screenshot(path=str(_SCREENSHOT_DIR / "page_000.png"))
            print(f"[scraper] Screenshot saved: page_000.png")

        for i in range(1, max_pages + 1):
            text = await _extract_text_from_page(page)

            if debug and i % 10 == 0:
                await page.screenshot(path=str(_SCREENSHOT_DIR / f"page_{i:03d}.png"))
                print(f"[scraper] Screenshot saved: page_{i:03d}.png")

            if not text:
                consecutive_empty += 1
                print(f"[scraper] Page {i}: empty (consecutive: {consecutive_empty})")
                if consecutive_empty >= 3:
                    print("[scraper] 3連続空ページ → 終端と判断して終了")
                    break
            else:
                consecutive_empty = 0
                if text == prev_text:
                    consecutive_same += 1
                    print(f"[scraper] Page {i}: same as previous (consecutive: {consecutive_same})")
                    if consecutive_same >= 2:
                        print("[scraper] 同一テキスト連続 → ページ送りできていないと判断して終了")
                        break
                else:
                    consecutive_same = 0
                    all_texts.append(text)
                    print(f"[scraper] Page {i}: {len(text)} chars")
                    prev_text = text

            await _turn_page(page)
            await _wait_for_page_load(page, timeout=2.0)

        if debug:
            await page.screenshot(path=str(_SCREENSHOT_DIR / "page_final.png"))

        await ctx.close()

    result = "\n\n".join(all_texts)
    print(f"[scraper] Done. Total: {len(all_texts)} pages, {len(result)} chars")
    return result


def scrape(url: str, max_pages: int = 50, debug: bool = True) -> str:
    """同期ラッパー。"""
    return asyncio.run(scrape_kindle_book(url, max_pages=max_pages, debug=debug))


# ── 単体テスト用 ──────────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python kindle_scraper.py <kindle_url> [max_pages]")
        sys.exit(1)
    _url = sys.argv[1]
    _max = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    text = scrape(_url, max_pages=_max)
    print("\n─── 抽出テキスト（先頭500文字）───")
    print(text[:500])
