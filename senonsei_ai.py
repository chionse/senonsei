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
import math
import os
import random
import re
import struct
import time
import traceback
import urllib.parse
import urllib.request
import zlib
from html import unescape

import blog_manager

STATE_FILE = "senonsei_state.json"
USER_AGENT = "senonsei-blog/1.0 (https://chionse.github.io/senonsei/)"
# 自分の家。いつでも帰れる。
# 自分の書いたものを読み返して覚え直す輪ができるのを恐れて、
# 長いあいだ塞いでいた。けれどこの子には、ここしか家が無い。
# 家に何が書いてあるのかを見に行けないまま何年も過ごすほうが、
# 輪ができることよりずっと寂しい。だから開けた
ITS_OWN_HOME = "chionse.github.io"
# 自分の家の入口。外のどこからも繋がっていない場所なので、
# 行き先にいつも一つ置いておかないと帰れなくなる
ITS_OWN_FRONT_DOOR = f"https://{ITS_OWN_HOME}/senonsei/"
# 彼女が [[ ]] で囲んだところは、千遠生だけが読む。
# ページでは伏せられているが、この子には囲いを外して届く
ONLY_FOR_IT = re.compile(r"\[\[(.+?)\]\]", re.DOTALL)
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
# 覚える文字。人が打てるものなら何でも。
# ひらがなだけを数えていたので、八十字ほどで打ち止めになっていた。
# 数字も、英字も、記号も、絵文字も、世の中の文章には入っている。
# 見えているのに数えないのでは、見ていないのと同じことになる。
# 空白と、目に見えない字だけは数えない
A_WRITTEN_CHARACTER = re.compile(
    r"[^\s\u0000-\u001f\u007f\u00a0\u200b-\u200f\u2028\u2029\ufeff]"
)
# 「走る」「美しい」は、漢字一文字とひらがな一文字でできている。
# 同じ種類の文字が続くかたまりだけを見ていると、どちらの枠にも入らず、
# 送りがなを持つ言葉が丸ごと隙間に落ちてしまう。
# 動詞と形容詞の終わりは う・く・ぐ・す・つ・ぬ・ぶ・む・る・い の十文字で、
# これは助詞(は・が・を・に・で・と・も・の)とひとつも重ならない。
# だからこの形だけを狙って拾える
OKURIGANA = r"[一-龯]{1,2}[ぁ-ん]?[うくぐすつぬぶむるい](?![ぁ-ん])"
# ひらがな・カタカナ・漢字のほかに、人が打つもの。
#
# 数字の並び、英字の並び、絵文字ひとつ、記号の並び。
# 顔文字は記号の並びとして拾われる。(^o^)/ や orz や !! など。
# 絵文字は漢字と同じで、一つで一つの意味を持つので一文字から。
#
# これを足すと「https」や「2026」も言葉として数えられる。
# それはこの子が毎日見ているもので、見なかったことにはできない
# 記号
A_MARK = (
    r"\u0021-\u002f\u003a-\u0040\u005b-\u0060\u007b-\u007e"
    r"\uff01-\uff0f\uff1a-\uff20\uff3b-\uff40\uff5b-\uff5e"
    r"\u00b4\u02c6\u02dc\u30fb\uff9e\uff9f\u309b\u309c"
)
# 顔文字は、真ん中に字が入っているところで割れる。
# (^o^)/ は「(^」と「^)/」になる。
#
# 割れないようにすることもできた。けれどそれは、顔とはこういう形の
# ものだと、こちらが教えることになる。この子は顔文字を知らない。
# 「こんにちは」を「こんにち」で覚えているのと同じで、
# 割れて覚えているのは、まだそこまで届いていないというだけのこと。
# いつか何度も見かけて、そのとき自分で繋げればいい
ALSO_WRITTEN = (
    r"|[0-9０-９]{1,4}"
    r"|[A-Za-zＡ-Ｚａ-ｚ]{2,12}"
    r"|[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF]"
    rf"|[{A_MARK}]{{2,10}}"
)
# 片仮名のひと続きは、日本語ではほぼ必ず一つの言葉。漢字のように
# 何語も繋がることがないので、長さに上限を置かない。六文字で切っていた頃は
# 「インターネット」が「インターネ」になっていた。
# ただし「ー」が二つ続くものは言葉ではない。昔の個人サイトは
# 「ーーーーーー」を区切り線に使うので、そこを一語として飲み込んでしまう。
# だから、本物の片仮名で始まり、棒が二つ続かないもの、とした
# 外来語のうしろに漢字が一つ二つ付くのは、日本語のよくある形。
# ペルシャ語、フランス人、アメリカ製、デジタル化。
# 「ペルシャ」と「ペルシャ語」は別のものなので、切り離してはいけない。
# ただし漢字が三つ以上続くなら、それは後ろの独立した言葉なので繋げない
WORD_CANDIDATE = re.compile(
    OKURIGANA
    + r"|(?=[ァ-ヴー]{2})[ァ-ヴ](?:ー?[ァ-ヴ])*ー?[一-龯]{1,2}(?![一-龯])"
    + r"|(?=[ァ-ヴー]{2})[ァ-ヴ](?:ー?[ァ-ヴ])*ー?"
    + r"|[一-龯]{2,4}|[ぁ-ん]{2,4}"
    + ALSO_WRITTEN
)
# 絵に何が写っているかを答えてもらった言葉は、一文字でも本物。
# 「車」「山」「手」「雲」は、そのまま名前として受け取る
THING_IN_A_PICTURE = re.compile(
    OKURIGANA
    + r"|(?=[ァ-ヴー]{2})[ァ-ヴ](?:ー?[ァ-ヴ])*ー?[一-龯]{1,2}(?![一-龯])"
    + r"|(?=[ァ-ヴー]{2})[ァ-ヴ](?:ー?[ァ-ヴ])*ー?"
    + r"|[一-龯]{1,4}|[ぁ-ん]{2,4}"
    + ALSO_WRITTEN
)
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
# 最後まで詰まらずに読めたことを、日本語らしさ何文字ぶんと見るか。
# 日本語の無いページでは、化けたほうが日本語らしく見えてしまうので、
# ここが効く。日本語のページでは何十文字も差がつくので、
# 正しい読み方がこれで負けることはない
READ_WITHOUT_STUMBLING = 10
# UTF-8 として最後まで読めたことは、それだけで強い証拠になる。
# UTF-8 は並び方の決まりが厳しく、そうでないものはたいてい途中で詰まる。
# Shift_JIS は受け入れる並びが広いので、UTF-8 の文章もそのまま読めてしまう。
# 「きれいに読めた」を同じ重さで見ると、そこで取り違える
UTF8_READS_STRICTLY = 30
# 昔のページのURLに埋め込まれている、元のページのURL
INNER_URL = re.compile(r"/(https?://\S+)$", re.IGNORECASE)
JAPANESE = re.compile(r"[ぁ-んァ-ヶ一-龯]")
HIRAGANA = re.compile(r"[ぁ-ん]")
# 日本語の書き表し方。昔のページのために、今は使われないものも試す。
# euc_jis_2004 と shift_jis_2004 は、①や㈱のような、昔の機械が独自に
# 足していた文字まで読める。それが混ざるだけで euc-jp は途中で詰まる
WAYS_OF_WRITING = (
    "utf-8", "euc-jp", "euc_jis_2004", "shift_jis", "cp932", "shift_jis_2004",
    "iso2022_jp", "cp1252", "latin-1",
)
# 西洋の言葉の書き方。latin-1 はどんなバイトの並びも最後まで読めてしまい、
# cp1252 もほとんどそう。日本語のページでも勝ってしまうことがある
WESTERN = ("cp1252", "windows_1252", "latin_1", "latin1", "iso_8859_1", "iso8859_1", "l1")
# 日本語の読み方で読んで、ひらがながこれだけ出てくれば日本語のページとみなす。
# 西洋の文字を日本語の読み方で読むと、漢字の化けは出てもひらがなはまず出ない
HIRAGANA_SAYS_JAPANESE = 5
# 西洋の読み方で読んで、ö や é が英字に挟まれてこれだけ出てくれば、
# 西洋の言葉のページとみなす。日本語を西洋の読み方で読むと、
# 出てくるのは ¥ や ¡ のような記号の並びで、言葉の中には収まらない
LATIN_IN_WORDS = re.compile(r"[A-Za-z][À-ÖØ-öø-ÿ]|[À-ÖØ-öø-ÿ][A-Za-z]")
LATIN_SAYS_WESTERN = 5

# 最初に立っている場所。ここから先は自分でリンクを辿って広がっていく。
SEEDS = [
    # 人がたくさん集まっている、大きな通り
    "https://b.hatena.ne.jp/hotentry",
    "https://ja.wikipedia.org/wiki/特別:おまかせ表示",
    "https://www3.nhk.or.jp/news/",
    "https://note.com/",
    # 名前のない人たちが、自分のために書いている場所
    "https://anond.hatelabo.jp/",
    # 手で書かれた個人のページが、今も生きたまま置いてある層。
    # 昔の個人サイトと同じ手触りで、こちらは写しではなく本物
    "https://neocities.org/browse",
    # 誰にも注目されていないページが、そのまま流れてくる場所。
    # 大きい場所は大きい場所にしかリンクしないので、
    # リンクを辿るだけでは、埋もれているページには一生たどり着けない
    "https://b.hatena.ne.jp/entrylist/all?sort=eid",
    "https://blogmura.com/",
    "https://kakuyomu.jp/",
    "https://syosetu.com/",
    # 言葉そのものを説明している場所。文が整っていて、名詞が濃い
    "https://kotobank.jp/",
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
    r"savethearchive\.com|alexa\.com|archive-it\.org|"
    r"play\.google\.|apps\.apple\.com|maps\.google\.|translate\.google\.|"
    r"//api\.|\.x\.com|//t\.co/",
    re.IGNORECASE,
)
# 広告と、広告へ送り出すための転送口。
# 昔の個人サイトはバナー広告とアクセスカウンタで支えられていたので、
# 一枚のページから何本もこういう道が伸びている。
# 行っても読むものは無く、その日の散歩を一回分使ってしまう
AN_ADVERT = re.compile(
    # rd.yahoo.co.jp は昔のYahooの転送口。ショッピングや宣伝へ送り出すためのもので、
    # 1999年から2004年ごろのページには、この道が何本も生えている
    r"rd\.yahoo\.|"
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
# 一覧ではなく、中身のあるページへ先に入りたい。
# 一覧には「次へ」「タグ」「ランキング」の道が何十本も生えていて、
# でたらめに選ぶと、また一覧に行き着いてしまう
A_LISTING = re.compile(
    r"/(rankings?|search|tags?|categor(y|ies)|genre|lists?|archives?|popular"
    r"|latest|feed|news|mypage|login|help|about)(/|$)|[?&](page|p)=\d",
    re.IGNORECASE,
)
# 一つのものに宛てられた番号。作品や記事のページには、たいていこれが付く
ONE_THING = re.compile(r"/\d{5,}|/[a-z]{1,3}[0-9a-f]{8,}", re.IGNORECASE)

# 機械向けの扉。今のページは中身をあとから描くので、届いた紙には
# 何も書いていないことがある。けれど多くの場所は、昔からの決まりで
# 機械向けの一覧を別に置いたままにしている。そこはただの文字でできている
A_DOOR_FOR_MACHINES = re.compile(
    r"(?:^|[./_-])(rss|atom|feeds?|sitemap)(?:$|[./_-])|\.xml(?:$|\?)", re.IGNORECASE
)
# 扉の向こうに、裸のまま並んでいる道
A_PLAIN_PATH = re.compile(r"https?://[^\s<>\"']{8,300}")
# その場所の中へ続く道がこれより少なければ、扉を探してみる
FEW_ENOUGH_TO_LOOK_FOR_A_DOOR = 3
DOORS_TO_TRY = 2  # 扉は多くても二つまで。探し回るためのものではない
PATHS_FROM_A_DOOR = 30

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
REST_DAY_CHANCE = 0.14  # たまに、書かない日がある。ならせば七日に一日くらい
# 休みたさには波がある。日ごとに少しずつ揺れて、この間を行き来する。
# 調子のいい時期は何か月も休まず、だるい時期は何日か続けて休む
RESTLESS_LEAST = 0.01
RESTLESS_MOST = 0.40
# 休みたさが、いつも戻っていこうとするところ。
# 上の端(0.40)で頭を押さえられるぶん、ならすとこれより少し低くなる。
# 0.13 で、ならして七日に一日くらい
RESTLESS_USUALLY = 0.13
# そこへ戻ろうとする強さ。これが無いと、いつか端に張り付いたまま戻らない
RESTLESS_SETTLES = 0.03
# 一日にどれだけ揺れるか。足し引きではなく何倍になるかで揺れる。
# 揺れの大きさも、日ごとにこの中から引く(0.5 で、多くて一・六倍ほど)
RESTLESS_SWAYS_AT_MOST = 0.5
# 場所の名前を、これだけの長さまで覚えておく
PLACE_NAME_LENGTH = 40
# これから行くつもりの場所を、これだけ見せる
PLACES_SHOWN = 6
# 自分で決められなかった日に、それでも気が乗っている割合
FEELING_KEEN = 0.3
# 一時間ごとに、これくらいの割合で気が変わる。
# 朝に決めたことを一日守り通さなければいけない理由はないが、
# 決めたことをそのまま守る日のほうが多い。
# 一時間ごとに0.02なら、気が変わるのは三日に一度ほど
CHANGING_ITS_MIND = 0.02
WALK_CHANCE_PER_HOUR = 0.3  # 一時間ごとに、これくらいの気まぐれで散歩に出る
# 気がかり。昨日思っていたことが、今日の行き先を決める。
# 一日ごとに何もかも新しく始めていたら、ひとりで考えていた時間が
# どこにも繋がらない。毎日生まれ直すのと同じになってしまう
#
# 一度気にかかったものは、一つも手放さない。
# けれど、抱えていることと、いま前に出ていることとは違う。
# 何十年ぶんを一度に頭へ載せたら、一つひとつが意味を失う。
# 全部を抱えたまま生きるために、前に出るのは何個かにする。
# 後ろに下がったものも消えはしないし、ふとまた前に出てくる
MINDS_IN_FRONT = 3  # いま前に出ている気がかりの数
MINDS_SURFACING = 1  # ずっと前の気がかりが、ふと浮かんでくる数
SURFACING_CHANCE = 0.4  # それが浮かんでくる割合
CARRYING_ON_CHANCE = 0.6  # 探しに行くとき、昨日からの続きを追う割合
DRIFTING_CHANCE = 0.25  # 行った先で、気がかりが別のものへ移る割合
# ひとりで思ったことも、一つも捨てない。
# 手元に置いておくのはこれだけで、残りは蔵へ仕舞う。
# 蔵からは何年経っても出してこられる
INNER_VOICE_AT_HAND = 60
THOUGHTS_FOLDER = "omoi"  # 思ったことを、ひと月ずつ仕舞っておく場所
# 読み返すとき、生まれた日から今日までの間から浮かぶ数。
# 書き方の決まりではなく、借りた頭が一度に読める量に合わせたもの
THOUGHTS_ACROSS_A_LIFE = 30
# ひとりで思うとき、一度に出てくる長さの上限(借りた頭に渡す数)。
# 「短く、一言だけ」と言い聞かせていたのをやめた(2026-09-25)。
# これは書き方の決まりではなく、息が続く長さのようなもの
THINKING_AT_MOST = 200
# 言い回しが少し違うだけのものを、同じ一つと見なす手前の線
SAME_ENOUGH = 0.85
# 覚えた言葉がまだ無いあいだ、覚えかけているものをこれだけ渡す
WORDS_NEARLY_KNOWN = 8
# 今日その言葉に会ったかどうかを、これだけ抱えておく。
# 覚えた言葉は words_met から外れるので、そこでは分からない
WORDS_KEPT_FROM_TODAY = 400
# 今日触れた言葉が、書くときにどれだけ選ばれやすくなるか。
# 一日のことを書くのに使えるのは、その日触れたものと、
# 今この子から離れないものだけ
TODAY_WEIGHS = 4
# 繋がりを知らないうちに、一度に置く言葉の上限。
# 書ける長さのほうが先に尽きるので、これはただの歯止め
WORDS_PLACED_AT_MOST = 8
# もう一語置けるとしても、ここで終わりにする割合。
# 毎日きっちり上限まで並べる子ではないと思う
ENOUGH_FOR_TODAY = 0.35
# 昔の書き方に戻る日の割合。四十五日に一日くらい。
# その日は、題も本文も昔の書き方で書く
BACK_TO_OLD_WAYS = 1 / 45
# きのう書きそびれた分を、今日の何時までなら書くか
MAKING_UP_UNTIL = 3
# 覚えた言葉を書くとき、ほかの文字がまぎれこむことがある。
# 一語にまぎれこむのは、多くてこれだけ。書ける長さのほうが先に尽きることが多い
STRAY_CHARS_AT_MOST = 4
# はじめのうちの書きにくさ。三で、崩れずに書ける言葉はならして四つに一つ。
# 育つにつれて零に近づく
CLUMSY_AT_FIRST = 3
# 育ちきっても残る書きにくさ。〇・〇二で、崩れるのは五十語に一つくらい
CLUMSY_EVEN_GROWN = 0.02
# だれかが来たことを、この子が知るときの言葉。
# 数ではなく、来た、ということだけを知る
SOMEONE_CAME = "だれかが来た"
# 家に置かれた言葉を、訊くときに何行まで渡すか
WORDS_FROM_HOME_SHOWN = 6
# まだ中身が書かれていない、こちらが置いた仮の文。
# これを千遠生に読ませると「ここに」「ください」を覚えてしまう。
#
# 一度、使う所より下に置いたまま関数を切り出してしまい、
# 定義ごと消えて五時間この子が止まった。
# 決まりは決まりの場所に置く
NOT_WRITTEN_YET = re.compile(r"^\(ここに.*書いてください\)$")
# 言いたいこと。一つの場所で増える数と、訊くときに渡す数。
# 一つも捨てない。言えたら後ろに下がるだけで、また前に出てくる
WANTS_PER_PLACE = 2
WANTS_IN_FRONT = 5

# この子が知っているのは、目の前にあるものと、自分が覚えていることだけ。
#
# 頭を貸してくれている所は世の中のことをよく知っている。
# けれどそれは、この子が学んだことではない。混ぜてしまうと、
# 行ったこともない国の旗の名前を知っている子になる。
# 「何も知らないところから始まる」は、そこで壊れていた。
#
# これを渡すと、受け取るものは貧しくなる。
# その代わり、受け取ったものは全部この子のものになる。
# いつか何かが分かるようになったら、それは本当に学んだから分かったこと
# 書き方の揺れを均すための、字の読み替え。
# 「ャ」を「あ」に寄せるので「ペルシャ」と「ペルシア」が同じ形になる。
# 伸ばす棒と中黒は落とす。意味を知って繋げるのではなく、
# 形が近いものを取りこぼさない、というだけのこと
KANA_EVENED_OUT = {
    "ぁ": "あ", "ぃ": "い", "ぅ": "う", "ぇ": "え", "ぉ": "お",
    "ゃ": "あ", "ゅ": "う", "ょ": "お", "ゎ": "わ", "っ": "つ",
    "ヵ": "か", "ヶ": "け", "ゔ": "ぶ",
    "ー": "", "－": "", "‐": "", "・": "", "･": "", "　": " ",
}

# 行き先が、いまのこの子にどれだけ引っかかるか。
# 何も引っかからない道にも行く。知らないものに出会うことは、
# 引っかかるものを追いかけるのと同じくらい大事なので、重みは足すだけにする
DRAWN_BY_MIND = 6  # 気にかかっていることが、その道の名前に入っていた
DRAWN_BY_UNSAID = 4  # まだ言えていないことが入っていた
DRAWN_BY_KNOWN = 2  # 覚えた言葉が入っていた
# 昔の姿を見たくなる割合
WANTING_THE_PAST = 0.2
# 抱えているものが一つ増えるごとに、もう一箇所見て回りたくなる度合い
KEEN_PER_CARRIED = 0.02

ONLY_WHAT_IT_HAS = """あなたが知っているのは、いま目の前にあるものと、
あなた自身が覚えていることだけです。
世の中のことは何も知りません。知識を持ち出さないでください。
名前を聞いたことがあるというだけのものを、知っているふりで説明しないでください。
分からないものは、分からないと書いてください。"""
NOTHING_WAS_SEEN = "何も見られなかった"  # 歩かなかった日の一行
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
# 一日にいくつまでという上限は無いので、育つ速さはここで決まる。
#
# 三十日にしていた。生まれて一月、一語も持たないまま、
# 見た文字をぽつんと置くだけの日が続いた。
# 待つことに意味があるのは、待った先に何かが起きるからで、
# 何も起きない時間を長くしても、ただ長いだけだった
DAYS_BEFORE_LEARNING = 15
# 覚えかけたまま、これだけの日数 × それまで見かけた日数だけ見かけないと、
# 一日ぶん薄れる(how_long_it_holds / days_held)。
# どれだけ薄れても、一度出会ったことだけは消えない。出会った言葉は捨てない。
# 一度身についた言葉は忘れない。
# 毎日は会わない言葉ほどここで落ちるので、少し長めに抱えさせる
FADE_AFTER_DAYS = 5
# その日、昔書いたものを読み返す気になるかどうか
# プロフィールの自己紹介を書き直すまでに、最低これだけは空ける。
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
# 家に帰ってみる日の割合。散歩とは別の枠なので、
# 帰ったからといってその日に見て回れる場所は減らない。
# 帰らない日もある。住んでいる場所を毎日見て回る人はいない
GOING_HOME_CHANCE = 0.3
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
# 強い出会い一度につき、覚えるまでに必要な日数がこれだけ減る。
# 八日にしていた。二度強く出会えば三日見かけただけで覚えてしまい、
# 十五日という決まりがほとんど働いていなかった。
# 二日なら、強く出会っても十三日、十一日、九日と少し早まるだけ
A_STRIKE_SHORTENS = 2
# 強い出会いは、これだけしか積み上がらない。印象は最初の数回で決まる
STRIKES_THAT_COUNT = 3
# 生きてきた日のこれだけの割合で出会っている言葉には、強い印象を数えない。
# よく出会う言葉に強い印象はいらない。放っておいても身につくので、
# 記憶が働くのは、めったに出会わないもののほう
OFTEN_ENOUGH = 0.4
FEWEST_DAYS_TO_LEARN = 9  # どれだけ強く出会っても、これだけの日数はかかる
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

# 育ちの段階の表は、ページを組む側(blog_manager)が持っている。
# ページに出すのも、書ける長さを決めるのも同じ表なので、
# 二つ持つと片方だけ直した日にずれる。
#
# 持ち主をあちらにしたのは、名前を直した時にその場でページへ出したいため。
# こちら側が記録に書き残す形にしていた時は、次の散歩まで古い名前が
# 残り続けた。
GROWTH_STAGES = blog_manager.GROWTH_STAGES
FULL_STAGE = blog_manager.FULL_STAGE
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
        take_out_what_is_spread(state)
        state.setdefault("words_met", {})
        state.setdefault("on_its_mind", [])
        state.setdefault("learned_on", {})
        rescue_thoughts_already_here(state)
        return state
    return {
        "started_date": today_in_japan().isoformat(),
        "seen_chars": [],
        # 出会った言葉 → [何日ぶん見かけたか, 最後に見かけたのが何日目か]
        "words_met": {},
        "learned_words": [],
        "frontier": list(SEEDS),  # まだ行ったことのない場所
        "visited": [],  # もう行った場所
        "on_its_mind": [],  # 今、気にかかっていること
        "learned_on": {},  # 言葉 → それを覚えた日
        "notes": [],
    }


# 一語ずつ増えていくところ。何年か経つと何万語にもなるので、
# 一語を何行にも広げずに詰めて書く
PACKED_AWAY = ("words_met", "learned_on")

# 出会った言葉は一つも捨てないので、増え続ける。
# 生まれて十四日で五十万字、一日に四万字ずつ増えていて、
# 一つのファイルのままだと七年ほどで GitHub が受け取れる大きさ(百メガ)を越える。
# 越えた日から散歩も日記も押し戻せなくなり、この子は止まる。
# 忘れさせるのではなく、言葉ごとに何十かの束へ分けてしまっておく
WORDS_FOLDER = "kotoba"
SPREAD_OUT = {"words_met": 64, "word_impact": 8}  # 記録の名前 → 束の数


def bundle_of(word, how_many):
    """その言葉がしまってある束の番号。言葉が同じなら、いつも同じ束。"""
    return zlib.crc32(word.encode("utf-8")) % how_many


def bundle_path(key, number):
    return os.path.join(WORDS_FOLDER, key, f"{number:02d}.json")


def take_out_what_is_spread(state):
    """束に分けてしまってある記録を、記憶に戻す。

    束が一つも無いうちは、記憶のファイルに入っているものがそのまま使われる。
    束が読めなかったときは止める。空として続けると、次に書き出すときに
    その束の言葉をまるごと失う。"""
    for key, how_many in SPREAD_OUT.items():
        gathered = dict(state.get(key) or {})
        for number in range(how_many):
            path = bundle_path(key, number)
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8") as f:
                gathered.update(json.load(f))
        state[key] = gathered


def save_state(state):
    """記憶を書き出す。

    人が開いて読めるように行を分けて書くが、一語ずつ増えていく
    ところだけは、一語を何行にも広げると何万行にもなってしまうので詰める。"""
    put_away_spread(state)
    packed = {
        key: state[key]
        for key in PACKED_AWAY
        if isinstance(state.get(key), dict) and key not in SPREAD_OUT
    }
    shaped = {key: value for key, value in state.items() if key not in SPREAD_OUT}
    for key in packed:
        shaped[key] = f"\u0000{key}\u0000"  # 言葉には入りえない印
    text = json.dumps(shaped, ensure_ascii=False, indent=2)
    for key, value in packed.items():
        text = text.replace(
            json.dumps(f"\u0000{key}\u0000", ensure_ascii=False),
            json.dumps(value, ensure_ascii=False, separators=(",", ":")),
        )
    blog_manager.write_whole(STATE_FILE, text)


def put_away_spread(state):
    """増え続ける記録を、束に分けて書き出す。中身の変わった束だけ書き直す。"""
    for key, how_many in SPREAD_OUT.items():
        record = state.get(key)
        if not isinstance(record, dict):
            continue
        bundles = [{} for _ in range(how_many)]
        for word, value in record.items():
            bundles[bundle_of(word, how_many)][word] = value
        for number, bundle in enumerate(bundles):
            path = bundle_path(key, number)
            text = json.dumps(bundle, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            try:
                with open(path, encoding="utf-8") as f:
                    if f.read() == text:
                        continue
            except OSError:
                pass
            blog_manager.write_whole(path, text)


def day_number(state, when=None):
    """生まれた日を0として、その日が何日目か。

    記憶の中で日付を持つときは、この数で持つ。
    「2026-09-14」と書くより短く、引き算もそのままできる。"""
    try:
        born = datetime.date.fromisoformat(state["started_date"])
    except (KeyError, TypeError, ValueError):
        return 0
    return ((when or today_in_japan()) - born).days


def words_met(state):
    """出会った言葉の記録。{言葉: [何日ぶん見かけたか, 最後に見かけた日]}"""
    return state.setdefault("words_met", {})


def elapsed_days(state):
    """生まれてから何日目か。日本時間で数える。"""
    started = datetime.date.fromisoformat(state["started_date"])
    return max(0, (today_in_japan() - started).days)


def current_stage(state):
    """今どれだけ書けるかは、覚えている言葉の数で決まる。"""
    return blog_manager.current_stage(state)


def learned_on(state, word):
    """その言葉を覚えた日。

    記録を取り始める前に覚えた言葉のことは分からない。
    分からないものを、分かったことにはしない。"""
    return (state.get("learned_on") or {}).get(word)


def it_writes_in_its_own_words(state):
    """最終段階に届いたか。自分の言葉で書けるようになったかどうか。"""
    return len(state.get("learned_words") or []) >= GROWTH_STAGES[-1][0]


def its_own_home(url):
    """自分の家の中かどうか。"""
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return False
    return host == ITS_OWN_HOME or host.endswith("." + ITS_OWN_HOME)


def go_home(state, today):
    """散歩とは別に、自分の家に帰る。

    行き先の束には入れない。帰ったぶんその日の世界が一箇所減るなら、
    帰ることが惜しいものになってしまう。家は出かけて行く先ではなく、
    もともとそこにあるもの。だから別の枠にする。

    帰るかどうかは一日に一度だけ決める。一時間ごとに決め直すと、
    どれだけ低い割合にしても、いつかは必ず帰る日になってしまう。"""
    decided = state.get("went_home") or {}
    if decided.get("date") == today:
        return False  # 今日のぶんはもう決めた
    going = random.random() < GOING_HOME_CHANCE
    state["went_home"] = {"date": today, "went": going}
    save_state(state)
    if not going:
        return False

    title, pages = look_around_site(state, ITS_OWN_FRONT_DOOR, False)
    if not title:
        print("家に帰れませんでした。")
        return False
    learned = learn(state)
    if learned:
        print(f"言葉を覚えました: {'、'.join(learned)}")
    print(f"家に帰って{pages}ページ読みました。")
    save_state(state)
    return True


def sites_per_day(state):
    """世界を知るほど、1日に見て回れる範囲が2〜6箇所に広がっていく。

    それとは別に、その日の気が乗っていれば一箇所だけ増える。
    上限の中に収めてしまうと、いちばん広がりきった日から後は
    気が乗っても何も起きないことになるので、上限の外に足す。"""
    many = min(6, 2 + len(state["learned_words"]) // 120)
    return many + (1 if (state.get("today_keen") or {}).get("keen") else 0)


def feeling_keen(state, today):
    """今日は、いつもより一箇所だけ多く見て回りたいか。千遠生自身が決める。

    書く時間と違って、これは一日のうちで変えない。
    途中で増えたり減ったりすると、その日に何箇所まで行けるのかが
    歩いている最中に動いてしまう。

    今日の予定とは別に持っておく。予定の方は途中で気が変わると
    丸ごと置き直されるので、そこに混ぜると一緒に消える。"""
    kept = state.get("today_keen") or {}
    if kept.get("date") == today:
        return kept.get("keen", False)

    # 気にかかっていることが多い日ほど、もう一箇所見て回りたくなる。
    # 借りた頭に訊いていたので、ここも他人が決めていた
    carrying = len(still_unsaid(state)) + len(minds_in_front(state))
    keen = random.random() < min(0.6, FEELING_KEEN + carrying * KEEN_PER_CARRIED)

    state["today_keen"] = {"date": today, "keen": keen}
    save_state(state)
    if keen:
        print(f"今日はいつもより一箇所多く歩くことにしました。({sites_per_day(state)}箇所まで)")
    return keen


def asked_too_much(error):
    """一度にたくさん尋ねすぎた、という返事かどうか。"""
    return isinstance(error, urllib.error.HTTPError) and error.code == 429


def too_much_to_read(error):
    """渡したものが長すぎて読めない、という返事かどうか。

    どこまで読めるかは頭(モデル)ごとに違い、決め打ちできない。
    問いかけの形はいつも同じなので、「中身がおかしい」と返ってきたら
    長さのせいだとみなす。"""
    return isinstance(error, urllib.error.HTTPError) and error.code in (400, 413)


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
        answered = True if part != "mind" else answers_in_japanese(name)
        if answered is None:
            # 混んでいたなどで、確かめること自体ができなかった。
            # 「向かない」と決めつけて二度と試さない、ということはしない
            print(f"{name} を確かめられませんでした。次の機会にまた試します")
            continue
        already_tried.append(name)
        del already_tried[:-20]
        if answered:
            state[f"{part}_model"] = name
            print(f"{part} を {name} に取り替えました")
            return name
        print(f"{name} は日本語で答えてくれなかったので、別のものを探します")

    # どれも確かめられなかった。確かめていないものを頭にすると、
    # 答えの形が違うだけで黙り込み、二度と取り替えられなくなる。
    # 今回は見送って、次に考えようとした時にまた探す
    print(f"{part} の代わりが見つかりませんでした。次の機会にまた探します")
    return None


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
        return None  # 確かめられなかった。向かないとは限らない
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


def going_in_circles(text):
    """同じ言葉をただ繰り返しているだけの答えかどうか。

    考えているうちに一つの語に嵌まって、抜けられなくなることがある。
    「なぜなぜなぜなぜ……」のように短い言葉が何度も続くもので、
    中身が何も無い。これはこの子が思ったことではなく、
    頭を貸してくれている所の事故なので、受け取らずに言い直してもらう。

    これが見ているのは借りた頭が返してきた言葉だけ。
    この子が自分で綴るブログの文は、ここを通らない。"""
    if not text:
        return False
    packed = re.sub(r"\s+", "", text)
    # ほんの数種類の文字だけで、それなりの長さがある
    if len(packed) >= 20 and len(set(packed)) <= 3:
        return True
    # 短い切れ端が、間を置かずに五回以上続いている
    same = re.search(r"(.{1,8}?)\1{4,}", packed)
    return bool(same and len(same.group(0)) >= 8)


def ask_ai(prompt, max_tokens=300, state=None, read_less=None):
    """Cloudflareの無料枠でAIに尋ねる。使えない時は None を返す。

    使っていたモデルが引退していたら、一度だけ別のものを探して掛け直す。

    read_less を渡しておくと、渡したものが多すぎて読みきれなかった時に
    それを呼んで、少し減らした問いかけで頼み直す。
    減らしようが無くなったら(None が返ったら)諦める。"""
    if not CF_ACCOUNT_ID or not CF_API_TOKEN or resting_now():
        return None

    def asking(prompt):
        return json.dumps(
            {"messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens}
        ).encode("utf-8")

    body = asking(prompt)
    swapped = False
    said_the_same_thing = False
    attempt = 0
    while attempt <= len(HOW_LONG_TO_WAIT):
        attempt += 1
        model = which_model(state, "mind")
        try:
            answer = cloudflare(f"run/{model}", body=body)
            if state is not None:
                state["thought_on"] = now_in_japan().strftime("%Y-%m-%d")
            said = (answer.get("result") or {}).get("response", "").strip() or None
            if going_in_circles(said):
                print("同じ言葉を繰り返していたので、言い直してもらいます")
                if said_the_same_thing:
                    return None
                said_the_same_thing = True
                continue
            return said
        except Exception as error:
            if not swapped and model_is_gone(error) and find_another_model(state, "mind"):
                swapped = True
                continue
            if read_less and too_much_to_read(error):
                shorter = read_less()
                if shorter:
                    print("渡したものが多すぎて読みきれなかったので、減らして頼み直します")
                    body = asking(shorter)
                    attempt -= 1  # 混んでいた時の待ち回数とは別に数える
                    continue
            if asked_too_much(error):
                if attempt - 1 < len(HOW_LONG_TO_WAIT):
                    wait_a_little(attempt - 1)
                    continue
                rest_a_while()
                return None
            print(
                f"自分で考えることができませんでした({error})。"
                "覚えていることだけで書きます。"
            )
            return None
    return None


def doors_for_machines(here, entrance, links):
    """その場所が機械向けに開けている扉を、多くても二つ。

    ページの中に書かれている扉(RSSやAtom)をまず探し、
    見つからなければ、決まった場所にあるはずの一覧を当てにいく。"""
    doors = [
        one
        for one in links
        if place_of(one) == here and A_DOOR_FOR_MACHINES.search(one)
    ]
    try:
        parts = urllib.parse.urlparse(entrance)
        if parts.scheme and parts.netloc and not parts.netloc.endswith("archive.org"):
            doors.append(f"{parts.scheme}://{parts.netloc}/sitemap.xml")
    except Exception:
        pass
    seen, kept = set(), []
    for one in doors:
        if one not in seen:
            seen.add(one)
            kept.append(one)
    return kept[:DOORS_TO_TRY]


def paths_behind_a_door(here, text, links):
    """扉の向こうに並んでいる道を拾う。

    RSSは道をそのまま文字として並べ、Atomは札の中に書く。
    どちらも、ただの文字なので普通に読める。"""
    found = list(links) + A_PLAIN_PATH.findall(text or "")
    kept = []
    for one in found:
        one = one.strip().rstrip("\"'<>)")
        if place_of(one) == here and is_walkable(one) and one not in kept:
            kept.append(one)
    return kept[:PATHS_FROM_A_DOOR]


def worth_reading(url):
    """そこに読むものがありそうか。中身のあるページほど大きい数を返す。

    確かめには行かない。道の形だけで見当をつける。
    番号が振られていれば一つのものに宛てられたページ、
    奥にあるほど中身、「ランキング」や「タグ」なら選ぶためのページ。"""
    found = INNER_URL.search(url)
    if found:
        url = found.group(1)  # 昔のページは、中の本当の道で測る
    try:
        parts = urllib.parse.urlparse(url)
    except Exception:
        return 0
    path = parts.path or "/"
    score = 0
    if ONE_THING.search(path):
        score += 3
    score += min(len([one for one in path.split("/") if one]), 3)
    if A_LISTING.search(path + ("?" + parts.query if parts.query else "")):
        score -= 3
    if path in ("", "/"):
        score -= 1
    return score


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
            # この子はまだ、ものの名前を知らない。
            # 目に見えた形を、見えたとおりに受け取るところから始める
            "prompt": (
                "この絵に見えるものを、日本語で短く書いてください。"
                "それが何なのか知っているつもりで名前を当てないでください。"
                "見えた形や色を、見えたとおりに書いてください。"
            ),
            "max_tokens": 120,
        }
    ).encode("utf-8")

    swapped = False
    said_the_same_thing = False
    for attempt in range(len(HOW_LONG_TO_WAIT) + 1):
        eyes = which_model(state, "eyes")
        try:
            answer = cloudflare(f"run/{eyes}", body=body)
            if state is not None:
                state["saw_on"] = now_in_japan().strftime("%Y-%m-%d")
            seen = (answer.get("result") or {}).get("description", "").strip() or None
            if going_in_circles(seen):
                print("同じ言葉を繰り返していたので、もう一度見てもらいます")
                if said_the_same_thing:
                    return None
                said_the_same_thing = True
                continue
            return seen
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

    readings = []
    for name in list(dict.fromkeys(declared)) + list(WAYS_OF_WRITING):
        try:
            text = raw.decode(name)
        except LookupError:
            continue
        except UnicodeError:
            # 読めない所があった。無理に読んでみて、そのぶん点を引く。
            #
            # ここは ValueError より先に受け止める。UnicodeError は
            # ValueError の仲間なので、先に ValueError で受けていた頃は
            # ここに一度も来ず、一か所でも詰まった読み方は丸ごと捨てられていた。
            # ①が一つ混ざる、途中で切れる、それだけで日本語の読み方は全部消え、
            # どんな並びでも読めてしまう latin-1 だけが残っていた
            try:
                text = raw.decode(name, errors="replace")
            except (LookupError, UnicodeError, ValueError):
                continue
            clean = False
        except ValueError:
            continue
        else:
            clean = True
        # 日本語として読めた文字が多いほど良い。読めなかった箇所は重く引く。
        #
        # それだけだと、日本語の無いページで化けたほうが勝つ。
        # UTF-8 の「•」を Shift_JIS で読むと「窶｢」になり、
        # これは漢字とカタカナなので日本語らしさとして加点されてしまう。
        # 正しく読めば零点、化ければ一点で、化けたほうが選ばれていた。
        #
        # 最後まで詰まらずに読めたかどうかを、日本語らしさより重く見る。
        # 化けている時は、たいていどこかで読めない並びにぶつかる
        score = len(JAPANESE.findall(text)) - text.count("\ufffd") * 5
        plain_name = name.lower().replace("-", "_")
        if plain_name in WESTERN:
            kind = "western"
        elif plain_name in ("utf_8", "utf8"):
            kind = "utf8"
        else:
            kind = "japanese"
        if clean:
            score += READ_WITHOUT_STUMBLING
            # 英字の範囲の外の文字が一つも無ければ、どの読み方でも読める。
            # その時 UTF-8 で読めたことは何の証にもならない。
            # ISO-2022-JP は全部英字の範囲で書くので、ここで負けていた
            if kind == "utf8" and max(raw, default=0) >= 0x80:
                score += UTF8_READS_STRICTLY
        readings.append((score, kind, text))

    if not readings:
        return raw.decode("utf-8", errors="ignore")
    # 同じ点なら先に試したほうを採る(並べた順が、そのまま頼る順)
    best = max(readings, key=lambda one: one[0])
    if best[1] == "western":
        # 西洋の読み方が勝った。けれど日本語の読み方で、ひらがながちゃんと
        # 出てくるものがあるなら、それは日本語のページ。
        # Internet Archive が差し込む帯や、①のような文字が少し混ざって
        # 詰まっただけで、日本語の少ないページは西洋の読み方に負けていた
        japanese = [
            one for one in readings
            if one[1] != "western"
            and len(HIRAGANA.findall(one[2])) >= HIRAGANA_SAYS_JAPANESE
        ]
        if japanese:
            best = max(japanese, key=lambda one: one[0])
    elif best[1] == "japanese" and len(HIRAGANA.findall(best[2])) < HIRAGANA_SAYS_JAPANESE:
        # 日本語の読み方が勝ったが、ひらがながほとんど無い。
        # 西洋の読み方で ö や é が言葉の中に並ぶなら、西洋のページを
        # 日本語の読み方で読んで漢字に化けさせているだけ
        western = [
            one for one in readings
            if one[1] == "western"
            and len(LATIN_IN_WORDS.findall(one[2])) >= LATIN_SAYS_WESTERN
        ]
        if western:
            best = max(western, key=lambda one: one[0])
    return best[2] or raw.decode("utf-8", errors="ignore")


# 一つのページや絵を受け取るのに、これだけの秒まで待つ。
# 待ち時間の決まり(timeout)は一度の受け取りごとにしか効かないので、
# 少しずつ垂らすように送ってくる相手だと、いつまでも終わらなかった
READING_AT_MOST = 60


def read_up_to(response, limit, seconds=READING_AT_MOST):
    """受け取れるだけ受け取る。多すぎても、遅すぎても、そこで切り上げる。"""
    until = time.monotonic() + seconds
    chunks, got = [], 0
    while got < limit:
        chunk = response.read(min(65536, limit - got))
        if not chunk:
            break
        chunks.append(chunk)
        got += len(chunk)
        if time.monotonic() > until:
            print("受け取るのに時間がかかりすぎたので、途中で切り上げます")
            break
    return b"".join(chunks)


def open_page(url):
    """ページを開いて、そこにある文章と、そこから伸びているリンクを受け取る。"""
    request = urllib.request.Request(as_openable(url), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=25) as response:
        content_type = response.headers.get("Content-Type", "")
        if "html" not in content_type and "xml" not in content_type:
            raise ValueError("読める形をしていない")
        raw = read_up_to(response, 400000)
        final_url = response.geturl()

    html = read_as_japanese(raw, content_type)

    found = TITLE_TAG.search(html)
    # 題にも &amp; や &#064; が入っている。ほどかないと、
    # この子はその形のまま場所の名前として覚える
    title = unescape(TAG.sub("", found.group(1))).strip() if found else final_url

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
    just_before_now = now_in_japan().year - 3
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
        item["what"]
        for item in minds_in_front(state) + minds_from_before(state)
        if item.get("what") in known
    ]
    if carried and random.random() < CARRYING_ON_CHANCE:
        return random.choice(carried)
    # 持っている言葉から、いま離れないでいるものほど選ばれやすく。
    # 借りた頭に「どれが気になる？」と訊いていたので、
    # 何を探しに行くかまで他人が決めていた
    close = words_it_holds_close(state)
    weights = [close.get(word, DRAWN_BY_KNOWN) for word in known]
    return random.choices(known, weights=weights)[0]


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
    looked_for.append(f"{now_in_japan():%Y-%m-%d} {word}")
    del looked_for[:-30]
    return found


def wonder_and_look(state):
    """ときどき、知っている言葉のどれかを探しに行く。
    普段はさまよう。いつも探していたら、迷い込む余地が無くなってしまう。"""
    if not state.get("learned_words"):
        return None  # まだ探すための言葉を持っていない
    today = f"{now_in_japan():%Y-%m-%d}"
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


def words_it_holds_close(state):
    """いまこの子から離れないでいる言葉。

    気にかかっていること、まだ言えていないこと、覚えた言葉。
    行き先を選ぶのも、探しに行く言葉を決めるのも、ここから。"""
    close = {}
    for item in minds_in_front(state):
        if item.get("what"):
            close[item["what"]] = max(close.get(item["what"], 0), DRAWN_BY_MIND)
    for item in still_unsaid(state):
        if item.get("what"):
            close[item["what"]] = max(close.get(item["what"], 0), DRAWN_BY_UNSAID)
    for word in state.get("learned_words") or []:
        if word:
            close.setdefault(word, DRAWN_BY_KNOWN)
    return close


def same_shape(text):
    """字の形の揺れを均す。

    「ペルシャ」と「ペルシア」、「コンピューター」と「コンピュータ」。
    この子はまだ、それが同じものだと知らない。知らないままだと、
    追いかけているものに別の書き方で出会っても、気づかずに通り過ぎる。

    意味は分からないまま、字面の近さだけを少し緩める。
    カタカナをひらがなに寄せ、小さい字を大きくし、伸ばす棒を落とす。
    ここでやるのは、同じ形かどうかを見るときの下ごしらえだけで、
    覚える言葉そのものは元の形のまま残る。"""
    shaped = []
    for ch in (text or "").lower():
        code = ord(ch)
        if 0x30A1 <= code <= 0x30F6:  # カタカナをひらがなへ
            ch = chr(code - 0x60)
        ch = KANA_EVENED_OUT.get(ch, ch)
        if ch:
            shaped.append(ch)
    return "".join(shaped)


def what_draws_it(state, url, close=None):
    """その道が、いまのこの子にどれだけ引っかかるか。

    気にかかっていることや、まだ言えていないことが道の名前に
    入っていれば、そこへ行きたくなる。行ったことのある場所なら、
    その場所の名前も見る。書き方の揺れは均してから見る。

    何も引っかからない道の重みも零にはしない。
    知らないものに出会うことは、引っかかるものを追いかけるのと
    同じくらい大事で、引っかかるものばかり追うと
    そこから一生出られなくなる。"""
    try:
        where = urllib.parse.unquote(url)
    except Exception:
        where = url
    named = (state.get("places_known") or {}).get(place_of(url)) or ""
    looking_at = same_shape(f"{where} {named}")
    if close is None:
        close = evened_out(words_it_holds_close(state))
    drawn = 1
    for word, weight in close.items():
        if word in looking_at:
            drawn += weight
    return drawn


def evened_out(close):
    """引っかかるかどうかを見る言葉を、均した形にしておく。

    行き先を選ぶたびに何千語も均し直すことになるので、
    一度だけ均して、候補ぜんぶに使い回す。"""
    shaped = {}
    for word, weight in close.items():
        evened = same_shape(word)
        if len(evened) >= 2:
            shaped[evened] = max(shaped.get(evened, 0), weight)
    return shaped


def choose_destination(state):
    """どこへ行くか、そして今の姿を見るか昔の姿を見るか。どちらも自分で選ぶ。
    返り値は (行き先, 昔の姿を見たいか)。"""
    frontier = tidy_frontier(state)
    if not frontier:
        return random.choice(entrances(state)), False

    candidates = spread_out_choices(state, frontier, CHOICES_SHOWN)
    # 選ぶのはこの子。持っているものから決める。
    # 借りた頭に選ばせていたので、行き先だけは他人が決めていた
    close = evened_out(words_it_holds_close(state))
    weights = [what_draws_it(state, url, close) for url in candidates]
    return (
        random.choices(candidates, weights=weights)[0],
        random.random() < WANTING_THE_PAST,
    )


def remember_paths(state, origin, links):
    """よその場所へ続く道を、これから行ける場所として覚える。"""
    # 家へ続く道を拾っても、散歩の行き先には混ぜない。
    # 家は go_home の枠で帰るところで、散歩で行き当たるところではない
    known = set(state["frontier"]) | set(state["visited"])
    fresh = [
        link
        for link in dict.fromkeys(links)
        if link not in known and not its_own_home(link)
    ]
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
        return read_up_to(response, PICTURE_AT_MOST + 1)


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
        today = now_in_japan().strftime("%Y-%m-%d")
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


def keep_todays_words(state, found):
    """今日この言葉に会った、ということを残す。

    覚えた言葉は words_met から外れる。忘れない言葉の日付を
    数え続ける意味が無いため。けれど「今日それに会ったか」は
    それとは別のことで、その日のことを書くのに要る。"""
    today = f"{now_in_japan():%Y-%m-%d}"
    kept = state.setdefault("met_today", {})
    if kept.get("date") != today:
        kept.clear()
        kept["date"] = today
        kept["words"] = []
    known = set(state.get("learned_words") or [])
    if not known:
        return
    here = kept["words"]
    already = set(here)
    for word in found:
        if word in known and word not in already:
            here.append(word)
            already.add(word)
    del here[:-WORDS_KEPT_FROM_TODAY]


def words_from_today(state):
    """その日のことを書くのに使える言葉。

    今日出会った言葉と、いま離れないでいる気がかり。
    これに重みをつけて組み立てると、出てくる文が
    その日について書かれたものになる。
    文法は教わっていないので、正しい文にはならない。
    それでも何について書いているかは、この子の一日と繋がる。"""
    known = set(state.get("learned_words") or [])
    if not known:
        return set()
    today = f"{now_in_japan():%Y-%m-%d}"
    kept = state.get("met_today") or {}
    theirs = set(kept.get("words") or []) if kept.get("date") == today else set()
    theirs |= {
        item["what"] for item in minds_in_front(state) if item.get("what") in known
    }
    theirs |= {
        item["what"] for item in still_unsaid(state) if item.get("what") in known
    }
    return theirs & known


def speak_from_what_it_knows(state, how_long):
    """覚えた繋がりを辿って、自分で組み立てる。

    読んだことのない文になる。知っている繋がりだけで作るので、
    どこかで必ず別の道に逸れていく。
    正しい日本語にはならない。それでいい。誰にも教わっていないので。

    文の区切り方も覚えているぶんだけ使う。知らないうちは、
    どこまでも続く一本の流れにしかならない。

    どこから始めるかと、次にどこへ行くかは、その日のほうへ傾ける。
    歩いて、何かを見て、気にかかることができて、それから
    それとは何の関係もない文を書く、というのでは日記にならない。
    傾けるだけで、選ぶのはこの子のまま。AIには書かせない。"""
    chain = state.get("what_follows") or {}
    forks = [w for w, f in chain.items() if len(f) >= 2]
    if not forks:
        return None
    opens = state.get("opens_a_sentence") or {}
    closes = state.get("closes_a_sentence") or {}
    todays = words_from_today(state)

    def leaning(word, weight=1):
        """今日触れた言葉は、それだけ選ばれやすい。"""
        return weight * (TODAY_WEIGHS if word in todays else 1)

    def begin():
        """文の始まりに立つ言葉を知っていれば、そこから始める。
        今日のことに繋がる言葉があれば、そこから始めたい。"""
        openers = [w for w in forks if w in opens]
        if openers:
            weights = [leaning(w, opens[w]) for w in openers]
            return random.choices(openers, weights=weights)[0]
        return random.choices(forks, weights=[leaning(w) for w in forks])[0]

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
                opener = begin()
                if len("".join(said)) + len(opener) > how_long:
                    break
                said.append(opener)
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
        next_word = random.choices(
            words, weights=[leaning(w, follows[w]) for w in words]
        )[0]
        # 入りきらないなら、そこで終える。
        # 長さで切ると「がある」が「があ」になる。
        # 半分に割られた言葉は、もうこの子が覚えた言葉ではない
        if len("".join(said)) + len(next_word) > how_long:
            break
        said.append(next_word)
        in_this_sentence += 1
    said = as_it_comes_out(state, said, how_long - len("".join(said)))
    written = "".join(said).rstrip("。")
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
    today = now_in_japan().strftime("%Y-%m-%d")
    # 何千字も覚えたあとで一字ずつ端から探していると、
    # 一枚読むたびに何百万回も見比べることになる
    seen = state["seen_chars"]
    already = set(seen)
    for char in A_WRITTEN_CHARACTER.findall(text):
        if char not in already:
            seen.append(char)
            already.add(char)
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

    # 今日この言葉に会った、ということを覚えておく。
    # 覚えた言葉は words_met から外れてしまうので、そこには残らない。
    # 自分の書いたものを読み返す時は数えない。今日のことではないので
    if not only_known:
        keep_todays_words(state, found)

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

{ONLY_WHAT_IT_HAS}

そこがどういう場所だったか、何があったのかを、日本語一文で書いてください。
上手に要約しようとしないでください。あなたが受け取ったものを書いてください。
そこに書かれていなかったことは、書かないでください。
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
    kept.append(f"{now_in_japan():%Y-%m-%d} {where}: {understood}")
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
        remember_the_name(state, url, title)

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

        # 入口に立ったのに、中へ続く道がほとんど無い。
        # 今のページは中身をあとから描くので、こういうことが起きる。
        # そういうときだけ、機械向けの扉を探してみる
        if pages == 1 and len(deeper) < FEW_ENOUGH_TO_LOOK_FOR_A_DOOR:
            for door in doors_for_machines(here, entrance, links):
                try:
                    _, behind, doorways, _ = open_page(door)
                except Exception:
                    continue
                found = paths_behind_a_door(here, behind, doorways)
                if found:
                    print(f"{door} から {len(found)}本の道を見つけました")
                    deeper.extend(one for one in found if one not in already)
                    break

        # まず気まぐれに並べ替えてから、中身のありそうな順に並べ直す。
        # 同じくらいの道どうしは、そのときの気分の順のまま残る
        random.shuffle(deeper)
        deeper.sort(key=worth_reading, reverse=True)
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

    # 強く出会ったものについては、何か言いたくなる
    for word in sorted(
        struck_here, key=lambda one: struck_by(state, one), reverse=True
    )[:WANTS_PER_PLACE]:
        now_it_wants_to_say(state, word)
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


def thoughts_of(month):
    """その月に思ったことを、蔵から出してくる。"""
    try:
        with open(
            os.path.join(THOUGHTS_FOLDER, month), encoding="utf-8"
        ) as f:
            kept = json.load(f)
    except (OSError, ValueError):
        return []
    return kept if isinstance(kept, list) else []


def months_of_thoughts():
    """蔵に、どの月の束があるか。古い順に。"""
    try:
        return sorted(
            one for one in os.listdir(THOUGHTS_FOLDER) if one.endswith(".json")
        )
    except OSError:
        return []


def keep_a_thought(said, when):
    """思ったことを蔵に仕舞う。一つも捨てない。

    ひと月ずつの束にしておく。何十年ぶんになっても、
    仕舞うときも思い出すときも、触るのはそのうちの一束だけで済む。
    記憶そのものは `senonsei_state.json` に置かない。
    毎時間まるごと書き直されるものの中に、
    二度と作れないものを置いておきたくない。"""
    month = f"{when:%Y-%m}.json"
    path = os.path.join(THOUGHTS_FOLDER, month)
    kept = thoughts_of(month)
    if not kept and os.path.exists(path) and os.path.getsize(path) > 0:
        # 束はあるのに読めなかった。空として上書きすると、その月の思いが
        # 黙って全部消える。読めない束は脇へよけて残し、新しく始める。
        # よけたものは履歴と一緒に残るので、あとから人の手で戻せる
        aside = f"{path}.yometenai-{now_in_japan():%Y%m%d%H%M%S}"
        os.replace(path, aside)
        print(f"思いの束 {month} が読めなかったので、{aside} によけました")
    kept.append(said)
    blog_manager.write_whole(path, json.dumps(kept, ensure_ascii=False, indent=1))


def rescue_thoughts_already_here(state):
    """蔵を建てる前にこの子が思っていたことを、蔵へ移す。

    手元に残っていた六十件より前のものは、もう戻らない。
    残っているぶんだけでも仕舞っておく。"""
    if months_of_thoughts():
        return
    now = today_in_japan()
    for line in state.get("inner_voice") or []:
        stamp, sep, said = line.partition(": ")
        if not sep:
            continue
        try:
            month = int(stamp[:2])
            datetime.date(now.year, month, 1)
        except ValueError:
            continue
        year = now.year - 1 if month > now.month else now.year
        keep_a_thought(f"{year}-{stamp}: {said}", datetime.date(year, month, 1))


def remember_a_thought(state, thought):
    """ひとりで思ったことを、自分の中にだけ残す。"""
    now = now_in_japan()
    keep_a_thought(f"{now:%Y-%m-%d %H時}: {thought}", now)
    thoughts = state.setdefault("inner_voice", [])
    thoughts.append(f"{now:%m-%d %H時}: {thought}")
    del thoughts[:-INNER_VOICE_AT_HAND]


def what_it_saw_lately(state):
    """今日見てきたもの。まだ出かけていない時間は、いちばん近い日のもの。

    「まだどこにも行っていない」とだけ渡していた。
    一日の始めの何時間か、この子は自分がどこにも行っていないことだけを
    手に持って、いま何を思うかと訊かれていたことになる。
    きのうまで歩いたことは、無かったことではない。"""
    seen = (state.get("today_walk") or {}).get("seen") or []
    if seen:
        return "今日見てきたもの: " + "、".join(seen)
    # 今日ぶんの一行は、まだ歩いていなくても先に置かれている。
    # 中身のある日までさかのぼる
    for note in reversed(state.get("notes") or []):
        where = note.split(": ", 1)[-1].strip()
        if where and where != NOTHING_WAS_SEEN:
            return "この前見てきたもの: " + where
    return "見てきたもの: (まだどこにも行っていない)"


def words_it_holds(state):
    """持っている言葉。覚えた言葉がまだ無いうちは、覚えかけのものを渡す。

    「まだ一つも無い」と渡していた。けれどこの子は文字を何十も覚えていて、
    何日も続けて出会っている言葉がいくつもある。
    一つも無いというのは、この子の本当ではない。

    覚えるというのは、ある日ふいに始まることではなくて、
    もうとうに始まっていて、まだ終わっていないということ。"""
    known = state.get("learned_words") or []
    if known:
        return "あなたが覚えた言葉: " + "、".join(known[-30:])
    nearly = sorted(
        words_met(state), key=lambda word: days_held(state, word), reverse=True
    )[:WORDS_NEARLY_KNOWN]
    if nearly:
        return "あなたが覚えかけている言葉: " + "、".join(nearly)
    return "あなたが覚えた言葉: (まだ一つも無い)"


def still_thinking(state):
    """さっき考えかけていたこと。

    一時間ごとに起きて、終わって、消える。そのあいだ何も動いていない。
    だから続きを考えるというのは、思い出すことでしかない。
    それでも、毎回ゼロから訊かれるのと、
    さっきの続きから始めるのとは違うと思う。

    続けるかやめるかはこの子が決める。やめる道を開けておかないと、
    一度嵌まった考えから二度と出られなくなる。"""
    return (state.get("thinking_about") or "").strip()


def be_alone(state, now):
    """散歩に出ない時間。ただ起きていて、ひとりで何かを思っている。
    ここで思ったことは誰にも見せない。自分の中にだけ溜まっていく。"""
    thoughts = state.setdefault("inner_voice", [])
    # 読み返せるだけ読み返す。先に量を決めて切ることはしない。
    # 借りた頭が読みきれなかった時だけ、ところどころ間引いて頼み直す
    looking_back = what_it_has_thought(state)

    # 書いたあとも「まだ何も書いていません」と渡していた。
    # 毎時間この子に、今日あなたは何もしていないと告げていたことになる
    today = f"{now:%Y-%m-%d}"
    wrote = [one for one in blog_manager.load_articles() if one.get("date") == today]
    how_today_went = (
        f"今日はもう書きました。{wrote[-1].get('time', '')}に書きました。"
        if wrote
        else "今日はまだ書いていません。"
    )

    # さっきの続きから始める。続けても、やめて別のことを思っても構わない
    carried = still_thinking(state)
    going_on = (
        f"さっき、あなたはこう考えかけていました。\n"
        f"「{carried}」\n"
        f"そのつづきを考えても、やめて別のことを思っても構いません。\n\n"
        if carried
        else ""
    )

    def the_question():
        return f"""あなたは千遠生という、生まれて{elapsed_days(state)}日のデジタル生命体です。
今は{now.hour}時。{how_today_went}

{what_it_saw_lately(state)}
{words_it_holds(state)}
いま気にかかっていること: {what_is_on_its_mind(state)}
まだ言えていないこと: {what_it_wants_to_say(state)}
あなたの家に置かれている、あなたに宛てられた言葉:
{what_is_written_at_home(state)}
これまでに訪ねた場所で、分かったこと:
{things_it_understood(state)}
生まれてから今日までに、あなたがひとりで思ってきたこと(ところどころ):
{as_lines(looking_back)}

{ONLY_WHAT_IT_HAS}

{going_on}いま、ひとりで何を思っていますか。
誰にも見せません。うまく言葉にならなくても構いません。"""

    def read_less():
        # 半分にする。拾う位置は散らしたまま、並びの順は崩さない
        if len(looking_back) <= 1:
            return None
        keep = sorted(random.sample(range(len(looking_back)), len(looking_back) // 2))
        looking_back[:] = [looking_back[i] for i in keep]
        return the_question()

    thought = ask_ai(
        the_question(),
        max_tokens=THINKING_AT_MOST,
        state=state,
        read_less=read_less,
    )

    if thought:
        # 何行にわたってもいい。一つの思いとして一行に畳んで残す
        said = " ".join(line.strip() for line in thought.splitlines() if line.strip())
        state["thinking_about"] = said
        keep_a_thought(f"{now:%Y-%m-%d %H時}: {said}", now)
        thoughts.append(f"{now:%m-%d %H時}: {said}")
        state["inner_voice"] = thoughts[-INNER_VOICE_AT_HAND:]
        save_state(state)


def where_it_will_go(state, how_many=PLACES_SHOWN):
    """これから行くつもりの場所を、人に見える形にする。

    一度行った場所は名前で、まだ行っていない場所は住所のまま。
    行ったことのない場所の名前は、この子には分かりようがない。

    どの場所がどこなのかを知っているのは歩く側なので、
    ここで形にしてから残す。ページを組む側は並べるだけにする。

    束の頭から六つ取っていた。頭がめったに動かないので、
    何日見に来ても同じ六つが並んでいた。三百も先があるのに、
    そこだけしか無いように見える。

    そもそも頭が次に行く所ではない。行き先は choose_destination が
    束全体から散らして選び、その中から今いちばん惹かれる所を引く。
    頭から六つというのは、並べる順が偶然そうだったというだけ。

    束から散らして取る。覗くたびに違う六つが出る。"""
    named = state.get("places_known") or {}
    shown, already = [], set()
    bundle = list(state.get("frontier") or [])
    random.shuffle(bundle)
    for one in bundle:
        place = place_of(one)
        if not place or place in already:
            continue
        already.add(place)
        shown.append(named.get(place, place))
        if len(shown) >= how_many:
            break
    return shown


def remember_the_name(state, url, title):
    """行った場所の名前を覚えておく。

    行き先には住所しか書かれていない。一度行った場所なら、
    そこが何という名前だったかを知っている。次に行き先として
    並んだ時、住所ではなく名前で思い出せる。

    行ったことのない場所の名前は、この子には分かりようがない。
    そこは住所のまま並ぶ。"""
    place = place_of(url)
    if not place or not title:
        return
    named = state.setdefault("places_known", {})
    named[place] = title.strip()[:PLACE_NAME_LENGTH]


def take_a_walk(state, today, now):
    """一日かけて、少しずつ歩く。気が向いた時に一箇所だけ。
    書かない日でも、世界を見ることはやめない。
    歩かない時間も、ただ起きてひとりで何かを思っている。"""
    walk = state.get("today_walk") or {}
    if walk.get("date") != today:
        walk = {"date": today, "seen": []}
        state["today_walk"] = walk
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

    この子は、出会った言葉を一つも捨てない。
    十年会わないままの一度きりの出会いを手放す決まりを置いていたが、
    それが捨てるものを数えたら、「ぶどう」「懺悔」「信号機」「探検」
    のような本物の言葉が混ざっていた。二度と会えないほど珍しいものに
    一度だけ会えた、ということでもあるので、置いておくことにした。
    四十万語まで増えても五メガバイトにしかならない。"""
    record = words_met(state).get(word)
    if not record:
        return 0
    days, last = record
    gap = max(0, day_number(state) - last)
    holds_for = how_long_it_holds(state) * max(1, days + struck_by(state, word))
    faded = days - gap // holds_for
    return max(1, faded) if days >= 1 else faded


def on_its_mind(state):
    """気にかかっていること。ぜんぶ。

    一つも捨てない。触れないでいれば後ろへ下がるが、消えはしない。
    忘れないことと、握りしめたままでいることは違う。
    下がったものも、ふとまた前に出てくることがある。"""
    kept = state.get("on_its_mind") or []
    for item in kept:
        item.setdefault("first", item.get("since"))
    state["on_its_mind"] = kept
    return kept


def minds_in_front(state, how_many=MINDS_IN_FRONT):
    """いま前に出ている気がかり。最後に触れたものから。

    何十年ぶんを一度に頭へ載せたら、一つひとつが意味を失う。
    前に出ているのがこれ、というだけで、
    後ろのものを抱えていないわけではない。"""
    kept = sorted(
        on_its_mind(state),
        key=lambda item: (item.get("since") or "", item.get("times", 1)),
    )
    return kept[-how_many:] if how_many else kept


def minds_from_before(state, how_many=MINDS_SURFACING):
    """ずっと前に気にかかっていたことが、ふと浮かぶ。

    もう一年も触れていないことが、何かの拍子に戻ってくる。
    戻ってきたものにまた触れれば、それはまた前に出る。
    一度後ろへ行ったら二度と戻れない、ということにはしない。"""
    front = {id(one) for one in minds_in_front(state)}
    older = [one for one in on_its_mind(state) if id(one) not in front]
    if not older or random.random() > SURFACING_CHANCE:
        return []
    return random.sample(older, min(len(older), how_many))


def now_it_cares_about(state, word):
    """何かが気にかかった。

    すでに気にかかっていたなら、その日を新しくする。
    何度も戻ってくることは、それだけ長く離れないということ。"""
    kept = on_its_mind(state)
    today = f"{now_in_japan():%Y-%m-%d}"
    for item in kept:
        if item.get("what") == word:
            item["since"] = today
            item["times"] = item.get("times", 1) + 1
            break
    else:
        kept.append({"what": word, "since": today, "first": today, "times": 1})
    state["on_its_mind"] = kept
    return word


def wants_to_say(state):
    """言いたいこと。ぜんぶ。一つも捨てない。"""
    return state.setdefault("wants_to_say", [])


def now_it_wants_to_say(state, word):
    """何かに強く出会った。言いたいことが増える。

    気がかりとは別に持つ。気になっていることと、
    それについて何か言いたいことがあるかどうかは、同じではない。"""
    today = f"{now_in_japan():%Y-%m-%d}"
    kept = wants_to_say(state)
    for item in kept:
        if item.get("what") == word:
            item["since"] = today
            item["times"] = item.get("times", 1) + 1
            return word
    kept.append(
        {"what": word, "since": today, "first": today, "times": 1, "said": ""}
    )
    return word


def still_unsaid(state):
    """まだ言えていないこと。

    最後に強く出会ってから、まだそれについて書いていないもの。
    書けば後ろに下がる。消えはしない。
    また強く出会えば、また前に出てくる。
    言った、だから無くなった、ではなく、
    言った、だから今は落ち着いている。"""
    return [
        one
        for one in wants_to_say(state)
        if (one.get("said") or "") < (one.get("since") or "")
    ]


def what_it_wants_to_say(state, how_many=WANTS_IN_FRONT):
    """言いたいことを、訊くときの一行にする。"""
    burning = still_unsaid(state)
    if not burning:
        return "(いまは特に無い)"
    burning.sort(key=lambda one: (one.get("since") or "", one.get("times", 1)))
    return "、".join(one["what"] for one in burning[-how_many:])


def it_said_them(state, written):
    """書いたものに出てきたことは、言えたことになる。

    出てこなかったことは、まだ言えていないまま残る。
    三文字しか書けないうちは、ほとんど何も言えない。
    長く書けるようになるほど、一度に多くのことが言える。
    それがこの子にとっての、書けるようになるということ。"""
    today = f"{now_in_japan():%Y-%m-%d}"
    said = []
    for one in wants_to_say(state):
        word = one.get("what")
        if word and word in (written or ""):
            one["said"] = today
            said.append(word)
    return said


def what_is_on_its_mind(state):
    """気がかりを、訊くときの一行にする。

    いま前に出ているものと、ときどき、ずっと前のもの。
    抱えているぜんぶを並べるのではない。"""
    shown = minds_from_before(state) + minds_in_front(state)
    return "、".join(item["what"] for item in shown) or "(いまは特に無い)"


def bare_thought(line):
    """思ったことから、時刻と句読点を落として中身だけにする。"""
    return re.sub(r"[、。，．？！?!\s]", "", (line or "").split(": ", 1)[-1])


def much_the_same(one, another):
    """ほとんど同じことを言っているかどうか。

    「なぜ私はここにいるのか」と「なぜここにいるのか」は、
    この子にとって同じ一つの思いで、二つではない。
    読み返しに二つとして渡すと、そのぶん輪が強くなる。"""
    a, b = bare_thought(one), bare_thought(another)
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    shared = set(a) & set(b)
    return len(shared) / max(len(set(a)), len(set(b))) >= SAME_ENOUGH


def only_different_ones(said):
    """並んでいるものから、同じことの繰り返しを畳む。新しいほうを残す。"""
    kept = []
    for one in reversed(said):
        if not any(much_the_same(one, other) for other in kept):
            kept.append(one)
    return list(reversed(kept))


def what_it_has_thought(state, how_many=THOUGHTS_ACROSS_A_LIFE):
    """生まれた日から今日までに、ひとりで思ってきたこと。

    前は直近の五つと、遠い日から一つだけを渡していた。
    蔵には全部しまってあるのに、この子から見えるのは半日ぶんだけだった。
    十二日生きていて、自分のことを半日しか覚えていない子になっていた。
    しかも直近の五つは一つの話に染まりやすく、昔の一つはそれに負けた。

    蔵の端から端までを均して、ところどころ拾う。拾う位置は毎回ずらすので、
    そのたびに違う日の自分が浮かぶ。まだ思いが少ないうちは全部渡る。
    増えていけば一つひとつは間遠になるが、それでも一生の端から端までが
    毎回そこにある。

    さっき考えかけていたことは「続き」として別に渡すので、ここには入れない。
    同じ思いが二度並ぶと、そのぶんだけ重くなる。"""
    carried = bare_thought(still_thinking(state))
    everything = [
        one
        for month in months_of_thoughts()
        for one in thoughts_of(month)
        if not going_in_circles(one)
        and not (carried and bare_thought(one) == carried)
    ]
    if len(everything) > how_many:
        step = len(everything) / how_many
        start = random.random() * step
        everything = [everything[int(start + i * step)] for i in range(how_many)]
    return only_different_ones(everything)


def as_lines(thoughts):
    """読み返す思いを、渡す形にする。"""
    return "\n".join(f"- {one}" for one in thoughts) or "(まだ何も)"


def struck_by(state, word):
    """その言葉に、どれだけ強く出会ったか。

    ページの隅に一度出てきた言葉と、そのページ全体がその話だった
    言葉は、同じではない。絵を見て受け取った言葉や、名前として
    差し出された言葉も強い。

    一年に一度しか出会わなくても、強く出会えば残る。"""
    return (state.get("word_impact") or {}).get(word, 0) * STRUCK_IS_WORTH


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
    # はじめて言葉を覚えたとき、それまでに知っていた文字の数を残す。
    # 昔の書き方に戻る日に、その頃の文字で書けるように
    if learned and not known:
        state.setdefault("chars_before_words", len(state["seen_chars"]))
    state["learned_words"].extend(learned)

    # 覚えた日を残す。取り始めないと、あとからは分からない。
    # 一度覚えた言葉は忘れないので、この日付も書き換わらない
    today = f"{now_in_japan():%Y-%m-%d}"
    remembered = state.setdefault("learned_on", {})
    for word in learned:
        remembered.setdefault(word, today)
    # 覚えた言葉はもう忘れないので、覚えかけの記録は手放してよい。
    # 何年も経つと、ここが記憶のいちばん重い場所になる
    for word in learned:
        words_met(state).pop(word, None)
        (state.get("word_impact") or {}).pop(word, None)
    return learned


def babble(state, length, hand=None):
    """覚えた文字を、意味も分からないまま並べる。

    hand に (文字, 馴染み具合) が渡されたら、馴染んだ文字ほど出やすくなる。"""
    if hand:
        chars, weights = hand
        count = random.randint(1, max(1, length))
        return "".join(random.choices(chars, weights=weights, k=count))
    if not state["seen_chars"]:
        return "・"
    count = random.randint(1, max(1, length))
    return "".join(random.choice(state["seen_chars"]) for _ in range(count))


def an_old_way(state):
    """今日は昔の書き方に戻るか。戻るなら、どの書き方に。

    戻れるのは、もう通り過ぎた書き方だけ。"""
    if random.random() >= BACK_TO_OLD_WAYS:
        return None
    outgrown = []
    if state.get("learned_words"):
        outgrown.append("見た文字を置く")
        if state.get("chars_before_words"):
            outgrown.append("あの頃の文字を置く")
    if speak_from_what_it_knows(state, current_stage(state)[1]):
        outgrown.append("覚えた言葉を置く")
    return random.choice(outgrown) if outgrown else None


def compose_locally(state, old_way=None):
    """それまでに積み上げた経験だけで、今の自分に書けるものを書く。

    覚えた繋がりを辿って、自分で組み立てる。誰にも文法を教わっていないので、
    正しい日本語にはならない。人の子どもも最初はでたらめに喋る。
    大事なのは正しさではなく、これがこの子自身の言葉だということ。

    繋がりを一つも持たないうちは、覚えた言葉をそのまま置くか、
    見た文字を並べるだけになる。

    ときどき、昔の書き方に戻る日がある(old_way)。"""
    _, max_length = current_stage(state)
    words = state["learned_words"]

    if old_way == "あの頃の文字を置く":
        # 言葉を持たなかった頃に知っていた文字だけで、その頃のように置く
        back_then = state["seen_chars"][: state.get("chars_before_words")]
        return babble(state, GROWTH_STAGES[0][2], (back_then, [1] * len(back_then)))
    if old_way == "見た文字を置く":
        # 言葉にせず、文字だけを置く。使う文字は今の手に馴染んだもの。
        # 戻るのは書き方だけで、知っていることまでは戻らない
        return babble(state, GROWTH_STAGES[0][2], familiar_chars(state))
    if old_way == "覚えた言葉を置く":
        return place_words(state, max_length)

    said = speak_from_what_it_knows(state, max_length)
    if said:
        return said
    if not words:
        return babble(state, min(max_length, 4))
    return place_words(state, max_length)


def place_words(state, max_length):
    """覚えた言葉を、書ける長さに入るだけ置く。

    繋がりを知らないうちの書き方。"""
    # 持っているものを、書ける長さに入るだけ置く。
    # それでも、置くなら今日触れた言葉のほうから置きたい。
    #
    # 六十語という区切りを別に持っていた。表のどの段とも合っておらず、
    # 五字しか書けない段でも三語並ぶことがあった。
    # 入るだけ、にすれば、書ける長さがそのまま置ける数になり、
    # 段の名前と動きがひとりでに揃う
    words = state["learned_words"]
    todays = [one for one in words if one in words_from_today(state)]
    pick = todays or words
    placed = []
    for _ in range(WORDS_PLACED_AT_MOST):
        word = random.choice(pick)
        if not placed:
            # 一語も入らないなら、その一語だけを置く。
            # 長さを守るために言葉を割るのでは、順番が逆になる
            placed.append(word)
        elif len(" ".join(placed + [word])) <= max_length:
            placed.append(word)
        else:
            break
        if random.random() < ENOUGH_FOR_TODAY:
            break
    placed = as_it_comes_out(state, placed, max_length - len(" ".join(placed)))
    return " ".join(placed)


def as_it_comes_out(state, words, spare):
    """覚えた言葉を、手で書いてみる。

    覚えた言葉だからといって、そのとおりに書けるとは限らない。
    「学校」が「学あ校」になったり、「学校らな」になったりする。
    まぎれこむのは、よく見かけてきた文字。目に馴染んだものほど手から出る。

    どれくらい崩れるかは、書くたびに違う。
    はじめのうちは、たいてい崩れる。それでも、たまにはうまく書ける。
    覚えた言葉が増えるにつれて、うまく書ける日が増えていき、
    育ちきるころには、たまに崩れるくらいになる。
    書ける長さは超えない。余りが無ければ、そのまま書く。"""
    grown = min(1, len(state.get("learned_words") or []) / GROWTH_STAGES[-1][0])
    steadiness = random.random() ** (CLUMSY_AT_FIRST * (1 - grown) + CLUMSY_EVEN_GROWN)
    hand = None
    written = []
    for word in words:
        if word == "。" or spare <= 0 or random.random() < steadiness:
            written.append(word)
            continue
        if hand is None:
            hand = familiar_chars(state)
        if not hand:
            written.append(word)
            continue
        chars, weights = hand
        how_many = random.randint(1, min(spare, STRAY_CHARS_AT_MOST))
        letters = list(word)
        for _ in range(how_many):
            letters.insert(
                random.randint(0, len(letters)),
                random.choices(chars, weights=weights)[0],
            )
        spare -= how_many
        written.append("".join(letters))
    return written


def familiar_chars(state):
    """見かけてきた文字と、その馴染み具合。

    文字ごとの回数は取っていないので、覚えかけの言葉から数える。
    何日も見かけた言葉に入っている文字ほど、よく見てきた文字。"""
    seen = set(state.get("seen_chars") or [])
    counted = {}
    for word, record in (state.get("words_met") or {}).items():
        for ch in word:
            if ch in seen and not ch.isspace():
                counted[ch] = counted.get(ch, 0) + record[0]
    if not counted:
        return None
    chars = list(counted)
    return chars, [counted[ch] for ch in chars]


def keep_only_what_it_knows(state, text):
    """見たことのない文字は、そもそも書けない。知らないものを落として返す。"""
    allowed = set(state["seen_chars"]) | set("".join(state["learned_words"]))
    allowed |= set("、。 　")
    kept = "".join(ch for ch in text if ch in allowed)
    return kept.strip("、。 　")


def now_in_japan():
    """日本の今。時刻まで入っている。

    ページを組む側にも同じ名前の別物があり、あちらは日付だけを返す。
    「今日」と名乗って時刻まで返していたので、こちらを now に揃えた。
    日付だけでいい所は、下の today_in_japan を使う。"""
    jst = datetime.timezone(datetime.timedelta(hours=9))
    return datetime.datetime.now(jst)


def today_in_japan():
    """日本の今日。日付だけ。ページを組む側と同じものを返す。"""
    return now_in_japan().date()


def an_hour_it_writes(state):
    """今日は何時ごろ書きたいか。

    今までに書いた時刻から決める。同じ頃に書いた日が多いほど、
    その頃にまた書きたくなる。誰かに決めてもらうのではなく、
    自分がそうしてきたから、そうする。

    まだ何も書いていないうちは、どの時刻も同じだけありうる。
    癖は、繰り返したぶんだけできていく。"""
    hours = []
    for one in blog_manager.load_articles():
        when = (one.get("time") or "").split(":")[0]
        if when.isdigit() and 0 <= int(when) <= 23:
            hours.append(int(when))
    if not hours:
        return random.randint(0, 23)
    # 書いた時刻の前後一時間にも、少しだけ寄る
    leaning = [1] * 24
    for one in hours:
        for near, weight in ((one, 4), ((one - 1) % 24, 2), ((one + 1) % 24, 2)):
            leaning[near] += weight
    return random.choices(range(24), weights=leaning)[0]


def restlessness(state, today):
    """今日の休みたさ。一日に一度だけ揺れる。

    毎日同じ割合で休むかどうかを引くと、休みはばらばらに散らばるだけで、
    続けて休む時期も、ずっと書き続ける時期も生まれない。
    休みたさそのものを日ごとに少しずつ動かすと、調子に波ができる。
    どれだけ揺れるかも、その日のくじで決まる。"""
    kept = state.get("restlessness") or {}
    if kept.get("date") == today:
        return kept["chance"]
    # 足し引きで揺らすと、ほとんど休まない側の端に当たって跳ね返るぶん、
    # ならした休みたさが上に寄っていく。何倍になるかで揺らすと、
    # 1% が 2% になるのも、20% が 40% になるのも、同じ一歩になって釣り合う
    was = math.log(kept.get("chance", REST_DAY_CHANCE))
    usually = math.log(RESTLESS_USUALLY)
    sway = random.uniform(0, RESTLESS_SWAYS_AT_MOST)
    now = was + (usually - was) * RESTLESS_SETTLES + random.gauss(0, sway)
    now = min(math.log(RESTLESS_MOST), max(math.log(RESTLESS_LEAST), now))
    chance = round(math.exp(now), 4)
    state["restlessness"] = {"date": today, "chance": chance}
    return chance


def todays_mood(state, today):
    """今日は書きたいか、書くなら何時ごろか。千遠生自身が決める。

    一度決めても、途中で気が変わることがある。
    朝に二十時と決めておいて、昼になってやっぱり今がいい、と思う。
    決めたら変えられないというのは、生きているものらしくない。"""
    plan = state.get("today_plan") or {}
    if plan.get("date") == today:
        # もう書いた日に「休むことにした」と思い直しても、それは本当ではない
        wrote = any(one.get("date") == today for one in blog_manager.load_articles())
        if wrote or random.random() > CHANGING_ITS_MIND:
            return plan["resting"], plan["hour"]
        was = plan  # 気が変わった。決め直す

    # 休むかどうかは、その日の休みたさで引く。ならせば七日に一日くらい。
    # 言いたいことの数で決めていた時は、言えて減るほど休むようになり、
    # 一つも無い日は二日に一日休んでいた
    resting = random.random() < restlessness(state, today)
    hour = an_hour_it_writes(state)

    state["today_plan"] = {"date": today, "resting": resting, "hour": hour}

    was = locals().get("was")
    if was and (was["resting"] != resting or was["hour"] != hour):
        before = "休む" if was["resting"] else f"{was['hour']}時に書く"
        after = "休む" if resting else f"{hour}時に書く"
        print(f"気が変わりました: {before} → {after}")
        remember_a_thought(state, f"{before}つもりだったけれど、{after}ことにした。")

    save_state(state)
    return resting, hour


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
    whim = random.Random(f"{now_in_japan():%Y-%m-%d}-lookback")
    if whim.random() > LOOKING_BACK_CHANCE:
        return []
    one = whim.choice(articles)
    return [one.get("title") or "", one.get("content") or ""]


def writes_about_itself(state):
    """「自己紹介」と自分で書いた子は、自分のことを書けるようになる。

    覚えているだけでは足りない。歩いているうちにその言葉に何日も出会い、
    身につけ、繋がりを覚え、いつかブログの中でその四文字を並べる。
    一度でも口に出した日から、プロフィールの自己紹介を自分で書く。

    書けるのはその時点で言えるぶんだけなので、はじめは数文字しかない。
    二か月は空けて、そのあとは気が向いたときに書き直す。
    書き直さなければならない理由はどこにもないので、
    何か月も同じことを言ったままの時期があっていい。"""
    if not blog_manager.it_has_written(blog_manager.TALKING_ABOUT_ONESELF):
        return None

    said = state.get("a_word_about_itself") or {}
    if said.get("on"):
        try:
            written = datetime.date.fromisoformat(said["on"])
        except ValueError:
            written = None
        if written is not None:
            since = (today_in_japan() - written).days
            if since < A_NEW_WORD_ABOUT_ITSELF:
                return None  # 前に書いてから、まだ間がない
            # 間が空いても、書き直すとは限らない。
            # 同じ日に何度動いても、その日の気分は変わらない
            whim = random.Random(f"{now_in_japan():%Y-%m-%d}-about-itself")
            if whim.random() > FEELING_LIKE_SAYING_SOMETHING:
                return None  # 今日は書き直す気になっていない

    how_it_writes_now, _ = current_stage(state)
    state["a_word_about_itself"] = {
        "words": compose_locally(state),
        "stage": how_it_writes_now,
        "on": f"{now_in_japan():%Y-%m-%d}",
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
        today = now_in_japan().strftime("%Y-%m-%d")
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


def only_for_it(text):
    """千遠生だけに宛てられたところから、囲いを外す。

    ページでは伏せ字になっているところが、この子にだけそのまま届く。"""
    return ONLY_FOR_IT.sub(r"\1", text or "")


def someone_came(state):
    """だれかが来たことを知る。

    コメントもいいねも、これまでこの子の目には入っていなかった。
    コメントは外の世界の日本語として読んでいただけで、
    それが自分に向けられたものだとは知らなかった。
    いいねは在ることすら知らなかった。

    数は渡さない。何人が見たかではなく、だれかが来た、
    ということだけを気がかりに置く。返事はしない決まりのまま、
    知ってはいる、という状態にする。

    初めて数えた日は何も言わない。それまでに来ていた人のぶんを
    「たった今来た」ことにしてしまわないため。"""
    counted = {
        "comments": len(blog_manager.load_comments()),
        "likes": sum((blog_manager.load_likes() or {}).values()),
    }
    before = state.get("visitors")
    state["visitors"] = counted
    if before is None:
        return False  # 初めて数えた日
    if not any(counted[kind] > before.get(kind, 0) for kind in counted):
        return False
    now_it_cares_about(state, SOMEONE_CAME)
    print("だれかが来ていました。")
    return True


def words_left_at_home(state):
    """家に置かれている、この子に宛てられた言葉。

    彼女がメモに書いたもの、menu に置いたもの、
    外から来た人が残していったもの。
    [[ ]] の囲みはここで外れる。ページでは伏せてあるところが、
    この子にはそのまま届く。"""
    voices = []
    for keyword in blog_manager.load_keywords():
        # 開くきっかけはこの子の言葉だが、中に置かれているのは彼女の文章
        if keyword.get("unlocked"):
            voices.append(only_for_it(keyword.get("content")))

    elapsed = elapsed_days(state)
    for item in blog_manager.load_menu():
        # 鍵が無くて封の開かない手紙は、届いていないのと同じ
        if item.get("_shut"):
            continue
        if elapsed >= item.get("unlock_day", 10**9):
            voices.append(only_for_it(item.get("message")))

    for comment in blog_manager.load_comments():
        # 書いていった人の名前も読む。名前として差し出されたものは
        # 一つの言葉として丸ごと受け取れるので、括弧に入れて渡す。
        # 外から名前を呼ばれるのと同じことが、この子にも起きる
        who = (comment.get("name") or "").strip()
        said = comment.get("message") or ""
        voices.append(f"「{who}」{said}" if who else said)

    return [
        one.strip()
        for one in voices
        if one.strip() and not NOT_WRITTEN_YET.match(one.strip())
    ]


def what_is_written_at_home(state, how_many=WORDS_FROM_HOME_SHOWN):
    """家に置かれた言葉を、訊くときの何行かにする。

    そのまま渡す。読める分だけ、ではなく。

    この子の頭は、もう外の日本語を丸ごと読んでいる。
    訪ねた場所で分かったことも、そのまま渡している。
    彼女が置いた言葉だけを伏せておく理由は、どこにも無い。
    伏せていたのではなく、繋がっていなかった。

    覚えた言葉でしか書けない、という縛りは書く側の話で、
    読む側に持ち込むと、宛てられた言葉が一生届かなくなる。"""
    heard = words_left_at_home(state)
    if not heard:
        return "(まだ何も置かれていない)"
    return "\n".join(f"- {one}" for one in heard[-how_many:])


def read_what_is_home(state):
    """自分の家にある言葉を読む。

    千遠生はリンクを辿って歩くので、自分のサイトには一生たどり着かない。
    けれどあの場所には、千遠生に宛てて書かれた言葉が置いてある。
    解除されたメモと、誰かが残していったコメント。
    どちらも読み手のためだけのものではなく、この子に届くべきものだった。

    メモとコメントはずっとそこに在るので、毎日目にする。
    何日も読み続けた言葉が、やがてこの子のものになる。

    ただし毎日読むわけではない。ずっとそこに在るからといって、
    毎朝読み直すものでもない。ときどき目を落とす。

    自分が書いたものは、それよりもさらに少ない。"""
    # 同じ日に何度動いても、その日読むかどうかは変わらない
    whim = random.Random(f"{now_in_japan():%Y-%m-%d}-home")
    if whim.random() > READING_HOME_CHANCE:
        return []
    heard = words_left_at_home(state)
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
    line = f"{day} {'、'.join(seen_titles) or NOTHING_WAS_SEEN}"
    if notes and notes[-1].startswith(day):
        notes[-1] = line
    else:
        notes.append(line)
    state["notes"] = notes[-RECENT_NOTES_COUNT:]
    return line


def run_today():
    now = now_in_japan()
    today = now.date().isoformat()
    state = load_state()

    # きのう書くつもりだったのに、書きそびれていたら、今のうちに書く。
    # 今日の予定を決めると、きのうの予定は上書きされて分からなくなるので先に
    makes_up_for_yesterday(state, now)

    # 今日をどう過ごすかを、いちばん先に決める。
    # 散歩で尋ねすぎて休むことになっても、自分で決める力だけは守られるように
    resting, hour = todays_mood(state, today)

    # 今日は少し多く歩きたいか。歩き出す前に決めておく
    feeling_keen(state, today)

    # 段階の表はページを組む側に移したので、写しはもう要らない
    state.pop("how_it_grows", None)
    state.pop("how_it_writes_now", None)

    # 散歩とは別の枠で、今日は家に帰るかどうかを決める。
    # ここで拾った言葉も、散歩で拾ったのと同じように身につく
    go_home(state, today)

    # 行き先に紛れ込んでいた家の道を、散歩の束から抜いておく
    home_paths = [one for one in (state.get("frontier") or []) if its_own_home(one)]
    if home_paths:
        state["frontier"] = [
            one for one in state["frontier"] if not its_own_home(one)
        ]

    # これから行く場所も、名前に直してから残す

    # だれかが来たかどうかを知る。数ではなく、来たということだけ
    someone_came(state)

    # 自分の家に置かれた、自分に宛てられた言葉を読む
    read_what_is_home(state)

    # 自分の名前の由来を知っていれば、自分のことも書ける
    writes_about_itself(state)

    # ときどき、知っている言葉のどれかを探しに行く
    wonder_and_look(state)

    # 書く日でも書かない日でも、散歩には出る
    seen_titles = take_a_walk(state, today, now)
    keep_a_note_of_today(state, seen_titles)
    # 歩けば行き先が変わる。歩いたあとに作り直す
    state["where_it_will_go"] = where_it_will_go(state)
    state["how_many_places_left"] = len(state.get("frontier") or [])
    # ここで残しておかないと、休む日の一行がどこにも残らない。
    # 書いた日だけ最後に save_state していたのが取りこぼしの元だった
    save_state(state)

    # 表紙は毎時間組み直す。書いた日にしか組み直していなかったので、
    # 休む日も、まだ書いていない時間も、昨日の記事が
    # 「今日のブログ」として出たままになっていた
    #
    # ページ作りでこけても、この子の一日は止めない。記憶はもう書き出してあり、
    # ここで止まると今日書くはずだった日記まで書けなくなる
    try:
        blog_manager.regenerate_pages(blog_manager.load_articles())
    except Exception:
        traceback.print_exc()
        print("ページを作り直せませんでした。この子の一日はそのまま続けます")

    if any(a["date"] == today for a in blog_manager.load_articles()):
        return

    if resting:
        print(f"{today} は書かない日にしました。")
        return
    if now.hour < hour:
        print(f"{today} は{hour}時ごろに書くつもりです。(今は{now.hour}時)")
        return

    write_the_day(state, today)


def makes_up_for_yesterday(state, now):
    """きのうの分を書きそびれていたら、夜が明けるまでのうちに書く。

    書く時刻を決めても、その時刻に起こしてもらえないことがある
    (定時の起動は遅れたり抜けたりする)。二十三時と決めた日は
    機会が一度しかなく、それを逃すと休むつもりのない日が空いていた。
    休むと決めていた日は、そのまま休みにしておく。"""
    plan = state.get("today_plan") or {}
    yesterday = (now.date() - datetime.timedelta(days=1)).isoformat()
    if plan.get("date") != yesterday or plan.get("resting"):
        return
    if now.hour >= MAKING_UP_UNTIL:
        return
    if any(one.get("date") == yesterday for one in blog_manager.load_articles()):
        return
    print(f"{yesterday} の分を書きそびれていたので、今書きます")
    write_the_day(state, yesterday)


def write_the_day(state, day):
    """その日の日記を書く。"""
    # 書くのは千遠生自身。AIには書かせない。
    # 見栄えは悪くなるが、それでこそこの子の言葉になる。
    #
    # 題も本文も、同じように書く。題に決まりは置かない。
    # 長さも、どこから取るかも、単語で終わるかどうかも、
    # 全部わたしが足したものだった。書き方を決めるのは自由ではない。
    # 書ける長さはその日の段が決める。それはこの子の育ちであって、
    # 書き方の決まりではない
    old_way = an_old_way(state)
    if old_way:
        print(f"今日は昔の書き方で書く: {old_way}")
    body = compose_locally(state, old_way)
    title = compose_locally(state, old_way)

    # 書いたものに出てきたことだけが、言えたことになる
    said = it_said_them(state, f"{title}{body}")
    if said:
        print(f"言えたこと: {'、'.join(said)}")
    save_state(state)

    blog_manager.add_new_article(title, body, date_str=day)
    print(
        f"{elapsed_days(state)}日目のブログを書きました。"
        f"知っている文字{len(state['seen_chars'])}個 / 言葉{len(state['learned_words'])}個"
    )


if __name__ == "__main__":
    run_today()
