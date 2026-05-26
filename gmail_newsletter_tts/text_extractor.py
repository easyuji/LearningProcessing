import re

from bs4 import BeautifulSoup

# 読み上げ不要なノイズパターン
_NOISE_PATTERNS = [
    # フッター系
    r"配信停止.*",
    r"登録解除.*",
    r"メールの配信を停止.*",
    r"このメールは.*送信されています.*",
    r"unsubscribe.*",
    r"©\s*.{0,120}",
    r"Copyright\s*.{0,120}",
    r"All rights reserved.*",
    r"プライバシーポリシー.*",
    r"特定商取引法.*",
    r"発行者.*",
    r"発行元.*",
    r"お問い合わせ.*",
    # URLを含む行（URLだけの行 or 矢印+URLの行）
    r"[→▶►]\s*https?://\S+",
    r"■\S+→https?://\S+",
    # SNS・ボタン系テキスト
    r"(詳しくはこちら|続きはこちら|こちらをクリック|クリックしてください).*",
    r"(view in browser|view this email|read online).*",
    r"(forward|フォワード|転送).*このメール.*",
]
_NOISE_RE = re.compile("|".join(_NOISE_PATTERNS), re.IGNORECASE | re.MULTILINE)

# URLパターン（残ったURLを全除去）
_URL_RE = re.compile(r"https?://[^\s　「」【】。、！？\)\]）\]]*", re.IGNORECASE)

# メールアドレス除去
_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

# 記号だけの行を除去（→、■、◆、・のみの行）
_SYMBOL_ONLY_RE = re.compile(r"^[\s→▶►■◆●◎▼△○×※＊\*\-=_/|\\]+$")


def extract_text(html: str, plain: str) -> str:
    if html:
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "head", "meta", "link", "img",
                         "button", "nav", "footer", "a"]):
            # <a>タグはテキストだけ残してhrefを消す
            if tag.name == "a":
                tag.unwrap()
            else:
                tag.decompose()
        text = soup.get_text(separator="\n")
    else:
        text = plain

    # ノイズ行・フッター除去
    text = _NOISE_RE.sub("", text)
    # URL除去
    text = _URL_RE.sub("", text)
    # メールアドレス除去
    text = _EMAIL_RE.sub("", text)

    # 行ごとにクリーニング
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if len(line) <= 2:
            continue
        if _SYMBOL_ONLY_RE.match(line):
            continue
        lines.append(line)

    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
