import re

from bs4 import BeautifulSoup

_NOISE_PATTERNS = [
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
]
_NOISE_RE = re.compile("|".join(_NOISE_PATTERNS), re.IGNORECASE | re.MULTILINE)


def extract_text(html: str, plain: str) -> str:
    if html:
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "head", "meta", "link", "img", "button", "nav", "footer"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
    else:
        text = plain

    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if len(line) > 2]
    text = "\n".join(lines)

    text = _NOISE_RE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
