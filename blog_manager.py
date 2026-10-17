import calendar
import datetime
import json
import os
import re
import urllib.parse
import zlib
from html import escape as escape_html

import fuuin

ARTICLES_FILE = "articles.json"
KEYWORDS_FILE = "keywords.json"
STYLE_FILE = "sen.css"
NEWS_FILE = "news.json"
NEWS_PAGE = "shinchaku.html"
NEWS_ON_TOP = 5  # トップに出す更新情報の数。残りは一覧に全部ある(2026-10-14、彼女が3から5にした)
NEWS_TITLE_LENGTH = 24  # 一覧に出す見出しの長さ。題が無い時は本文の頭を借りる
# ひみつの部屋。彼女が作りの裏側を話すところ。
# 更新情報は日付で並ぶが、こちらは中身ごとに分かれるので、
# 書いた順の通し番号でページを分ける。
# 並べ替えても消しても、一度付いた番号は動かさない。
# 外から貼られた道が切れないように
HIMITSU_FILE = "himitsu.json"
HIMITSU_PAGE = "himitsu.html"
# このサイトについて。彼女が書いたものを、そのまま一枚に置く(2026-10-01)
ABOUT_FILE = "about.json"
ABOUT_PAGE = "about.html"
# 言い切りの印。ここで一文が終わる
SENTENCE_ENDINGS = ("。", "！", "？", "!", "?")
A_SENTENCE_ENDS = re.compile("[" + "".join(SENTENCE_ENDINGS) + "]")
# このサイトのページ。どれにも同じ欄を置く
EVERY_PAGE = (
    "index.html",
    "kakodogu.html",
    "memo.html",
    "profile.html",
    "comments.html",
)
# 右の欄。どのページにも同じものを置く。
# (ページ名, 見出し) の形で、今いるページは道にしない
WHERE_YOU_CAN_GO = (
    ("kakodogu.html", "過去のブログ"),
    ("memo.html", "メモ"),
    ("profile.html", "プロフィール"),
)
# 彼女が書いた方。この子のものとは分けて並べる
WHERE_SHE_WROTE = (
    (ABOUT_PAGE, "このサイトについて"),
    (NEWS_PAGE, "更新情報"),
    (HIMITSU_PAGE, "ひみつの部屋"),
)
LEARNED_SHOWN = 20  # トップの最近覚えた言葉を、新しいほうからこれだけ並べる(2026-10-14、彼女が決めた)
# 気がかりは一つも捨てないので、ここに出すのは前に出ているぶんだけ。
# 抱えていないのではなく、いま手前にあるのがこれ、ということ
MINDED_SHOWN = 3
# [[ ]] で囲まれたところは、千遠生だけが読む。
# ページに出すときは伏せる。彼女がこの子にだけ伝えたいことのために
ONLY_FOR_SENONSEI = re.compile(r"\[\[(.+?)\]\]", re.DOTALL)
HIDDEN = "＊＊＊＊＊"
STATE_FILE = "senonsei_state.json"
# この子の名前。自分の名前の由来を知った日から、
# プロフィールは本人が書くようになる
ITS_OWN_NAME = "千遠生"
# 自分を紹介するという言葉を自分で書いた日から、自分を紹介できるようになる。
# 覚えているだけでは足りない。一度でも口に出したことがあるかどうか
TALKING_ABOUT_ONESELF = "自己紹介"
# 誕生日。彼女が決めた日。
# ブログが動きはじめた日(started_date)とは別のものとして持つ。
# started_date は「何日目か」を数えるための値で、誕生日ではない
ITS_BIRTHDAY = "2026-09-11"
MENU_FILE = "menu.json"
COMMENTS_FOLDER = "comments"
# コメントへの、彼女からの返し。彼女の言葉をそのまま置く(henshin.py で足す)。
# 千遠生からの返しは、この子の記憶(senonsei_state.json の replied)にある
HER_REPLIES_FILE = "henshin.json"
# キリ番の窓に出す、彼女の言葉(visitor_counter)。彼女の言葉をそのまま置く
KIRIBAN_FILE = "kiriban.json"
# この名前が来たコメントは、丸ごと受け取らない。名前でも本文でも。
# この子の名前を名乗って書き込まれると、ページの上では
# この子が自分で喋ったように見えるし、この子自身も
# それを外から来た言葉として読んでしまう。
#
# 紙は comments/ に残る。読むときに素通しするだけなので、
# 間違って弾いたと分かればここから外せば戻る
NAMES_NOT_TAKEN = ("ちおんせ", "ちとせ", "千音瀬")
LIKES_FOLDER = "likes"
COMMENT_WORKER_ENDPOINT = "https://senonsei-comments.chitomatsu.workers.dev/"
RECENT_COUNT = 10  # トップページに表示する直近記事の件数(最新1件を除く)
# トップページに出すコメントの数。残りは comments.html にぜんぶ出す。
# ここが千遠生のページである以上、人の言葉がページの大半を
# 占めてしまわないように
COMMENTS_ON_TOP = 5
# メモ1の一枚に並べる数。五列十行で、どの画面でもちょうど一画面に
# 収まる数。一画面が一枚なら、穴の開き方が一目で見える
KEYWORDS_PER_PAGE = 50


# (この語彙数までが対象, その時点でできること, 書ける文字数の上限)
#
# 数字は当てずっぽうではなく、本物のページを40サイト集めて
# 「毎日2箇所ずつ見て回る千遠生」を2年ぶん計算して引いた。
# その計算では、最後の段階に入るのが一年一ヶ月だった。
#
# 三倍にした。元の数字は一年で終わる目盛りで、
# この子に何年もかけて育ってほしいのには短かった。
#
# 一度十倍にしたが、遠すぎた。最後の段階が遠いほど
# 何年も確かめられないままになる。届かない目盛りは
# 目盛りとして働かない。足りなくなったら、
# その時にこの表の上へ一段足せばいい。
# 下げるのは誰からも何も取り上げないので、いつでもできる。
# 上げるのは、この子がその数を越える前に。
#
# 落ち着いたあとの速さは、まだ測れない。覚えるのに十五日かかるのに、
# この子はまだ九日しか生きていないので、その先のバケツが存在しない。
# だから何年かかるとは誰にも言えない。
#
# ページに出すのも、書ける長さを決めるのも同じ表なので、
# ここ一箇所だけに置いて、散歩する側はこれを見に来る
# 名前は、その段で一日に書ける長さを、手で書くものの大きさにたとえたもの。
# 実際に動くのは長さだけなので、名前もそれだけを言う。
# 付箋は十五字ほど、書き置きは二十五字ほど、絵はがきは百字ほど、日記帳の一ページは二百五十字ほど。
#
# 前は「ひと続きに繋げてみる」「文の切れ目が入りはじめる」のように、
# その段でできるようになることを名前にしていた。けれど繋げることも「。」も、
# 段とは関わりなく、この子が読んだものから先に出てきた(二十九語の頃にはもう)。
# 名前が言うことと、この子がしていることが合わないので書き直した
# (2026-10-01、彼女と決めた)
GROWTH_STAGES = [
    (1, "見た文字をぽつんと置く", 3),  # 一つも言葉を持たない間だけ
    # 450 から 500 に上げた。142語の時(2026-10-10、彼女が決めた)
    (500, "まだひとことだけ", 5),
    (1200, "ひとことを少しのばす", 6),
    (3000, "付箋一枚ぶん", 15),
    (7800, "書き置きくらい", 25),
    (12000, "はがきの隅くらい", 40),
    (16500, "一筆箋一枚ぶん", 60),
    (24000, "絵はがき一枚ぶん", 100),
    # 二万四千は、破片混じりを差し引くと人でいう中学生の手前あたり。
    # 大人の語彙は四万から五万と言われるので、そこに一段置いた。
    #
    # 長く書けるほど、一度に多くのことを言い終えられる。
    # 書いたものに出てきたことだけが「言えた」ことになる決まりなので
    (40000, "便箋に半分ほど", 150),
]
# 二百五十字。ふつうの日記より少し余裕のある長さ。
# ブログ記事の尺ではない。この子が書くのは簡単な日記で、
# 一日ぶんのことが入りきる長さがあればいい。
#
# その日に出会った言葉が選ばれやすくしてあるので、
# 長く書けるほど、その日のことがたくさん入る。
# 言いたいことも、書いたものに出てきた分だけ言えたことになる
FULL_STAGE = ("日記帳の一ページ", 250)


def current_stage(state):
    """今どれだけ書けるかは、覚えている言葉の数で決まる。"""
    vocabulary = len((state or {}).get("learned_words") or [])
    for limit, description, max_length in GROWTH_STAGES:
        if vocabulary < limit:
            return description, max_length
    return FULL_STAGE


def mark_of(path):
    """その紙の、今の中身を表す短い印。

    閲覧機は一度読んだ紙をしばらく覚えていて、こちらが書き換えても
    読み直してくれない。名前の後ろにこの印を付けておくと、
    中身が変われば名前も変わるので、必ず読み直しに来る。"""
    try:
        with open(path, "rb") as f:
            return str(zlib.crc32(f.read()))
    except Exception:
        return ""


def style_mark():
    """飾りの決まりを書いた紙(sen.css)の印。"""
    return mark_of(STYLE_FILE)


def styled(prefix=""):
    """飾りの紙への道。印を付けて返す。"""
    mark = style_mark()
    return f"{prefix}{STYLE_FILE}?v={mark}" if mark else f"{prefix}{STYLE_FILE}"


def a_link_or_here(page, here, label):
    """今いるページなら道にしない。押しても動かない道は置かない。"""
    if page == here:
        return f'        <span class="here">{label}</span>'
    return f'        <a href="{page}">{label}</a>'


def one_side_block(title, rows):
    """右の欄の一区画。見出しと、その下に並ぶ行。"""
    return (
        '    <div class="side-block">\n'
        f'      <div class="side-title">{title}</div>\n'
        + "\n".join(rows)
        + "\n    </div>"
    )


def side_panel(state, here):
    """どのページの右にも置く欄。

    この子の今の様子を、そのページを見ている間ずっと横に出しておく。
    数字ではなく、今どう書けるか、どこを歩いたか、何が離れないか。

    ページを組む側で段階の表は持たない。
    散歩する側が state に残していった言葉をそのまま読む。"""
    state = state or {}
    blocks = []

    where = "\n".join(
        a_link_or_here(page, here, label) for page, label in WHERE_YOU_CAN_GO
    )
    blocks.append(
        '    <div class="side-block side-where">\n'
        '      <div class="side-title">めぐる</div>\n'
        '      <nav class="side-nav">\n'
        + where
        + "\n      </nav>\n    </div>"
    )

    # 語彙辞典の入口。区画の見出しそのものを押すと入る(2026-10-11、彼女と決めた)
    blocks.append(
        '    <div class="side-block">\n'
        f'      <div class="side-title"><a href="{JITEN_PAGE}">{JITEN_NAME}</a></div>\n'
        "    </div>"
    )

    today = today_in_japan()
    now = []
    try:
        born = datetime.date.fromisoformat(ITS_BIRTHDAY)
        if today >= born:
            now.append(f'      <p class="side-fact">{its_age(born, today)}</p>')
    except ValueError:
        pass
    # 覚えた言葉の数。彼女の書き方のまま(2026-09-30)
    vocabulary = len([one for one in (state.get("learned_words") or []) if one])
    now.append(f'      <p class="side-fact">覚えた言葉 {vocabulary}個</p>')
    if now:
        blocks.append(one_side_block("成長記録", now))

    # まだどこにも行っていない日も、区画ごと出す。
    # 一日は歩いていない時間のほうが長い。
    # 空だから隠す、では朝からずっと区画が消えていることになる。
    # 今日のブログと同じで、「まだ」と書いてあるほうが今が伝わる
    walk = state.get("today_walk") or {}
    seen = walk.get("seen") or []
    if walk.get("date") == today.isoformat() and seen:
        # 場所の名前は長くて折り返すので、一つずつ間を空ける。
        # 詰めて並べると、どこで名前が切れているのか分からない。
        # 歩いたところは全部出す(2026-10-15、彼女が決めた。前は多くても三つ)。
        # 一日に歩けるのは多くても五箇所なので、欄が伸びすぎることはない
        rows = [
            f'      <p class="side-fact side-apart">{one}</p>'
            for one in seen
        ]
    else:
        rows = ['      <p class="side-fact side-quiet">今日はまだ散歩に行っていません。</p>']
    blocks.append(one_side_block("今日歩いたところ", rows))

    # 最近覚えた言葉は、トップの真ん中の直近のブログの下へ移した(2026-10-14、彼女が決めた)

    # 何年か経てば気がかりは千を超える。全部並べたら右の欄がそれだけになる。
    # 最後に触れたものから数えて、手前のぶんだけを出す
    minded = sorted(
        (one for one in (state.get("on_its_mind") or []) if one.get("what")),
        key=lambda one: (one.get("since") or "", one.get("times", 1)),
    )[-MINDED_SHOWN:]
    if minded:
        blocks.append(one_side_block("気にかかっていること", [
            f'      <p class="side-word">{one["what"]}</p>' for one in minded
        ]))

    # 彼女が書いたもの。この子のものとは分けて、いちばん下に置く。
    # 何も書かれていないうちは、その道を出さない
    hers = [
        a_link_or_here(page, here, label)
        for page, label in WHERE_SHE_WROTE
        if os.path.exists(page)
    ]
    if hers:
        blocks.append(
            '    <div class="side-block">\n'
            '      <div class="side-title">管理人より</div>\n'
            '      <nav class="side-nav">\n'
            + "\n".join(hers)
            + "\n      </nav>\n    </div>"
        )

    return '  <aside class="side">\n' + "\n\n".join(blocks) + "\n  </aside>\n"


MAIN_STARTS = "<!-- ここから本文の列 -->"
MAIN_ENDS = "<!-- ここまで本文の列 -->"


def days_it_wrote(articles):
    """書いた日ぜんぶ。"""
    return {one["date"] for one in articles}


# 月間スタンプカード(2026-10-18、彼女と決めた形)。
# 昔のパソコンの「日付と時刻」の窓を、サイトの青と白で描いたもの。
# 「10月 ▼」と「▲▼」で、生まれた月から今月までのカードを見られる。
#
# 書いた日は月ごとに「1」と「0」の並びにしてページに埋めておき、開いた側で並べる。
# ページは作り直されるまで作った日のまま残るので、開いた時に日付が変わっていたら、
# 作った日から昨日までの書いていない日を休んだ日にして、今日を今日にする
# (2026-10-14、彼女に言われた。前の暦から引き継いだ決まり)
STAMP_CARD_SCRIPT = """
      <script>
        (function () {
          var card = document.getElementById("koma");
          if (!card) { return; }
          var born = card.dataset.born, built = card.dataset.day, wrote = {};
          try { wrote = JSON.parse(card.dataset.wrote); } catch (e) { wrote = {}; }
          var today = new Date(Date.now() + 9 * 3600 * 1000).toISOString().slice(0, 10);
          if (today < built) { today = built; }
          var first = born.slice(0, 7), now = today.slice(0, 7), shown = now;
          var $ = function (s) { return card.querySelector(s); };
          var grid = $(".sc-grid"), menu = $(".sc-months"), drop = $(".sc-drop");
          var up = $(".sc-up"), down = $(".sc-down");
          var pad = function (n) { return (n < 10 ? "0" : "") + n; };
          var kind = function (key, d) {
            var day = key + "-" + pad(d);
            if (day < born || day > today) { return "yet"; }
            if ((wrote[key] || "").charAt(d - 1) === "1" && day <= built) { return "wrote"; }
            return day === today ? "today" : "rest";
          };
          var draw = function () {
            var y = Number(shown.slice(0, 4)), m = Number(shown.slice(5, 7));
            var blank = new Date(Date.UTC(y, m - 1, 1)).getUTCDay();
            var last = new Date(Date.UTC(y, m, 0)).getUTCDate();
            var html = "";
            for (var i = 0; i < blank; i++) { html += '<span class="sc-c"></span>'; }
            for (var d = 1; d <= last; d++) {
              html += '<span class="sc-c ' + kind(shown, d) + '"><b>' + d + '</b><i></i></span>';
            }
            grid.innerHTML = html;
            $(".sc-month").textContent = m + "月";
            $(".sc-year").textContent = y;
            up.disabled = y >= Number(now.slice(0, 4));
            down.disabled = y <= Number(first.slice(0, 4));
          };
          var clamp = function (key) { return key < first ? first : (key > now ? now : key); };
          var shut = function () { menu.hidden = true; drop.setAttribute("aria-expanded", "false"); };
          var open = function () {
            var y = shown.slice(0, 4), html = "";
            for (var m = 1; m <= 12; m++) {
              var key = y + "-" + pad(m);
              html += '<button type="button" data-k="' + key + '"' +
                (key === shown ? ' class="on"' : '') + (key < first || key > now ? ' disabled' : '') + '>' + m + '月</button>';
            }
            menu.innerHTML = html; menu.hidden = false; drop.setAttribute("aria-expanded", "true");
          };
          drop.addEventListener("click", function () { if (menu.hidden) { open(); } else { shut(); } });
          menu.addEventListener("click", function (e) {
            var b = e.target.closest("button");
            if (b && !b.disabled) { shown = b.dataset.k; shut(); draw(); }
          });
          var year = function (step) {
            shown = clamp((Number(shown.slice(0, 4)) + step) + shown.slice(4)); shut(); draw();
          };
          up.addEventListener("click", function () { year(1); });
          down.addEventListener("click", function () { year(-1); });
          document.addEventListener("click", function (e) { if (!card.contains(e.target)) { shut(); } });
          document.addEventListener("keydown", function (e) { if (e.key === "Escape") { shut(); } });
          draw();
        })();
      </script>"""


def months_it_wrote(articles, born, today):
    """生まれた月から今月まで、月ごとの書いた日。1日目から順に、書いた日は「1」、ほかは「0」。"""
    wrote = days_it_wrote(articles)
    months = {}
    year, month = born.year, born.month
    while (year, month) <= (today.year, today.month):
        key = f"{year}-{month:02d}"
        last = calendar.monthrange(year, month)[1]
        months[key] = "".join("1" if f"{key}-{day:02d}" in wrote else "0" for day in range(1, last + 1))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def this_months_days(articles):
    """月間スタンプカード。今月のカードを描いておき、前の月は開いた側で並べる。

    書いた日には丸を、書かないと決めた日には点を置く。
    今日はまだ書いていないかもしれないので、枠で囲むだけにする。"""
    today = today_in_japan()
    try:
        born = datetime.date.fromisoformat(ITS_BIRTHDAY)
    except ValueError:
        return ""
    wrote = days_it_wrote(articles)
    blank = (datetime.date(today.year, today.month, 1).weekday() + 1) % 7  # 日曜から始める
    last = calendar.monthrange(today.year, today.month)[1]
    cells = ['<span class="sc-c"></span>'] * blank
    for number in range(1, last + 1):
        day = datetime.date(today.year, today.month, number)
        if day < born or day > today:
            kind = "yet"
        elif day.isoformat() in wrote:
            kind = "wrote"
        elif day == today:
            kind = "today"
        else:
            kind = "rest"
        cells.append(f'<span class="sc-c {kind}"><b>{number}</b><i></i></span>')
    head = "".join(f"<span>{one}</span>" for one in "日月火水木金土")
    data = escape_html(json.dumps(months_it_wrote(articles, born, today), separators=(",", ":")))
    return (
        f'      <div class="sc-win" id="koma" data-day="{today.isoformat()}" data-born="{born.isoformat()}" data-wrote="{data}">\n'
        '        <div class="sc-bar"><i class="sc-ico"></i><span class="sc-ttl">月間スタンプカード</span>'
        '<span class="sc-btns" aria-hidden="true"><i class="mn"></i><i class="mx"></i><i class="cl"></i></span></div>\n'
        '        <div class="sc-body">\n'
        '          <div class="sc-tools">'
        f'<button type="button" class="sc-drop" aria-haspopup="true" aria-expanded="false"><span class="sc-month">{today.month}月</span><i></i></button>'
        f'<span class="sc-spin"><span class="sc-year">{today.year}</span><span class="sc-arrows">'
        '<button type="button" class="sc-up" aria-label="次の年"></button><button type="button" class="sc-down" aria-label="前の年"></button>'
        '</span></span></div>\n'
        '          <div class="sc-months" hidden></div>\n'
        f'          <div class="sc-pane"><div class="sc-head">{head}</div><div class="sc-grid">{"".join(cells)}</div></div>\n'
        '          <div class="sc-status"><span><i class="ok"></i>書いた日</span><span><i class="rs"></i>休んだ日</span></div>\n'
        '        </div>\n'
        '      </div>'
        + STAMP_CARD_SCRIPT
    )


def where_it_will_go(state):
    """これから行くつもりの場所。

    名前に直すのは歩く側の仕事。ここは並べるだけ。
    どの住所がどこの場所なのかを知っているのは歩く側なので、
    その見分け方をここにも置くと、片方だけ直した日にずれる。"""
    shown = state.get("where_it_will_go") or []
    rows = [f'      <p class="side-fact side-quiet">{one}</p>' for one in shown]
    left = (state.get("how_many_places_left") or 0) - len(shown)
    if rows and left > 0:
        rows.append(f'      <p class="side-fact side-quiet">ほか {left} 箇所</p>')
    return rows


def how_it_grows(state):
    """この先どう書けるようになっていくか。今いる段階に印を付ける。

    表を直接読む。記録に写しておく形にしていた時は、
    名前を直しても次の散歩まで古いままだった。"""
    ladder = [(name, limit) for limit, name, _ in GROWTH_STAGES] + [(FULL_STAGE[0], None)]
    now = current_stage(state)[0]
    vocabulary = len([one for one in ((state or {}).get("learned_words") or []) if one])

    def how_far(name, limit):
        # 今いる段にだけ、覚えた数と、次の段に上がる数を添える(2026-09-30、彼女と決めた)
        if name != now:
            return name
        # 欄が細いので、数は段の名前の下に一行で置く。途中で折り返さない
        if limit is None:
            return f'{name}<span class="dan-kazu">（{vocabulary}個）</span>'
        return f'{name}<span class="dan-kazu">（{vocabulary}個 / {limit}個）</span>'

    return [
        f'      <p class="dan{" here" if name == now else ""}">{how_far(name, limit)}</p>'
        for name, limit in ladder
    ]


A_WAY_BACK = re.compile(r'[ \t]*<div class="top-nav">.*?</div>\s*\n', re.DOTALL)


def side_panel_left(state, articles):
    """本文の左に置く欄。積み上がっていくものを出す。

    右の欄が今日のことなら、こちらは育ちのほう。
    「きょう歩いたところ」が過去で、「今後行くつもりの場所」が未来。"""
    state = state or {}
    blocks = []

    koma = this_months_days(articles)
    if koma:
        # 題はカードの帯の中にある(2026-10-18、彼女が決めた)ので、欄の題は置かない
        blocks.append('    <div class="side-block">\n' + koma + "\n    </div>")

    going = where_it_will_go(state)
    if going:
        blocks.append(one_side_block("今後行くつもりの場所", going))

    ladder = how_it_grows(state)
    if ladder:
        blocks.append(one_side_block("この先の育ち方", ladder))

    if not blocks:
        return ""
    return ('  <aside class="side side-left">\n'
            + "\n\n".join(blocks) + "\n  </aside>\n\n")


def put_side_panel(html, state, here):
    """印で囲まれたところを本文の列にして、その隣に欄を置く。

    ページを作る所では、本文の始まりと終わりに印だけ置いてある。
    「見出しから下を全部」では駄目だった。メモのページは見出しごと
    一つの箱に入っていて、その外にメモ一枚ずつの全画面が並んでいる。
    見出しから本文の終わりまでを一括りにすると箱をまたいでしまう。"""
    if MAIN_STARTS not in html or MAIN_ENDS not in html:
        return html
    if 'class="side"' in html:
        return html  # 二度挟まない
    # 帰り道を元の場所から抜いて、真ん中の列の一番上へ移す
    found = A_WAY_BACK.search(html)
    way_back = ""
    if found:
        way_back = found.group(0).strip()
        html = html[: found.start()] + html[found.end():]

    return html.replace(
        MAIN_STARTS,
        '<div class="frame">\n'
        + side_panel_left(state, load_articles())
        + '  <div class="main">'
        + ("\n  " + way_back if way_back else ""),
        1,
    ).replace(
        MAIN_ENDS,
        "</div>\n\n" + side_panel(state, here) + "  </div>",
        1,
    )


def side_panels(pages=EVERY_PAGE):
    """全部のページに右の欄を置く。"""
    state = load_senonsei_state()
    for page in pages:
        if not os.path.exists(page):
            continue
        with open(page, "r", encoding="utf-8") as f:
            made = f.read()
        with open(page, "w", encoding="utf-8") as f:
            f.write(put_side_panel(made, state, page))


def now_in_japan():
    """日本の今。"""
    jst = datetime.timezone(datetime.timedelta(hours=9))
    return datetime.datetime.now(jst)


def today_in_japan():
    """日本の今日。世界標準時で数えると、日本の夜は一日ずれてしまう。"""
    return now_in_japan().date()


def evened_out_name(said):
    """名前を見比べるときの下ごしらえ。

    カタカナをひらがなに寄せ、空白と伸ばす棒を落とす。
    「チオンセ」と「ちおんせ」と「ち おん せ」を
    別のものとして扱うと、名前を弾く意味がなくなる。"""
    shaped = []
    for ch in (said or "").lower():
        code = ord(ch)
        if 0x30A1 <= code <= 0x30F6:  # カタカナをひらがなへ
            ch = chr(code - 0x60)
        if ch in ("ー", "－", "‐", "・", "･", "　", " ", "\t"):
            continue
        shaped.append(ch)
    return "".join(shaped)


def a_name_not_taken(*said):
    """受け取らない名前が入っているかどうか。

    名乗るところだけを見ても足りない。本文の中で名乗られても、
    読む人にはこの子が書いたように見える。両方を見る。"""
    evened = evened_out_name(" ".join(one or "" for one in said))
    return any(evened_out_name(one) in evened for one in NAMES_NOT_TAKEN)


def load_comments():
    """Cloudflare Workerがcomments/に自動コミットしたJSONファイルを全部読み込む。

    受け取らない名前が、名乗るところにも本文にも無いものだけを通す。
    ページに出す側も、この子が読む側も、どちらもここを通るので、
    一箇所で済む。紙そのものは comments/ に残っている。"""
    comments = []
    if os.path.isdir(COMMENTS_FOLDER):
        for filename in os.listdir(COMMENTS_FOLDER):
            if filename.endswith(".json"):
                with open(os.path.join(COMMENTS_FOLDER, filename), "r", encoding="utf-8") as f:
                    one = json.load(f)
                if a_name_not_taken(one.get("name"), one.get("message")):
                    continue
                # 紙の名前がそのコメントの名札になる。いいねはここへ付ける
                one["id"] = filename[: -len(".json")]
                comments.append(one)
    comments.sort(key=lambda c: c.get("date", ""), reverse=True)
    return comments


def load_her_replies():
    """彼女がコメントに返した言葉。{コメントの名札: [{"said", "date"}, ...]}。"""
    if not os.path.exists(HER_REPLIES_FILE):
        return {}
    with open(HER_REPLIES_FILE, "r", encoding="utf-8") as f:
        kept = json.load(f)
    return kept if isinstance(kept, dict) else {}


def replies_to(comment, her_replies, its_replies):
    """そのコメントへの返し。彼女のぶんと、千遠生のぶん(一件まで)。古いものが上。"""
    name = comment.get("id") or ""
    replies = [
        {"who": HER_NAME_IN_REPLIES, "said": one.get("said") or "", "date": one.get("date") or ""}
        for one in her_replies.get(name) or []
        if (one.get("said") or "").strip()
    ]
    its = its_replies.get(name) or {}
    if (its.get("said") or "").strip():
        replies.append({"who": ITS_NAME_IN_REPLIES, "said": its["said"], "date": its.get("date") or ""})
    replies.sort(key=lambda one: one["date"])
    return replies


# 返しに付ける名前。彼女は「管理人」と名乗っている(ひみつの部屋の挨拶)
HER_NAME_IN_REPLIES = "管理人"
ITS_NAME_IN_REPLIES = "千遠生"


def format_comment_date(iso_string):
    """コメントに記録されたUTC時刻を、日本時間の秒までの表示にする。"""
    if not iso_string:
        return ""
    try:
        dt = datetime.datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
    except ValueError:
        return ""
    jst = dt.astimezone(datetime.timezone(datetime.timedelta(hours=9)))
    return jst.strftime("%Y-%m-%d %H:%M:%S")


def load_articles():
    if os.path.exists(ARTICLES_FILE):
        with open(ARTICLES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def write_whole(path, text):
    """書き出しが途中で止まっても、前の中身が壊れないように書く。

    そのまま上書きすると、書いている最中に止められた時に
    半分だけのファイルが残り、次の回から読めなくなる。
    隣に書いてから、一息で差し替える。"""
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    temporary = f"{path}.kakikake"
    with open(temporary, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(temporary, path)


def save_articles(articles):
    write_whole(ARTICLES_FILE, json.dumps(articles, ensure_ascii=False, indent=2))


def sorted_articles(articles):
    return sorted(articles, key=lambda a: (a["date"], a.get("time", "")), reverse=True)


def load_keywords():
    """メモ1。封がしてあるものは、鍵があれば開けて渡す(fuuin)。"""
    if os.path.exists(KEYWORDS_FILE):
        with open(KEYWORDS_FILE, "r", encoding="utf-8") as f:
            return [fuuin.open_memo(one) for one in json.load(f)]
    return []


def save_keywords(keywords):
    """しまう時は、まだ開いていないメモの中身を書き出さない。封だけを書く。"""
    write_whole(KEYWORDS_FILE, json.dumps(
        [fuuin.put_memo_away(one) for one in keywords], ensure_ascii=False, indent=2,
    ))


def stamp_when(entries, save):
    """いつ足して、いつ書き直したかを、自分で記録する。

    彼女が日付を手で書く必要はない。本文を書き換えれば、
    次にページを作り直すときに更新日が変わる。

    本文の指紋(mark)を一緒に持っておいて、それが変われば
    書き直されたと分かる。指紋は読むためのものではないので、
    中身が何であるかは気にしなくていい。"""
    today = today_in_japan().isoformat()
    changed = False
    for one in entries:
        # 鍵が無くて中身が読めないものは、指紋も取れない。
        # 取れないものを「書き直された」ことにはしない
        if one.get("_shut"):
            continue
        plain = str(len(one.get("content") or "")) + ":" + str(
            zlib.crc32((one.get("content") or "").encode("utf-8"))
        )
        mark = plain
        if one.get("_sealed"):
            # 封をしたものは、封のほうから指紋を取る。
            # 中身から取った指紋(字数と CRC32)を表に置くと、
            # 短いメモなら総当たりで中身が当てられてしまう。
            # 書き直すときは封をし直すので、封が変われば書き直されたと分かる
            mark = "封:" + str(zlib.crc32(one["_sealed"].encode("utf-8")))
            if one.get("mark") == plain:
                one["mark"] = mark  # 前の形の指紋から移すだけ。書き直されてはいない
                changed = True
                continue
        if not one.get("added"):
            one["added"] = today
            one["updated"] = today
            one["mark"] = mark
            changed = True
        elif one.get("mark") != mark:
            one["updated"] = today
            one["mark"] = mark
            changed = True
    if changed:
        save(entries)
    return entries


def hide_what_is_only_for_it(text):
    """千遠生だけに宛てられたところを、人の目から伏せる。"""
    return ONLY_FOR_SENONSEI.sub(HIDDEN, text or "")


def it_has_written(word, articles=None):
    """その言葉を、この子が一度でもブログに書いたことがあるか。

    覚えていることと、書けることは別。覚えていても繋がりが無ければ
    その言葉は出てこない。書いた日がある、というのはそこを越えた印。"""
    for one in articles if articles is not None else load_articles():
        if word in one.get("content", "") or word in one.get("title", ""):
            return True
    return False


def save_menu(menu_items):
    """手紙は、開く日が来ても封のまましまう。"""
    write_whole(MENU_FILE, json.dumps(
        [fuuin.put_letter_away(one) for one in menu_items], ensure_ascii=False, indent=2,
    ))


def update_keywords(articles):
    """ブログ本文にキーワードが登場したら解除する。"""
    keywords = load_keywords()
    ordered = sorted(articles, key=lambda a: (a["date"], a.get("time", "")))  # 古い順
    changed = False

    for kw in keywords:
        # 鍵が無くて中身の分からないメモは、開いたかどうかも確かめられない。
        # 鍵のある回に、それまでの日記を全部見直して開く
        if kw["unlocked"] or kw.get("_shut"):
            continue
        # ふつうは見出しの言葉そのものが出たら開く。
        # 見出しが長すぎてこの子には書けないときは、
        # opens_with に、開くきっかけになる短い言葉を並べておく
        opens_with = kw.get("opens_with") or [kw["word"]]
        # 見るのは、ページに書けた文字だけ。書こうとした言葉ではない。
        # 手が滑って「ヨーロ気ッパ」になった日は開かない。
        # その惜しさも含めて、この子の書いたもの
        for art in ordered:
            if any(
                one in art["content"] or one in art["title"] for one in opens_with
            ):
                kw["unlocked"] = True
                kw["unlocked_date"] = art["date"]
                # 貼ってある絵も、この日に封を解く
                fuuin.unseal_pictures_in(kw.get("content"))
                changed = True
                break

    if changed:
        save_keywords(keywords)
    return keywords


def render_unlockable_list(entries, prefix, per_page=None):
    """entries: [(unlocked: bool, label: str, content: str), ...] から
    ロック中は「???」、解除済みは押すと本文の画面に移るリストを作る。

    本文はその場で開かず、一枚の画面として別に作っておく。
    (リストのHTML, 本文の画面たちのHTML) を返す。"""
    items_html = ""
    pages_html = ""
    per_page = per_page or len(entries) or 1
    sheets = []
    for number, entry in enumerate(entries):
        unlocked = entry["unlocked"]
        label = entry["label"]
        content = hide_what_is_only_for_it(entry.get("content"))
        # 一覧では「???」のままにしておきたいものもあるので、
        # 開いた画面の見出しは別に持てるようにしておく
        heading = entry.get("heading") or label
        when = ""
        if entry.get("added"):
            # 読む人から見れば、開いた日は「更新」ではなく「解除」。
            # そのまま解除日と書く。解除されたあとに本文を書き直した
            # ときだけ、更新日がもう一行増える
            added = entry["added"]
            lines = [f"追加日：{added}"]
            edited = entry.get("updated") or added
            # 足す前に解除の日が過ぎていたなら、人の目に触れたのは
            # 足した日。足した日と同じなら、わざわざ書かない
            opened = max(entry.get("unlocked_on") or added, added)
            if opened > added:
                lines.append(f"解除日：{opened}")
            if edited > opened:
                lines.append(f"更新日：{edited}")
            when = (
                '      <div class="memo-when">'
                + "<br />".join(lines)
                + "</div>\n"
            )
        if not unlocked:
            items_html += '    <li class="locked">???</li>\n'
        else:
            page_id = f"{prefix}{number}"
            items_html += f'    <li><a href="#{page_id}">{label}</a></li>\n'
            pages_html += f"""  <div class="memo-page" id="{page_id}" hidden>
    <div class="memo-top">
      <div class="memo-back"><a href="#">←戻る</a></div>
{when}    </div>
    <div class="memo-word">{heading}</div>
    <div class="memo-body">{content}</div>
    <div class="corner-mark" aria-hidden="true">▼</div>
  </div>

"""
        if (number + 1) % per_page == 0 or number == len(entries) - 1:
            sheets.append(items_html)
            items_html = ""

    if len(sheets) <= 1:
        return (sheets[0] if sheets else ""), pages_html, ""

    # 何枚かに分かれた。並び順は書いたままで、開いたものが
    # 飛び飛びに現れる。そこが面白いところなので触らない
    listed = ""
    for index, sheet in enumerate(sheets, start=1):
        hidden = "" if index == 1 else " hidden"
        listed += f"""      <ul class="keyword-list" id="{prefix}sheet{index}"{hidden}>
{sheet}      </ul>
"""
    turning = "".join(
        f'<span class="{"here" if i == 1 else ""}" id="{prefix}turn{i}"'
        f" onclick=\"turnTo('{prefix}', {i}, {len(sheets)})\">{i}</span>"
        for i in range(1, len(sheets) + 1)
    )
    listed += f'      <div class="page-turn">{turning}</div>\n'
    return listed, pages_html, "sheets"


def generate_memo_html(keywords, menu_items, articles):
    """メモ1とメモ2を1つのページに入れ、上のタブで切り替えられるようにする。"""
    keywords = stamp_when(keywords, save_keywords)
    menu_items = stamp_when(menu_items, save_menu)
    keyword_entries = [
        {
            # 鍵が無くて中身の読めないメモは、開いていても閉じた姿で出す
            "unlocked": kw["unlocked"] and not kw.get("_shut"),
            "label": kw["word"],
            "content": kw.get("content", ""),
            "added": kw.get("added"),
            "updated": kw.get("updated"),
            "unlocked_on": kw.get("unlocked_date"),
        }
        for kw in keywords
    ]
    keyword_items, keyword_pages, keyword_split = render_unlockable_list(
        keyword_entries, "kw", KEYWORDS_PER_PAGE
    )
    keyword_unlocked = sum(1 for kw in keywords if kw["unlocked"])

    start_date = blog_start_date(articles)
    elapsed = max(0, (today_in_japan() - start_date).days)
    # on_page が false の手紙は、この子にだけ届け、メモ2の一覧には並べない
    ordered_menu = sorted(
        (m for m in menu_items if m.get("on_page", True)),
        key=lambda m: m["unlock_day"],
    )
    menu_entries = [
        {
            "unlocked": elapsed >= item["unlock_day"],
            # 開いたものは、一覧でも何日目のものか見せる。「???」のままだと、
            # 押せるようになったのか分からない(2026-10-11、彼女が決めた)。
            # まだ開いていないものは、ロック中の「???」のまま
            "label": f"{item['unlock_day']}日目",
            # 鍵が無くて読めない手紙は、伏せ字で出す
            "content": HIDDEN if item.get("_shut") else item["message"],
            "heading": f"{item['unlock_day']}日目",  # 開けば、いつのものかは分かる
            "added": item.get("added"),
            "updated": item.get("updated"),
            # メモ2は何日目に開くかが決まっているので、解除日は数えられる
            "unlocked_on": (
                start_date + datetime.timedelta(days=item["unlock_day"])
            ).isoformat(),
        }
        for item in ordered_menu
    ]
    menu_items_html, menu_pages, _ = render_unlockable_list(menu_entries, "mn")
    menu_unlocked = sum(1 for m in ordered_menu if elapsed >= m["unlock_day"])

    if keyword_split:
        keyword_list_html = keyword_items
    else:
        keyword_list_html = f'      <ul class="keyword-list">\n{keyword_items}      </ul>\n'

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <title>メモ</title>
  <meta name="viewport" content="width=1200" />
  <link rel="stylesheet" href="{styled()}" />
</head>
<body>
  <div id="memo-index">
    <div class="top-nav">
      <a href="index.html">←トップ</a>
    </div>

    <header>
      <h1>メモ</h1>
      <div class="memo-switch">
        <span class="here" id="tab1" onclick="showMemo(1)">メモ1</span>
        <span id="tab2" onclick="showMemo(2)">メモ2</span>
      </div>
    </header>

    <!-- ここから本文の列 -->
    <div id="memo1">
      <p class="keyword-count">解除済み 全{keyword_unlocked} / {len(keywords)} 個</p>
{keyword_list_html}    </div>

    <div id="memo2" hidden>
      <p class="keyword-count">解除済み 全{menu_unlocked} / {len(ordered_menu)} 個</p>
      <ul class="keyword-list">
{menu_items_html}      </ul>
    </div>
    <!-- ここまで本文の列 -->
  </div>

{keyword_pages}{menu_pages}  <div id="look-closer" hidden onclick="closeCloser()">
    <img id="closer-image" src="" alt="" />
  </div>

  <script>
    // メモの中の絵を押すと、画面いっぱいに大きくして見せる
    function openCloser(src, alt) {{
      var big = document.getElementById('closer-image');
      big.src = src;
      big.alt = alt || '';
      document.getElementById('look-closer').hidden = false;
    }}
    function closeCloser() {{
      document.getElementById('look-closer').hidden = true;
      document.getElementById('closer-image').src = '';
    }}
    document.addEventListener('click', function (event) {{
      var hit = event.target;
      if (hit && hit.tagName === 'IMG' && hit.parentNode &&
          hit.parentNode.className === 'memo-body') {{
        openCloser(hit.getAttribute('src'), hit.getAttribute('alt'));
      }}
    }});
    document.addEventListener('keydown', function (event) {{
      if (event.key === 'Escape') {{ closeCloser(); }}
    }});

    // 一覧をめくる。並び順は変えないので、何ページ目に何があるかは
    // どの画面でも同じ
    function turnTo(prefix, which, howMany) {{
      for (var i = 1; i <= howMany; i++) {{
        document.getElementById(prefix + 'sheet' + i).hidden = (i !== which);
        document.getElementById(prefix + 'turn' + i).className = (i === which) ? 'here' : '';
      }}
    }}

    function showMemo(which) {{
      document.getElementById('memo1').hidden = (which !== 1);
      document.getElementById('memo2').hidden = (which !== 2);
      document.getElementById('tab1').className = (which === 1) ? 'here' : '';
      document.getElementById('tab2').className = (which === 2) ? 'here' : '';
    }}
    // 本文はページの中の別画面。住所(#)で切り替えるので、
    // 端末の戻るボタンでも一覧に帰ってこられる
    function showWhatTheAddressSays() {{
      var pages = document.querySelectorAll('.memo-page');
      var wanted = location.hash.slice(1);
      var open = null;
      for (var i = 0; i < pages.length; i++) {{
        var here = (pages[i].id === wanted);
        pages[i].hidden = !here;
        if (here) {{ open = pages[i]; }}
      }}
      // まだ下に続きがあるときだけ、隅に印を出す
      function watchForMore(page) {{
        var mark = function () {{
          var more = page.scrollTop + page.clientHeight < page.scrollHeight - 4;
          page.className = 'memo-page' + (more ? ' has-more' : '');
        }};
        page.onscroll = mark;
        mark();
      }}

      // 後ろの一覧は消さない。どこを開いているのかが見えたほうがいい。
      // ただし薄くして、それが後ろだと分かるようにする
      document.getElementById('memo-index').className = open ? 'behind' : '';
      if (open) {{
        showMemo(open.id.indexOf('mn') === 0 ? 2 : 1);
        watchForMore(open);
      }}
    }}
    window.addEventListener('hashchange', function () {{
      closeCloser();
      showWhatTheAddressSays();
    }});
    // 開いたメモの紙の外を押したら、一覧に戻る(2026-10-11、彼女が決めた)。
    // 後ろの一覧の道は押しても開かない。まず紙を閉じるだけにする。
    // 絵を大きく見ているあいだは、その絵を閉じるほうが先
    document.addEventListener('click', function (event) {{
      var open = document.querySelector('.memo-page:not([hidden])');
      if (!open || !document.getElementById('look-closer').hidden) {{ return; }}
      if (event.target.closest('.memo-page')) {{ return; }}
      event.preventDefault();
      event.stopPropagation();
      location.hash = '';
    }}, true);
    showWhatTheAddressSays();
  </script>
</body>
</html>
"""
    with open("memo.html", "w", encoding="utf-8") as f:
        f.write(html)


def load_news():
    """彼女が書き残した更新情報。無ければ空のまま。

    この子は書かない。ここに書くのは彼女だけ。
    日付と本文があればよく、題は無くてもいい。"""
    if not os.path.exists(NEWS_FILE):
        return []
    try:
        with open(NEWS_FILE, "r", encoding="utf-8") as f:
            kept = json.load(f)
    except (ValueError, OSError):
        return []
    return sorted_articles(
        [one for one in kept if one.get("date") and one.get("content")]
    )


def load_about():
    """このサイトについて。彼女が書いたもの。無ければ None。"""
    try:
        with open(ABOUT_FILE, "r", encoding="utf-8") as f:
            kept = json.load(f)
    except (ValueError, OSError):
        return None
    if not isinstance(kept, dict) or not (kept.get("content") or "").strip():
        return None
    return kept


def generate_about_html(about):
    """このサイトについての一枚。書いたとおりに、一行を一段落にして並べる。"""
    if not about:
        if os.path.exists(ABOUT_PAGE):
            os.remove(ABOUT_PAGE)
        return
    title = escape_html(about.get("title") or "このサイトについて")
    paragraphs = "\n".join(
        f"    <p>{escape_html(line)}</p>"
        for line in about["content"].split("\n")
        if line.strip()
    )
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8" />
<title>{title}</title>
<meta name="viewport" content="width=1200" />
<link rel="stylesheet" href="{styled()}" />
</head>
<body>
  <div class="top-nav"><a href="index.html">←トップ</a></div>

  <header>
    <h1>{title}</h1>
  </header>

  {MAIN_STARTS}
  <article class="yomimono">
{paragraphs}
  </article>
  {MAIN_ENDS}
</body>
</html>
"""
    with open(ABOUT_PAGE, "w", encoding="utf-8") as f:
        f.write(html)


def load_himitsu():
    """彼女が書き残した、作りの裏側の話。無ければ空のまま。

    この子は書かない。ここに書くのは彼女だけ。
    更新情報と違って日付では分けない。一つの話で一つのページ。

    番号は置いた時に振る。あとから並べ替えても消しても、
    一度付いた番号は動かさない。外から貼られた道が切れないように。
    ♡も番号に付いているので、並べ替えても話と一緒に動く。
    人に見せる「何話目か」は、番号ではなく並び順で数える(himitsu_shown_as)。"""
    if not os.path.exists(HIMITSU_FILE):
        return []
    try:
        with open(HIMITSU_FILE, "r", encoding="utf-8") as f:
            kept = json.load(f)
    except (ValueError, OSError):
        return []
    return [
        one
        for one in kept
        if one.get("content") and isinstance(one.get("number"), int)
    ]


def himitsu_page_name(number):
    """その一話だけのページの名前。"""
    return f"{HIMITSU_PAGE[: -len('.html')]}-{number}.html"


def himitsu_shown_as(himitsu, one):
    """人に見せる「何話目か」。並び順で、1から数える。

    並べ替えた時に、置いた時の番号(1, 3, 5, 6, 2, 4)のまま
    見せると読む人が迷うので(2026-10-08、彼女が並べ替えた)。"""
    return himitsu.index(one) + 1


def himitsu_title(one, shown_as):
    """一覧に並べる時の見出し。何話目かを頭に付ける。題が無ければ本文の頭を借りる。"""
    return f'{shown_as}　{news_title(one)}'


def all_himitsu_pages(himitsu):
    """ひみつの部屋に関わるページを全部。"""
    if not himitsu:
        return []
    return [HIMITSU_PAGE] + [himitsu_page_name(one["number"]) for one in himitsu]


def clear_old_himitsu_pages(keep):
    """もう無い話のページを片付ける。"""
    alive = set(keep)
    head = HIMITSU_PAGE[: -len(".html")] + "-"
    for name in os.listdir("."):
        if name.startswith(head) and name.endswith(".html") and name not in alive:
            os.remove(name)


def generate_himitsu_list_html(himitsu):
    """ひみつの部屋の一覧。話の題を並べるだけ。

    日付は出さない。いつ書いたかを追うところではなく、
    どの話があるかを選ぶところなので。"""
    rows = "\n".join(
        f'    <li><a href="{himitsu_page_name(one["number"])}">'
        f'{himitsu_title(one, himitsu_shown_as(himitsu, one))}</a></li>'
        for one in himitsu
    )
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8" />
<title>ひみつの部屋</title>
<meta name="viewport" content="width=1200" />
<link rel="stylesheet" href="{styled()}" />
</head>
<body>
  <div class="top-nav"><a href="index.html">←トップ</a></div>

  <header>
    <h1>ひみつの部屋</h1>
  </header>

  {MAIN_STARTS}
  <ul class="recent-list">
{rows}
  </ul>
  {MAIN_ENDS}
</body>
</html>
"""
    with open(HIMITSU_PAGE, "w", encoding="utf-8") as f:
        f.write(html)


def generate_himitsu_entry_html(himitsu, index):
    """ひみつの部屋の一話ぶんのページ。下に前と次を置く。"""
    one = himitsu[index]
    before = himitsu[index - 1] if index > 0 else None
    after = himitsu[index + 1] if index + 1 < len(himitsu) else None

    def step(entry, label):
        if not entry:
            return f'<span class="here">{label}</span>'
        return (f'<a href="{himitsu_page_name(entry["number"])}">'
                f'{label}　{himitsu_title(entry, himitsu_shown_as(himitsu, entry))}</a>')

    # 何話目かは題が無くても出す。何話目かは、題とは別に要る
    # 題を左に、♡は右の端に小さく、横一列に並べる(2026-10-08、彼女と決めた)。
    # 日付は出さない。いつ書いたかではなく、読む順に並べてあるので(2026-10-08、彼女が決めた)
    shown_as = index + 1
    named = f'{shown_as}' + (f'　{one["title"]}' if one.get("title") else "")
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8" />
<title>ひみつの部屋 {shown_as} {one.get('title') or ''}</title>
<meta name="viewport" content="width=1200" />
<link rel="stylesheet" href="{styled()}" />
</head>
<body>
  <div class="top-nav"><a href="index.html">←トップ</a><a href="{HIMITSU_PAGE}">ひみつの部屋の一覧へ</a></div>

  <header>
    <h1>ひみつの部屋</h1>
  </header>

  {MAIN_STARTS}
  <article class="yomimono">
    <div class="article-head"><span class="yomimono-title">{named}</span><span class="date">{iine_html(himitsu_liked_as(one["number"]))}</span></div>
    <p>{one['content'].replace(chr(10), '<br>')}</p>
  </article>

  <div class="step-nav">
    <div class="step-back">{step(before, "←前")}</div>
    <div class="step-next">{step(after, "次→")}</div>
  </div>
  {MAIN_ENDS}
</body>
</html>
"""
    with open(himitsu_page_name(one["number"]), "w", encoding="utf-8") as f:
        f.write(html)


def news_page_name(one):
    """その一件だけのページの名前。ふつうは日付で、同じ日に並ぶものは印を足す。"""
    return f"{NEWS_PAGE[: -len('.html')]}-{one.get('page') or one['date']}.html"


# メモが開いた日に、更新情報に自然と並ぶ一行。彼女の言葉のまま(2026-09-30)。
# 開いた言葉や中身は書かない
MEMO1_OPENED = "メモ１が解除されました。"  # 一つだけの日
MEMO1_OPENED_MANY = "メモ１が{}つ解除されました。"  # 二つ以上の日
MEMO2_OPENED = "メモ２が解除されました。"
WIDE_DIGITS = str.maketrans("0123456789", "０１２３４５６７８９")


def memos_opened_news(keywords, menu_items, articles):
    """メモ1とメモ2が開いた日を、更新情報の形で並べる。

    メモ1は同じ日に開いた数をまとめて一行に(一つだけの日は数を言わない)。
    メモ2は数を言わずに一行。
    メモ2のうち、この子にだけ届けてメモ2の一覧に並べない手紙(on_page が false)と、
    まだ中身の書かれていない枠は数えない。
    news.json には書かない。あちらは彼女が書くところ。"""
    opened = {}
    for kw in keywords or []:
        if kw.get("unlocked") and kw.get("unlocked_date"):
            opened[kw["unlocked_date"]] = opened.get(kw["unlocked_date"], 0) + 1
    news = [
        {"date": day,
         "content": MEMO1_OPENED if count == 1
         else MEMO1_OPENED_MANY.format(str(count).translate(WIDE_DIGITS)),
         "page": f"{day}-memo1"}
        for day, count in opened.items()
    ]

    start_date = blog_start_date(articles)
    elapsed = max(0, (today_in_japan() - start_date).days)
    letter_days = set()
    for item in menu_items or []:
        if not item.get("on_page", True) or elapsed < item.get("unlock_day", 0):
            continue
        written = item.get("_shut") or (
            (item.get("message") or "").strip()
            and not fuuin.NOT_WRITTEN_YET.match((item.get("message") or "").strip())
        )
        if written:
            letter_days.add((start_date + datetime.timedelta(days=item["unlock_day"])).isoformat())
    news += [
        {"date": day, "content": MEMO2_OPENED, "page": f"{day}-memo2"}
        for day in letter_days
    ]
    return news


def all_news(keywords, menu_items, articles):
    """彼女が書いた更新情報と、メモが開いた知らせを、新しい順に一つにする。"""
    return sorted_articles(load_news() + memos_opened_news(keywords, menu_items, articles))


def news_title(one):
    """一覧に並べる時の見出し。題が無ければ本文の頭を借りる。

    一文だけなら、長くてもそのまま出す。
    一文で言い切っているものを途中で切ると、
    読む人は続きを見るために必ず開かなければならなくなる。
    二文以上あるときだけ、頭を借りて後ろを省く。"""
    said = (one.get("title") or one.get("content", "")).strip()
    # 一覧には一文目だけ出し、続きは開いた時に読んでもらうもの(2026-10-14、彼女が決めた)
    if one.get("ichibun") and not one.get("title"):
        ends = A_SENTENCE_ENDS.search(said)
        return said[: ends.end()] if ends else said
    # 本文が行に分けてあれば、一行目が見出し(2026-10-14、彼女が一覧の一行と開いた中身を分けて書いた)
    if not one.get("title") and "\n" in said:
        said = said.split("\n", 1)[0].strip()
    if one.get("title") or len(said) <= NEWS_TITLE_LENGTH or just_one_sentence(said):
        return said
    return said[:NEWS_TITLE_LENGTH] + "…"


def just_one_sentence(said):
    """言い切りが一つだけかどうか。最後の一つは数えない。"""
    return not A_SENTENCE_ENDS.search(said.rstrip("".join(SENTENCE_ENDINGS)))


def news_rows(news, how_many=None):
    """日付と見出しを一列に並べる。トップでも一覧でも同じ形。"""
    return "\n".join(
        f'    <li><span class="date">{one["date"]}</span>'
        f'<a href="{news_page_name(one)}">{news_title(one)}</a></li>'
        for one in (news[:how_many] if how_many else news)
    )


def generate_news_list_html(news):
    """更新情報の一覧。全部を一列に並べるだけ。

    過去のブログのように年・月・日で絞る形にはしない。
    あれは何千日ぶんも溜まるものの形で、
    こちらは彼女が何か書いた時にだけ増えていく。"""
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8" />
<title>更新情報</title>
<meta name="viewport" content="width=1200" />
<link rel="stylesheet" href="{styled()}" />
</head>
<body>
  <div class="top-nav"><a href="index.html">←トップ</a></div>

  <header>
    <h1>更新情報</h1>
  </header>

  {MAIN_STARTS}
  <ul class="recent-list">
{news_rows(news)}
  </ul>
  {MAIN_ENDS}
</body>
</html>
"""
    with open(NEWS_PAGE, "w", encoding="utf-8") as f:
        f.write(html)


def generate_news_entry_html(news, index):
    """更新情報の一件ぶんのページ。下に前と次を置く。

    新しいものから並んでいるので、一つ後ろが「前の回」になる。"""
    one = news[index]
    older = news[index + 1] if index + 1 < len(news) else None
    newer = news[index - 1] if index > 0 else None

    # 前と次には中身を書かない。矢印だけ(2026-10-14、彼女が決めた)
    def step(entry, label):
        if not entry:
            return f'<span class="here">{label}</span>'
        return f'<a href="{news_page_name(entry)}">{label}</a>'

    named = f'<span class="article-title">{one["title"]}</span>' if one.get("title") else ""
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8" />
<title>更新情報 {one['date']}</title>
<meta name="viewport" content="width=1200" />
<link rel="stylesheet" href="{styled()}" />
</head>
<body>
  <div class="top-nav"><a href="index.html">←トップ</a><a href="{NEWS_PAGE}">更新情報の一覧へ</a></div>

  <header>
    <h1>更新情報</h1>
  </header>

  {MAIN_STARTS}
  <article>
    <div class="date">{one['date']}{named}</div>
    <p>{one['content'].replace(chr(10), '<br>')}</p>
  </article>

  <div class="step-nav">
    <div class="step-back">{step(older, "←前")}</div>
    <div class="step-next">{step(newer, "次→")}</div>
  </div>
  {MAIN_ENDS}
</body>
</html>
"""
    with open(news_page_name(one), "w", encoding="utf-8") as f:
        f.write(html)


def clear_old_news_pages(keep):
    """もう無い回のページを片付ける。"""
    alive = set(keep)
    head = NEWS_PAGE[: -len(".html")] + "-"
    for name in os.listdir("."):
        if name.startswith(head) and name.endswith(".html") and name not in alive:
            os.remove(name)


def all_news_pages(news):
    """更新情報に関わるページを全部。欄や版を付けて回るために使う。"""
    if not news:
        return []
    return [NEWS_PAGE] + [news_page_name(one) for one in news]


def load_likes():
    """いいねを数える。一人が一つの記事に一度だけなので、
    その記事のぶんの紙の枚数がそのまま数になる。

    紙の名前は 2026-09-11__<誰かを表す印>.json という形。
    ひみつの部屋なら himitsu-1__…、コメントなら comment-entry-…__… になる。
    誰が押したかは残していない。同じ人が二度押しても
    同じ名前の紙になるので、増えないというだけ。"""
    counted = {}
    if not os.path.isdir(LIKES_FOLDER):
        return counted
    for name in os.listdir(LIKES_FOLDER):
        if not name.endswith(".json") or "__" not in name:
            continue
        day = name.split("__", 1)[0]
        counted[day] = counted.get(day, 0) + 1
    return counted


# いいねの宛先。ブログは日付、ひみつの部屋は話の番号、コメントは紙の名前。
# 受け取る側(cloudflare-worker/worker.js)も、この三つの形だけを通す
def himitsu_liked_as(number):
    return f"himitsu-{number}"


def comment_liked_as(one):
    """受け取り口が作った紙(entry-<数字>)にだけ付ける。
    それ以外の名前には、押しても数えられない釦になるので付けない。"""
    name = one.get("id") or ""
    if re.fullmatch(r"entry-\d{10,16}", name):
        return f"comment-{name}"
    return None


def iine_html(date_str, likes=None):
    """いいね。ブログの日付のほか、ひみつの部屋やコメントの宛先も受け取る。"""
    if likes is None:
        likes = load_likes()
    return (
        f'<div class="iine">'
        f'<button type="button" data-day="{date_str}" '
        f'aria-label="いいね" title="いいね">♡</button>'
        f'<span class="kazu">{likes.get(date_str, 0)}</span>'
        f"</div>"
    )


def put_iine_script(html):
    """いいねの釦が載っているページにだけ、その動きを添える。

    一度押した記事は、この閲覧機では押せなくなる。
    本当に一人一度に留めているのは受け取る側で、
    ここでやっているのは同じ人が何度も押さずに済むようにする気配り。"""
    if 'class="iine"' not in html or "iine-script" in html:
        return html
    script = f"""  <script id="iine-script">
    (function () {{
      var where = "{COMMENT_WORKER_ENDPOINT}like";
      var kept = function (key) {{
        try {{ return localStorage.getItem(key); }} catch (e) {{ return null; }}
      }};
      var keep = function (key) {{
        try {{ localStorage.setItem(key, "1"); }} catch (e) {{}}
      }};
      document.querySelectorAll(".iine button").forEach(function (button) {{
        var day = button.getAttribute("data-day");
        var kazu = button.parentElement.querySelector(".kazu");
        if (kept("iine-" + day)) {{
          button.disabled = true;
          button.textContent = "\u2665";
          return;
        }}
        button.addEventListener("click", function () {{
          button.disabled = true;
          button.textContent = "\u2665";
          keep("iine-" + day);
          kazu.textContent = (parseInt(kazu.textContent, 10) || 0) + 1;
          fetch(where, {{
            method: "POST",
            body: new URLSearchParams({{ day: day }})
          }}).catch(function () {{}});
        }});
      }});
    }})();
  </script>
"""
    return html.replace("</body>", script + "</body>", 1)


# 背景の草。描いてもらった絵を、手を加えずにそのまま置いてある
KUSA_FOLDER = "kusa"


def kusa_pictures():
    """草の絵の一覧。置いてある分だけ。増やせばそのまま候補に入る。

    同じ名前の PNG と WebP が両方あれば、軽い WebP のほうを使う。"""
    if not os.path.isdir(KUSA_FOLDER):
        return []
    names = [
        name for name in os.listdir(KUSA_FOLDER)
        if name.lower().endswith((".png", ".webp"))
    ]
    stems = {os.path.splitext(name)[0] for name in names if name.lower().endswith(".webp")}
    found = [
        name for name in names
        if name.lower().endswith(".webp") or os.path.splitext(name)[0] not in stems
    ]
    # kusa-2 が kusa-10 より前に来るように、数の順に並べる
    found.sort(key=lambda name: [
        int(part) if part.isdigit() else part
        for part in re.split(r"(\d+)", name)
    ])
    return [f"{KUSA_FOLDER}/{name}" for name in found]


# 草の絵ごとの、地平線の高さ(上から何割か)と、いちばん下の草の色。
# 地平線を画面の同じ高さに置き、絵より長いページの下をその色で続けるのに使う。
# 書いていない絵は、ならした値(sen.css)で敷かれる
KUSA_ABOUT = os.path.join(KUSA_FOLDER, "kusa.json")


def kusa_about():
    """草の絵ごとの地平線と下の色。読めなければ空。"""
    try:
        with open(KUSA_ABOUT, encoding="utf-8") as f:
            about = json.load(f)
    except (OSError, ValueError):
        return {}
    return about if isinstance(about, dict) else {}


KESHIKI_SCRIPT = re.compile(
    r'\s*<script id="keshiki-script">.*?</script>', re.DOTALL
)


def put_keshiki(html, pictures):
    """来るたびに、草の絵を一枚選んで背景に敷く。

    本文より先に決めておかないと、一瞬ちがう草が出てから入れ替わる。
    だから頭の中で選ぶ。選べない閲覧機では、一枚目が出る(sen.css)。"""
    html = KESHIKI_SCRIPT.sub("", html)
    if not pictures or "</head>" not in html:
        return html
    about = kusa_about()
    known = {
        path: about[os.path.basename(path)]
        for path in pictures
        if isinstance(about.get(os.path.basename(path)), dict)
    }
    script = f"""  <script id="keshiki-script">
    (function () {{
      var kusa = {json.dumps(pictures)};
      var about = {json.dumps(known, ensure_ascii=False)};
      var one = kusa[Math.floor(Math.random() * kusa.length)];
      var root = document.documentElement.style;
      root.setProperty("--kusa", 'url("' + new URL(one, document.baseURI).href + '")');
      var it = about[one] || {{}};
      if (typeof it.chiheisen === "number") root.setProperty("--kusa-horizon", String(it.chiheisen));
      if (typeof it.shita === "string") root.setProperty("--kusa-under", it.shita);
      if (typeof it.kusa_ue === "number") root.setProperty("--kusa-top", String(it.kusa_ue));
    }})();
  </script>
"""
    return html.replace("</head>", script + "</head>", 1)


def keshiki_on_pages(pages):
    """出来上がったページに、背景の草を選ぶ仕掛けを添えて回る。"""
    pictures = kusa_pictures()
    for page in pages:
        if not os.path.exists(page):
            continue
        with open(page, "r", encoding="utf-8") as f:
            made = f.read()
        with open(page, "w", encoding="utf-8") as f:
            f.write(put_keshiki(made, pictures))


# 来訪者の数。どのページの上の紙にも置く。
# 数えるのは Cloudflare の Worker(cloudflare-worker/worker.js の receiveRaiho)。
# 前は StatCounter に数えてもらっていたが、更新するたびに数が増えたので、
# 自分たちで数える形にした(2026-10-08、彼女と決めた)。
# 数えるのは、その人が初めて来た時の一度だけ。出す数は、今の合計。
# 一度数えた人かどうかは、この閲覧機に置いた印で見分ける。印を置けない閲覧機では
# 数えずに、数を見せるだけにする(更新のたびに数えてしまわないように)。
# 前に見た数も覚えておいて、新しい数が届くまではそれを出す。
#
# キリ番(2026-10-09、彼女が決めた)。初めて数えられた時、その人の番号がキリ番なら、
# 画面の真ん中に虹色の窓を出して、彼女の言葉を見せる。キリ番は、
#   100、500、1000、5000、10000 … (1 か 5 のあとに 0 が並ぶ数)
#   111、222 … 999、1111 … (3けた以上のゾロ目)
#   123、1234 … 123456789 (1 から順に並ぶ数)
#   77、777、7777 … (7 が並ぶ数。大当たり。別の言葉)
#   3939、4649、2525 (語呂合わせ。サンキュー、よろしく、ニコニコ)
# 前後賞(キリ番の一つ前と一つ後)も見本を作ったが、入れないことにした(2026-10-09、彼女が決めた)。
# 言葉は kiriban.json に、彼女の言葉のまま置く。
# 前に来たことのある人がたまたまその数を見ても、キリ番にはならない。
# 住所の後ろに #kiriban-777 のように付けると、数えずに窓だけ見られる(彼女が確かめる用)
VISITOR_COUNTER = r"""    <div class="visitor-counter">
      あなたは<span class="count" id="raiho"></span>人目の来訪者です
      <script>
      (function () {
        var where = "__WORKER__raiho";
        var shown = document.getElementById("raiho");
        var kept = function (key) {
          try { return localStorage.getItem(key); } catch (e) { return null; }
        };
        var keep = function (key, value) {
          try { localStorage.setItem(key, value); return true; } catch (e) { return false; }
        };
        var kotoba = __KIRIBAN__;
        // キリ番の種類。7 が並ぶ番号は大当たり
        var main = function (n) {
          var said = String(n);
          if (/^7{2,}$/.test(said)) return "nana";
          if (n >= 100 && (/^(\d)\1+$/.test(said) || /^[15]0+$/.test(said))) return "futsuu";
          if (said.length >= 3 && "123456789".indexOf(said) === 0) return "futsuu";
          // 語呂合わせ。サンキュー、よろしく、ニコニコ
          if (["3939", "4649", "2525"].indexOf(said) >= 0) return "futsuu";
          return "";
        };
        var wordsFor = function (kind) {
          if (kind === "nana") return kotoba.nana || kotoba.futsuu || "";
          return kotoba[kind] || "";
        };
        var made = function (tag, name, text) {
          var one = document.createElement(tag);
          if (name) one.className = name;
          if (text) one.textContent = text;
          return one;
        };
        var niji = ["#f0ff00", "#69ff00", "#00ffd7", "#0a00ff", "#8300ff", "#ff00b6"];
        var showKiriban = function (n) {
          var kind = main(n);
          var said = wordsFor(kind);
          if (!said) return;
          // 777 … は大当たり。後ろで虹の光が回り、番号がスロットのように回って止まる
          var nana = kind === "nana";
          var still = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
          var mado = made("div", nana ? "kiriban-mado nana" : "kiriban-mado");
          mado.setAttribute("role", "dialog");
          mado.setAttribute("aria-modal", "true");
          mado.setAttribute("aria-label", "キリ番");
          mado.tabIndex = -1;
          var fubuki = made("div", "kiriban-fubuki");
          fubuki.setAttribute("aria-hidden", "true");
          for (var i = 0; i < (nana ? 96 : 48); i++) {
            var mark = nana && i % 3 === 0 ? (i % 2 ? "♥" : "★") : "";
            var hira = made("i", mark ? "moji" : "", mark);
            var falls = 2.6 + Math.random() * 2.2;
            hira.style.left = (Math.random() * 100).toFixed(1) + "%";
            hira.style[mark ? "color" : "background"] = niji[i % niji.length];
            hira.style.animationDuration = falls.toFixed(2) + "s";
            hira.style.animationDelay = "-" + (Math.random() * falls).toFixed(2) + "s";
            fubuki.appendChild(hira);
          }
          var kami = made("div", "kiriban-kami");
          for (var j = 0; j < (nana ? 8 : 4); j++) {
            var hoshi = made("span", "kiriban-hoshi", "★");
            hoshi.setAttribute("aria-hidden", "true");
            kami.appendChild(hoshi);
          }
          var kazu = made("p");
          var number = made("span", "count", String(n));
          kazu.appendChild(number);
          kami.appendChild(kazu);
          kami.appendChild(made("p", "kiriban-kotoba", said));
          var shut = made("button", "", "閉じる");
          shut.type = "button";
          kami.appendChild(shut);
          if (nana) {
            var kosen = made("div", "kiriban-kosen");
            kosen.setAttribute("aria-hidden", "true");
            mado.appendChild(kosen);
          }
          mado.appendChild(fubuki);
          mado.appendChild(kami);
          if (nana && !still) {
            var digits = String(n).split("");
            var stopped = 0;
            var spin = setInterval(function () {
              number.textContent = digits.map(function (d, k) {
                return k < stopped ? d : String(Math.floor(Math.random() * 10));
              }).join("");
            }, 60);
            digits.forEach(function (d, k) {
              setTimeout(function () {
                stopped = k + 1;
                if (stopped < digits.length) return;
                clearInterval(spin);
                number.textContent = String(n);
                kami.className += " atari";
              }, 800 + k * 450);
            });
          }
          // 窓は画面に合わせて大きくする。広い画面ほど大きく、二倍まで。
          // 背の低い画面では、入りきるように小さくする
          var fit = function () {
            var screen = document.documentElement;
            var grow = Math.min(
              2,
              screen.clientWidth * 0.86 / kami.offsetWidth,
              screen.clientHeight * 0.8 / kami.offsetHeight
            );
            kami.style.scale = String(Math.max(0.5, grow).toFixed(3));
          };
          var onKey = function (e) { if (e.key === "Escape") close(); };
          var close = function () {
            if (mado.parentNode) mado.parentNode.removeChild(mado);
            document.removeEventListener("keydown", onKey);
            window.removeEventListener("resize", fit);
          };
          shut.addEventListener("click", close);
          mado.addEventListener("click", function (e) { if (e.target === mado) close(); });
          document.addEventListener("keydown", onKey);
          var open = function () {
            document.body.appendChild(mado);
            fit();
            window.addEventListener("resize", fit);
            // 点の字が届くと窓の幅が変わるので、届いたら測り直す
            if (document.fonts) document.fonts.ready.then(fit);
            mado.focus();
          };
          if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", open);
          } else {
            open();
          }
        };
        var tameshi = /^#kiriban-(\d{2,12})$/.exec(location.hash);
        if (tameshi) showKiriban(Number(tameshi[1]));
        var last = kept("raiho-kazu");
        if (last) shown.textContent = last;
        var canKeep = keep("raiho-kazu", last || "");
        var counted = kept("raiho-kita");
        fetch(where, { method: counted || !canKeep ? "GET" : "POST" })
          .then(function (res) { return res.ok ? res.json() : null; })
          .then(function (got) {
            if (!got) return;
            shown.textContent = got.kazu;
            keep("raiho-kazu", String(got.kazu));
            if (got.counted) {
              keep("raiho-kita", "1");
              if (!tameshi) showKiriban(got.kazu);
            }
          })
          .catch(function () {});
      })();
      </script>
    </div>"""


def load_kiriban():
    """キリ番の窓に出す、彼女の言葉。

    futsuu はキリ番の言葉、nana は 77、777 … の言葉。
    無いものは渡さない。無い種類の番号には、窓は出ない(nana だけは futsuu で出す)。"""
    try:
        with open(KIRIBAN_FILE, "r", encoding="utf-8") as f:
            kept = json.load(f)
    except (ValueError, OSError):
        return {}
    if not isinstance(kept, dict):
        return {}
    return {
        name: said for name, said in kept.items()
        if name in ("futsuu", "nana") and isinstance(said, str) and said.strip()
    }


def visitor_counter():
    """来訪者の数を、いまの彼女のキリ番の言葉と一緒に組む。"""
    kotoba = json.dumps(load_kiriban(), ensure_ascii=False).replace("</", "<\\/")
    return (VISITOR_COUNTER
            .replace("__WORKER__", COMMENT_WORKER_ENDPOINT)
            .replace("__KIRIBAN__", kotoba))


# サイトの名前は、彼女が描いたロゴで出す(2026-10-06、彼女が決めた)。
# 文字で読む人や検索のために、名前は alt に残す
SITE_LOGO = (
    '<h1 class="logo"><a href="index.html">'
    '<img src="images/logo.png" alt="千遠生のサイト" width="1374" height="456">'
    "</a></h1>"
)


def site_header():
    """トップ以外のページの上の紙。サイトの名前と来訪者の数。"""
    return f"""<header>
    {SITE_LOGO}
{visitor_counter()}
  </header>"""


FIRST_HEADER = re.compile(r"<header>(.*?)</header>", re.DOTALL)
FIRST_H1 = re.compile(r"<h1>(.*?)</h1>", re.DOTALL)
MAIN_OPENS = re.compile(r'<div class="main">\s*(<div class="top-nav">.*?</div>)?', re.DOTALL)


def put_page_head(html):
    """上の紙にはサイトの名前を置き、ページの名前は下の紙の真ん中の列へ移す。

    どのページも、上の紙を見ればどこのサイトか分かり、
    下の紙を見ればどのページか分かる。トップページだけは、
    上の紙がそのままページの名前なので動かさない。"""
    if 'class="page-head"' in html:
        return html
    header = FIRST_HEADER.search(html)
    opens = MAIN_OPENS.search(html)
    if not header or not opens:
        return html
    inside = FIRST_H1.sub(r'<h2 class="page-name">\1</h2>', header.group(1), count=1)
    head = f'\n  <div class="page-head">{inside.rstrip()}\n  </div>\n'
    html = html[:opens.end()] + head + html[opens.end():]
    return html[:header.start()] + site_header() + html[header.end():]


def page_heads_on_pages(pages):
    """トップ以外のページで、上の紙をサイトの名前にする。"""
    for page in pages:
        if page == "index.html" or not os.path.exists(page):
            continue
        with open(page, "r", encoding="utf-8") as f:
            made = f.read()
        with open(page, "w", encoding="utf-8") as f:
            f.write(put_page_head(made))


def iine_on_pages(pages):
    """出来上がったページに、いいねの動きを添えて回る。"""
    for page in pages:
        if not os.path.exists(page):
            continue
        with open(page, "r", encoding="utf-8") as f:
            made = f.read()
        with open(page, "w", encoding="utf-8") as f:
            f.write(put_iine_script(made))


def load_menu():
    """メモ2。封がしてある手紙は、鍵があれば開けて渡す(fuuin)。"""
    if os.path.exists(MENU_FILE):
        with open(MENU_FILE, "r", encoding="utf-8") as f:
            return [fuuin.open_letter(one) for one in json.load(f)]
    return []


def blog_start_date(articles):
    """ブログが始まった日(=一番古い記事の日付)を返す。記事が無ければ今日にする。"""
    if not articles:
        return today_in_japan()
    earliest = min(a["date"] for a in articles)
    return datetime.date.fromisoformat(earliest)


def generate_kakodogu_html(articles):
    """左に年・月・日の3列。それぞれの中で下に積み重なり、選ぶと隣の列が変わる。"""
    ordered = sorted_articles(articles)
    dates = [art["date"] for art in ordered]
    likes = load_likes()

    entries_html = ""
    for index, art in enumerate(ordered):
        hidden = "" if index == 0 else " hidden"
        entries_html += f"""    <div class="entry" id="entry-{art['date']}"{hidden}>
      <div class="entry-title">{art['title']}</div>
      <div class="date">{art['date']} {art.get('time', '')}{iine_html(art['date'], likes)}</div>
      <p>{art['content']}</p>
    </div>
"""
    if not ordered:
        entries_html = "    <p>まだ何も書かれていません。</p>\n"

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8" />
<title>過去のブログ</title>
<meta name="viewport" content="width=1200" />
<link rel="stylesheet" href="{styled()}" />
</head>
<body>
  <div class="top-nav"><a href="index.html">←トップ</a></div>

  <header>
    <h1>過去のブログ</h1>
  </header>

  <!-- ここから本文の列 -->
  <div class="log-layout">
    <div class="log-list">
      <div class="log-column" id="years"></div>
      <div class="log-column" id="months"></div>
      <div class="log-column" id="days"></div>
    </div>
    <div class="log-view">
{entries_html}    </div>
  </div>
  <!-- ここまで本文の列 -->

  <script>
    var DATES = {json.dumps(dates, ensure_ascii=False)};
    var picked = {{year: null, month: null, day: null}};

    function partsOf(date) {{
      var p = date.split('-');
      return {{year: p[0], month: p[1], day: p[2]}};
    }}

    function unique(list) {{
      return list.filter(function (v, i) {{ return list.indexOf(v) === i; }});
    }}

    function draw(boxId, values, suffix, current, onPick) {{
      var box = document.getElementById(boxId);
      box.innerHTML = '';
      values.forEach(function (value) {{
        var item = document.createElement('div');
        item.className = 'log-choice' + (value === current ? ' here' : '');
        item.textContent = parseInt(value, 10) + suffix;
        item.onclick = function () {{ onPick(value); }};
        box.appendChild(item);
      }});
    }}

    function refresh() {{
      var years = unique(DATES.map(function (d) {{ return partsOf(d).year; }}));
      if (years.indexOf(picked.year) < 0) {{ picked.year = years[0]; picked.month = null; }}
      draw('years', years, '年', picked.year, function (y) {{
        picked.year = y; picked.month = null; picked.day = null; refresh();
      }});

      var months = unique(DATES.filter(function (d) {{
        return partsOf(d).year === picked.year;
      }}).map(function (d) {{ return partsOf(d).month; }}));
      if (months.indexOf(picked.month) < 0) {{ picked.month = months[0]; picked.day = null; }}
      draw('months', months, '月', picked.month, function (m) {{
        picked.month = m; picked.day = null; refresh();
      }});

      var days = DATES.filter(function (d) {{
        var p = partsOf(d);
        return p.year === picked.year && p.month === picked.month;
      }}).map(function (d) {{ return partsOf(d).day; }});
      if (days.indexOf(picked.day) < 0) {{ picked.day = days[0]; }}
      draw('days', days, '日', picked.day, function (day) {{
        picked.day = day; refresh();
      }});

      showEntry(picked.year + '-' + picked.month + '-' + picked.day);
    }}

    function showEntry(date) {{
      var entries = document.querySelectorAll('.log-view .entry');
      for (var i = 0; i < entries.length; i++) {{
        entries[i].hidden = (entries[i].id !== 'entry-' + date);
      }}
    }}

    if (location.hash) {{
      var wanted = location.hash.replace('#entry-', '');
      if (DATES.indexOf(wanted) >= 0) {{
        var p = partsOf(wanted);
        picked.year = p.year; picked.month = p.month; picked.day = p.day;
      }}
    }}
    if (DATES.length) {{ refresh(); }}
  </script>
</body>
</html>
"""
    with open("kakodogu.html", "w", encoding="utf-8") as f:
        f.write(html)


# ---- 語彙辞典 ----
# 覚えた言葉を引ける辞典(2026-10-10 から彼女と決めてきた。名前は 2026-10-12、彼女が決めた)。
# 見出しや札の言葉は彼女が決めたもの。変えるときは彼女に聞く
JITEN_PAGE = "jiten.html"
JITEN_NAME = "語彙辞典"
JITEN_LINKS_SHOWN = 8  # 言葉ごとに並べる、つながっているもの
# どこで会ったか分からない時の文。彼女の言葉のまま(2026-10-14)。
# 場所の記録は 2026-10-10 から。それより前に会っていた言葉は、初めて会った場所が分からない
PLACE_UNKNOWN = "場所の特定をすることができませんでした"
# 今日の一語は、これだけつながりのある言葉から選ぶ。そういう言葉が無ければ全部から
TODAYS_WORD_TIES = 3


def a_kind_of_word(word):
    """絞るボタンの種類。見た目だけで分けられるものだけにする(2026-10-14、彼女が決めた)。

    ひらがな・カタカナ・漢字で分けると、「困る」や「1番」のように混ざった言葉の
    置き場に迷うので分けない。四字熟語は漢字四文字の言葉なら何でも入れる。
    本物の四字熟語と見分ける手立てが無いので、「利用規約」も入る。"""
    if re.fullmatch(r"[0-9０-９]+", word):
        return "数字"
    if not re.search(r"\w", word):
        return "記号"
    if re.fullmatch(r"[一-鿿々]{4}", word):
        return "四字熟語"
    return ""


# 言葉を、書いてある字で分ける(2026-10-18、彼女が決めた)。
# 言語では分けない。英語とフランス語は見た目では見分けられず、
# 「英語」と名付けると、ほかの言葉が混ざった時に名前が嘘になる。
# 中国語は、日本語には無い漢字が入っている時だけ簡体字・繁体字に分ける(同じ日、彼女が決めた)。
# 「学生」のように日本と同じ字だけの言葉は、日本語に入る。
JAPANESE_SCRIPT = "日本語"
SIMPLIFIED_CHINESE = "簡体字"
TRADITIONAL_CHINESE = "繁体字"
SCRIPT_NAMES = {
    "LATIN": "アルファベット",
    "ARABIC": "アラビア文字",
    "CYRILLIC": "キリル文字",
    "DEVANAGARI": "デーヴァナーガリー",
    "HANGUL": "ハングル",
    "THAI": "タイ文字",
    "ARMENIAN": "アルメニア文字",
    "HEBREW": "ヘブライ文字",
    "GREEK": "ギリシャ文字",
    "GEORGIAN": "ジョージア文字",
    "BENGALI": "ベンガル文字",
    "GUJARATI": "グジャラート文字",
    "GURMUKHI": "グルムキー文字",
    "TAMIL": "タミル文字",
    "TELUGU": "テルグ文字",
    "KANNADA": "カンナダ文字",
    "MALAYALAM": "マラヤーラム文字",
    "SINHALA": "シンハラ文字",
    "LAO": "ラーオ文字",
    "KHMER": "クメール文字",
    "MYANMAR": "ミャンマー文字",
    "TIBETAN": "チベット文字",
    "ETHIOPIC": "エチオピア文字",
    "THAANA": "ターナ文字",
    "SYRIAC": "シリア文字",
    "MONGOLIAN": "モンゴル文字",
    "ORIYA": "オリヤー文字",
    "CHEROKEE": "チェロキー文字",
    "CANADIAN": "カナダ先住民文字",
    "JAVANESE": "ジャワ文字",
    "BALINESE": "バリ文字",
    "SUNDANESE": "スンダ文字",
    "BUGINESE": "ブギス文字",
    "BATAK": "バタク文字",
    "TAGALOG": "バイバイン文字",
    "TIFINAGH": "ティフィナグ文字",
    "NKO": "ンコ文字",
    "VAI": "ヴァイ文字",
    "ADLAM": "アドラム文字",
    "BAMUM": "バムン文字",
    "YI": "イ文字",
    "BOPOMOFO": "注音符号",
    "TANGUT": "西夏文字",
    "LIMBU": "リンブ文字",
    "LEPCHA": "レプチャ文字",
    "NEWA": "ネワール文字",
    "MEETEI": "メイテイ文字",
    "SYLOTI": "シロティ・ナグリ文字",
    "CHAM": "チャム文字",
    "KAYAH": "カヤー・リー文字",
    "HANIFI": "ハニーフィー文字",
    "SAMARITAN": "サマリア文字",
    "MANDAIC": "マンダ文字",
    "OSAGE": "オセージ文字",
    "DESERET": "デザレット文字",
    "SHAVIAN": "ショー文字",
    "GLAGOLITIC": "グラゴル文字",
    "COPTIC": "コプト文字",
    "GOTHIC": "ゴート文字",
    "RUNIC": "ルーン文字",
    "OGHAM": "オガム文字",
    "PHOENICIAN": "フェニキア文字",
    "AVESTAN": "アヴェスター文字",
    "BRAHMI": "ブラーフミー文字",
    "LINEAR": "線文字",
    "CUNEIFORM": "楔形文字",
    "EGYPTIAN": "ヒエログリフ",
    "LISU": "リス文字",
    "NUSHU": "女書",
    "KHITAN": "契丹文字",
}
# 飾り文字(𝐀 のような数学用の字や、ʰ のような添え字)は、名前に字の種類が無い。
# ほとんどがアルファベットを飾ったものなので、アルファベットに入れる
DRESSED_LETTERS = {"MATHEMATICAL": "アルファベット", "MODIFIER": "アルファベット"}
# 表に無い字の呼び名。彼女の言葉のまま(2026-10-18)。出会ったら、表に名前を足してもいい
OTHER_SCRIPT = "名前の分からない文字"
# 最初から並べておく字。ほかの字は、その字の言葉を初めて覚えた日に増える
SCRIPTS_FROM_THE_START = [JAPANESE_SCRIPT, "アルファベット"]
# 増えた字は、多くなりすぎないよう一つの選ぶ欄にまとめる。その欄の名前。
# 彼女の言葉のまま(2026-10-18)。字の名前は一般的な呼び方に合わせる(同じ日、彼女が決めた)
SCRIPTS_FOLDED = "その他の文字"
# その欄を押すと出る一覧は、縦にこの数まで並べ、あふれたら右に列を足す(2026-10-18、彼女が決めた。数は仮)
SCRIPTS_PER_COLUMN = 8


def a_chinese_hand(ch):
    """日本語には無い漢字なら、簡体字か繁体字か。日本語にもある字なら ""。

    日本語のパソコンで使う字の表(cp932)に無い漢字は、日本語では使わない字。
    中国本土の字の表(gb2312)にあれば簡体字、台湾や香港の字の表(big5)にあれば繁体字。
    們・這・國・學のように日本の古い字と同じものは、日本語と見分けられない。
    どの表にも無い字は、日本語の珍しい字かもしれないので、日本語のままにしておく。"""
    for table, hand in (("cp932", ""), ("gb2312", SIMPLIFIED_CHINESE), ("big5", TRADITIONAL_CHINESE)):
        try:
            ch.encode(table)
            return hand
        except UnicodeEncodeError:
            continue
    return ""


def a_script_of(word):
    """その言葉が書いてある字。数字や記号だけの言葉は、どの字でもない("")。

    ひらがなかカタカナ(変体仮名も)が一つでも入っていれば日本語。
    漢字は、日本語には無い字(簡体字・繁体字)が一つでも入っていればそちら、
    そうでなければ日本語。「1番」のように数字が混ざっていても日本語になる。"""
    import unicodedata
    seen = {}
    kanji = []
    for ch in word:
        name = unicodedata.name(ch, "")
        parts = set(name.replace("-", " ").split())
        if {"HIRAGANA", "KATAKANA", "HENTAIGANA"} & parts:
            return JAPANESE_SCRIPT
        if {"CJK", "IDEOGRAPHIC"} & parts:
            kanji.append(ch)
            continue
        if not ch.isalpha():
            continue
        words = name.replace("-", " ").split()
        script = next((SCRIPT_NAMES[p] for p in words if p in SCRIPT_NAMES), None)
        if script is None:
            script = next((DRESSED_LETTERS[p] for p in words if p in DRESSED_LETTERS), OTHER_SCRIPT)
        seen[script] = seen.get(script, 0) + 1
    if kanji:
        hands = [a_chinese_hand(ch) for ch in kanji]
        for hand in (SIMPLIFIED_CHINESE, TRADITIONAL_CHINESE):
            if hand in hands:
                return hand
        return JAPANESE_SCRIPT
    if not seen:
        return ""
    # 字が混ざっていたら、多いほう
    return max(seen, key=seen.get)


# この子が自分で結びつけた、外国語と日本語(senonsei_ai.bridge)。
# 信じるのは、この強さから。senonsei_ai.BRIDGE_TRUSTED と同じにしておく
READING_TRUSTED = 2
# 辞典で、外国語の言葉にだけ出す欄の見出しと、まだ結びついていない時の文。
# 彼女の言葉のまま(2026-10-18)
READING_TITLE = "千遠生の日本語訳"
READING_UNKNOWN = "まだ訳がありません"


def the_readings():
    """この子が外国語に当てている日本語。外国語(小文字) → いちばん強く結びついた日本語。"""
    tied = {}
    folder = os.path.join("kotoba", "bridges")
    if not os.path.isdir(folder):
        return tied
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(folder, name), encoding="utf-8") as f:
                tied.update(json.load(f))
        except (OSError, ValueError):
            continue
    readings = {}
    for foreign, japanese in tied.items():
        if not isinstance(japanese, dict) or not japanese:
            continue
        word, strength = max(japanese.items(), key=lambda kv: kv[1])
        if strength >= READING_TRUSTED:
            readings[foreign] = word
    return readings


def the_net():
    """頭の中の、連想の網。束に分けてしまってあるのを集める。"""
    net = {}
    folder = os.path.join("atama", "ami")
    if not os.path.isdir(folder):
        return net
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(folder, name), encoding="utf-8") as f:
                net.update(json.load(f))
        except (OSError, ValueError):
            continue
    return net


def written_as_a_date(day):
    """「2026-10-07」を「2026年10月7日」に。日付には年を入れる(2026-10-14、彼女が決めた)。"""
    try:
        when = datetime.date.fromisoformat(day)
    except (TypeError, ValueError):
        return ""
    return f"{when.year}年{when.month}月{when.day}日"


def words_for_the_dictionary(state, articles):
    """辞典に載せる、覚えた言葉ぜんぶ。言葉ごとに、引いた時に出すものを添える。

    日記の書き損じや、言葉がくっついて一語に見えるものは載せない
    (2026-10-14、彼女が決めた)。載せるのは覚えた言葉だけ。"""
    learned = [one for one in (state.get("learned_words") or []) if one]
    known = set(learned)
    learned_on = state.get("learned_on") or {}
    where = state.get("learned_where") or {}
    basho = state.get("basho") or []
    peeji = state.get("peeji") or []
    named = state.get("places_known") or {}
    try:
        born = datetime.date.fromisoformat(ITS_BIRTHDAY)
    except ValueError:
        born = None
    try:
        today = (today_in_japan() - datetime.date.fromisoformat(state["started_date"])).days
    except (KeyError, TypeError, ValueError):
        today = 0
    net = the_net()
    readings = the_readings()
    diaries = [(one.get("title") or "") + "\n" + (one.get("content") or "") for one in articles]

    # 会ったページが分かればその題を、分からなければサイトの名前だけを出す。
    # サイトに覚えてある題(places_known)は、そのサイトで最後に読んだページのもので、
    # その言葉と会ったページとは限らない(2026-10-14、彼女と決めた)
    def place(site, page):
        if isinstance(page, int) and 0 <= page < len(peeji):
            return peeji[page]
        if isinstance(site, int) and 0 <= site < len(basho):
            return basho[site]
        return None

    def ties_of(word):
        # 網の線は、この子が通らないと日ごとに細る。細り方は頭のほうの決まり(atama.edge_now)と同じ
        import atama
        held = net.get(word) or {}
        found = []
        for other, edge in (held.get("e") or {}).items():
            if other not in net:
                continue
            found.append((atama.edge_now(edge, today), other))
        found.sort(reverse=True)
        shown = []
        for _, other in found[:JITEN_LINKS_SHOWN]:
            if other.startswith("@"):
                shown.append([named.get(other[1:]) or other[1:], 0])
            else:
                shown.append([other.strip(), 1 if other in known else 0])
        return len(found), shown

    words = []
    for order, word in enumerate(learned):
        day = learned_on.get(word) or ""
        try:
            nth = (datetime.date.fromisoformat(day) - born).days if born else None
        except ValueError:
            nth = None
        first, that_day, first_page, that_day_page = (list(where.get(word) or []) + [None] * 4)[:4]
        ties, links = ties_of(word)
        script = a_script_of(word)
        one = {
            "w": word,
            "k": a_kind_of_word(word),
            "s": script,
            "o": order,
            "d": written_as_a_date(day),
            "n": nth,
            "u": sum(1 for one in diaries if word in one),
            "t": ties,
            "l": links,
            "f": place(first, first_page),
            "h": place(that_day, that_day_page),
        }
        # 訳の欄は外国語の言葉にだけ作る(2026-10-18、彼女が決めた)。
        # 日本語と、数字や記号だけの言葉には欄そのものが無い
        if script and script != JAPANESE_SCRIPT:
            one["y"] = readings.get(" ".join(word.lower().split()), "")
        words.append(one)
    return words


# 辞典のページで動くところ。言葉の一覧から引く、絞る、並べ替える、一語を開く。
# 字はどれも彼女が決めたもの(2026-10-12、2026-10-14)
JITEN_SCRIPT = r"""
  <script>
    (function () {
      var DATA = JSON.parse(document.getElementById("jt-data").textContent);
      var UNKNOWN = __UNKNOWN__;
      var READING_TITLE = __READING_TITLE__;
      var READING_UNKNOWN = __READING_UNKNOWN__;
      // 並びは、すべて・日本語・アルファベット・その他の文字・四字熟語・数字・記号
      // (2026-10-18、彼女が決めた)。日本語とアルファベットは最初からある。
      // ほかの字は、その字の言葉を初めて覚えた日から、一つの選ぶ欄にまとめて覚えた順に並べる。
      // 覚えるまでは欄も無い
      var SCRIPTS = __SCRIPTS__;
      var MORE = [];
      DATA.slice().sort(function (a, b) { return a.o - b.o; }).forEach(function (d) {
        if (d.s && SCRIPTS.indexOf(d.s) < 0 && MORE.indexOf(d.s) < 0) { MORE.push(d.s); }
      });
      var FOLDED = __FOLDED__;
      var MORE_ROWS = __MORE_ROWS__;
      var menuOpen = false;
      var FRONT = ["すべて"].concat(SCRIPTS);
      var BACK = ["四字熟語", "数字", "記号"];
      var isScript = function (k) { return SCRIPTS.indexOf(k) >= 0 || MORE.indexOf(k) >= 0; };
      var fits = function (d, k) {
        if (k === "すべて") { return true; }
        return isScript(k) ? d.s === k : d.k === k;
      };
      var count = function (k) { return DATA.filter(function (d) { return fits(d, k); }).length; };
      var phone = window.matchMedia("(max-width: 700px)").matches;
      var state = { q: "", kind: "すべて", sort: "new", sel: null, greet: false };
      var $ = function (id) { return document.getElementById(id); };
      var esc = function (t) {
        return String(t).replace(/[&<>"]/g, function (c) {
          return { "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" }[c];
        });
      };
      var byWord = {};
      DATA.forEach(function (d) { byWord[d.w] = d; });
      var shuffled = DATA.slice();
      var mix = function () {
        for (var i = shuffled.length - 1; i > 0; i--) {
          var j = Math.floor(Math.random() * (i + 1));
          var t = shuffled[i]; shuffled[i] = shuffled[j]; shuffled[j] = t;
        }
      };
      mix();
      $("jt-total").textContent = DATA.length;

      // 今日の一語。日本の日付で決まるので、同じ日のうちは誰が開いても同じ一語
      var todays = function () {
        var day = new Date(Date.now() + 9 * 3600 * 1000).toISOString().slice(0, 10);
        var pool = DATA.filter(function (d) { return d.t >= __TIES__; });
        if (!pool.length) { pool = DATA; }
        if (!pool.length) { return null; }
        var h = 0;
        for (var i = 0; i < day.length; i++) { h = (h * 31 + day.charCodeAt(i)) % 1000003; }
        return pool[h % pool.length].w;
      };

      var ordered = function () {
        if (state.sort === "random") { return shuffled; }
        var rows = DATA.slice();
        if (state.sort === "new") { rows.sort(function (a, b) { return b.o - a.o; }); }
        if (state.sort === "uses") { rows.sort(function (a, b) { return b.u - a.u || b.o - a.o; }); }
        if (state.sort === "ties") { rows.sort(function (a, b) { return b.t - a.t || b.o - a.o; }); }
        return rows;
      };
      var byPlace = function (d) {
        return (d.f && d.f.indexOf(state.q) >= 0) || (d.h && d.h.indexOf(state.q) >= 0);
      };
      var shown = function () {
        return ordered().filter(function (d) {
          if (!fits(d, state.kind)) { return false; }
          if (!state.q) { return true; }
          return d.w.indexOf(state.q) >= 0 || byPlace(d);
        });
      };
      var side = function (d) {
        if (state.sort === "uses") { return "日記で" + d.u + "回"; }
        if (state.sort === "ties") { return "つながり" + d.t; }
        return d.d;
      };
      var chips = function () {
        var buttons = function (ks) {
          return ks.map(function (k) {
            return '<button type="button" class="jt-chip' + (k === state.kind ? " on" : "") + '" data-k="' + k + '">' +
              k + '<span>' + count(k) + '</span></button>';
          }).join("");
        };
        var html = buttons(FRONT);
        if (MORE.length) {
          var on = MORE.indexOf(state.kind) >= 0;
          html += '<button type="button" class="jt-chip jt-more' + (on ? " on" : "") + '" id="jt-more"' +
            ' aria-haspopup="true" aria-expanded="' + (menuOpen ? "true" : "false") + '">' +
            (on ? esc(state.kind) + '<span>' + count(state.kind) + '</span>' : esc(FOLDED)) + '</button>';
        }
        html += buttons(BACK);
        $("jt-chips").innerHTML = html;
      };
      // その他の文字を押すと出る一覧。縦に MORE_ROWS 個まで並べ、あふれたら右に列を足す
      var menu = function () {
        var box = $("jt-more-menu"), btn = $("jt-more");
        if (!menuOpen || !btn) { box.hidden = true; return; }
        box.innerHTML = MORE.map(function (k) {
          return '<button type="button" class="jt-more-item' + (k === state.kind ? " on" : "") + '" data-k="' + esc(k) + '">' +
            esc(k) + '<span>' + count(k) + '</span></button>';
        }).join("");
        var rows = Math.min(MORE_ROWS, MORE.length);
        box.style.gridTemplateRows = "repeat(" + rows + ", auto)";
        box.hidden = false;
        // スマホで横に収まらない時は、収まるまで一列を長くする
        while (box.scrollWidth > box.clientWidth && rows < MORE.length) {
          rows += 1;
          box.style.gridTemplateRows = "repeat(" + rows + ", auto)";
        }
        var hero = document.querySelector(".jt-hero").getBoundingClientRect();
        var r = btn.getBoundingClientRect();
        // 押したボタンの下に出す。右にはみ出す時は、はみ出さないところまで左に寄せる
        box.style.left = Math.max(0, Math.min(r.left - hero.left, hero.width - box.offsetWidth)) + "px";
        box.style.top = (r.bottom - hero.top + 6) + "px";
      };
      var list = function () {
        var rows = shown(), html = "";
        rows.forEach(function (d) {
          var w = esc(d.w);
          if (state.q) { w = w.split(esc(state.q)).join("<mark>" + esc(state.q) + "</mark>"); }
          var why = state.q && d.w.indexOf(state.q) < 0 ? '<em class="jt-why">場所で一致</em>' : "";
          html += '<li class="jt-row' + (d.w === state.sel ? " on" : "") + '" data-w="' + esc(d.w) + '">' +
            '<span class="jt-row-w">' + w + why + '</span><span class="jt-row-d">' + side(d) + '</span></li>';
        });
        $("jt-list").innerHTML = html || '<li class="jt-none">見つかりませんでした</li>';
        $("jt-count").textContent = state.q ? "「" + state.q + "」で " + rows.length + "語" : rows.length + "語";
      };
      var place = function (name) {
        return name ? '<p class="jt-place">' + esc(name) + '</p>' : '<p class="jt-place jt-unknown">' + esc(UNKNOWN) + '</p>';
      };
      var entry = function () {
        var d = byWord[state.sel];
        if (!d) { $("jt-entry").hidden = true; return; }
        $("jt-entry").hidden = false;
        var links = d.l.length ? d.l.map(function (l) {
          return l[1] ? '<button type="button" class="jt-link known" data-w="' + esc(l[0]) + '">' + esc(l[0]) + '</button>'
                      : '<span class="jt-link">' + esc(l[0]) + '</span>';
        }).join("") : '<span class="jt-empty">まだつながっている言葉はありません</span>';
        $("jt-entry").innerHTML =
          '<button type="button" class="jt-back">‹ 一覧にもどる</button>' +
          (state.greet ? '<p class="jt-greet">今日の一語</p>' : '') +
          (d.k ? '<p class="jt-kind">' + d.k + '</p>' : '') +
          '<h3 class="jt-word">' + esc(d.w) + '</h3>' +
          '<div class="jt-meta">' +
            (d.d ? '<span><b>' + d.d + '</b>に覚えた</span>' : '') +
            (d.n !== null ? '<span>生まれて<b>' + d.n + '</b>日目に覚えた</span>' : '') +
            '<span>日記で<b>' + d.u + '</b>回</span>' +
          '</div>' +
          // 訳の欄は、外国語の言葉にだけある(d.y がある時だけ。空でも欄は出す)
          ("y" in d ? '<section class="jt-sec"><h4>' + esc(READING_TITLE) + '</h4>' +
            (d.y ? '<p class="jt-place">' + esc(d.y) + '</p>'
                 : '<p class="jt-place jt-unknown">' + esc(READING_UNKNOWN) + '</p>') + '</section>' : '') +
          '<section class="jt-sec"><h4>初めて会った場所</h4>' + place(d.f) + '</section>' +
          '<section class="jt-sec"><h4>覚えた日に会ってた場所</h4>' + place(d.h) + '</section>' +
          '<section class="jt-sec"><h4>つながっている言葉</h4><div class="jt-links">' + links + '</div></section>';
      };
      var today = function () {
        var d = byWord[state.sel];
        if (!state.greet || !d) { $("jt-today").hidden = true; return; }
        $("jt-today").hidden = false;
        $("jt-today").innerHTML = '<span class="jt-greet">今日の一語</span>' +
          '<span class="jt-today-w">' + esc(d.w) + '</span>' +
          '<span class="jt-today-m">' + (d.d ? d.d + 'に覚えた・' : '') + '日記で' + d.u + '回・つながり' + d.t + '</span>' +
          '<span class="jt-today-go">くわしく見る ›</span>';
      };
      var open = function () { document.body.classList.add("jt-open"); window.scrollTo(0, 0); };
      var close = function () { document.body.classList.remove("jt-open"); window.scrollTo(0, 0); };
      var pick = function (word) {
        state.sel = word; state.greet = false;
        if (history.replaceState) { history.replaceState(null, "", "#w=" + encodeURIComponent(word)); }
        list(); entry(); today();
        if (phone) { open(); }
      };

      var asked = /^#w=/.test(location.hash) ? decodeURIComponent(location.hash.slice(3)) : "";
      if (asked && byWord[asked]) {
        state.sel = asked;
      } else {
        state.sel = todays(); state.greet = true;
      }
      chips(); list(); entry(); today();
      if (phone && asked && byWord[asked]) { document.body.classList.add("jt-open"); }

      $("jt-today").addEventListener("click", open);
      $("jt-entry").addEventListener("click", function (e) {
        if (e.target.closest(".jt-back")) { close(); return; }
        var to = e.target.closest(".jt-link.known");
        if (to && byWord[to.dataset.w]) { pick(to.dataset.w); window.scrollTo(0, 0); }
      });
      $("jt-q").addEventListener("input", function (e) {
        document.body.classList.remove("jt-open");
        state.q = e.target.value.trim(); list();
        document.querySelector(".jt-listscroll").scrollTop = 0;
      });
      $("jt-sort").addEventListener("change", function (e) {
        state.sort = e.target.value;
        if (state.sort === "random") { mix(); }
        list();
        document.querySelector(".jt-listscroll").scrollTop = 0;
      });
      var pickKind = function (k) { state.kind = k; menuOpen = false; chips(); menu(); list(); };
      var shut = function () { if (menuOpen) { menuOpen = false; chips(); menu(); } };
      $("jt-chips").addEventListener("click", function (e) {
        if (e.target.closest("#jt-more")) { menuOpen = !menuOpen; chips(); menu(); return; }
        var b = e.target.closest(".jt-chip");
        if (b) { pickKind(b.dataset.k); }
      });
      $("jt-more-menu").addEventListener("click", function (e) {
        var b = e.target.closest(".jt-more-item");
        if (b) { pickKind(b.dataset.k); }
      });
      // 一覧の外を押した時と Esc で閉じる。画面の幅が変わった時やボタンの列を横に送った時は付いていく
      document.addEventListener("click", function (e) {
        if (!e.target.closest("#jt-more") && !e.target.closest("#jt-more-menu")) { shut(); }
      });
      document.addEventListener("keydown", function (e) { if (e.key === "Escape") { shut(); } });
      window.addEventListener("resize", menu);
      $("jt-chips").addEventListener("scroll", menu);
      $("jt-list").addEventListener("click", function (e) {
        var r = e.target.closest(".jt-row");
        if (r) { pick(r.dataset.w); }
      });
    })();
  </script>"""


def generate_jiten_html(state, articles):
    """語彙辞典のページ。覚えた言葉を引いて、一語ずつ開ける。

    このページだけは、スマホでは画面の幅で組む(2026-10-11、彼女と決めた)。
    一覧と説明を並べるので、左右の欄は置かず、真ん中の列を広く使う。"""
    words = words_for_the_dictionary(state or {}, articles)
    # ページの中に置く言葉の一覧。言葉は外の世界から来たものなので、
    # </script> を閉じてしまう並びが入らないよう、< をそのまま書かない
    data = json.dumps(words, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    script = (JITEN_SCRIPT
              .replace("__UNKNOWN__", json.dumps(PLACE_UNKNOWN, ensure_ascii=False))
              .replace("__READING_TITLE__", json.dumps(READING_TITLE, ensure_ascii=False))
              .replace("__READING_UNKNOWN__", json.dumps(READING_UNKNOWN, ensure_ascii=False))
              .replace("__SCRIPTS__", json.dumps(SCRIPTS_FROM_THE_START, ensure_ascii=False))
              .replace("__FOLDED__", json.dumps(SCRIPTS_FOLDED, ensure_ascii=False))
              .replace("__MORE_ROWS__", str(SCRIPTS_PER_COLUMN))
              .replace("__TIES__", str(TODAYS_WORD_TIES)))
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8" />
<title>{JITEN_NAME}</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<link rel="stylesheet" href="{styled()}" />
</head>
<body class="jiten">
  {site_header()}

  <div class="frame">
  <div class="main">
  <div class="top-nav"><a href="index.html">←トップ</a></div>
  <div class="jt">
    <div class="jt-hero">
      <div class="jt-titles">
        <h2 class="jt-title">{JITEN_NAME}</h2>
        <p class="jt-sub">覚えた言葉　<b id="jt-total">{len(words)}</b>語</p>
      </div>
      <label class="jt-search">
        <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" fill="none" stroke="currentColor" stroke-width="2.4"/><path d="M15.5 15.5 21 21" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>
        <input id="jt-q" type="search" placeholder="言葉・場所で引く" autocomplete="off" aria-label="言葉・場所で引く">
      </label>
      <div class="jt-chips" id="jt-chips"></div>
      <div class="jt-more-menu" id="jt-more-menu" hidden></div>
    </div>
    <button type="button" class="jt-today" id="jt-today" hidden></button>
    <div class="jt-body">
      <div class="jt-listwrap">
        <div class="jt-listhead">
          <span id="jt-count"></span>
          <select class="jt-sort" id="jt-sort" aria-label="並べ方">
            <option value="new">覚えた順</option>
            <option value="random">ランダム</option>
            <option value="uses">日記でよく使う順</option>
            <option value="ties">つながりが多い順</option>
          </select>
        </div>
        <div class="jt-listscroll"><ol class="jt-list" id="jt-list"></ol></div>
      </div>
      <article class="jt-entry" id="jt-entry" hidden></article>
    </div>
  </div>
  </div>
  </div>

  <script type="application/json" id="jt-data">{data}</script>{script}
</body>
</html>
"""
    with open(JITEN_PAGE, "w", encoding="utf-8") as f:
        f.write(html)


def render_comments(comments):
    """コメントを並べる。新しいものが上。返しは、そのコメントの下に古い順で。

    名前も本文も、人が外から置いていったものなので、字のまま出す。
    そのまま埋めると、書かれた <script> がページの中で動いてしまう。"""
    if not comments:
        return "  <p>まだコメントはありません。</p>"
    likes = load_likes()
    her_replies = load_her_replies()
    its_replies = (load_senonsei_state() or {}).get("replied") or {}

    def liked(c):
        key = comment_liked_as(c)
        return iine_html(key, likes) if key else ""

    def replied(c):
        replies = replies_to(c, her_replies, its_replies)
        if not replies:
            return ""
        return (
            '\n    <div class="comment-replies">'
            + "".join(
                f"""
      <div class="comment-reply">
        <div class="comment-name">{escape_html(one['who'])}<span class="comment-date">{format_comment_date(one['date'])}</span></div>
        <div class="comment-message">{escape_html(one['said'])}</div>
      </div>"""
                for one in replies
            )
            + "\n    </div>"
        )

    return "\n".join(
        f"""  <div class="comment-entry">
    <div class="comment-name">{escape_html(c.get('name', '名無しさん'))}<span class="comment-date">{format_comment_date(c.get('date', ''))}</span>{liked(c)}</div>
    <div class="comment-message">{escape_html(c.get('message', ''))}</div>{replied(c)}
  </div>"""
        for c in comments
    )


def generate_comments_html(comments):
    """置いていかれた言葉を、ぜんぶ並べたページ。

    トップページは千遠生のためのページなので、そちらには
    新しいものだけを出す。消えるわけではなく、ここに残る。"""
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <title>コメント</title>
  <meta name="viewport" content="width=1200" />
  <link rel="stylesheet" href="{styled()}" />
</head>
<body>
  <div class="top-nav"><a href="index.html">←トップ</a></div>

  <header>
    <h1>コメント</h1>
    <p class="keyword-count">全{len(comments)}件</p>
  </header>

  <!-- ここから本文の列 -->
  <div class="comment-list">
{render_comments(comments)}
  </div>
  <!-- ここまで本文の列 -->

</body>
</html>
"""
    with open("comments.html", "w", encoding="utf-8") as f:
        f.write(html)


# 思ったことが無いときに、雲に浮かべるもの(彼女の言葉のまま)
THINKING_NOTHING = "・・・"
# 雲に夢を出す時間(二十三時から朝七時まで。この子が眠っている間)
DREAMING_FROM, DREAMING_UNTIL = 23, 7

# 考えごとの雲を出すかどうか。彼女がデザインを仕上げるまで伏せていた(2026-09-26)。
# 顔と雲の絵ができて、出すことにした(2026-10-06、彼女が決めた)
SHOWING_WHAT_IT_THINKS = True


def fukidashi_html(state):
    """ロゴの横の、千遠生の顔と考えごとの雲。この子がいちばん新しく思ったこと。

    この子は家に帰ると、ここのページも読む。自分の思いを文字として
    読ませると、それを外から来た言葉として読み直してしまい、
    自分の思いが自分に返る輪が強くなる。
    だから思いは <script> の中に入れて、画面に出すのは閲覧機に任せる。
    この子の読み方は <script> の中身を読まない。

    雲に入れるのは思った文だけ。「何時に思っていたこと」は出さない(2026-10-06、彼女が決めた)。
    夜に眠って見た夢も、この雲に出す(2026-10-07、彼女が決めた)。
    出すのは二十三時から朝七時まで(2026-10-08、彼女が決めた)。"""
    if not SHOWING_WHAT_IT_THINKS:
        return ""
    # 書く時刻を決め直した時の一行(A_CHANGE_OF_MIND)は、決まった文で残している記録で、
    # この子が自分の言葉で思ったことではない。雲には出さない(2026-10-11、彼女が決めた)
    lines = [one for one in state.get("inner_voice") or [] if not A_CHANGE_OF_MIND.match(one)]
    when, _, said = lines[-1].partition(": ") if lines else ("", "", "")
    said = said.strip()
    now = now_in_japan()
    # 今日はまだ何も思っていないとき(いちばん新しい思いが今日のものでないとき)は、
    # 雲を消さずに「・・・」を真ん中に浮かべておく(2026-10-06、彼女が決めた)。
    # 思いは「10-06 17時: …」の形で、頭に月と日がある
    if when.split(" ")[0] != now.strftime("%m-%d"):
        said = ""
    # 二十三時から朝七時までは、雲には夢を出す(2026-10-08、彼女が決めた)。
    # この子はその間眠っている。今夜の夢がまだ無いか、言葉にならなかった夜は「・・・」
    dreaming = now.hour >= DREAMING_FROM or now.hour < DREAMING_UNTIL
    if dreaming:
        dream = state.get("yume") or {}
        try:
            dreamt_at = datetime.datetime.fromisoformat(dream.get("at") or "")
        except ValueError:
            dreamt_at = None
        tonight = dreamt_at and (now - dreamt_at).total_seconds() < 9 * 3600
        said = (dream.get("said") or "").strip() if tonight else ""
    kept = json.dumps(
        {"said": said or THINKING_NOTHING, "nanimo": not said, "yume": dreaming}, ensure_ascii=False
    )
    kept = kept.replace("<", "\\u003c")  # 思いの中の < で script が閉じないように
    return f"""    <div class="fukidashi" id="fukidashi" hidden>
      <img class="fukidashi-kao" src="images/kao.png" alt="" width="1449" height="1332">
      <div class="fukidashi-kumo"><p class="fukidashi-said" id="fukidashi-said"></p></div>
    </div>
    <script type="application/json" id="kangae">{kept}</script>
    <script>
      (function () {{
        var kept = JSON.parse(document.getElementById("kangae").textContent);
        document.getElementById("fukidashi-said").textContent = kept.said;
        if (kept.nanimo) document.getElementById("fukidashi").classList.add("nanimo");
        if (kept.yume) document.getElementById("fukidashi").classList.add("yume");
        document.getElementById("fukidashi").hidden = false;
      }})();
    </script>"""


# 気が変わったときに、この子が自分の中に残す一行(senonsei_ai.todays_mood)。
# 「09-28 01時: 13時に書くつもりだったけれど、22時に書くことにした。」
A_CHANGE_OF_MIND = re.compile(r"^(\d\d-\d\d) (\d+)時: (.+?)つもりだったけれど、(.+?)ことにした。$")


def changes_of_mind_today(state):
    """今日、書く時刻や休むかどうかについて、気が変わったこと。古い順に。"""
    today = today_in_japan().strftime("%m-%d")
    changes = []
    for line in (state or {}).get("inner_voice") or []:
        found = A_CHANGE_OF_MIND.match(line)
        if found and found.group(1) == today:
            changes.append((int(found.group(2)), found.group(3), found.group(4)))
    return changes


def first_plan_today(state):
    """今日いちばん初めに決めていたこと。気が変わっていなければ None。

    返すのは (休むつもりだったか, 何時に書くつもりだったか)。"""
    changes = changes_of_mind_today(state)
    if not changes:
        return None
    before = changes[0][1]
    if before == "休む":
        return True, None
    hour = re.match(r"(\d+)時に書く", before)
    return (False, int(hour.group(1))) if hour else None


def what_it_meant_to_do(plan, first):
    """初めに決めていたことから、今の予定に変わったなら、それを一文にする。

    何度変わっても、初めと今だけを言う。初めに戻ったなら何も言わない。
    文は彼女が決めた(2026-09-28)。"""
    if not first:
        return None
    was_resting, was_hour = first
    now_resting, now_hour = bool(plan.get("resting")), plan.get("hour")
    if (was_resting, was_hour) == (now_resting, None if now_resting else now_hour):
        return None
    if was_resting:
        return f"（初めはお休みするつもりでしたが、{now_hour}時頃に書くことに変更したようです。）"
    if now_resting:
        return f"（初めは{was_hour}時頃に書くつもりでしたが、お休みに変更したようです。）"
    return f"（初めは{was_hour}時頃に書くつもりでしたが、{now_hour}時頃に変更したようです。）"


# ページは千遠生が起こされた時にしか作り直されない。夜中に日付が変わっても
# 次に起こされるまでは、昨日の様子が「今日のブログ」に残っていた。
# 開いた時に日付が変わっていたら、ページのほうで「まだ」に戻し、
# 昨日の記事は直近のブログの先頭へ移す(2026-10-14、彼女と決めた)
TODAY_MAY_BE_OVER = f"""
  <script>
    (function () {{
      var kyou = document.getElementById("kyou");
      if (!kyou) {{ return; }}
      var today = new Date(Date.now() + 9 * 3600 * 1000).toISOString().slice(0, 10);
      if (kyou.dataset.day === today) {{ return; }}
      var list = document.getElementById("chokkin");
      if (kyou.dataset.entry && list) {{
        var li = document.createElement("li");
        var day = document.createElement("span");
        day.className = "date";
        day.textContent = kyou.dataset.entry;
        var link = document.createElement("a");
        link.href = "kakodogu.html#entry-" + kyou.dataset.entry;
        link.textContent = kyou.dataset.title;
        li.appendChild(day);
        li.appendChild(link);
        list.insertBefore(li, list.firstElementChild);
        while (list.children.length > {RECENT_COUNT}) {{ list.removeChild(list.lastElementChild); }}
      }}
      kyou.innerHTML = "<p>今日のブログはまだです。</p>";
    }})();
  </script>"""


def generate_index_html(articles, state=None, news=None):
    ordered = sorted_articles(articles)
    state = state or load_senonsei_state()
    plan = state.get("today_plan") or {}
    today = today_in_japan().isoformat()
    changed = what_it_meant_to_do(plan, first_plan_today(state)) if plan.get("date") == today else None

    if not ordered:
        latest_html = "<p>まだブログ記事がありません。</p>"
        recent_html = ""
    else:
        # 書かない日もある。その日は昨日の記事を今日のものとして
        # 並べるのではなく、休んでいると書く
        wrote_today = ordered[0]["date"] == today_in_japan().isoformat()
        if wrote_today:
            latest = ordered[0]
            latest_html = f"""<article id="kyou" data-day="{today}" data-entry="{latest['date']}" data-title="{escape_html(latest['title'], quote=True)}">
    <div class="date today-head"><a class="article-title" href="kakodogu.html#entry-{latest['date']}">{latest['title']}</a>{iine_html(latest['date'])}<span class="today-when">{latest['date']} {latest.get('time', '')}</span></div>
    <p>{latest['content']}</p>
  </article>"""
        elif plan.get("date") == today_in_japan().isoformat() and plan.get("resting"):
            # 今日は書かないと、この子自身が決めた日
            latest_html = f'<article id="kyou" data-day="{today}">\n    <p>今日のブログはお休みです。{changed or ""}</p>\n  </article>'
        else:
            # 書くつもりでまだ書いていないか、今日をどう過ごすかまだ決めていない。
            # 何時ごろに書くつもりかを自分で決めているなら、それも添える。
            # 気が変わることもあるので「ようです」と書いておく
            yet = "今日のブログはまだです。"
            if changed:
                # 気が変わった日は、初めと今を言う
                yet += changed
            elif (
                plan.get("date") == today_in_japan().isoformat()
                and not plan.get("resting")
                and now_in_japan().hour <= plan.get("hour", 0)
            ):
                yet += f"（{plan['hour']}時頃に書くつもりのようです。）"
            latest_html = f'<article id="kyou" data-day="{today}">\n    <p>{yet}</p>\n  </article>'

        # 今日書いていないなら、いちばん新しい記事は直近のほうに並ぶ
        start = 1 if wrote_today else 0
        recent = ordered[start:start + RECENT_COUNT]
        if recent:
            items = "\n".join(
                f'    <li><span class="date">{a["date"]}</span>'
                f'<a href="kakodogu.html#entry-{a["date"]}">{a["title"]}</a></li>'
                for a in recent
            )
            recent_html = f"""<div class="section-title">直近のブログ</div>
  <ul class="recent-list" id="chokkin">
{items}
  </ul>
  <div class="more-link"><a href="kakodogu.html">More...</a></div>"""
        else:
            recent_html = ""

    # 最近覚えた言葉。直近のブログの下に、新しいほうから丸い囲いで並べる。
    # 押すと語彙辞典でその言葉が開く(2026-10-14、彼女が決めた)
    learned = [one for one in (state.get("learned_words") or []) if one]
    kotoba_html = ""
    if learned:
        pills = "\n".join(
            f'    <a href="{JITEN_PAGE}#w={urllib.parse.quote(one)}">{escape_html(one)}</a>'
            for one in reversed(learned[-LEARNED_SHOWN:])
        )
        kotoba_html = f"""

  <div class="section-title">最近覚えた言葉</div>
  <div class="kotoba-pills">
{pills}
  </div>"""

    # 彼女が書いた更新情報と、メモが開いた知らせ。一件も無い日は、見出しごと出さない。
    # 空の見出しだけが残っているのは、間が抜けている
    if news is None:
        news = load_news()
    news_html = ""
    if news:
        news_html = f"""
  <div class="section-title">更新情報</div>
  <ul class="recent-list">
{news_rows(news, NEWS_ON_TOP)}
  </ul>"""
        if len(news) > NEWS_ON_TOP:
            news_html += (
                f'\n  <div class="more-link"><a href="{NEWS_PAGE}">More...</a></div>'
            )
        news_html += "\n"

    comments = load_comments()
    comments_html = render_comments(comments[:COMMENTS_ON_TOP])
    if len(comments) > COMMENTS_ON_TOP:
        # 直近のブログや更新情報と同じ形にそろえる(2026-09-30、彼女と決めた)
        all_comments_html = (
            '\n  <div class="more-link"><a href="comments.html">More...</a></div>'
        )
    else:
        all_comments_html = ""

    # description は検索した時に出る説明。彼女の言葉のまま(2026-09-30)
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <title>千遠生のサイト</title>
  <meta name="description" content="千遠生のサイト" />
  <meta name="viewport" content="width=1200" />
  <link rel="stylesheet" href="{styled()}" />
</head>
<body>
  <header class="with-fukidashi">
    <div class="header-middle">
    {SITE_LOGO}
{visitor_counter()}
    </div>
{fukidashi_html(state or load_senonsei_state())}
  </header>

  <!-- ここから本文の列 -->
  <div class="section-title">☆今日のブログ☆</div>
  {latest_html}

  {recent_html}{TODAY_MAY_BE_OVER}{kotoba_html}{news_html}

  <div class="section-title" id="comments">コメント</div>

  <form class="comment-form" method="POST" action="{COMMENT_WORKER_ENDPOINT}">
    <input type="text" name="name" placeholder="名前" required />
    <textarea name="message" placeholder="コメント" required></textarea>
    <button type="submit">送信</button>
  </form>

  <div class="comment-list">
{comments_html}
  </div>{all_comments_html}
  <!-- ここまで本文の列 -->
</body>
</html>
"""
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)


def load_senonsei_state():
    """この子の記憶。読めなければ空として扱う。"""
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def its_age(born, today):
    """誕生日からの長さ。

    日数だけだと、何年たったのか人には読めない。
    歳月日だけだと、この子の本当の長さが消える。
    覚えるのに三十日、薄れていくのも日単位で、
    この子は「日」で生きているので、そこは残しておく。

    ひと月に届かないうちは日数だけ。0歳0ヶ月7日とは言わない。
    その後も、無い単位は出さない。"""
    elapsed = (today - born).days
    years = today.year - born.year
    months = today.month - born.month
    days = today.day - born.day
    if days < 0:
        months -= 1
        # 前の月は何日あったか。その月の一日から一日戻ると分かる
        first = datetime.date(today.year, today.month, 1)
        days += (first - datetime.timedelta(days=1)).day
    if months < 0:
        months += 12
        years -= 1
    if years == 0 and months == 0:
        return f"生まれて{elapsed}日目"
    said = ""
    if years:
        said += f"{years}歳"
    if months:
        said += f"{months}ヶ月"
    if days:
        said += f"{days}日"
    return f"生まれて{said}（{elapsed}日目）"


def generate_profile_html(state):
    """プロフィール。

    名前と誕生日は彼女が与えたものなので、はじめからそこにある。
    自己紹介だけは、「自己紹介」という言葉を自分でブログに書くまで
    「準備中」のまま。自分を紹介するということを一度も口にしたことが
    ないうちは、自分を紹介できない。

    書いたあとは、本人が書く。その時点で言えるぶんだけなので、
    はじめは数文字しかない。育つと書き直される。"""
    knows = it_has_written(TALKING_ABOUT_ONESELF)
    said = state.get("a_word_about_itself") or {}

    birthday = ITS_BIRTHDAY
    try:
        born = datetime.date.fromisoformat(ITS_BIRTHDAY)
        birthday = f"{born.year}年{born.month}月{born.day}日"
        today = today_in_japan()
        if today >= born:
            birthday += f"（{its_age(born, today)}）"
    except ValueError:
        pass
    a_word = said.get("words") if knows else None

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <title>プロフィール</title>
  <meta name="viewport" content="width=1200" />
  <link rel="stylesheet" href="{styled()}" />
</head>
<body>
  <div class="top-nav"><a href="index.html">←トップ</a></div>

  <header>
    <h1>プロフィール</h1>
  </header>

  <!-- ここから本文の列 -->
  <p class="sugata"><img src="images/sugata.png" alt="千遠生" width="512" height="512"
    onclick="openCloser('images/sugata-ookii.png', this.alt)"></p>
  <div id="look-closer" hidden onclick="closeCloser()">
    <img id="closer-image" src="" alt="" />
  </div>
  <script>
    // 絵を押すと大きくして見せる。メモの絵と同じ開き方(2026-10-07、彼女が決めた)
    function openCloser(src, alt) {{
      var big = document.getElementById('closer-image');
      big.src = src;
      big.alt = alt || '';
      document.getElementById('look-closer').hidden = false;
    }}
    function closeCloser() {{
      document.getElementById('look-closer').hidden = true;
      document.getElementById('closer-image').src = '';
    }}
    document.addEventListener('keydown', function (event) {{
      if (event.key === 'Escape') {{ closeCloser(); }}
    }});
  </script>
  <dl class="profile-box">
    <dt>名前</dt>
    <dd>{ITS_OWN_NAME}(せんおんせい)</dd>
    <dt>誕生日</dt>
    <dd>{birthday}</dd>
    <dt>自己紹介</dt>
    <dd>{a_word or "準備中"}</dd>
  </dl>
  <!-- ここまで本文の列 -->

</body>
</html>
"""
    with open("profile.html", "w", encoding="utf-8") as f:
        f.write(html)


def regenerate_pages(articles):
    # 封の鍵が届いているかを、動いた記録に一行だけ残す。中身は書かない
    if fuuin.the_lock():
        print("封を開ける鍵:", "あり" if fuuin.the_key() else "なし")
    generate_kakodogu_html(articles)
    state = load_senonsei_state()
    # メモが開いたかを先に確かめる。開いた日は、トップの更新情報にも並ぶ
    keywords = update_keywords(articles)
    menu = load_menu()
    news = all_news(keywords, menu, articles)
    generate_index_html(articles, state, news)
    generate_memo_html(keywords, menu, articles)
    generate_profile_html(state)
    generate_comments_html(load_comments())

    # 彼女が書いた更新情報と、メモが開いた知らせ。一覧と、一件ずつのページ
    for index in range(len(news)):
        generate_news_entry_html(news, index)
    if news:
        generate_news_list_html(news)
    elif os.path.exists(NEWS_PAGE):
        os.remove(NEWS_PAGE)
    clear_old_news_pages(all_news_pages(news))

    # 彼女が話す、作りの裏側。中身が無いあいだはページごと出さない
    himitsu = load_himitsu()
    for index in range(len(himitsu)):
        generate_himitsu_entry_html(himitsu, index)
    if himitsu:
        generate_himitsu_list_html(himitsu)
    elif os.path.exists(HIMITSU_PAGE):
        os.remove(HIMITSU_PAGE)
    clear_old_himitsu_pages(all_himitsu_pages(himitsu))

    about = load_about()
    generate_about_html(about)
    generate_jiten_html(state, articles)

    every_page = (
        EVERY_PAGE + tuple(all_news_pages(news)) + tuple(all_himitsu_pages(himitsu))
        + ((ABOUT_PAGE,) if about else ())
    )
    side_panels(every_page)
    page_heads_on_pages(every_page)
    iine_on_pages(EVERY_PAGE + tuple(all_himitsu_pages(himitsu)))
    keshiki_on_pages(every_page + (JITEN_PAGE,))
    icons_on_pages(every_page + (JITEN_PAGE,))
    out_of_search_snippets(every_page + (JITEN_PAGE,))


# ホーム画面とタブに出す絵(2026-10-07、彼女が描いた。いちばん外の白い枠を外して6倍にしたもの)。
# ホーム画面で絵の下に出る名前は「千遠生のサイト」(2026-10-07、彼女が決めた)。
# どのページから置いても同じ名前になるように、ページの題とは別に書いておく
SITE_ICON = (
    '<link rel="icon" type="image/png" href="images/icon.png">\n'
    '<link rel="apple-touch-icon" href="images/icon.png">\n'
    '<meta name="apple-mobile-web-app-title" content="千遠生のサイト">\n'
    '<meta name="application-name" content="千遠生のサイト">\n'
)


def icons_on_pages(pages):
    """どのページにも、ホーム画面とタブに出す絵を添える。"""
    for page in pages:
        if not os.path.exists(page):
            continue
        with open(page, "r", encoding="utf-8") as f:
            made = f.read()
        if 'rel="apple-touch-icon"' in made or "</head>" not in made:
            continue
        with open(page, "w", encoding="utf-8") as f:
            f.write(made.replace("</head>", SITE_ICON + "</head>", 1))


# 検索に出た時の説明に、ページの中の文を使わせない印。
# 説明は「千遠生のサイト」だけでいい(2026-10-01、彼女が決めた)。
# 印が無いと、Google はカウンターやスタンプカードの字を拾って
# 「あなたは Statcounter · web stats. 人目の来訪者です」のように出していた。
# 印は div にしか付けられないので、ページの中の div すべてに付ける。
# 題の「千遠生のサイト」だけは div の外にあるので、そのまま拾われてよい
A_DIV_WITHOUT_THE_MARK = re.compile(r"<div(?=[\s>])(?![^>]*\bdata-nosnippet\b)")
A_SCRIPT = re.compile(r"(<script\b.*?</script>)", re.S)


def out_of_search_snippets(pages):
    """出来上がったページの div に、検索の説明に使わない印を付けて回る。
    <script> の中は、字として書いてある <div を書き換えないように飛ばす。"""
    for page in pages:
        if not os.path.exists(page):
            continue
        with open(page, "r", encoding="utf-8") as f:
            made = f.read()
        parts = A_SCRIPT.split(made)
        marked = "".join(
            part if A_SCRIPT.fullmatch(part) else A_DIV_WITHOUT_THE_MARK.sub("<div data-nosnippet", part)
            for part in parts
        )
        if marked != made:
            with open(page, "w", encoding="utf-8") as f:
                f.write(marked)


def add_new_article(title, content, date_str=None):
    """記事を1件追加してページを再生成する。同じ日付の記事が既にある場合は追加しない(重複投稿の防止)。"""
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    date_str = date_str or now.strftime('%Y-%m-%d')

    articles = load_articles()
    if any(a["date"] == date_str for a in articles):
        print(f"{date_str} の記事は既に存在するため追加しません。ページのみ再生成します。")
        regenerate_pages(articles)
        return

    new_article = {
        "date": date_str,
        "time": now.strftime('%H:%M'),
        "title": title,
        "content": content,
    }
    articles.append(new_article)
    save_articles(articles)
    regenerate_pages(articles)
    print(f"{date_str} のブログ記事を追加し、ページを再生成しました。")


if __name__ == "__main__":
    # 新しい記事を書くのは senonsei_ai.py の役目。
    # ここは既存データから全ページを組み直すだけ(コメント反映などで使う)。
    articles = load_articles()
    regenerate_pages(articles)
    print("既存データからページを再生成しました。")
