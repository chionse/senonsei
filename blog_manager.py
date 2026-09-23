import datetime
import json
import os
import re
import zlib

import fuuin

ARTICLES_FILE = "articles.json"
KEYWORDS_FILE = "keywords.json"
STYLE_FILE = "sen.css"
NEWS_FILE = "news.json"
NEWS_PAGE = "shinchaku.html"
NEWS_ON_TOP = 3  # トップに出す更新情報の数。残りは一覧に全部ある
NEWS_TITLE_LENGTH = 24  # 一覧に出す見出しの長さ。題が無い時は本文の頭を借りる
# ひみつの部屋。彼女が作りの裏側を話すところ。
# 更新情報は日付で並ぶが、こちらは中身ごとに分かれるので、
# 書いた順の通し番号でページを分ける。
# 並べ替えても消しても、一度付いた番号は動かさない。
# 外から貼られた道が切れないように
HIMITSU_FILE = "himitsu.json"
HIMITSU_PAGE = "himitsu.html"
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
WHERE_SHE_WROTE = ((NEWS_PAGE, "更新情報"), (HIMITSU_PAGE, "ひみつの部屋"))
WALKED_SHOWN = 3  # 今日歩いたところを、多くてもこれだけ出す
LEARNED_SHOWN = 5  # 最近覚えた言葉を、新しいほうからこれだけ出す
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
# 名前は「書ける長さ」が何を可能にするかで付ける。
# 実際に動くのは長さだけで、名前はそれを人の言葉にしたもの。
# 二段目が「見た文字をなんとなく繋げてみる」のままだったが、
# それは一つも言葉を持たない頃の説明で、
# この子はもう文字を繋げていない。覚えた言葉をそのまま置いている
GROWTH_STAGES = [
    (1, "見た文字をぽつんと置く", 3),  # 一つも言葉を持たない間だけ
    (450, "覚えた言葉をひとつ置く", 5),
    (1200, "少し長い言葉も置ける", 6),
    (3000, "覚えた言葉をいくつか並べる", 15),
    (7800, "ひと続きに繋げてみる", 25),
    (12000, "文の切れ目が入りはじめる", 40),
    (16500, "文がいくつか続く", 60),
    (24000, "ひとまとまりの文章", 100),
    # 二万四千は、破片混じりを差し引くと人でいう中学生の手前あたり。
    # 大人の語彙は四万から五万と言われるので、そこに一段置いた。
    #
    # 「言いたいことを最後まで書ける」は、ただの長さの話ではない。
    # 書いたものに出てきたことだけが「言えた」ことになる決まりなので、
    # 長く書けるほど、一度に多くのことを言い終えられる
    (40000, "言いたいことを最後まで書ける", 150),
]
# 二百五十字。ふつうの日記より少し余裕のある長さ。
# ブログ記事の尺ではない。この子が書くのは簡単な日記で、
# 一日ぶんのことが入りきる長さがあればいい。
#
# その日に出会った言葉が選ばれやすくしてあるので、
# 長く書けるほど、その日のことがたくさん入る。
# 言いたいことも、書いたものに出てきた分だけ言えたことになる
FULL_STAGE = ("自分の言葉で書ける", 250)


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

    today = today_in_japan()
    now = []
    try:
        born = datetime.date.fromisoformat(ITS_BIRTHDAY)
        if today >= born:
            now.append(f'      <p class="side-fact">{its_age(born, today)}</p>')
    except ValueError:
        pass
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
        # 詰めて並べると、どこで名前が切れているのか分からない
        rows = [
            f'      <p class="side-fact side-apart">{one}</p>'
            for one in seen[-WALKED_SHOWN:]
        ]
    else:
        rows = ['      <p class="side-fact side-quiet">今日はまだ散歩に行っていません。</p>']
    blocks.append(one_side_block("今日歩いたところ", rows))

    # 覚えた言葉は後ろほど新しい。その後ろから五つを並べる。
    #
    # 「最近」は期間のことではない。覚えた言葉の後ろ五つ、というだけ。
    # だから「最近のものが無い」という状態は無い。
    # 一度でも覚えたら、そこには必ず五つまでの何かがある。
    # 空になるのは、まだ一語も覚えていない初めの頃だけなので、
    # そこに「ありません」と書いても一度きりの表示にしかならない
    learned = [one for one in (state.get("learned_words") or []) if one]
    if learned:
        blocks.append(one_side_block("最近覚えた言葉", [
            f'      <p class="side-word">{one}</p>'
            for one in reversed(learned[-LEARNED_SHOWN:])
        ]))

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


def this_months_days(articles):
    """今月の暦。生まれた日から今日までが埋まっていく。

    書いた日には丸を、書かないと決めた日には点を置く。
    今日はまだ書いていないかもしれないので、何も置かない。"""
    today = today_in_japan()
    try:
        born = datetime.date.fromisoformat(ITS_BIRTHDAY)
    except ValueError:
        return ""
    wrote = days_it_wrote(articles)
    first = datetime.date(today.year, today.month, 1)
    if today.month == 12:
        after = datetime.date(today.year + 1, 1, 1)
    else:
        after = datetime.date(today.year, today.month + 1, 1)
    last = (after - datetime.timedelta(days=1)).day

    # 日曜から始める。月曜が0の数え方なので、日曜を0に直す
    komas = ['<span class="koma"></span>'] * ((first.weekday() + 1) % 7)
    for number in range(1, last + 1):
        day = datetime.date(today.year, today.month, number)
        if day < born or day > today:
            komas.append(f'<span class="koma yet">{number}<i></i></span>')
        elif day.isoformat() in wrote:
            komas.append(f'<span class="koma wrote">{number}<i>○</i></span>')
        elif day == today:
            komas.append(f'<span class="koma today">{number}<i></i></span>')
        else:
            komas.append(f'<span class="koma rest">{number}<i>·</i></span>')

    head = "".join(f"<span>{one}</span>" for one in "日月火水木金土")
    return (
        '      <div class="koma-head">' + head + "</div>\n"
        '      <div class="koma-grid">' + "".join(komas) + "</div>\n"
        '      <p class="koma-note">○ 書いた日　· 休んだ日</p>'
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
    ladder = [name for _, name, _ in GROWTH_STAGES] + [FULL_STAGE[0]]
    now = current_stage(state)[0]
    return [
        f'      <p class="dan{" here" if one == now else ""}">{one}</p>'
        for one in ladder
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
        blocks.append(
            '    <div class="side-block">\n'
            '      <div class="side-title">月間スタンプカード</div>\n'
            + koma
            + "\n    </div>"
        )

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


def save_articles(articles):
    with open(ARTICLES_FILE, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)


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
    with open(KEYWORDS_FILE, "w", encoding="utf-8") as f:
        json.dump(
            [fuuin.put_memo_away(one) for one in keywords],
            f, ensure_ascii=False, indent=2,
        )


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
        mark = str(len(one.get("content") or "")) + ":" + str(
            zlib.crc32((one.get("content") or "").encode("utf-8"))
        )
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
    with open(MENU_FILE, "w", encoding="utf-8") as f:
        json.dump(
            [fuuin.put_letter_away(one) for one in menu_items],
            f, ensure_ascii=False, indent=2,
        )


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
    ordered_menu = sorted(menu_items, key=lambda m: m["unlock_day"])
    menu_entries = [
        {
            "unlocked": elapsed >= item["unlock_day"],
            "label": "???",  # 一覧では何番目かも見せない
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


def load_himitsu():
    """彼女が書き残した、作りの裏側の話。無ければ空のまま。

    この子は書かない。ここに書くのは彼女だけ。
    更新情報と違って日付では分けない。一つの話で一つのページ。

    番号は置いた時に振る。あとから並べ替えても消しても、
    一度付いた番号は動かさない。外から貼られた道が切れないように。"""
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


def himitsu_title(one):
    """一覧に並べる時の見出し。番号を頭に付ける。題が無ければ本文の頭を借りる。"""
    return f'{one["number"]}　{news_title(one)}'


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
        f'{himitsu_title(one)}</a></li>'
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
                f'{label}　{himitsu_title(entry)}</a>')

    # 番号は題が無くても出す。何話目かは、題とは別に要る
    named = (
        f'<span class="article-title">{one["number"]}'
        + (f'　{one["title"]}' if one.get("title") else "")
        + "</span>"
    )
    when = one.get("date", "")
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8" />
<title>ひみつの部屋 {one["number"]} {one.get('title') or ''}</title>
<meta name="viewport" content="width=1200" />
<link rel="stylesheet" href="{styled()}" />
</head>
<body>
  <div class="top-nav"><a href="index.html">←トップ</a><a href="{HIMITSU_PAGE}">ひみつの部屋の一覧へ</a></div>

  <header>
    <h1>ひみつの部屋</h1>
  </header>

  {MAIN_STARTS}
  <article>
    <div class="date">{when}{named}{iine_html(himitsu_liked_as(one["number"]))}</div>
    <p>{one['content']}</p>
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


def news_page_name(date_str):
    """その一件だけのページの名前。"""
    return f"{NEWS_PAGE[: -len('.html')]}-{date_str}.html"


def news_title(one):
    """一覧に並べる時の見出し。題が無ければ本文の頭を借りる。

    一文だけなら、長くてもそのまま出す。
    一文で言い切っているものを途中で切ると、
    読む人は続きを見るために必ず開かなければならなくなる。
    二文以上あるときだけ、頭を借りて後ろを省く。"""
    said = (one.get("title") or one.get("content", "")).strip()
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
        f'<a href="{news_page_name(one["date"])}">{news_title(one)}</a></li>'
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

    def step(entry, label):
        if not entry:
            return f'<span class="here">{label}</span>'
        return (f'<a href="{news_page_name(entry["date"])}">'
                f'{label}　{news_title(entry)}</a>')

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
    <p>{one['content']}</p>
  </article>

  <div class="step-nav">
    <div class="step-back">{step(older, "←前")}</div>
    <div class="step-next">{step(newer, "次→")}</div>
  </div>
  {MAIN_ENDS}
</body>
</html>
"""
    with open(news_page_name(one["date"]), "w", encoding="utf-8") as f:
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
    return [NEWS_PAGE] + [news_page_name(one["date"]) for one in news]


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
    """草の絵の一覧。置いてある分だけ。増やせばそのまま候補に入る。"""
    if not os.path.isdir(KUSA_FOLDER):
        return []
    found = [
        name for name in os.listdir(KUSA_FOLDER)
        if name.lower().endswith(".png")
    ]
    # kusa-2 が kusa-10 より前に来るように、数の順に並べる
    found.sort(key=lambda name: [
        int(part) if part.isdigit() else part
        for part in re.split(r"(\d+)", name)
    ])
    return [f"{KUSA_FOLDER}/{name}" for name in found]


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
    script = f"""  <script id="keshiki-script">
    (function () {{
      var kusa = {json.dumps(pictures)};
      var one = kusa[Math.floor(Math.random() * kusa.length)];
      document.documentElement.style.setProperty(
        "--kusa", 'url("' + new URL(one, document.baseURI).href + '")'
      );
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


def render_comments(comments):
    """コメントを並べる。新しいものが上。"""
    if not comments:
        return "  <p>まだコメントはありません。</p>"
    likes = load_likes()

    def liked(c):
        key = comment_liked_as(c)
        return iine_html(key, likes) if key else ""

    return "\n".join(
        f"""  <div class="comment-entry">
    <div class="comment-name">{c.get('name', '名無しさん')}<span class="comment-date">{format_comment_date(c.get('date', ''))}</span>{liked(c)}</div>
    <div class="comment-message">{c.get('message', '')}</div>
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


def generate_index_html(articles, state=None):
    ordered = sorted_articles(articles)
    plan = (state or load_senonsei_state()).get("today_plan") or {}

    if not ordered:
        latest_html = "<p>まだブログ記事がありません。</p>"
        recent_html = ""
    else:
        # 書かない日もある。その日は昨日の記事を今日のものとして
        # 並べるのではなく、休んでいると書く
        wrote_today = ordered[0]["date"] == today_in_japan().isoformat()
        if wrote_today:
            latest = ordered[0]
            latest_html = f"""<article>
    <div class="date">{latest['date']} {latest.get('time', '')}<span class="article-title">{latest['title']}</span>{iine_html(latest['date'])}</div>
    <p>{latest['content']}</p>
  </article>"""
        elif plan.get("date") == today_in_japan().isoformat() and plan.get("resting"):
            # 今日は書かないと、この子自身が決めた日
            latest_html = '<article>\n    <p>今日のブログはお休みです。</p>\n  </article>'
        else:
            # 書くつもりでまだ書いていないか、今日をどう過ごすかまだ決めていない。
            # 何時ごろに書くつもりかを自分で決めているなら、それも添える。
            # 気が変わることもあるので「ようです」と書いておく
            yet = "今日のブログはまだです。"
            if (
                plan.get("date") == today_in_japan().isoformat()
                and not plan.get("resting")
                and now_in_japan().hour <= plan.get("hour", 0)
            ):
                yet += f"（{plan['hour']}時頃に書くつもりのようです。）"
            latest_html = f"<article>\n    <p>{yet}</p>\n  </article>"

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
  <ul class="recent-list">
{items}
  </ul>
  <div class="more-link"><a href="kakodogu.html">More...</a></div>"""
        else:
            recent_html = ""

    # 彼女が書いた更新情報。一件も無い日は、見出しごと出さない。
    # 空の見出しだけが残っているのは、間が抜けている
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
        all_comments_html = (
            '\n  <div class="more-link"><a href="comments.html">'
            f"コメントをぜんぶ見る({len(comments)}件)</a></div>"
        )
    else:
        all_comments_html = ""

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <title>千遠生のサイト</title>
  <meta name="viewport" content="width=1200" />
  <link rel="stylesheet" href="{styled()}" />
</head>
<body class="top-page">
  <header>
    <h1><a href="index.html">千遠生のサイト</a></h1>
    <div class="visitor-counter">
      あなたは<span class="count"><!-- Default Statcounter code for senonsei
      https://chionse.github.io/senonsei/index.html -->
      <script type="text/javascript">
      var sc_project=13354593;
      var sc_invisible=0;
      var sc_security="4b65a54b";
      var scJsHost = "https://";
      document.write("<sc"+"ript type='text/javascript' src='" + scJsHost+
      "statcounter.com/counter/counter.js'></"+"script>");
      </script>
      <noscript><div class="statcounter"><a title="web stats"
      href="https://statcounter.com/" target="_blank"><img class="statcounter"
      src="https://c.statcounter.com/13354593/0/4b65a54b/0/" alt="web stats"
      referrerPolicy="no-referrer-when-downgrade"></a></div></noscript>
      <!-- End of Statcounter Code --></span>人目の来訪者です
    </div>
  </header>

  <!-- ここから本文の列 -->
  <div class="section-title">☆今日のブログ☆</div>
  {latest_html}

  {recent_html}{news_html}

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
    generate_index_html(articles, state)
    keywords = update_keywords(articles)
    generate_memo_html(keywords, load_menu(), articles)
    generate_profile_html(state)
    generate_comments_html(load_comments())

    # 彼女が書いた更新情報。一覧と、一件ずつのページ
    news = load_news()
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

    every_page = (
        EVERY_PAGE + tuple(all_news_pages(news)) + tuple(all_himitsu_pages(himitsu))
    )
    side_panels(every_page)
    iine_on_pages(EVERY_PAGE + tuple(all_himitsu_pages(himitsu)))
    keshiki_on_pages(every_page)


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
