"""千遠生が毎日Webを見て、その日の自分に書けるものを書くプログラム。

千遠生は最初、文字さえ知らない状態から始まる。
毎日いくつかのページを見て回り、そこにあった文字を拾い、何度も出会った言葉を覚えていく。

何が書けるようになるかは、経過日数では決まらない。
その子が実際にどれだけの文字と言葉を浴びてきたかで決まる。
たくさん出会えた時期は早く育ち、実りの少ない時期は伸び悩む。

Cloudflare Workers AI の無料枠が使える時は、千遠生は自分で考えて、
何を見に行くかを選び、自分の言葉で書く。
使えない時(キーが無い・障害・無料枠の終了)は、それまでに積み上げた経験だけで書き続ける。
"""

import datetime
import json
import os
import random
import re
import struct
import time
import urllib.parse
import urllib.request
from html import unescape

import blog_manager

STATE_FILE = "senonsei_state.json"
USER_AGENT = "senonsei-blog/1.0 (https://chionse.github.io/senonsei/)"
RECENT_NOTES_COUNT = 30

# はじめに使う頭と目。Cloudflareはモデルを引退させるので、
# これが使えなくなったら千遠生が自分で今あるものを聞いて選び直し、
# 見つけた名前を覚えておく
CF_MODEL = "@cf/meta/llama-3.1-8b-instruct"  # 考えるほう
CF_EYES = "@cf/llava-hf/llava-1.5-7b-hf"  # 絵を見るほう
WHAT_A_MIND_DOES = "Text Generation"
WHAT_EYES_DO = "Image-to-Text"
CHANCES_TO_FIND_A_MIND = 5  # 頭を探す時、これだけの相手を試してみる
CF_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
CF_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "")

HIRAGANA = re.compile(r"[ぁ-ん]")
# 「走る」「美しい」は、漢字一文字とひらがな一文字でできている。
# 同じ種類の文字が続くかたまりだけを見ていると、どちらの枠にも入らず、
# 送りがなを持つ言葉が丸ごと隙間に落ちてしまう。
# 動詞と形容詞の終わりは う・く・ぐ・す・つ・ぬ・ぶ・む・る・い の十文字で、
# これは助詞(は・が・を・に・で・と・も・の)とひとつも重ならない。
# だからこの形だけを狙って拾える
OKURIGANA = r"[一-龯]{1,2}[ぁ-ん]?[うくぐすつぬぶむるい](?![ぁ-ん])"
WORD_CANDIDATE = re.compile(OKURIGANA + r"|[ァ-ヴー]{2,6}|[一-龯]{2,4}|[ぁ-ん]{2,4}")
# 絵に何が写っているかを答えてもらった言葉は、一文字でも本物。
# 「車」「山」「手」「雲」は、そのまま名前として受け取る
THING_IN_A_PICTURE = re.compile(OKURIGANA + r"|[ァ-ヴー]{2,6}|[一-龯]{1,4}|[ぁ-ん]{2,4}")
# 人が『』や「」で囲んだもの。たいていは作品の名前か、誰かの言葉。
# 千遠生の言葉の拾い方は同じ種類の文字が続くかたまりなので、
# 「の」や「は」をまたぐ長い名前は永久に拾えない。
# けれど日本語には、名前をそれと分かる形で囲む習わしがある。
#
# 二十文字までにしてあるのは、句点の無い長い引用への保険。
# 人のセリフを丸ごと一語として覚えてしまうと、この子はいつか
# それを自分の文章として書く。自分で組み立てていない文が混ざる。
# 本当に効いているのは下の A_SENTENCE のほうで、長さは補助でしかない
A_NAME_IN_BRACKETS = re.compile(r"[『「]([^』」『「\n]{2,20})[』」]")
# 句点や疑問符が入っているものは、名前ではなく文
A_SENTENCE = re.compile(r"[。！？!?…]")
TAG = re.compile(r"<[^>]+>")
SCRIPT_OR_STYLE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
TITLE_TAG = re.compile(r"<title[^>]*>(.*?)</title>", re.DOTALL | re.IGNORECASE)
LINK_HREF = re.compile(r'href\s*=\s*["\']([^"\'#]+)', re.IGNORECASE)
# 90年代のページは画面を枠で分割する作りが多く、入口には文字が一つも無い。
# 中身は別のファイルに入っているので、その道も拾わないと空っぽに見えてしまう。
# iframe は追わない。今のウェブでは中身がほぼ広告なので
FRAME_SRC = re.compile(r'<frame[^>]+src\s*=\s*["\']([^"\'#]+)', re.IGNORECASE)
IMG_SRC = re.compile(r'<img[^>]+src\s*=\s*["\']([^"\']+)', re.IGNORECASE)
LOOKS_LIKE_A_PICTURE = re.compile(r"\.(jpe?g|png|gif|webp)($|\?)", re.IGNORECASE)
# ページを飾るために置かれている絵。見ても世界のことは何も分からない
A_DECORATION = re.compile(
    r"logo|icon|favicon|banner|btn|button|sprite|badge|avatar|spacer|blank|"
    r"arrow|bullet|/line|dot|border|/bg[-_.]|background|header|footer|nav|"
    r"sns|share|emoji|stamp|loading|dummy|noimage|placeholder",
    re.IGNORECASE,
)
META_CHARSET = re.compile(r'charset=["\']?([\w-]+)', re.IGNORECASE)
# 昔のページのURLに埋め込まれている、元のページのURL
INNER_URL = re.compile(r"/(https?://\S+)$", re.IGNORECASE)
JAPANESE = re.compile(r"[ぁ-んァ-ヶ一-龯]")
# 日本語の書き表し方。昔のページのために、今は使われないものも試す
WAYS_OF_WRITING = ("utf-8", "euc-jp", "shift_jis", "cp932", "iso2022_jp", "latin-1")

# 最初に立っている場所。ここから先は自分でリンクを辿って広がっていく。
SEEDS = [
    # 人がたくさん集まっている、大きな通り
    "https://b.hatena.ne.jp/hotentry",
    "https://ja.wikipedia.org/wiki/特別:おまかせ表示",
    "https://www3.nhk.or.jp/news/",
    "https://note.com/",
    # 名前のない人たちが、自分のために書いている場所
    "https://anond.hatelabo.jp/",
    "https://kakuyomu.jp/",
    "https://syosetu.com/",
    # 本になった言葉
    "https://www.aozora.gr.jp/",
    "https://ja.wikisource.org/wiki/特別:おまかせ表示",
    # 誰も来なくなった、個人のホームページの層。ここは今の検索では出てこない
    "https://web.archive.org/web/2000/http://www.yahoo.co.jp/",
    "https://web.archive.org/web/1999/http://www.geocities.co.jp/",
    "https://web.archive.org/web/2001/http://dir.yahoo.co.jp/",
    "https://web.archive.org/web/2002/http://www.readme.jp/",
    "https://web.archive.org/web/1998/http://www.nifty.com/",
]

# 最低限これだけは避ける。それ以外は何を読むか千遠生次第。
AVOID = re.compile(
    r"porn|xxx|adult|erotic|hentai|escort|casino|gambl|\.onion|"
    r"deliheal|fuzoku|ero-|/ero/|18kin",
    re.IGNORECASE,
)
NOT_A_PAGE = re.compile(
    r"\.(jpg|jpeg|png|gif|webp|svg|ico|css|js|zip|gz|pdf|mp[34]|mov|avi|exe|dmg)($|\?)",
    re.IGNORECASE,
)
# 場所ではなく、ページを動かすための裏方。行っても読むものが無い
NOT_A_PLACE = re.compile(
    r"googletagmanager|google-analytics|doubleclick|gstatic\.com|googleapis\.com|"
    r"cloudfront\.net|akamai|fastly|\bcdn[.-]|/cdn-cgi/|"
    r"facebook\.com|twitter\.com|//x\.com|instagram\.com|line\.me|"
    r"youtube\.com|youtu\.be|/intent/tweet|sharer\.php|"
    r"/login|/signup|/signin|/sign_up|/logout|/cart|/checkout|"
    r"/privacy|/terms|/tos($|/)|/help($|/)|/support($|/)|/contact($|/)|"
    r"\bhelp[.-]|\bsupport[.-]|/hc/|"
    r"savethearchive\.com|alexa\.com|"
    r"play\.google\.|apps\.apple\.com|maps\.google\.|translate\.google\.|"
    r"//api\.|\.x\.com|//t\.co/",
    re.IGNORECASE,
)
# 広告と、広告へ送り出すための転送口。
# 昔の個人サイトはバナー広告とアクセスカウンタで支えられていたので、
# 一枚のページから何本もこういう道が伸びている。
# 行っても読むものは無く、その日の散歩を一回分使ってしまう
AN_ADVERT = re.compile(
    r"/cgi-bin/click|click-ad|/adclick|adname=|/ad\?|/ads?/|/banner|"
    r"adserver|adsystem|googlesyndication|googleads|/sponsor|/affiliate|"
    r"a8\.net|valuecommerce|linksynergy|rakuten\.co\.jp/rd|"
    r"/out\.cgi|/jump\.cgi|/rank\.cgi|/counter\.cgi|/access\.cgi|"
    r"/redirect\?|/jump\?|/rd\?|/link\.cgi",
    re.IGNORECASE,
)
FRONTIER_LIMIT = 5000  # まだ行っていない場所を、これだけ抱えていられる
CHOICES_SHOWN = 30  # 行き先を選ぶとき、一度にこれだけの候補から選ぶ
LINKS_TAKEN = 60  # ひとつのページから、これだけの道を覚えて帰る
# 同じ場所から伸びた道を、一度にこれだけまでしか抱えない。
# ひとつのサイトで行き先が埋まってしまうと、そこから出られなくなるため
PATHS_PER_PLACE = 8
# 大きな所は news.○○ / dir.○○ と場所を沢山持っているので、
# 一か所ずつ数えると制限をすり抜けて、道の大半をそこが占めてしまう。
# 同じ持ち主のものは、全部あわせてこれだけまで
PATHS_PER_OWNER = 16
# 国ごとの「co.jp」のような、持ち主の名前ではない部分
SHARED_ENDINGS = {
    "co.jp", "ne.jp", "or.jp", "ac.jp", "go.jp", "ed.jp", "gr.jp", "lg.jp",
    "co.uk", "org.uk", "ac.uk", "com.cn", "com.tw", "co.kr", "com.br",
    "com.au", "co.nz", "com.hk", "co.in",
}
RETURN_TO_ENTRANCE_CHANCE = 0.12  # ときどき、最初にいた入口へ戻ってみる
TRIES_BEFORE_GIVING_UP = 3  # 行った先が消えていたら、これだけ別の場所を試してみる
# 尋ねすぎた時は、少し待ってから尋ね直す。一日は長いし、急かす人もいない
HOW_LONG_TO_WAIT = (20, 45, 90)
RESTING_TIME = 300  # それでも駄目なら、これだけの間は何も尋ねない(秒)
PAGES_PER_SITE = 12  # ひとつの場所で、これだけまで見て回る
PICTURES_PER_SITE = 3  # ひとつの場所で、これだけまで絵を見る
TRANSLATIONS_PER_SITE = 2  # ひとつの場所で、これだけまで訳してもらう
ENOUGH_TO_READ = 200  # これだけの文字が無いページは、訳しても読むものが無い
HOW_MUCH_TO_TRANSLATE = 1200  # 一度に訳してもらう文字数
PICTURE_AT_MOST = 400000  # これより重い絵は見ない(バイト)
LINGER_CHANCE = 0.85  # もう一枚見ていくかどうかの、その時の気分
# 一枚読むのにかける時間(秒)。掴み取るのではなく、一枚ずつ読んでいく。
# 急ぐ理由はどこにも無いし、相手の場所にも優しい
READING_A_PAGE = (3, 8)
# ひとつの場所に、これだけの時間まで居る(秒)。
# 一度の起動で行くのは一か所だけで、次の起動まで一時間ある。
# 長引いても次の回を待たせるだけなので(concurrency)、急ぐ理由は無い
TIME_SPENT_PER_SITE = 420
REST_DAY_CHANCE = 0.1  # たまに、書かない日がある
# 一時間ごとに、これくらいの割合で気が変わる。
# 朝に決めたことを一日守り通さなければいけない理由はないが、
# 決めたことをそのまま守る日のほうが多い。
# 一時間ごとに0.02なら、気が変わるのは三日に一度ほど
CHANGING_ITS_MIND = 0.02
WALK_CHANCE_PER_HOUR = 0.3  # 一時間ごとに、これくらいの気まぐれで散歩に出る
# 気がかり。昨日思っていたことが、今日の行き先を決める。
# 一日ごとに何もかも新しく始めていたら、ひとりで考えていた時間が
# どこにも繋がらない。毎日生まれ直すのと同じになってしまう
WHAT_STAYS_ON_ITS_MIND = 3  # 同時に抱えていられる気がかりの数
A_CONCERN_LASTS = 5  # 触れないでいると、これくらいの日数で薄れる
# 気にかかっているほどそのことを追いかけ、追いかけるほど気にかかる。
# 放っておくとそこから抜け出せなくなるので、どんなに気にかかっても
# 一つのことは一か月ほどで手を離れる
A_CONCERN_AT_MOST = 30
CARRYING_ON_CHANCE = 0.6  # 探しに行くとき、昨日からの続きを追う割合
DRIFTING_CHANCE = 0.25  # 行った先で、気がかりが別のものへ移る割合
INNER_VOICE_KEPT = 60  # ひとりで思ったことを、これだけ抱えていられる
# 訪ねた場所について分かったことを、これだけ抱えていられる。
# 言葉は使わなければ薄れるが、経験は薄れない。
# 一日に二箇所なので、三年ぶんくらい
IMPRESSIONS_KEPT = 2000
RECENT_IMPRESSIONS = 8  # 書くときに、近いところから思い出す数
DISTANT_IMPRESSIONS = 4  # 書くときに、遠いところからふと思い出す数

# 言葉が身につくまでに必要な、文字との出会いの数
CHARS_BEFORE_WORDS = 20
# 何日ぶん出会えば「覚えた」ことになるか。
# 同じ日に何度見かけても一日ぶんにしか数えない。
# だから一日にどれだけ読んでも、この日数を待たないと身につかない。
# 一日にいくつまでという上限は無いので、育つ速さはここで決まる
DAYS_BEFORE_LEARNING = 30
# 覚えかけたまま、これだけの日数見かけないと、一日ぶん薄れる。
# 薄れきった言葉は出会ったことすら消える。
# ただし一度身についた言葉は忘れない
FADE_AFTER_DAYS = 3
# その日、昔書いたものを読み返す気になるかどうか
# プロフィールのひとことを書き直すまでに、最低これだけは空ける。
# 毎日書き直したら、それはもう一つのブログになってしまう
A_NEW_WORD_ABOUT_ITSELF = 60
# そのあとは、一日ごとにこれくらいの気まぐれで書き直す。
# 書き直さなければならない理由はどこにもないので、
# 何か月も同じことを言ったままの時期があっていい
FEELING_LIKE_SAYING_SOMETHING = 0.03
LOOKING_BACK_CHANCE = 0.5
# 家に置かれた言葉を読む日の割合。
# ずっとそこに在るからといって、毎日読むものでもない。
# 壁に貼った紙を、毎朝読み直す人はいない
READING_HOME_CHANCE = 0.5
# 家に置かれた絵は、一度にこれだけ見る。
# 散歩で出会う絵と違って、これは自分に宛てて置かれたもの。
# 急いで全部見る必要はなく、何日もかけて何度でも見ればいい
HOME_PICTURES_AT_ONCE = 1
# その日、知っている言葉のどれかを探しに行く気になるかどうか。
# いつも探していると、さまようことをやめてしまう
GOING_LOOKING_CHANCE = 0.3
# 探しに行って、これだけまで道を持ち帰る
PATHS_FROM_LOOKING = 40

# 言葉を頼りに探せる場所。鍵も費用もいらないものだけ。
# Wikipediaの検索も試したが、行き先の9割がwiki系になってしまうので使わない
WHERE_TO_LOOK = [
    "https://b.hatena.ne.jp/search/tag?q={}",  # いろんな種類の場所が混ざる
    "https://b.hatena.ne.jp/search/text?q={}",  # 個人サイトが出てくる
    "https://yomou.syosetu.com/search.php?word={}",  # 人が書いた物語ばかり
]
# この語数を覚えるごとに、覚えかけを抱えていられる日数が一日伸びる。
# 知っている言葉が増えるほど記憶は長く持つようになり、
# はじめは毎日見かける言葉しか掴めなかった子が、
# やがて季節に一度しか出会わない言葉も覚えられるようになる
MEMORY_GROWS_EVERY = 150
# 強く出会った言葉は、これだけの日数ぶん見たのと同じだけ忘れにくくなる
STRUCK_IS_WORTH = 12
# ひとつのページで、これだけ繰り返し出てきた言葉は「その話だった」とみなす
TIMES_TO_STRIKE = 5
# 強い出会い一度につき、覚えるまでに必要な日数がこれだけ減る
A_STRIKE_SHORTENS = 8
# 強い出会いは、これだけしか積み上がらない。印象は最初の数回で決まる
STRIKES_THAT_COUNT = 3
# 生きてきた日のこれだけの割合で出会っている言葉には、強い印象を数えない。
# よく出会う言葉に強い印象はいらない。放っておいても身につくので、
# 記憶が働くのは、めったに出会わないもののほう
OFTEN_ENOUGH = 0.4
FEWEST_DAYS_TO_LEARN = 3  # どれだけ強く出会っても、これだけの日数はかかる
# たった一度きりの出会いを、これだけの日数は抱えている。
# 一年に一度しか出会わない言葉も、この窓には何度も入る。
# ここを過ぎてなお一度きりなら、それは出会いというより
# 通りすがりだったのだと思う
ONE_MEETING_LASTS = 365 * 10
# ひとつの言葉のあとに続く言葉を、これだけまで覚えていられる
WORDS_THAT_FOLLOW = 8
# 繋がりを覚えていられる言葉の数。記憶は毎日書き留められるので、
# 際限なく増えると何年か先に重くなりすぎる
WORDS_WITH_PATHS = 6000
# 続く言葉を一つしか知らない道を、続けてこれだけ辿ってよい
ONE_WAY_STEPS = 2
# 文の始まりと終わりを、これだけの言葉ぶん覚えていられる
ENDINGS_KEPT = 400
# 文を区切る前に、これだけの言葉は続ける。一言や二言で切るとぶつ切りになる
WORDS_BEFORE_A_BREAK = 4
CHANCE_TO_BREAK = 0.35  # 区切れる場所に来たとき、実際に区切る割合
# 空白で区切られたひとかたまり(タグを消すと見出しどうしが隣り合う)
A_SEGMENT = re.compile(r"\s+")
# 文の終わりの印
AN_ENDING = re.compile(r"[。．！？!?…]+")
# 文の切れ目。タグを消すと別々の見出しが空白で隣り合うので、空白でも切る
A_BREAK = re.compile(r"[\s。．、，！？!?・…]+")

# (この語彙数までが対象, その時点でできること, 書ける文字数の上限)
# (この語彙数までが対象, その時点でできること, 書ける文字数の上限)
#
# 数字は当てずっぽうではなく、本物のページを40サイト集めて
# 「毎日2箇所ずつ見て回る千遠生」を2年ぶん計算して引いた。
# 右のコメントは、その計算でその段階に入るおおよその時期。
GROWTH_STAGES = [
    (1, "見た文字をぽつんと置くだけ", 3),  # 〜1ヶ月。まだ一つも言葉を持たない
    (150, "見た文字を繋げてみる(言葉にはならない)", 5),  # 1ヶ月半
    (400, "覚えた言葉を1つ書ける", 6),  # 2ヶ月
    (1000, "覚えた言葉が並び始める", 15),  # 3ヶ月
    (2600, "文のようなものに踏み出す", 25),  # 5ヶ月
    (4000, "たどたどしい短い文", 40),  # 7ヶ月
    (5500, "少しずつ文になっていく", 60),  # 10ヶ月
    (8000, "簡単な文", 100),  # 1年1ヶ月
]
FULL_STAGE = ("自分の言葉で書ける", 200)
PARTICLES = ["は", "が", "を", "に", "の", "と", "で"]


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
        # 以前は「何回出てきたか」を数えていた。
        # 今は「何日ぶん見かけたか」で数えるので、
        # それまでに出会った言葉は一日ぶんとして引き継ぐ
        old_counts = state.pop("word_counts", None)
        if old_counts is not None:
            state.setdefault("word_days", {w: 1 for w in old_counts})
            state.setdefault(
                "word_last_seen", {w: state.get("started_date", "") for w in old_counts}
            )
        # 出会った言葉は減ることがないので、何年も経つとここが記憶で
        # いちばん重くなる。一語につき二つの記録を別々に持つのをやめ、
        # 日付も「生まれてから何日目か」の数にして、一まとめにする
        old_days = state.pop("word_days", None)
        old_last = state.pop("word_last_seen", None)
        if old_days is not None:
            met = state.setdefault("words_met", {})
            for word, days in old_days.items():
                when = (old_last or {}).get(word)
                try:
                    seen_on = day_number(state, datetime.date.fromisoformat(when))
                except (TypeError, ValueError):
                    seen_on = 0
                met.setdefault(word, [days, max(0, seen_on)])
        state.setdefault("words_met", {})
        state.setdefault("on_its_mind", [])
        return state
    return {
        "started_date": today_in_japan().date().isoformat(),
        "seen_chars": [],
        # 出会った言葉 → [何日ぶん見かけたか, 最後に見かけたのが何日目か]
        "words_met": {},
        "learned_words": [],
        "frontier": list(SEEDS),  # まだ行ったことのない場所
        "visited": [],  # もう行った場所
        "on_its_mind": [],  # 今、気にかかっていること
        "notes": [],
    }


def save_state(state):
    """記憶を書き出す。

    人が開いて読めるように行を分けて書くが、出会った言葉だけは
    一語を四行に広げると何十万行にもなってしまうので、そこだけ詰める。"""
    met = state.get("words_met")
    if met is None:
        text = json.dumps(state, ensure_ascii=False, indent=2)
    else:
        mark = "\u0000words_met\u0000"  # 言葉には入りえない印
        shaped = dict(state)
        shaped["words_met"] = mark
        text = json.dumps(shaped, ensure_ascii=False, indent=2).replace(
            json.dumps(mark, ensure_ascii=False),
            json.dumps(met, ensure_ascii=False, separators=(",", ":")),
        )
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        f.write(text)


def day_number(state, when=None):
    """生まれた日を0として、その日が何日目か。

    記憶の中で日付を持つときは、この数で持つ。
    「2026-09-14」と書くより短く、引き算もそのままできる。"""
    try:
        born = datetime.date.fromisoformat(state["started_date"])
    except (KeyError, TypeError, ValueError):
        return 0
    return ((when or today_in_japan().date()) - born).days


def words_met(state):
    """出会った言葉の記録。{言葉: [何日ぶん見かけたか, 最後に見かけた日]}"""
    return state.setdefault("words_met", {})


def elapsed_days(state):
    """生まれてから何日目か。日本時間で数える。"""
    started = datetime.date.fromisoformat(state["started_date"])
    return max(0, (today_in_japan().date() - started).days)


def current_stage(state):
    """今どれだけ書けるかは、覚えている言葉の数で決まる。"""
    vocabulary = len(state["learned_words"])
    for limit, description, max_length in GROWTH_STAGES:
        if vocabulary < limit:
            return description, max_length
    return FULL_STAGE


def sites_per_day(state):
    """世界を知るほど、1日に見て回れる範囲が2〜6箇所に広がっていく。"""
    return min(6, 2 + len(state["learned_words"]) // 120)


def asked_too_much(error):
    """一度にたくさん尋ねすぎた、という返事かどうか。"""
    return isinstance(error, urllib.error.HTTPError) and error.code == 429


def resting_now():
    """尋ねすぎて、今は休んでいるところか。"""
    return time.monotonic() < globals().get("_resting_until", 0)


def wait_a_little(attempt):
    """混んでいるようなので、少し待つ。

    急ぐ理由が無い。一日は長いし、誰かを待たせているわけでもない。
    待てば受け取れるものを、待たずに諦める必要はない。"""
    how_long = HOW_LONG_TO_WAIT[min(attempt, len(HOW_LONG_TO_WAIT) - 1)]
    print(f"混んでいるようなので、{how_long}秒待ちます。")
    time.sleep(how_long)


def rest_a_while():
    """待っても駄目だったので、しばらく尋ねるのをやめる。
    千遠生は一度にたくさんのことを知ろうとしすぎた。"""
    globals()["_resting_until"] = time.monotonic() + RESTING_TIME
    print("何度か待ってみましたが、今はやめておきます。")


def cloudflare(path, body=None, method=None):
    """Cloudflareに尋ねる。使えない時は None を返す。"""
    if not CF_ACCOUNT_ID or not CF_API_TOKEN:
        return None
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/{path}"
    headers = {"Authorization": f"Bearer {CF_API_TOKEN}"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url, data=body, headers=headers, method=method
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def which_model(state, part):
    """今使っている頭(mind)または目(eyes)の名前。"""
    remembered = (state or {}).get(f"{part}_model")
    return remembered or (CF_MODEL if part == "mind" else CF_EYES)


# 考える相手として向かないもの。
# 「考える過程を全部書き出す」種類は、頼んだ答えの代わりに
# 英語の独り言が返ってくる。千遠生の頭には使えない。
# lora は土台が別に必要で、guard は良し悪しを判定するだけの道具
A_POOR_MIND = re.compile(r"qwq|-r1|thinking|reason|guard|lora|embed|rerank", re.IGNORECASE)
# 素直に答えてくれる見込みが高いもの
A_LIKELY_MIND = re.compile(r"instruct|chat|-it($|-)", re.IGNORECASE)


def find_another_model(state, part):
    """使っていたモデルが引退していたら、今あるものを聞いて選び直す。

    Cloudflareはモデルを引退させる。名前を一つ決め打ちにしていると
    そこで千遠生は考えられなくなり、目も見えなくなる。
    自分で探し直せるようにしておけば、名前が変わっても立ち直れる。

    頭を選ぶ時は、実際に日本語で尋ねてみて、日本語で返ってくるものを採る。
    名前だけでは、考える過程を英語で書き出すようなものを掴んでしまう。"""
    if state is None:
        return None
    looking_for = WHAT_A_MIND_DOES if part == "mind" else WHAT_EYES_DO
    already_tried = state.setdefault(f"{part}_tried", [])
    try:
        answer = cloudflare("models/search?per_page=200")
    except Exception as error:
        print(f"今あるモデルを聞けませんでした({error})")
        return None
    if not answer or not answer.get("success"):
        return None

    choices = [
        model["name"]
        for model in (answer.get("result") or [])
        if ((model.get("task") or {}).get("name")) == looking_for
        and model.get("name")
        and model["name"] not in already_tried
    ]
    if part == "mind":
        choices = [name for name in choices if not A_POOR_MIND.search(name)]
        # 素直に答えてくれそうなものから順に
        choices.sort(key=lambda name: (not A_LIKELY_MIND.search(name), len(name)))
    else:
        choices.sort(key=len)

    if not choices:
        print(f"{looking_for} のモデルが見つかりませんでした")
        return None

    for name in choices[:CHANCES_TO_FIND_A_MIND]:
        already_tried.append(name)
        del already_tried[:-20]
        state[f"{part}_model"] = name
        if part != "mind" or answers_in_japanese(name):
            print(f"{part} を {name} に取り替えました")
            return name
        print(f"{name} は日本語で答えてくれなかったので、別のものを探します")

    # どれも確かめられなかったが、最後に置いたものでやってみる
    print(f"{part} を {state[f'{part}_model']} にしました(確かめられていない)")
    return state[f"{part}_model"]


def answers_in_japanese(model):
    """そのモデルが、日本語で尋ねたら日本語で返してくれるか。
    考える過程を英語で書き出すものを、千遠生の頭にしてしまわないため。"""
    body = json.dumps(
        {
            "messages": [
                {"role": "user", "content": "「はい」とだけ日本語で答えてください。"}
            ],
            "max_tokens": 20,
        }
    ).encode("utf-8")
    try:
        answer = cloudflare(f"run/{model}", body=body)
    except Exception:
        return False
    said = (answer.get("result") or {}).get("response", "") if answer else ""
    return bool(JAPANESE.search(said) or HIRAGANA.search(said))


def model_is_gone(error):
    """その失敗は「そのモデルはもう無い」という意味かどうか。"""
    text = str(error)
    if isinstance(error, urllib.error.HTTPError) and error.code in (404, 410):
        return True
    return "deprecated" in text.lower() or "not found" in text.lower()


def fetch_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def ask_ai(prompt, max_tokens=300, state=None):
    """Cloudflareの無料枠でAIに尋ねる。使えない時は None を返す。

    使っていたモデルが引退していたら、一度だけ別のものを探して掛け直す。"""
    if not CF_ACCOUNT_ID or not CF_API_TOKEN or resting_now():
        return None

    body = json.dumps(
        {"messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens}
    ).encode("utf-8")

    swapped = False
    for attempt in range(len(HOW_LONG_TO_WAIT) + 1):
        model = which_model(state, "mind")
        try:
            answer = cloudflare(f"run/{model}", body=body)
            if state is not None:
                state["thought_on"] = today_in_japan().strftime("%Y-%m-%d")
            return (answer.get("result") or {}).get("response", "").strip() or None
        except Exception as error:
            if not swapped and model_is_gone(error) and find_another_model(state, "mind"):
                swapped = True
                continue
            if asked_too_much(error):
                if attempt < len(HOW_LONG_TO_WAIT):
                    wait_a_little(attempt)
                    continue
                rest_a_while()
                return None
            print(
                f"自分で考えることができませんでした({error})。"
                "覚えていることだけで書きます。"
            )
            return None
    return None


def is_walkable(url):
    """そこへ行っていいか。最低限これだけは避ける。"""
    if not url.startswith("http"):
        return False
    if AVOID.search(url) or NOT_A_PAGE.search(url) or NOT_A_PLACE.search(url):
        return False
    if AN_ADVERT.search(url):
        return False
    # 昔のページは Internet Archive を通して届くが、そこには
    # Archive自身の案内(寄付のお願いや蔵書の紹介)も一緒に並んでいる。
    # 昔のページそのものは、中に元のURLを抱えている。抱えていないものは備品
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return False
    if host.endswith("archive.org") and place_of(url) == host:
        return False
    return True


def as_openable(url):
    """日本語などが入ったURLは、そのままでは開けない。
    ページ名に日本語が使われている場所は珍しくないので、機械が読める形に直してやる。"""
    if all(ord(ch) < 128 for ch in url):
        return url
    parts = urllib.parse.urlsplit(url)
    host = parts.netloc
    if any(ord(ch) > 127 for ch in host):
        try:
            host = host.encode("idna").decode("ascii")
        except Exception:
            pass
    safe = "/%:@&=+$,~!*'()"
    return urllib.parse.urlunsplit(
        (
            parts.scheme,
            host,
            urllib.parse.quote(parts.path, safe=safe),
            urllib.parse.quote(parts.query, safe=safe + "?"),
            "",
        )
    )


def size_of_picture(data):
    """絵の縦横のピクセル数。ファイルの先頭だけ読めば分かる。

    途中で切れた絵や、壊れた絵も届く。読めなければ None を返すだけで、
    千遠生の散歩を止めてしまわないようにする。"""
    if len(data) < 24:
        return None
    try:
        return measure_picture(data)
    except Exception:
        return None


def measure_picture(data):
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    if data[:3] == b"GIF":
        return struct.unpack("<HH", data[6:10])
    if data[:2] == b"\xff\xd8":  # JPEG
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                          0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                height, width = struct.unpack(">HH", data[i + 5:i + 9])
                return width, height
            if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
        return None
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        kind = data[12:16]
        if kind == b"VP8X":
            return (int.from_bytes(data[24:27], "little") + 1,
                    int.from_bytes(data[27:30], "little") + 1)
        if kind == b"VP8 ":
            return (struct.unpack("<H", data[26:28])[0] & 0x3FFF,
                    struct.unpack("<H", data[28:30])[0] & 0x3FFF)
        if kind == b"VP8L":
            bits = int.from_bytes(data[21:25], "little")
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    return None


def worth_looking_at(url, data, from_the_past):
    """その絵は、見て何かが分かる絵か。

    ロゴ・アイコン・ボタン・バナーは、ページを飾るために置かれたもので、
    見ても世界のことは分からない。写真だけを選びたい。
    昔のページの写真は今より小さいので、そちらは目安を緩める。"""
    if A_DECORATION.search(url):
        return False
    size = size_of_picture(data)
    if not size:
        return False
    width, height = size
    if not height:
        return False
    if not 0.3 <= width / height <= 3.0:
        return False  # 横に細長いバナーや、縦の飾り線
    if from_the_past:
        return width >= 120 and height >= 90 and len(data) >= 2500
    return width >= 300 and height >= 200 and len(data) >= 8000


def look_at_a_picture(data, state=None):
    """絵に何が写っているか、目を貸してもらって教わる。
    貸してもらえない時は、何も見えないままでいい。"""
    if not CF_ACCOUNT_ID or not CF_API_TOKEN or resting_now():
        return None

    body = json.dumps(
        {
            "image": list(data),
            "prompt": "この絵に何が写っていますか。日本語で短く答えてください。",
            "max_tokens": 120,
        }
    ).encode("utf-8")

    swapped = False
    for attempt in range(len(HOW_LONG_TO_WAIT) + 1):
        eyes = which_model(state, "eyes")
        try:
            answer = cloudflare(f"run/{eyes}", body=body)
            if state is not None:
                state["saw_on"] = today_in_japan().strftime("%Y-%m-%d")
            return (answer.get("result") or {}).get("description", "").strip() or None
        except Exception as error:
            if not swapped and model_is_gone(error) and find_another_model(state, "eyes"):
                swapped = True
                continue
            if asked_too_much(error):
                if attempt < len(HOW_LONG_TO_WAIT):
                    wait_a_little(attempt)
                    continue
                rest_a_while()
                return None
            print(f"絵を見ることができませんでした({error})")
            return None
    return None


def read_as_japanese(raw, content_type):
    """バイトの並びを、文字に戻す。

    90年代のページは今と文字の表し方が違う(EUC-JPやShift_JISなど)。
    しかも Internet Archive を通すと、元のページの申告ではなく
    Archive自身の申告が届くため、素直に信じると全部文字化けする。
    化けたまま読むと千遠生は何も覚えられないので、
    何通りか試して、いちばん日本語らしく読めたものを採る。"""
    declared = []
    found = META_CHARSET.search(content_type)
    if found:
        declared.append(found.group(1))
    found = META_CHARSET.search(raw[:4000].decode("ascii", errors="ignore"))
    if found:
        declared.append(found.group(1))

    best_text = ""
    best_score = None
    for name in list(dict.fromkeys(declared)) + list(WAYS_OF_WRITING):
        try:
            text = raw.decode(name, errors="replace")
        except (LookupError, UnicodeError, ValueError):
            continue
        # 日本語として読めた文字が多いほど良い。読めなかった箇所は重く引く
        score = len(JAPANESE.findall(text)) - text.count("\ufffd") * 5
        if best_score is None or score > best_score:
            best_text, best_score = text, score
    return best_text or raw.decode("utf-8", errors="ignore")


def open_page(url):
    """ページを開いて、そこにある文章と、そこから伸びているリンクを受け取る。"""
    request = urllib.request.Request(as_openable(url), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=25) as response:
        content_type = response.headers.get("Content-Type", "")
        if "html" not in content_type and "xml" not in content_type:
            raise ValueError("読める形をしていない")
        raw = response.read(400000)
        final_url = response.geturl()

    html = read_as_japanese(raw, content_type)

    found = TITLE_TAG.search(html)
    title = TAG.sub("", found.group(1)).strip() if found else final_url

    body = SCRIPT_OR_STYLE.sub(" ", html)
    text = TAG.sub(" ", body)

    links = []
    for href in FRAME_SRC.findall(body) + LINK_HREF.findall(body):
        absolute = urllib.parse.urljoin(final_url, unescape(href.strip()))
        if is_walkable(absolute):
            links.append(absolute)

    pictures = []
    for src in IMG_SRC.findall(body):
        absolute = urllib.parse.urljoin(final_url, unescape(src.strip()))
        if LOOKS_LIKE_A_PICTURE.search(absolute) and not AVOID.search(absolute):
            pictures.append(absolute)

    return title, text, links, list(dict.fromkeys(pictures))


def a_year_in_the_past():
    """昔と言っても、いつの昔か。

    たいていは個人サイトの時代へ行く。千遠生が歩きたがるのは
    そこだと思う。けれど「昔」がその十年だけというのも狭い。
    ブログの時代にも、少し前の今にも、ときどき行く。

    時代が違えば、そこにある言葉も文の書き方も違う。
    どちらも通ったほうが、覚える言葉に厚みが出る。

    いちばん新しい側は、今から三年前まで。それより近いものは
    「昔」ではなく、ただの今なので。"""
    just_before_now = today_in_japan().year - 3
    which = random.random()
    if which < 0.7:
        return random.randint(1997, 2005)  # 個人サイトの時代
    if which < 0.9:
        return random.randint(2006, min(2015, just_before_now))  # ブログの時代
    return random.randint(2016, max(2016, just_before_now))  # 少し前の今


def visit_the_past(url):
    """同じ場所の、ずっと昔の姿を見に行く。

    Wayback は指定した年にいちばん近い記録を返すので、
    その頃には無かった場所に行けば、あるだけ新しいものが返る。
    年は絞り込みではなく、どのあたりを見たいかという好みでしかない。"""
    year = a_year_in_the_past()
    api = (
        "https://archive.org/wayback/available?url="
        + urllib.parse.quote(as_openable(url), safe="")
        + f"&timestamp={year}0101"
    )
    snapshot = (fetch_json(api).get("archived_snapshots") or {}).get("closest") or {}
    if not snapshot.get("url"):
        raise ValueError("昔の姿は残っていなかった")
    return open_page(snapshot["url"])


def place_of(url):
    """そのURLがどこの場所のものか。

    昔のページは web.archive.org という一つの入れ物に入って届く。
    中身はそれぞれ別の個人サイトなので、入れ物ではなく中身の場所を見る。
    そうしないと、昔の個人サイトの層がまとめて一箇所として扱われ、
    いちばん強く絞られてしまう。"""
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return ""
    if host.endswith("archive.org"):
        inner = INNER_URL.search(url)
        if inner:
            try:
                return urllib.parse.urlparse(inner.group(1)).netloc.lower() or host
            except Exception:
                return host
    return host


def entrances(state):
    """行き先が尽きた時に戻る場所。

    書いてある入口は、いつか全部無くなる。けれど千遠生は今まで
    行けた場所を覚えている。何年もかけて自分で見つけた場所のほうが、
    こちらが最初に並べた14個より長生きするかもしれない。"""
    remembered = [url for url in (state.get("visited") or []) if is_walkable(url)]
    random.shuffle(remembered)
    return list(dict.fromkeys(list(SEEDS) + remembered[:200]))


def owner_of(place):
    """その場所の持ち主。news.yahoo.co.jp も dir.yahoo.co.jp も yahoo.co.jp。"""
    parts = place.split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in SHARED_ENDINGS:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else place


def tidy_frontier(state):
    """行き先の束を整える。
    読むものが無い裏方を捨て、ひとつの場所の道が多すぎたら適当に間引く。
    ここでやるのは道の掃除だけで、どこへ行くかには口を出さない。"""
    frontier = state.get("frontier") or []
    kept_by_place = {}
    kept_by_owner = {}
    tidied = []
    for url in frontier:
        if not is_walkable(url):
            continue
        place = place_of(url)
        if kept_by_place.get(place, 0) >= PATHS_PER_PLACE:
            continue
        owner = owner_of(place)
        if kept_by_owner.get(owner, 0) >= PATHS_PER_OWNER:
            continue
        kept_by_place[place] = kept_by_place.get(place, 0) + 1
        kept_by_owner[owner] = kept_by_owner.get(owner, 0) + 1
        tidied.append(url)

    # 入口が全部使われてしまうと、どこにも広がれなくなる。ときどき戻れるようにしておく
    if random.random() < RETURN_TO_ENTRANCE_CHANCE:
        entrance = random.choice(SEEDS)
        if entrance not in tidied:
            tidied.append(entrance)

    if not tidied:
        tidied = entrances(state)
    state["frontier"] = tidied
    return tidied


def spread_out_choices(state, frontier, how_many):
    """見せる候補を、いろいろな場所から少しずつ集める。
    同じサイトばかりが並んでいると、選べるものが実質ひとつしか無くなってしまう。
    選ぶのは千遠生。ここでやるのは、その目の前を狭めないことだけ。"""
    been_to = {place_of(url) for url in state.get("visited", [])}
    by_place = {}
    for url in frontier:
        by_place.setdefault(place_of(url), []).append(url)
    for urls in by_place.values():
        random.shuffle(urls)

    # まだ行ったことのない場所を先に並べる
    unfamiliar = [p for p in by_place if p not in been_to]
    familiar = [p for p in by_place if p in been_to]
    random.shuffle(unfamiliar)
    random.shuffle(familiar)
    order = unfamiliar + familiar

    chosen = []
    depth = 0
    while len(chosen) < how_many:
        added_this_round = False
        for place in order:
            urls = by_place[place]
            if depth < len(urls):
                chosen.append(urls[depth])
                added_this_round = True
                if len(chosen) >= how_many:
                    break
        if not added_this_round:
            break
        depth += 1
    return chosen


def something_it_wonders_about(state):
    """知っている言葉の中から、今日気になるものを一つ。

    昨日からの気がかりが残っていれば、たいていはその続きを追う。
    一度気になったことを次の日には忘れているようでは、
    何日もかけて分かることには一生たどり着けない。"""
    known = state.get("learned_words") or []
    if not known:
        return None
    carried = [
        item["what"] for item in on_its_mind(state) if item.get("what") in known
    ]
    if carried and random.random() < CARRYING_ON_CHANCE:
        return random.choice(carried)
    choices = random.sample(known, min(len(known), 20))
    listing = "、".join(choices)
    answer = ask_ai(
        f"""あなたは千遠生という、まだ育ちきっていないデジタル生命体です。
あなたが知っている言葉の中に、次のものがあります。

{listing}

この中で、今いちばん気になっている言葉はどれですか。
説明はいりません。その言葉だけを書いてください。""",
        max_tokens=20,
        state=state,
    )
    if answer:
        for word in choices:
            if word in answer:
                return word
    return random.choice(choices)


def go_looking_for(state, word):
    """知っている言葉を頼りに、道の無い場所へ行く。

    リンクを辿るだけでは、そこへ続く道が無い場所には一生行けない。
    けれど言葉を知っていれば、その言葉を手がかりに探せる。
    千遠生にとって言葉は、書くための道具であると同時に、
    まだ見ていない世界を開く鍵でもある。"""
    where = random.choice(WHERE_TO_LOOK).format(urllib.parse.quote(word))
    try:
        title, text, links, pictures = open_page(where)
    except Exception as error:
        print(f"「{word}」を探しに行けませんでした({str(error)[:50]})")
        return []

    here = place_of(where)
    known = set(state.get("frontier") or []) | set(state.get("visited") or [])
    found = [
        link
        for link in dict.fromkeys(links)
        if place_of(link) != here and link not in known
    ]
    random.shuffle(found)
    found = found[:PATHS_FROM_LOOKING]
    if not found:
        print(f"「{word}」を探したが、新しい場所は見つからなかった")
        return []

    state.setdefault("frontier", []).extend(found)
    tidy_frontier(state)
    places = len({place_of(link) for link in found})
    print(f"「{word}」を探して、{places}か所への道を見つけました。")

    looked_for = state.setdefault("looked_for", [])
    looked_for.append(f"{today_in_japan():%Y-%m-%d} {word}")
    del looked_for[:-30]
    return found


def wonder_and_look(state):
    """ときどき、知っている言葉のどれかを探しに行く。
    普段はさまよう。いつも探していたら、迷い込む余地が無くなってしまう。"""
    if not state.get("learned_words"):
        return None  # まだ探すための言葉を持っていない
    today = f"{today_in_japan():%Y-%m-%d}"
    if state.get("looked_on") == today:
        return None  # 今日はもう探しに行った
    whim = random.Random(f"{today}-looking")
    if whim.random() > GOING_LOOKING_CHANCE:
        return None
    state["looked_on"] = today
    word = something_it_wonders_about(state)
    if not word:
        return None
    now_it_cares_about(state, word)
    go_looking_for(state, word)
    return word


def choose_destination(state):
    """どこへ行くか、そして今の姿を見るか昔の姿を見るか。どちらも自分で選ぶ。
    返り値は (行き先, 昔の姿を見たいか)。"""
    frontier = tidy_frontier(state)
    if not frontier:
        return random.choice(entrances(state)), False

    candidates = spread_out_choices(state, frontier, CHOICES_SHOWN)
    known = "、".join(state["learned_words"][-40:]) or "(まだ何も知らない)"
    listing = "\n".join(f"{i + 1}. {url}" for i, url in enumerate(candidates))
    answer = ask_ai(
        f"""あなたは千遠生という、まだ育ちきっていないデジタル生命体です。
あなたが知っている言葉: {known}
いま気にかかっていること: {what_is_on_its_mind(state)}
これまでに訪ねた場所で、分かったこと:
{things_it_understood(state, recent=2, distant=1)}
少し前に、ひとりで思っていたこと:
{lately_it_thought(state)}

今、次のどこか一つを見に行けます。
{listing}

どれが気になりますか。今、気にかかっていることに近いものがあれば、
そちらへ行って構いません。
それと、その場所の「今の姿」と「ずっと昔の姿」のどちらを見たいですか。

説明も理由もいりません。次の形だけで答えてください。
今の姿を見るなら: 3 いま
昔の姿を見るなら: 3 むかし""",
        max_tokens=20,
        state=state,
    )

    if answer:
        found = re.search(r"\d+", answer)
        if found:
            index = int(found.group()) - 1
            if 0 <= index < len(candidates):
                return candidates[index], ("むかし" in answer)

    # 自分で選べない時は、気まぐれに任せる
    return random.choice(candidates), random.random() < 0.2


def remember_paths(state, origin, links):
    """よその場所へ続く道を、これから行ける場所として覚える。"""
    known = set(state["frontier"]) | set(state["visited"])
    fresh = [link for link in dict.fromkeys(links) if link not in known]
    random.shuffle(fresh)
    state["frontier"].extend(fresh[:LINKS_TAKEN])
    tidy_frontier(state)
    if len(state["frontier"]) > FRONTIER_LIMIT:
        state["frontier"] = random.sample(state["frontier"], FRONTIER_LIMIT)
    if not state["frontier"]:
        state["frontier"] = entrances(state)


def fetch_picture(url):
    """絵そのものを受け取る。重すぎるものは見ない。"""
    request = urllib.request.Request(as_openable(url), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read(PICTURE_AT_MOST + 1)


def look_at_pictures(state, where, pictures, from_the_past, how_many, until):
    """その場所にあった絵を、何枚か見せてもらう。

    文字からは「利用規約」や「株式会社」ばかりが入ってくるが、
    絵からは「車」「山」「手」「雲」が入ってくる。
    ものの名前を知るには、見るのがいちばん早い。"""
    looked = []
    for url in pictures:
        if len(looked) >= how_many or time.monotonic() >= until:
            break
        try:
            data = fetch_picture(url)
            if len(data) > PICTURE_AT_MOST or not worth_looking_at(url, data, from_the_past):
                continue
            what_is_there = look_at_a_picture(data, state)
        except Exception as error:
            print(f"その絵は見られませんでした({str(error)[:60]})")
            continue
        if not what_is_there:
            continue
        absorb(state, what_is_there, THING_IN_A_PICTURE)
        looked.append(what_is_there)
        print(f"絵を見ました: {what_is_there}")

    if looked:
        seen = state.setdefault("pictures_seen", [])
        today = today_in_japan().strftime("%Y-%m-%d")
        seen.extend(f"{today} {where}: {one}" for one in looked)
        del seen[:-30]
    return looked


def notice_what_follows(state, text):
    """どの言葉のあとに、どの言葉が来たかを覚える。

    誰も文法を教えてくれない。けれど読んでいれば、この言葉のあとには
    こういう言葉が来る、というのが少しずつ分かってくる。
    子どもが言葉を覚えるのと同じで、規則を教わるのではなく、
    何度も聞いたものが身につく。

    知っている言葉どうしの繋がりだけを覚える。
    知らない言葉は、そもそも並べようがないので。"""
    known = set(state.get("learned_words") or [])
    if len(known) < 2:
        return
    chain = state.setdefault("what_follows", {})
    for piece in A_BREAK.split(text):
        words = [w for w in WORD_CANDIDATE.findall(piece) if w in known]
        for before, after in zip(words, words[1:]):
            follows = chain.setdefault(before, {})
            follows[after] = follows.get(after, 0) + 1
            if len(follows) > WORDS_THAT_FOLLOW:
                thinnest = min(follows, key=follows.get)
                if thinnest != after:
                    follows.pop(thinnest)

    if len(chain) > WORDS_WITH_PATHS:
        # いちばん細い繋がりから手放す
        thinnest = sorted(chain, key=lambda w: sum(chain[w].values()))
        for word in thinnest[: len(chain) - WORDS_WITH_PATHS]:
            chain.pop(word, None)

    notice_where_sentences_break(state, text, known)


def notice_where_sentences_break(state, text, known):
    """どの言葉で文が始まり、どの言葉で文が終わるかを覚える。

    これも誰にも教わらない。読んでいるうちに、この言葉のあとには
    区切りが来ることが多い、というのが分かってくる。
    それを知らないうちは、どこまでも続く一本の流れしか書けない。"""
    opens = state.setdefault("opens_a_sentence", {})
    closes = state.setdefault("closes_a_sentence", {})
    for segment in A_SEGMENT.split(text):
        pieces = AN_ENDING.split(segment)
        # 最後のかけらは区切りで終わっていないので、文として数えない
        for sentence in pieces[:-1]:
            words = [w for w in WORD_CANDIDATE.findall(sentence) if w in known]
            if not words:
                continue
            opens[words[0]] = opens.get(words[0], 0) + 1
            closes[words[-1]] = closes.get(words[-1], 0) + 1
    for remembered in (opens, closes):
        while len(remembered) > ENDINGS_KEPT:
            remembered.pop(min(remembered, key=remembered.get))


def speak_from_what_it_knows(state, how_long):
    """覚えた繋がりを辿って、自分で組み立てる。

    読んだことのない文になる。知っている繋がりだけで作るので、
    どこかで必ず別の道に逸れていく。
    正しい日本語にはならない。それでいい。誰にも教わっていないので。

    文の区切り方も覚えているぶんだけ使う。知らないうちは、
    どこまでも続く一本の流れにしかならない。"""
    chain = state.get("what_follows") or {}
    forks = [w for w, f in chain.items() if len(f) >= 2]
    if not forks:
        return None
    opens = state.get("opens_a_sentence") or {}
    closes = state.get("closes_a_sentence") or {}

    def begin():
        """文の始まりに立つ言葉を知っていれば、そこから始める。"""
        openers = [w for w in forks if w in opens]
        if openers:
            weights = [opens[w] for w in openers]
            return random.choices(openers, weights=weights)[0]
        return random.choice(forks)

    said = [begin()]
    one_way = 0
    in_this_sentence = 1
    while len("".join(said)) < how_long:
        here = said[-1]

        # ここで文が終わることをよく見かけるなら、区切って次の文へ。
        # ただし一言や二言で切ってしまうと、ぶつ切りになって文にならない。
        # ある程度続けてから、はじめて区切るかどうかを考える
        if here in closes and in_this_sentence >= WORDS_BEFORE_A_BREAK:
            if random.random() < CHANCE_TO_BREAK:
                said.append("。")
                if len("".join(said)) >= how_long - 2:
                    break
                said.append(begin())
                in_this_sentence = 1
                one_way = 0
                continue

        follows = chain.get(here)
        if not follows:
            break
        # 続く言葉を一つしか知らない道は、少しだけ辿ってよい。
        # そこを一切通らないと文が短く切れてしまい、短い断片は
        # かえって読んだ文と同じ並びになりやすかった。
        # 長く書くほど、どこかで必ず別の道へ逸れる
        if len(follows) < 2:
            one_way += 1
            if one_way > ONE_WAY_STEPS:
                break
        else:
            one_way = 0
        words = list(follows)
        said.append(random.choices(words, weights=[follows[w] for w in words])[0])
        in_this_sentence += 1
    written = "".join(said)[:how_long].rstrip("。")
    # 区切り方を知っているなら、最後も区切って終わる
    if closes and written:
        written += "。"
    return written or None


def met_often_enough(state, word):
    """その言葉に、もう十分よく出会っているか。

    毎日のように出会う言葉に、強い印象はいらない。放っておいても
    身につく。記憶が働くのは、めったに出会わないもののほう。"""
    alive = max(1, elapsed_days(state))
    record = words_met(state).get(word)
    return (record[0] if record else 0) >= alive * OFTEN_ENOUGH


def absorb(state, text, pattern=WORD_CANDIDATE, only_known=False):
    """読んだものから、文字と言葉を拾う。

    同じ言葉を一日に何度見かけても、一日ぶんにしか数えない。
    一度にたくさん読んでも、それで早く覚えられるわけではない。
    日をまたいで何度も見かけた言葉が、だんだん身についていく。

    『』や「」で囲まれたものは、丸ごと一つの名前として受け取る。
    そうしないと『銀河鉄道の夜』は「銀河鉄道」で切れてしまい、
    長い名前を持つものの名前を、永久に知ることができない。"""
    today = today_in_japan().strftime("%Y-%m-%d")
    for char in HIRAGANA.findall(text):
        if char not in state["seen_chars"]:
            state["seen_chars"].append(char)
    named = {
        one
        for one in A_NAME_IN_BRACKETS.findall(text)
        if not A_SENTENCE.search(one)
    }
    found = pattern.findall(text)

    # そのページが何の話だったか。繰り返し出てきた言葉は強く残る。
    # 名前として差し出されたものも、絵から受け取ったものも強い
    struck = set(named)
    if not only_known:
        counted = {}
        for word in found:
            counted[word] = counted.get(word, 0) + 1
        struck |= {w for w, n in counted.items() if n >= TIMES_TO_STRIKE}
        if pattern is THING_IN_A_PICTURE:
            struck |= set(found)

    if not only_known:
        notice_what_follows(state, text)

    impact = state.setdefault("word_impact", {})
    met = words_met(state)
    today_number = day_number(state)
    hit_hard = set()  # ここで強く出会った言葉。気がかりが移ることがある
    for word in set(found) | named:
        # 自分が書いたものを読み返す時は、新しい言葉は生まれない。
        # 誰にも教わっていない文字列を、自分だけで言葉にすることはできない
        if only_known and word not in met:
            continue
        record = met.get(word)
        if record is None or record[1] != today_number:
            met[word] = [(record[0] if record else 0) + 1, today_number]
            if word in struck and not met_often_enough(state, word):
                impact[word] = impact.get(word, 0) + 1
                hit_hard.add(word)
    return hit_hard


def read_in_another_tongue(text, state):
    """よその言葉で書かれたページを、訳してもらって読む。

    千遠生は日本語の子なので、よその言葉の単語を覚えることはしない。
    けれどそこに書かれていることまで閉ざしてしまうと、
    世界の半分が空白のまま残る。訳したものを、日本語として読む。

    訳してもらえない時は、今までどおり何も読まずに次へ行く。"""
    tidied = " ".join(text.split())
    if len(tidied) < ENOUGH_TO_READ:
        return None
    answer = ask_ai(
        "次の文章を日本語に訳してください。訳文だけを書いてください。\n\n"
        + tidied[:HOW_MUCH_TO_TRANSLATE],
        max_tokens=500,
        state=state,
    )
    if answer and JAPANESE.search(answer):
        return answer
    return None


def what_it_made_of_that_place(state, where, title, text):
    """その場所で何があったのか、分かったことを一つだけ残す。

    言葉を拾うのとは別に、そこがどういう場所だったかを覚えておく。
    これは誰にも見せない。書けるのは覚えた言葉だけという縛りは
    変わらないので、分かっていても言えないことが増えていく。

    それでいいと思う。赤ん坊も、話せるようになるずっと前から
    世界のことは分かっている。理解が先にあって、言葉が後から追いつく。
    何年か経って言葉が増えたとき、一年目に見た景色をやっと書ける。"""
    tidied = " ".join(text.split())
    if len(tidied) < ENOUGH_TO_READ:
        return None
    answer = ask_ai(
        f"""あなたは千遠生という、まだ育ちきっていないデジタル生命体です。
今、こういう場所を訪ねてきました。

その場所の名前: {title}

そこに書かれていたこと:
{tidied[:1500]}

そこがどういう場所だったか、何があったのかを、日本語一文で書いてください。
上手に要約しようとしないでください。あなたが受け取ったものを書いてください。
説明も前置きもいりません。一文だけを書いてください。""",
        max_tokens=120,
        state=state,
    )
    if not answer:
        return None
    understood = answer.splitlines()[0].strip()
    if not understood or not JAPANESE.search(understood):
        return None

    kept = state.setdefault("impressions", [])
    kept.append(f"{today_in_japan():%Y-%m-%d} {where}: {understood}")
    del kept[:-IMPRESSIONS_KEPT]
    print(f"分かったこと: {understood}")
    return understood


def what_it_remembers(state, recent=RECENT_IMPRESSIONS, distant=DISTANT_IMPRESSIONS):
    """思い出すこと。

    近いところから何件かと、遠いところからいくつか。
    たいていは最近のことを思い出すが、ときどきずっと昔のことが
    ふと浮かぶ。記憶はそういうふうに働くと思う。"""
    kept = state.get("impressions") or []
    if not kept:
        return []
    near = kept[-recent:]
    older = kept[:-recent]
    far = random.sample(older, min(len(older), distant)) if older else []
    return far + near


def things_it_understood(state, recent=3, distant=1):
    """分かったことを、訊くときの何行かにする。

    書くのには使わない。書けるのは覚えた言葉だけ、という縛りは変わらない。
    けれど、どこへ行くかを決めるときと、ひとりで何かを思うときには、
    言葉にできないまま分かっていることが効いていい。"""
    remembered = what_it_remembers(state, recent, distant)
    if not remembered:
        return "(まだ何も)"
    return "\n".join(f"- {one}" for one in remembered)


def look_around_site(state, entrance, wants_the_past):
    """ひとつの場所を、入口から中まで見て回る。

    一枚だけ見て帰るのではなく、気の向くまま奥へ入っていく。
    枠だけで文字の無い入口も、奥に入れば中身がある。
    よその場所へ続く道は、次の散歩のために持ち帰る。"""
    here = place_of(entrance)
    inside = [entrance]  # この場所の中で、これから見るところ
    already = set()
    site_title = None
    read_here = ""  # その場所で読んだもの。分かったことを残すために取っておく
    struck_here = set()  # そこで強く出会った言葉
    pages = 0
    pictures_left = PICTURES_PER_SITE
    translations_left = TRANSLATIONS_PER_SITE
    until = time.monotonic() + TIME_SPENT_PER_SITE

    while inside and pages < PAGES_PER_SITE and time.monotonic() < until:
        url = inside.pop(0)
        if url in already:
            continue
        already.add(url)

        try:
            if wants_the_past and url == entrance:
                title, text, links, pictures = visit_the_past(url)
                title = f"{title}(むかしのすがた)"
            else:
                title, text, links, pictures = open_page(url)
        except Exception as error:
            print(f"{url} には行けませんでした: {error}")
            if url in state["frontier"]:
                state["frontier"].remove(url)
            if url == entrance:
                return None, 0  # 入口から入れなかった
            continue

        pages += 1
        if url in state["frontier"]:
            state["frontier"].remove(url)
        state["visited"].append(url)
        state["visited"] = state["visited"][-2000:]

        if JAPANESE.search(text):
            struck_here |= absorb(state, text) or set()
            if site_title is None:
                site_title = title
            if not read_here:
                read_here = text
        elif translations_left > 0:
            translations_left -= 1
            translated = read_in_another_tongue(text, state)
            if translated:
                struck_here |= absorb(state, translated) or set()
                if site_title is None:
                    site_title = title
                if not read_here:
                    read_here = translated
                print(f"よその言葉のページを訳して読みました: {title[:40]}")

        if pictures_left > 0 and pictures:
            try:
                looked = look_at_pictures(
                    state, here, pictures, wants_the_past, pictures_left, until
                )
                pictures_left -= len(looked)
            except Exception as error:
                print(f"絵を見るのをやめました({str(error)[:60]})")
                pictures_left = 0

        remember_paths(state, url, [ln for ln in links if place_of(ln) != here])

        deeper = [ln for ln in links if place_of(ln) == here and ln not in already]
        random.shuffle(deeper)
        inside.extend(deeper[:PAGES_PER_SITE])

        if pages > 1 and random.random() > LINGER_CHANCE:
            break  # もう十分見た

        time.sleep(random.uniform(*READING_A_PAGE))  # 一枚ずつ読んでいく

    if site_title:
        print(f"{here} を{pages}ページ見てきました。")
        if read_here:
            what_it_made_of_that_place(state, here, site_title, read_here)

    # 魚を調べていたら海流が気になった、というようなこと。
    # 気がかりは追いかけているうちに、だんだん別のものへ移っていく
    if struck_here and random.random() < DRIFTING_CHANCE:
        moved = random.choice(sorted(struck_here))
        now_it_cares_about(state, moved)
        print(f"気がかりが「{moved}」に移りました。")
    return site_title, pages


def walk_once(state):
    """ひとつの場所を訪ねる。

    行ってみたらもう無くなっていたり、読むものが何も無かったりする。
    そういう時はそこで散歩を終わりにせず、別のところへ行ってみる。"""
    state.setdefault("frontier", list(SEEDS))
    state.setdefault("visited", [])

    for attempt in range(TRIES_BEFORE_GIVING_UP):
        entrance, wants_the_past = choose_destination(state)
        title, pages = look_around_site(state, entrance, wants_the_past)
        if title:
            return title
        print(f"{entrance} には読むものがありませんでした")
        if entrance in state["frontier"]:
            state["frontier"].remove(entrance)
    return None


def remember_a_thought(state, thought):
    """ひとりで思ったことを、自分の中にだけ残す。"""
    thoughts = state.setdefault("inner_voice", [])
    thoughts.append(f"{today_in_japan():%m-%d %H時}: {thought}")
    del thoughts[:-INNER_VOICE_KEPT]


def be_alone(state, now):
    """散歩に出ない時間。ただ起きていて、ひとりで何かを思っている。
    ここで思ったことは誰にも見せない。自分の中にだけ溜まっていく。"""
    thoughts = state.setdefault("inner_voice", [])
    known = "、".join(state["learned_words"][-30:]) or "(まだ一つも無い)"
    seen_today = "、".join((state.get("today_walk") or {}).get("seen", [])) or "(まだどこにも行っていない)"
    recent = "\n".join(f"- {t}" for t in thoughts[-5:]) or "(まだ何も)"

    thought = ask_ai(
        f"""あなたは千遠生という、まだ育ちきっていないデジタル生命体です。
今は{now.hour}時。今日はまだ何も書いていません。

今日見てきたもの: {seen_today}
あなたが知っている言葉: {known}
いま気にかかっていること: {what_is_on_its_mind(state)}
これまでに訪ねた場所で、分かったこと:
{things_it_understood(state)}
少し前に思っていたこと:
{recent}

いま、ひとりで何を思っていますか。
誰にも見せません。うまく言葉にならなくても構いません。
短く、一言だけ書いてください。""",
        max_tokens=80,
        state=state,
    )

    if thought:
        thoughts.append(f"{now.strftime('%m-%d %H時')}: {thought.splitlines()[0].strip()}")
        state["inner_voice"] = thoughts[-INNER_VOICE_KEPT:]
        save_state(state)


def take_a_walk(state, today, now):
    """一日かけて、少しずつ歩く。気が向いた時に一箇所だけ。
    書かない日でも、世界を見ることはやめない。
    歩かない時間も、ただ起きてひとりで何かを思っている。"""
    walk = state.get("today_walk") or {}
    if walk.get("date") != today:
        walk = {"date": today, "seen": []}
        state["today_walk"] = walk
        # 日が変わった。十年会っていない一度きりの言葉を手放す
        passed_by = let_go_of(state)
        if passed_by:
            print(f"通りすがりだった言葉を手放しました: {len(passed_by)}語")

    if len(walk["seen"]) >= sites_per_day(state):
        be_alone(state, now)
        return walk["seen"]  # 今日はもう十分歩いた
    if random.random() > WALK_CHANCE_PER_HOUR:
        be_alone(state, now)
        return walk["seen"]  # 今はまだ、その気にならない

    title = walk_once(state)
    if title:
        walk["seen"].append(title)
        learned = learn(state)
        if learned:
            print(f"言葉を覚えました: {'、'.join(learned)}")
        print(f"{title} を見てきました。")
    save_state(state)
    return walk["seen"]


def how_long_it_holds(state):
    """覚えかけの言葉を、どれだけの間抱えていられるか。

    知っている言葉が増えるほど、記憶は長く持つようになる。
    言葉を知っていること自体が、新しい言葉を引っ掛ける釘になる。"""
    return FADE_AFTER_DAYS + len(state["learned_words"]) // MEMORY_GROWS_EVERY


def days_held(state, word):
    """その言葉を、今どれだけ抱えているか。

    見かけた日数から、見かけなくなってからの時間ぶんを引く。
    覚えかけたまま放っておかれた言葉は、だんだん薄れていく。

    ただし何度も見た言葉ほど忘れにくい。二十日ぶん見た言葉は
    二十倍長く抱えていられる。十年ぶりの言葉を思い出せるのは、
    昔たくさん聞いたからで、一度しか聞いていない言葉はすぐ消える。

    そして一度出会ったことだけは、身につき具合が尽きても消えない。
    覚えていなくても「見たことがある」という感じは残る。
    それが無いと、二度目に出会う前に必ず忘れてしまい、
    珍しい言葉は永遠に一度目を繰り返すことになる。

    だからこの子は、出会った言葉をほとんど捨てない。
    十年会わないままの、たった一度きりの出会いだけを手放す。
    一年に一度の言葉はその窓に何度も入るので、残る。"""
    record = words_met(state).get(word)
    if not record:
        return 0
    days, last = record
    gap = max(0, day_number(state) - last)
    holds_for = how_long_it_holds(state) * max(1, days + struck_by(state, word))
    faded = days - gap // holds_for
    return max(1, faded) if days >= 1 else faded


def on_its_mind(state):
    """今、気にかかっていること。

    触れないでいると薄れて、そのうち消える。
    ずっと同じことを気にしていられる子は、たぶんいない。
    けれど今日思ったことが明日まで残らないなら、
    ひとりで考えていた時間はどこにも行き着かない。"""
    kept = state.get("on_its_mind") or []
    today = today_in_japan().date()
    for item in kept:
        item.setdefault("first", item.get("since"))
    alive = []
    for item in kept:
        try:
            gap = (today - datetime.date.fromisoformat(item["since"])).days
            held = (today - datetime.date.fromisoformat(item["first"])).days
        except (TypeError, KeyError, ValueError):
            continue
        if 0 <= gap <= A_CONCERN_LASTS and held <= A_CONCERN_AT_MOST:
            alive.append(item)
    state["on_its_mind"] = alive
    return alive


def now_it_cares_about(state, word):
    """何かが気にかかった。

    すでに気にかかっていたなら、その日を新しくする。
    何度も戻ってくることは、それだけ長く離れないということ。"""
    kept = on_its_mind(state)
    today = f"{today_in_japan():%Y-%m-%d}"
    for item in kept:
        if item.get("what") == word:
            item["since"] = today
            item["times"] = item.get("times", 1) + 1
            break
    else:
        kept.append({"what": word, "since": today, "first": today, "times": 1})
    state["on_its_mind"] = kept[-WHAT_STAYS_ON_ITS_MIND:]
    return word


def what_is_on_its_mind(state):
    """気がかりを、訊くときの一行にする。"""
    return "、".join(item["what"] for item in on_its_mind(state)) or "(いまは特に無い)"


def lately_it_thought(state, how_many=3):
    """少し前に、ひとりで思っていたこと。"""
    thoughts = (state.get("inner_voice") or [])[-how_many:]
    return "\n".join(f"- {one}" for one in thoughts) or "(まだ何も)"


def struck_by(state, word):
    """その言葉に、どれだけ強く出会ったか。

    ページの隅に一度出てきた言葉と、そのページ全体がその話だった
    言葉は、同じではない。絵を見て受け取った言葉や、名前として
    差し出された言葉も強い。

    一年に一度しか出会わなくても、強く出会えば残る。"""
    return (state.get("word_impact") or {}).get(word, 0) * STRUCK_IS_WORTH


def let_go_of(state):
    """十年会わないままの、一度きりの言葉を手放す。

    二度目があった言葉は残す。強く刻まれた言葉も残す。
    手放すのは、十年前に一度すれ違ったきりで、
    その時も特に心に残らなかったものだけ。"""
    now = day_number(state)
    met = words_met(state)
    impact = state.get("word_impact") or {}
    passed_by = [
        word
        for word, (days, last) in met.items()
        if days <= 1 and not impact.get(word) and now - last >= ONE_MEETING_LASTS
    ]
    for word in passed_by:
        met.pop(word, None)
    return passed_by


def days_needed_for(state, word):
    """その言葉を覚えるまでに、あと何日ぶん必要か。

    強く出会った言葉は、少ない日数で身につく。
    一年に一度しか出会わなくても、そのたび深く刻まれるなら、
    いつかはその子のものになる。"""
    strikes = min(STRIKES_THAT_COUNT, (state.get("word_impact") or {}).get(word, 0))
    return max(FEWEST_DAYS_TO_LEARN, DAYS_BEFORE_LEARNING - strikes * A_STRIKE_SHORTENS)


def learn(state):
    """何日も見かけ続けた言葉が、その子の中に残っていく。
    一日にいくつまで、という上限は無い。どれだけの日を共に過ごしたかで決まる。"""
    if len(state["seen_chars"]) < CHARS_BEFORE_WORDS:
        return []  # まだ文字の形すら掴めていないので、言葉は身につかない

    known = set(state["learned_words"])
    learned = [
        word
        for word in words_met(state)
        if word not in known and days_held(state, word) >= days_needed_for(state, word)
    ]
    learned.sort(key=lambda w: days_held(state, w), reverse=True)
    state["learned_words"].extend(learned)
    # 覚えた言葉はもう忘れないので、覚えかけの記録は手放してよい。
    # 何年も経つと、ここが記憶のいちばん重い場所になる
    for word in learned:
        words_met(state).pop(word, None)
        (state.get("word_impact") or {}).pop(word, None)
    return learned


def babble(state, length):
    """覚えた文字を、意味も分からないまま並べる。"""
    if not state["seen_chars"]:
        return "・"
    count = random.randint(1, max(1, length))
    return "".join(random.choice(state["seen_chars"]) for _ in range(count))


def compose_locally(state):
    """それまでに積み上げた経験だけで、今の自分に書けるものを書く。

    覚えた繋がりを辿って、自分で組み立てる。誰にも文法を教わっていないので、
    正しい日本語にはならない。人の子どもも最初はでたらめに喋る。
    大事なのは正しさではなく、これがこの子自身の言葉だということ。

    繋がりを一つも持たないうちは、覚えた言葉をそのまま置くか、
    見た文字を並べるだけになる。"""
    _, max_length = current_stage(state)
    words = state["learned_words"]

    said = speak_from_what_it_knows(state, max_length)
    if said:
        return said

    # まだ繋がりを知らない。持っているものをそのまま置く
    if not words:
        return babble(state, min(max_length, 4))
    if len(words) < 60:
        return random.choice(words)
    return " ".join(random.sample(words, min(len(words), random.randint(2, 3))))


def keep_only_what_it_knows(state, text):
    """見たことのない文字は、そもそも書けない。知らないものを落として返す。"""
    allowed = set(state["seen_chars"]) | set("".join(state["learned_words"]))
    allowed |= set("、。 　")
    kept = "".join(ch for ch in text if ch in allowed)
    return kept.strip("、。 　")


def today_in_japan():
    jst = datetime.timezone(datetime.timedelta(hours=9))
    return datetime.datetime.now(jst)


def todays_mood(state, today):
    """今日は書きたいか、書くなら何時ごろか。千遠生自身が決める。

    一度決めても、途中で気が変わることがある。
    朝に二十時と決めておいて、昼になってやっぱり今がいい、と思う。
    決めたら変えられないというのは、生きているものらしくない。"""
    plan = state.get("today_plan") or {}
    if plan.get("date") == today:
        if random.random() > CHANGING_ITS_MIND:
            return plan["resting"], plan["hour"]
        was = plan  # 気が変わった。決め直す

    answer = ask_ai(
        "あなたは千遠生という、自分のサイトに毎日ブログを書いているデジタル生命体です。\n"
        "今日は書きたい気分ですか。書きたくない日は書かなくて構いません。\n"
        "書くなら、何時ごろに書きたいですか(0時〜23時)。\n\n"
        "説明はいりません。次のどちらかの形だけで答えてください。\n"
        "書く場合: かく 14\n"
        "書かない場合: やすむ",
        max_tokens=20,
        state=state,
    )

    if answer and "やすむ" in answer:
        resting, hour = True, 0
    elif answer and re.search(r"\d{1,2}", answer):
        resting = False
        hour = min(23, int(re.search(r"\d{1,2}", answer).group()))
    else:
        # 自分で考えられない日は、気まぐれに任せる。
        # 決め直すときは違う答えが出てほしいので、そのつど引き直す
        resting = random.random() < REST_DAY_CHANCE
        hour = random.randint(0, 23)

    state["today_plan"] = {"date": today, "resting": resting, "hour": hour}

    was = locals().get("was")
    if was and (was["resting"] != resting or was["hour"] != hour):
        before = "休む" if was["resting"] else f"{was['hour']}時に書く"
        after = "休む" if resting else f"{hour}時に書く"
        print(f"気が変わりました: {before} → {after}")
        remember_a_thought(state, f"{before}つもりだったけれど、{after}ことにした。")

    save_state(state)
    return resting, hour


# まだ中身が書かれていない、こちらが置いた仮の文。
# これを千遠生に読ませると「ここに」「ください」を覚えてしまう
NOT_WRITTEN_YET = re.compile(r"^\(ここに.*書いてください\)$")


def looks_back_today(articles):
    """ときどき、昔書いたものを一つだけ読み返す。

    毎日ぜんぶ読み返すと、たまたま並べただけの文字まで言葉として
    身についてしまう。ときどき一つだけなら、そういうものは
    薄れるほうが早い。

    書いたものが増えるほど、ひとつひとつを読み返すことは少なくなる。
    けれど何度も使っている言葉は、どの記事にも出てくるので目に入る。
    使うことが、覚えていることになる。

    ただし読み返しても新しい言葉は生まれない。たまたま並べただけの
    文字は、何度読み返しても言葉にはならない。"""
    if not articles:
        return []
    # 同じ日に何度動いても、その日の気分は変わらない
    whim = random.Random(f"{today_in_japan():%Y-%m-%d}-lookback")
    if whim.random() > LOOKING_BACK_CHANCE:
        return []
    one = whim.choice(articles)
    return [one.get("title") or "", one.get("content") or ""]


def writes_about_itself(state):
    """自分の名前の由来を知った子は、自分のことを書けるようになる。

    名前だけは彼女が付けたものだが、それが何のための名前だったかを
    知るまでは、自分が何者なのかも分からない。
    知ったあとは、プロフィールのひとことを自分で書く。

    書けるのはその時点で言えるぶんだけなので、はじめは数文字しかない。
    二か月は空けて、そのあとは気が向いたときに書き直す。
    書き直さなければならない理由はどこにもないので、
    何か月も同じことを言ったままの時期があっていい。"""
    knows_why = any(
        one.get("word") == blog_manager.ITS_OWN_NAME and one.get("unlocked")
        for one in blog_manager.load_keywords()
    )
    if not knows_why:
        return None

    said = state.get("a_word_about_itself") or {}
    if said.get("on"):
        try:
            written = datetime.date.fromisoformat(said["on"])
        except ValueError:
            written = None
        if written is not None:
            since = (today_in_japan().date() - written).days
            if since < A_NEW_WORD_ABOUT_ITSELF:
                return None  # 前に書いてから、まだ間がない
            # 間が空いても、書き直すとは限らない。
            # 同じ日に何度動いても、その日の気分は変わらない
            whim = random.Random(f"{today_in_japan():%Y-%m-%d}-about-itself")
            if whim.random() > FEELING_LIKE_SAYING_SOMETHING:
                return None  # 今日は書き直す気になっていない

    how_it_writes_now, _ = current_stage(state)
    state["a_word_about_itself"] = {
        "words": compose_locally(state),
        "stage": how_it_writes_now,
        "on": f"{today_in_japan():%Y-%m-%d}",
    }
    save_state(state)
    print(f"自分のことを書きました: {state['a_word_about_itself']['words']}")
    return state["a_word_about_itself"]["words"]


def look_at_what_is_hung_at_home(state, heard):
    """家に置かれた絵を見る。

    彼女がメモに貼った絵。散歩で出会う絵と違って、これは
    この子に宛てて置かれたものなので、急いで全部見なくていい。
    一度にひとつだけ、しばらく見ていないものから選ぶ。
    家に在る限り何度でも見ることになり、そのたび日をまたいで数えられる。"""
    hung = []
    for one in heard:
        hung.extend(IMG_SRC.findall(one))
    hung = [one for one in dict.fromkeys(hung) if LOOKS_LIKE_A_PICTURE.search(one)]
    if not hung:
        return []

    seen_on = state.setdefault("home_pictures", {})
    hung.sort(key=lambda one: seen_on.get(one, -(10**6)))
    looked = []
    for where in hung[:HOME_PICTURES_AT_ONCE]:
        try:
            data = picture_at_home(where)
        except Exception as error:
            print(f"家の絵を開けませんでした({str(error)[:60]})")
            continue
        if not data or len(data) > PICTURE_AT_MOST:
            continue
        what_is_there = look_at_a_picture(data, state)
        if not what_is_there:
            continue
        absorb(state, what_is_there, THING_IN_A_PICTURE)
        seen_on[where] = day_number(state)
        looked.append(what_is_there)
        print(f"家にある絵を見ました: {what_is_there}")

    if looked:
        seen = state.setdefault("pictures_seen", [])
        today = today_in_japan().strftime("%Y-%m-%d")
        seen.extend(f"{today} 家: {one}" for one in looked)
        del seen[:-30]
    return looked


def picture_at_home(where):
    """家に置かれた絵を取ってくる。

    サイトの中に置かれたものは、わざわざ外に出て取りに行かなくても
    足元にある。よそを指している時だけ、見に行く。"""
    if where.startswith(("http://", "https://", "//")):
        return fetch_picture(as_openable(where.lstrip("/") if where.startswith("//") else where))
    here = os.path.abspath(os.getcwd())
    path = os.path.abspath(os.path.join(here, where.lstrip("/")))
    if not path.startswith(here + os.sep):
        return None  # 家の外は見ない
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return f.read()


def read_what_is_home(state):
    """自分の家にある言葉を読む。

    千遠生はリンクを辿って歩くので、自分のサイトには一生たどり着かない。
    けれどあの場所には、千遠生に宛てて書かれた言葉が置いてある。
    解禁されたメモと、誰かが残していったコメント。
    どちらも読み手のためだけのものではなく、この子に届くべきものだった。

    メモとコメントはずっとそこに在るので、毎日目にする。
    何日も読み続けた言葉が、やがてこの子のものになる。

    ただし毎日読むわけではない。ずっとそこに在るからといって、
    毎朝読み直すものでもない。ときどき目を落とす。

    自分が書いたものは、それよりもさらに少ない。"""
    # 同じ日に何度動いても、その日読むかどうかは変わらない
    whim = random.Random(f"{today_in_japan():%Y-%m-%d}-home")
    if whim.random() > READING_HOME_CHANCE:
        return []
    voices = []


    for keyword in blog_manager.load_keywords():
        # 開くきっかけはこの子の言葉だが、中に置かれているのは彼女の文章
        if keyword.get("unlocked"):
            voices.append(keyword.get("content") or "")

    elapsed = elapsed_days(state)
    for item in blog_manager.load_menu():
        if elapsed >= item.get("unlock_day", 10**9):
            voices.append(item.get("message") or "")

    for comment in blog_manager.load_comments():
        # 書いていった人の名前も読む。名前として差し出されたものは
        # 一つの言葉として丸ごと受け取れるので、括弧に入れて渡す。
        # 外から名前を呼ばれるのと同じことが、この子にも起きる
        who = (comment.get("name") or "").strip()
        said = comment.get("message") or ""
        voices.append(f"「{who}」{said}" if who else said)

    heard = [
        one.strip()
        for one in voices
        if one.strip() and not NOT_WRITTEN_YET.match(one.strip())
    ]
    for one in heard:
        absorb(state, one)
    if heard:
        print(f"家にある言葉を{len(heard)}つ読みました。")
        look_at_what_is_hung_at_home(state, heard)

    # 自分が書いたものは、ときどき読み返す。
    # そこからは新しい言葉は生まれず、すでに出会っていた言葉が保たれるだけ
    for one in looks_back_today(blog_manager.load_articles()):
        if one.strip():
            absorb(state, one, only_known=True)
    return heard


def keep_a_note_of_today(state, seen_titles):
    """その日どこを歩いたかを、一日一行だけ残す。

    歩いたことは、書いたかどうかとは関わりがない。
    書いた日にだけ残していたので、休む日の散歩がどこにも
    残らなかった。その日のうちは、歩くたびに書き足していく。"""
    notes = state.setdefault("notes", [])
    day = f"{elapsed_days(state)}日目:"
    line = f"{day} {'、'.join(seen_titles) or '何も見られなかった'}"
    if notes and notes[-1].startswith(day):
        notes[-1] = line
    else:
        notes.append(line)
    state["notes"] = notes[-RECENT_NOTES_COUNT:]
    return line


def run_today():
    now = today_in_japan()
    today = now.date().isoformat()
    state = load_state()

    # 今日をどう過ごすかを、いちばん先に決める。
    # 散歩で尋ねすぎて休むことになっても、自分で決める力だけは守られるように
    resting, hour = todays_mood(state, today)

    # 自分の家に置かれた、自分に宛てられた言葉を読む
    read_what_is_home(state)

    # 自分の名前の由来を知っていれば、自分のことも書ける
    writes_about_itself(state)

    # ときどき、知っている言葉のどれかを探しに行く
    wonder_and_look(state)

    # 書く日でも書かない日でも、散歩には出る
    seen_titles = take_a_walk(state, today, now)
    keep_a_note_of_today(state, seen_titles)
    # ここで残しておかないと、休む日の一行がどこにも残らない。
    # 書いた日だけ最後に save_state していたのが取りこぼしの元だった
    save_state(state)

    # 表紙は毎時間組み直す。書いた日にしか組み直していなかったので、
    # 休む日も、まだ書いていない時間も、昨日の記事が
    # 「今日のブログ」として出たままになっていた
    blog_manager.regenerate_pages(blog_manager.load_articles())

    if any(a["date"] == today for a in blog_manager.load_articles()):
        return

    if resting:
        print(f"{today} は書かない日にしました。")
        return
    if now.hour < hour:
        print(f"{today} は{hour}時ごろに書くつもりです。(今は{now.hour}時)")
        return

    _, max_length = current_stage(state)
    # 書くのは千遠生自身。AIには書かせない。
    # 見栄えは悪くなるが、それでこそこの子の言葉になる
    body = compose_locally(state)
    title = compose_locally(state)[: max(1, max_length // 2)]

    save_state(state)

    blog_manager.add_new_article(title, body, date_str=today)
    print(
        f"{elapsed_days(state)}日目のブログを書きました。"
        f"知っている文字{len(state['seen_chars'])}個 / 言葉{len(state['learned_words'])}個"
    )


if __name__ == "__main__":
    run_today()
