"""
text_normalizer.py — APIキー不要のルールベース TTS テキスト正規化

メルマガ全文分析から抽出した誤読パターンを網羅的に処理する。
script_converter.py の Claude 変換の前処理として常時実行する。

処理順序:
  1. 英語文章の [EN][/EN] マーキング
  2. 数字・金額・単位の正規化
  3. アルファベット略語 → カタカナ
  4. 漢字誤読防止
  5. 読み上げ不要記号の除去
"""

import re


# ══════════════════════════════════════════════════════════════════
# 1. 英語文章の検出と [EN][/EN] マーキング
# ══════════════════════════════════════════════════════════════════

# 英語の文とみなす最小条件: ASCII英字が70%以上で10文字以上の「行または段落」
_EN_LINE_RE = re.compile(
    r"^(?:[A-Za-z0-9 ,.'\"()\-:;!?@#&*/+=<>_\[\]{}|~`%^\\]+\s*){3,}$",
    re.MULTILINE
)

def _mark_english_lines(text: str) -> str:
    """英語主体の行を [EN]...[/EN] で囲む。"""
    lines = text.split("\n")
    result = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            result.append(line)
            continue
        ascii_alpha = sum(1 for c in stripped if c.isascii() and c.isalpha())
        total_alpha = sum(1 for c in stripped if c.isalpha())
        if (
            total_alpha > 0
            and ascii_alpha / total_alpha > 0.70
            and len(stripped) > 15
            and not stripped.startswith("[EN]")
        ):
            result.append(f"[EN]{stripped}[/EN]")
        else:
            result.append(line)
    return "\n".join(result)


# ══════════════════════════════════════════════════════════════════
# 2. 数字・金額・単位の正規化
# ══════════════════════════════════════════════════════════════════

def _num_to_jp(n: int) -> str:
    """整数を日本語読みに変換（最大9999兆）。"""
    if n == 0:
        return "ゼロ"
    units = ["", "万", "億", "兆"]
    parts = []
    i = 0
    while n > 0:
        parts.append((n % 10000, units[i]))
        n //= 10000
        i += 1
    parts.reverse()

    kanji = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九"]
    pos = ["", "十", "百", "千"]

    result = ""
    for val, unit in parts:
        if val == 0:
            continue
        s = ""
        for j, d in enumerate(reversed(str(val))):
            d = int(d)
            if d == 0:
                continue
            k = kanji[d] if not (d == 1 and j > 0) else ""
            s = k + pos[j] + s
        result += s + unit
    return result


# $XXX billion/trillion/million パターン
def _replace_dollar_amount(m: re.Match) -> str:
    num_str = m.group(1).replace(",", "")
    unit = m.group(2).lower()
    try:
        num = float(num_str)
    except ValueError:
        return m.group(0)
    # billion=10億、trillion=1兆、million=100万 換算して日本語読みに
    multiplier = {"billion": 10**9, "trillion": 10**12, "million": 10**6}
    total = int(num * multiplier.get(unit, 1))
    return f"{_num_to_jp(total)}ドル"


_DOLLAR_RE = re.compile(r"\$([0-9,]+(?:\.[0-9]+)?)\s*(billion|trillion|million)(?![A-Za-z])", re.IGNORECASE)

# 第NNN号
def _replace_issue_num(m: re.Match) -> str:
    n = int(m.group(1))
    return f"第{_num_to_jp(n)}号"

_ISSUE_RE = re.compile(r"第(\d{2,4})号")

# XX%
_PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")

# XX倍 / XX兆 / XX億 / XX万
_LARGE_NUM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(兆|億|万|倍|基|台|人)")

# kWh / Wh / GW / MW / kW / W + 数字
_POWER_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(kWh|Wh|GWh|MWh|GW|MW|kW|W)\b")

# P/E 倍率
_PE_RE = re.compile(r"P/E(?:は|が|の)?\s*(\d+)\s*倍")


def _normalize_numbers(text: str) -> str:
    text = _DOLLAR_RE.sub(_replace_dollar_amount, text)
    text = _ISSUE_RE.sub(_replace_issue_num, text)
    text = _PCT_RE.sub(lambda m: f"{m.group(1)}パーセント", text)
    text = _POWER_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}", text)  # 単位はそのまま読ませる
    text = _PE_RE.sub(lambda m: f"株価収益率は{m.group(1)}倍", text)
    return text


# ══════════════════════════════════════════════════════════════════
# 3. アルファベット略語 → カタカナ / 日本語読み
#    ※メルマガ全文から実際に出現したものを優先収録
# ══════════════════════════════════════════════════════════════════

# Python 3 では \b が Unicode 文字（日本語・カタカナ等）も \w 扱いするため
# (?<![A-Za-z])...(?![A-Za-z]) を使う
def _ab(pattern: str, flags: int = 0) -> re.Pattern:
    """英字境界を考慮した略語マッチパターンを生成。"""
    return re.compile(r"(?<![A-Za-z])" + pattern + r"(?![A-Za-z])", flags)


_ABBREV_MAP: list[tuple[re.Pattern, str]] = [
    # AI / ML（長い順に並べて部分マッチを防ぐ）
    (_ab(r"LLM"), "エルエルエム"),
    (_ab(r"GPT-?4o?"), "ジーピーティー"),
    (_ab(r"GPT"), "ジーピーティー"),
    (_ab(r"GPU"), "ジーピーユー"),
    (_ab(r"CPU"), "シーピーユー"),
    (_ab(r"API"), "エーピーアイ"),
    (_ab(r"UX"), "ユーエックス"),
    (_ab(r"UI"), "ユーアイ"),
    (_ab(r"OS"), "オーエス"),
    (_ab(r"SaaS", re.IGNORECASE), "サース"),
    (_ab(r"PaaS", re.IGNORECASE), "パース"),
    (_ab(r"IaaS", re.IGNORECASE), "イアース"),
    (_ab(r"AI"), "エーアイ"),

    # クラウド・IT
    (_ab(r"AWS"), "エーダブリューエス"),
    (_ab(r"GCP"), "ジーシーピー"),
    (_ab(r"CDN"), "シーディーエヌ"),
    (_ab(r"VAT"), "ブイエーティー"),
    (_ab(r"PUE"), "ピーユーイー"),
    (_ab(r"ARR"), "エーアールアール"),
    (_ab(r"SDK"), "エスディーケー"),

    # 金融
    (_ab(r"IPO"), "アイピーオー"),
    (_ab(r"NISA"), "ニーサ"),
    (_ab(r"ETF"), "イーティーエフ"),
    (_ab(r"ESG"), "イーエスジー"),
    (_ab(r"P/E"), "ピーイー比"),
    (_ab(r"ROE"), "アールオーイー"),
    (_ab(r"GDP"), "ジーディーピー"),
    (_ab(r"IMF"), "アイエムエフ"),
    (_ab(r"FRB"), "エフアールビー"),
    (_ab(r"CEO"), "シーイーオー"),
    (_ab(r"CTO"), "シーティーオー"),
    (_ab(r"CFO"), "シーエフオー"),
    (_ab(r"COO"), "シーオーオー"),
    (_ab(r"MBA"), "エムビーエー"),

    # エネルギー・単位（長い順）
    (_ab(r"GWh"), "ギガワットアワー"),
    (_ab(r"MWh"), "メガワットアワー"),
    (_ab(r"kWh"), "キロワットアワー"),
    (_ab(r"GW"), "ギガワット"),
    (_ab(r"MW"), "メガワット"),
    (_ab(r"kW"), "キロワット"),
    (_ab(r"Wh"), "ワットアワー"),

    # 企業・サービス（固有名詞）
    (_ab(r"LVMH"), "エルブイエムエイチ"),
    (_ab(r"MAGA"), "マガ"),
    (_ab(r"NVIDIA"), "エヌビディア"),
    (_ab(r"OpenAI"), "オープンエーアイ"),
    (_ab(r"Anthropic"), "アンソロピック"),
    (_ab(r"Microsoft"), "マイクロソフト"),
    (_ab(r"Amazon"), "アマゾン"),
    (_ab(r"Google"), "グーグル"),
    (_ab(r"Apple"), "アップル"),
    (_ab(r"Oracle"), "オラクル"),
    (_ab(r"Meta"), "メタ"),
    (_ab(r"Xiaomi"), "シャオミ"),
    (_ab(r"Prada"), "プラダ"),
    (_ab(r"Hermes"), "エルメス"),
    (_ab(r"Burberry"), "バーバリー"),
    (_ab(r"Chandon"), "シャンドン"),

    # その他
    (_ab(r"JTC"), "ジェーティーシー"),
    (_ab(r"DVD"), "ディーブイディー"),
    (re.compile(r"Blu-ray", re.IGNORECASE), "ブルーレイ"),
]


def _normalize_abbrev(text: str) -> str:
    for pattern, replacement in _ABBREV_MAP:
        text = pattern.sub(replacement, text)
    return text


# ══════════════════════════════════════════════════════════════════
# 4. 漢字誤読防止（文脈ベース）
#    ※メルマガ実文から抽出した誤読リスト
# ══════════════════════════════════════════════════════════════════

# (検索パターン, 置換文字列) のリスト
# 文脈を考慮するため前後の文字も含めたパターンを優先する
_KANJI_FIXES: list[tuple[re.Pattern, str]] = [

    # ── 時間・日付 ───────────────────────────────────────────────
    (re.compile(r"今日は"), "きょうは"),           # 挨拶「こんにちは」誤読を防ぐ
    (re.compile(r"今日の"), "きょうの"),
    (re.compile(r"今日も"), "きょうも"),
    (re.compile(r"今日から"), "きょうから"),
    (re.compile(r"今日まで"), "きょうまで"),
    (re.compile(r"今朝"), "けさ"),
    (re.compile(r"今夜"), "こんや"),
    (re.compile(r"今週"), "こんしゅう"),
    (re.compile(r"先週"), "せんしゅう"),
    (re.compile(r"来週"), "らいしゅう"),
    (re.compile(r"今月"), "こんげつ"),
    (re.compile(r"先月"), "せんげつ"),
    (re.compile(r"来月"), "らいげつ"),
    (re.compile(r"今年"), "ことし"),
    (re.compile(r"来年"), "らいねん"),
    (re.compile(r"昨年"), "さくねん"),
    (re.compile(r"明日"), "あした"),
    (re.compile(r"昨日"), "きのう"),
    (re.compile(r"今後"), "こんご"),
    (re.compile(r"以後"), "いご"),
    (re.compile(r"以前"), "いぜん"),
    (re.compile(r"以来"), "いらい"),

    # ── 金融・投資用語 ───────────────────────────────────────────
    (re.compile(r"株式市場"), "かぶしきしじょう"),
    (re.compile(r"市場(?=は|が|の|で|に|を)"), "しじょう"),
    (re.compile(r"上場(?=し|する|して|した|企業|廃止)"), "じょうじょう"),
    (re.compile(r"上場(?=して|したら|すれば)"), "じょうじょうして"),
    (re.compile(r"配当利回り"), "はいとうりまわり"),
    (re.compile(r"株価収益率"), "かぶかしゅうえきりつ"),
    (re.compile(r"長期ビュー"), "ちょうきびゅー"),
    (re.compile(r"ビュー(?=を|の|が|は)"), "ビュー"),  # そのまま
    (re.compile(r"設備投資"), "せつびとうし"),
    (re.compile(r"資本コスト"), "しほんコスト"),
    (re.compile(r"資本効率"), "しほんこうりつ"),
    (re.compile(r"不良債権"), "ふりょうさいけん"),
    (re.compile(r"利確"), "りかく"),
    (re.compile(r"含み損"), "ふくみそん"),
    (re.compile(r"含み益"), "ふくみえき"),
    (re.compile(r"増刷"), "ぞうさつ"),

    # ── テクノロジー用語 ────────────────────────────────────────
    (re.compile(r"推論(?=を|の|が|は|モード|する)"), "すいろん"),
    (re.compile(r"実装(?=を|の|が|は|する|した|して)"), "じっそう"),
    (re.compile(r"設計(?=を|の|が|は|する)"), "せっけい"),
    (re.compile(r"開発(?=を|の|が|は|する|した)"), "かいはつ"),
    (re.compile(r"処理(?=を|の|が|は|する)"), "しょり"),
    (re.compile(r"規模(?=を|の|が|は|で)"), "きぼ"),
    (re.compile(r"需要(?=を|の|が|は|で)"), "じゅよう"),
    (re.compile(r"供給(?=を|の|が|は|で)"), "きょうきゅう"),
    (re.compile(r"演算(?=を|の|が|は)"), "えんざん"),
    (re.compile(r"消費(?=電力|税|者|する)"), "しょうひ"),
    (re.compile(r"消費電力"), "しょうひでんりょく"),
    (re.compile(r"発電容量"), "はつでんようりょう"),

    # ── 人名・固有名詞の読み ───────────────────────────────────
    (re.compile(r"藤沢数希"), "ふじさわかずき"),
    (re.compile(r"習近平"), "しゅうきんぺい"),
    (re.compile(r"習主席"), "しゅうしゅせき"),
    (re.compile(r"雷軍"), "らいじゅん"),
    (re.compile(r"中山泰秀"), "なかやまやすひで"),

    # ── 地名 ────────────────────────────────────────────────────
    (re.compile(r"深セン湾"), "しんせんわん"),
    (re.compile(r"深セン"), "しんせん"),
    (re.compile(r"上環"), "しゃんわん"),
    (re.compile(r"人民元"), "じんみんげん"),
    (re.compile(r"関税(?=を|の|が|は|で)"), "かんぜい"),

    # ── 読み間違いやすい一般語 ──────────────────────────────────
    (re.compile(r"大人(?=[にのはがをもで]|たち|向け)"), "おとな"),
    (re.compile(r"一方(?=[でにのはが、。])"), "いっぽう"),
    (re.compile(r"一部(?=[のはがをにで]|の人)"), "いちぶ"),
    (re.compile(r"一定(?=[のはがをにで])"), "いってい"),
    (re.compile(r"一致(?=[してしたしなしの])"), "いっち"),
    (re.compile(r"一般(?=[のにはがで的])"), "いっぱん"),
    (re.compile(r"上手(?=[くにい]|な|です)"), "じょうず"),
    (re.compile(r"下手(?=[くにい]|な|です)"), "へた"),
    (re.compile(r"苦手(?=[なにで]|です)"), "にがて"),
    (re.compile(r"得意(?=[なにで]|です)"), "とくい"),
    (re.compile(r"大事(?=[なにで]|です)"), "だいじ"),
    (re.compile(r"大切(?=[なにで]|です)"), "たいせつ"),
    (re.compile(r"最近(?=[はのがでも])"), "さいきん"),
    (re.compile(r"最後(?=[にのはがで])"), "さいご"),
    (re.compile(r"最初(?=[にのはがで])"), "さいしょ"),
    (re.compile(r"何度(?=[もかな])"), "なんど"),
    (re.compile(r"何人(?=[もかな]|で)"), "なんにん"),
    (re.compile(r"何倍(?=[もかな])"), "なんばい"),
    (re.compile(r"何年(?=[もかな]|も前)"), "なんねん"),

    # ── 略語・業界語 ─────────────────────────────────────────────
    (re.compile(r"バリキャリ"), "ばりきゃり"),
    (re.compile(r"タワマン"), "たわまん"),
    (re.compile(r"バイブ(?=・コーディング|コーディング)"), "ばいぶ"),
    (re.compile(r"ハイブランド"), "はいぶらんど"),
    (re.compile(r"ハイパースケーラー"), "はいぱーすけーらー"),
    (re.compile(r"チョークポイント"), "ちょーくぽいんと"),
    (re.compile(r"モンロー主義"), "もんろーしゅぎ"),
    (re.compile(r"封じ込め"), "ふうじこめ"),
    (re.compile(r"しがない"), "しがない"),  # そのまま（念のため）

    # ── 記号・特殊文字 ──────────────────────────────────────────
    # 読み上げ不要な記号行頭の処理は remove_noise で対応
]


def _normalize_kanji(text: str) -> str:
    for pattern, replacement in _KANJI_FIXES:
        text = pattern.sub(replacement, text)
    return text


# ══════════════════════════════════════════════════════════════════
# 5. 読み上げ不要なノイズ記号の除去
# ══════════════════════════════════════════════════════════════════

_NOISE_SYMBOLS = re.compile(
    r"^[★●■◆◎▼△○×※＊\*//→▶►◇□▪︎]+\s*",  # 行頭記号
    re.MULTILINE
)
_SECTION_MARK = re.compile(r"^[１２３４５６７８９０\d]+\．\s*", re.MULTILINE)  # 「１．」など


def _remove_noise_symbols(text: str) -> str:
    text = _NOISE_SYMBOLS.sub("", text)
    return text


# ══════════════════════════════════════════════════════════════════
# 公開インターフェース
# ══════════════════════════════════════════════════════════════════

_EN_BLOCK_RE = re.compile(r"(\[EN\].*?\[/EN\])", re.DOTALL)


def normalize(text: str) -> str:
    """
    メルマガテキストを TTS 向けに正規化して返す。

    処理順序:
      1. 英語行を [EN][/EN] でマーキング
      2. [EN]ブロック以外に対してのみ変換を適用
         a. 数字・金額の正規化
         b. 略語のカタカナ変換
         c. 漢字誤読防止置換
         d. ノイズ記号除去
    """
    # Step1: EN マーキング（まず英語行を検出）
    text = _mark_english_lines(text)

    # Step2: EN ブロックを保護しながら日本語部分だけ変換
    parts = _EN_BLOCK_RE.split(text)
    result = []
    for part in parts:
        if part.startswith("[EN]") and part.endswith("[/EN]"):
            result.append(part)   # 英語ブロックはそのまま
        else:
            part = _normalize_numbers(part)
            part = _normalize_abbrev(part)
            part = _normalize_kanji(part)
            part = _remove_noise_symbols(part)
            result.append(part)
    return "".join(result)


# ── 単体テスト ─────────────────────────────────────────────────
if __name__ == "__main__":
    sample = """
★今週のざっくばらん

今日の株式市場はAI需要の影響で大きく動きました。
AWS、GPU、LLMなどの関連銘柄が上場しており、P/Eは15倍程度。
$30billionの設備投資が発表され、配当利回りは4%に達しました。

This is an English paragraph about AI trends and market dynamics.

第731号では藤沢数希さんが習近平との米中首脳会談を分析。
来年は更なる成長が見込まれ、今月の数字は期待通りです。
上手に封じ込めることが大事です。一方で深セン市場も好調。
""".strip()

    result = normalize(sample)
    print("=== 正規化結果 ===")
    print(result)
