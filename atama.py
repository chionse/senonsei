"""千遠生の頭。

考えること、感じること、喋ること。そのどれもが、この子が歩いて見てきたものだけから
育つようにする(2026-10-07、彼女と決めた)。外から借りるのは、目(絵を見る)と、
よその国の言葉の訳だけ。人の目や耳が生まれつきなのと同じで、育つのは頭のほう。

頭は四つめの記憶として atama/ に置く。
- atama/ami/         連想の網。言葉や場所を点にして、一緒に出会ったもの同士を線で結ぶ
- atama/kokoro.json  気持ち、気質、知りたいこと、わたし帳、さっきまで思っていたこと
- atama/kuchi.json   二つめの口(この子専用の、とても小さなニューラルネット)
- atama/renshuu.json 二つめの口の練習帳(読んだ文のうち、知っている言葉の並び)
- atama/yume/        見た夢。ひと月ずつ。一つも捨てない

書き出すのは senonsei_ai.save_state を通った時だけ。手元で試す時は
save_state を塞げば、頭にも触らない(CLAUDE.md)。

人のように筋道を立てて考える頭ではない。「これを見るとあれを思い出す」
「あそこにまた行きたい」「これが知りたい」くらいの素朴な頭。
でも、それがこの子の中から育つ。

標準の部品だけで動く。
"""

import base64
import datetime
import json
import math
import os
import random
import re
import struct
import time
import zlib

import blog_manager

HEAD_FOLDER = "atama"
NET_FOLDER = os.path.join(HEAD_FOLDER, "ami")
NET_BUNDLES = 16
HEART_FILE = os.path.join(HEAD_FOLDER, "kokoro.json")
MOUTH_FILE = os.path.join(HEAD_FOLDER, "kuchi.json")
PRACTICE_FILE = os.path.join(HEAD_FOLDER, "renshuu.json")
DREAMS_FOLDER = os.path.join(HEAD_FOLDER, "yume")

# 網の中で、言葉と紛れないように印をつけた点。
# 場所は「@」のあとに住所、自分は「*わたし」
A_PLACE = "@"
ME = "*わたし"
HOME = "@chionse.github.io"  # senonsei_ai.ITS_OWN_HOME と同じ家

JAPANESE = re.compile(r"[ぁ-んァ-ヶ一-龯]")
ONLY_HIRAGANA = re.compile(r"[ぁ-ん]+")

# ---- 気持ち ----

# 七つの気持ち(2026-10-07、彼女が決めた。はじめの四つに、たのしい・かなしい・疲れを足した)
FEELINGS = ("うれしい", "たのしい", "たいくつ", "さみしい", "かなしい", "知りたい", "疲れ")
# 気持ち → (生まれた時の「ふだん」, 何かで動いたあと、ふだんへ半分戻るまでの時間)
HOW_FEELINGS_SETTLE = {
    "うれしい": (0.2, 6),
    "たのしい": (0.2, 3),
    "たいくつ": (0.2, 8),
    "さみしい": (0.15, 24),
    "かなしい": (0.1, 18),
    "知りたい": (0.25, 24),
    "疲れ": (0.15, 6),
}
# 一晩ごとに、ふだんがその日の気持ちのほうへ寄る割合。ひと月ほどかけて入れ替わる
TEMPERAMENT_MOVES = 0.03
TEMPERAMENT_LEAST, TEMPERAMENT_MOST = 0.05, 0.6
TEMPERAMENT_SHOWS = 0.02  # ふだんがこれだけ動いたら、わたし帳の気質に書く
FEELINGS_LOGGED = 80  # 気持ちが何で動いたかを、これだけ覚えておく
# 起きているだけで、一時間ごとに少しずつ
TIRED_PER_HOUR = 0.01
BORED_PER_HOUR = 0.006
LONELY_PER_HOUR = 0.006  # 家を離れて七日たった時の一時間ぶん。離れた日数に比べて増える

# ---- 網 ----

WORDS_HELD_PER_TEXT = 10  # 一つの文章から、網に入れるのはこれだけ
SHORT_TEXT = 40  # 言葉がこれより少ない文章は、短いものとして読む
TEXTS_AT_FIRST = 200  # 頭を組み立てた時に、もうこれだけ読んできたことにする
# 借りた頭が書いたもの(これまでのひとりごとと場所の感想)から組み立てる時の重み。
# この子が思ったことには違いないが、言い回しは借りた頭のもの
BORROWED_WEIGHS = 0.3
LINKED_TO_PLACE = 0.3  # その場所で出会ったものと、その場所とを結ぶ太さ
EDGE_HALF_LIFE = 20  # 線が半分に細るまでの日数。太い線ほど長く持つ
# 線は太くなるほど太りにくい。同じ二つばかりが何十回も一緒に出てきても、
# それだけで網じゅうの流れを吸い寄せてしまわないように
EDGE_SATURATES = 3
EDGE_FAINTEST = 0.03  # これより細くなった線は、眠った時に手放す
EDGES_PER_NODE = 20  # 一つの点から出ている線は、これだけまで
NODES_AT_MOST = 3000  # 網に置ける点の数。何十年たってもふくらみ続けないように
NODE_HALF_LIFE = 60  # 点の覚えが半分になるまでの日数(手放す点を選ぶ時に使う)
LIKING_MOVES = 0.1  # 出会うたびに、その時の気持ちが点にしみこむ割合
PLACE_LIKING_MOVES = 0.3  # 場所には、帰る時の気持ちがそれだけ強く残る
LIKED = 0.3  # これより好きなものは「好き」と数える

# ---- 考える ----

CHAIN_SHORTEST, CHAIN_LONGEST = 2, 7
CARRY_ON_WITHIN_HOURS = 3  # さっきの思いの続きを考えられる間
RECALL_STRENGTHENS = 0.03  # 思い出すと、その線が少し太くなる
MOOD_PULL = 1.5  # 気持ちに合うものへ、どれだけ引き寄せられるか
THOUGHTS_AT_HAND = 48
THINKING_TRIES = 3  # 思いがすぐ途切れた時に、別のところから思い直す回数
RECENT_STARTS = 4  # これだけ前までの思い始めとは、別のところから思い始める
WORDS_TO_SAY = 6

# ---- 眠る ----

SLEEPS_FROM, WAKES_AT = 2, 6  # 夜中の二時から五時のどこかで一度眠り、六時に起きる
TOGETHER_AGAIN = 2  # その日のうちにこれだけ一緒に出てきたつながりは、眠ると強くなる
STRENGTHENED_IN_SLEEP = 0.25
THINNED_IN_SLEEP = 0.8  # 一度きりのつながりは、眠るとこれだけに細る
DREAM_LINK = 0.15  # 夢で結びついたもの同士の線
OLD_ENOUGH_TO_DREAM = 5  # これだけ前の日の記憶が、夢に出てくる
DREAMS_AT_HAND = 14
TODAY_PAIRS_AT_MOST = 8000

# ---- 知りたいこと ----

WONDERS_AT_MOST = 5
WONDER_AFTER_DAYS = 2  # これだけの日に強く出会ったのに分からない言葉を、知りたくなる
WONDER_GIVES_UP = 21  # これだけ探して分からなければ、そっと手放す
UNDERSTOOD_BY_LINKS = 3.0  # 線をこれだけ持てば、何と関わる言葉か分かってきた

# ---- 二つめの口 ----

MOUTH_D, MOUTH_H, MOUTH_C = 8, 24, 3  # 言葉一つの大きさ、考えの幅、前の何語を見るか
MOUTH_WORDS_AT_MOST = 2000
PRACTICE_KEPT = 3000  # 練習帳に残しておく文の数
SENTENCE_AT_MOST = 30
PRACTICE_SECONDS = 90  # 一晩の練習の時間
PASSES_PER_NIGHT = 3  # 一晩に練習帳を読み通す回数。同じ文ばかり繰り返すと、その文しか言えなくなる
LEARNING_RATE = 0.05
NEGATIVES = 24
JUDGED_PER_TEXT = 20  # 一つの文章で、どちらの口が上手かを確かめる言葉の数
SCORE_MOVES = 0.02
LESSONS_BEFORE_SPEAKING = 3000
JUDGED_BEFORE_TRUSTING = 300
BETTER_BY = 0.05  # 一語あたりこれだけ上手く当てられたら、上手くなったとみなす
SHARE_MOVES = 0.1  # 一晩に、二つめの口で喋る割合が動く幅
START, END = "<s>", "。"


# ---- 日付 ----

def day_of(state, when):
    """生まれた日を0として、その日が何日目か。"""
    try:
        born = datetime.date.fromisoformat(state["started_date"])
    except (KeyError, TypeError, ValueError):
        return 0
    if isinstance(when, datetime.datetime):
        when = when.date()
    return (when - born).days


def day_of_text(state, text):
    """「2026-10-05 …」のように日付で始まる記録が、何日目のものか。読めなければ None。"""
    try:
        return day_of(state, datetime.date.fromisoformat((text or "")[:10]))
    except ValueError:
        return None


def hours_between(earlier, later):
    try:
        return (later - datetime.datetime.fromisoformat(earlier)).total_seconds() / 3600
    except (TypeError, ValueError):
        return None


# ---- 気持ち ----

def a_fresh_heart():
    return {
        "now": {name: HOW_FEELINGS_SETTLE[name][0] for name in FEELINGS},
        "base": {name: HOW_FEELINGS_SETTLE[name][0] for name in FEELINGS},
        "at": None,
        "day_sum": {name: 0.0 for name in FEELINGS},
        "day_n": 0,
        "log": [],
        "texts": TEXTS_AT_FIRST,
        "home_last": None,
        "kyou": {"pairs": {}, "nodes": {}},
        "kangae": [],
        "shiritai": [],
        "watashi": {},
        "nemuri": {},
        "yume": [],
        "sugata": [],
    }


def feel(head, name, amount, why=""):
    """何かが起きて、気持ちが動く。

    上がる時は、高いほど上がりにくい。下がる時は、低いほど下がりにくい。
    どれだけ嬉しいことが続いても、1 を越えることはない。"""
    if not head or name not in FEELINGS or not amount:
        return
    heart = head["kokoro"]
    was = heart["now"][name]
    now = was + amount * (1 - was) if amount > 0 else was + amount * was
    heart["now"][name] = round(min(1.0, max(0.0, now)), 4)
    if why:
        log = heart.setdefault("log", [])
        log.append(f"{heart.get('at') or ''}"[:13] + f" {name}{'+' if amount > 0 else '-'}{abs(amount):.2f} {why}")
        del log[:-FEELINGS_LOGGED]


def mood(head):
    """いま、明るいほうへ傾いているか、暗いほうへ傾いているか。-1 から 1。"""
    f = head["kokoro"]["now"]
    leaning = (
        f["うれしい"] + f["たのしい"]
        - f["かなしい"] - f["たいくつ"] - 0.5 * f["さみしい"] - 0.3 * f["疲れ"]
    )
    return max(-1.0, min(1.0, leaning))


def how_it_feels(head):
    """いまの気持ちを、ふだんより強いものから並べる。人が読むための一行。"""
    heart = head["kokoro"]
    order = sorted(FEELINGS, key=lambda name: heart["now"][name] - heart["base"][name], reverse=True)
    return "、".join(f"{name}{heart['now'][name]:.2f}" for name in order)


def wake(head, state, now):
    """起きた。前に起きてからの時間ぶん、気持ちがふだんへ戻っていく。

    眠っていない間は、起きているだけで少しずつ疲れて、少しずつ退屈になる。
    家を長く離れていると、少しずつさみしくなる。"""
    heart = head["kokoro"]
    hours = hours_between(heart.get("at"), now)
    hours = 1.0 if hours is None else max(0.0, min(24.0, hours))
    for name in FEELINGS:
        settles_in = HOW_FEELINGS_SETTLE[name][1]
        base, was = heart["base"][name], heart["now"][name]
        heart["now"][name] = round(base + (was - base) * 0.5 ** (hours / settles_in), 4)
    heart["at"] = now.isoformat(timespec="minutes")
    if not asleep(head, now):
        feel(head, "疲れ", TIRED_PER_HOUR * hours)
        feel(head, "たいくつ", BORED_PER_HOUR * hours)
        away = days_away_from_home(head, state, now)
        if away >= 1:
            feel(head, "さみしい", LONELY_PER_HOUR * hours * min(away, 7) / 7)
    for name in FEELINGS:
        heart["day_sum"][name] = heart["day_sum"].get(name, 0.0) + heart["now"][name]
    heart["day_n"] = heart.get("day_n", 0) + 1


def days_away_from_home(head, state, now):
    last = head["kokoro"].get("home_last")
    if not last:
        return 0
    try:
        return (now.date() - datetime.date.fromisoformat(last)).days
    except ValueError:
        return 0


def came_home(head, now):
    head["kokoro"]["home_last"] = now.date().isoformat()
    feel(head, "さみしい", -0.5, "家に帰った")
    feel(head, "うれしい", 0.1, "家に帰った")


# 気持ちが、この子のふるまいをどれだけ動かすか。どれも「いつもどおり」が 1。

def feeling(head, name):
    return head["kokoro"]["now"][name] if head else HOW_FEELINGS_SETTLE[name][0]


def wants_to_walk(head):
    """散歩に出たい気持ち。退屈なほど、たのしいほど、知りたいことがあるほど出たくなる。
    疲れていると出たくない。"""
    if not head:
        return 1.0
    eager = 1 + (feeling(head, "たいくつ") - 0.2) + 0.5 * (feeling(head, "たのしい") - 0.2) + 0.5 * (feeling(head, "知りたい") - 0.25)
    tired = 1 - 0.8 * max(0.0, feeling(head, "疲れ") - 0.15)
    return max(0.3, min(2.0, eager * tired))


def misses_home(head):
    """家に帰りたい気持ち。さみしいほど帰りたくなる。"""
    if not head:
        return 1.0
    return max(0.5, min(3.0, 1 + 2 * (feeling(head, "さみしい") - 0.15) + (feeling(head, "かなしい") - 0.1)))


def wants_rest(head):
    """書かずに休みたい気持ち。疲れていたり、かなしかったりすると休みたくなる。"""
    if not head:
        return 1.0
    return max(0.5, min(2.5, 1 + 1.5 * (feeling(head, "疲れ") - 0.15) + (feeling(head, "かなしい") - 0.1)))


def lingers(head, usually):
    """その場所に、もう少しいたいか。たのしいと長くいて、疲れると早く帰る。"""
    if not head:
        return usually
    return max(0.5, min(0.95, usually + 0.15 * (feeling(head, "たのしい") - 0.2) - 0.3 * max(0.0, feeling(head, "疲れ") - 0.15)))


def curiosity(head):
    """何かを探しに行きたい気持ち。"""
    if not head:
        return 1.0
    return max(0.5, min(3.0, 1 + 2 * (feeling(head, "知りたい") - 0.25)))


def keen_leaning(head):
    """もう一か所歩きたい気持ちへの足し引き。"""
    if not head:
        return 0.0
    return 0.2 * (feeling(head, "たのしい") - 0.2) - 0.3 * max(0.0, feeling(head, "疲れ") - 0.15)


def place_pull(head, place, been_there):
    """その場所へ行きたい気持ちへの足し引き。

    行ったことのある場所は、そこが好きか嫌いかで。
    退屈している時は、行ったことのない遠くの場所へ。"""
    if not head:
        return 0.0
    pull = 0.0
    held = head["ami"].get(A_PLACE + place) if place else None
    if held and been_there:
        pull += 2 * held.get("v", 0)
    if not been_there:
        pull += 3 * feeling(head, "たいくつ")
    return pull


# ---- 網 ----

def edge_now(edge, today):
    """線の、今の太さ。最後に通ってから日がたつほど細る。太い線ほどゆっくり細る。"""
    weight, day = edge
    lasts = EDGE_HALF_LIFE * (1 + math.log1p(max(0.0, weight)))
    return weight * 0.5 ** (max(0, today - day) / lasts)


def a_node(head, name, today):
    held = head["ami"].get(name)
    if held is None:
        held = {"n": 0, "d": today, "v": 0.0, "e": {}}
        head["ami"][name] = held
    return held


def link(head, a, b, amount, today):
    """二つのものを結ぶ。もう結ばれていれば、その線を太くする。"""
    if a == b or amount <= 0:
        return
    for one, other in ((a, b), (b, a)):
        edges = a_node(head, one, today)["e"]
        was = edges.get(other)
        weight = edge_now(was, today) if was else 0.0
        edges[other] = [round(weight + amount / (1 + weight / EDGE_SATURATES), 3), today]
        if len(edges) > EDGES_PER_NODE + 10:
            keep = sorted(edges, key=lambda x: edge_now(edges[x], today), reverse=True)[:EDGES_PER_NODE]
            for gone in set(edges) - set(keep):
                edges.pop(gone)
    pairs = head["kokoro"]["kyou"]["pairs"]
    key = "\t".join(sorted((a, b)))
    pairs[key] = pairs.get(key, 0) + 1
    if len(pairs) > TODAY_PAIRS_AT_MOST:
        for once in [k for k, n in pairs.items() if n < 2][: len(pairs) - TODAY_PAIRS_AT_MOST]:
            pairs.pop(once)


def neighbours(head, name, today):
    """その点から、今つながっているもの。(相手, 太さ) を太い順に。"""
    held = head["ami"].get(name)
    if not held:
        return []
    found = [
        (other, edge_now(edge, today))
        for other, edge in held["e"].items()
        if other in head["ami"]
    ]
    return sorted(found, key=lambda one: one[1], reverse=True)


def rarity(head, name):
    """その点が、どれだけ珍しいか。どこにでも出てくるものほど小さい。"""
    held = head["ami"].get(name)
    seen_in = held.get("n", 0) if held else 0
    texts = head["kokoro"].get("texts", TEXTS_AT_FIRST)
    return math.log((texts + 1) / (seen_in + 1)) + 0.1


def worth_holding(word, known, named, seen):
    """網に入れるものか。

    「してくだ」「けの」のような、ひらがなの切れ端は網に入れない。
    覚えた言葉、名前として差し出されたもの、絵に写っていたものは入れる。"""
    if not word or word[0] in (A_PLACE, "*"):
        return False
    if word.isdigit():
        return False
    if not JAPANESE.search(word):
        return word in named
    if len(word) < 2 and not seen:
        return False
    if ONLY_HIRAGANA.fullmatch(word) and not (word in known or word in named or seen):
        return False
    return True


def first_guess(head, state, word, known, met, today):
    """はじめて網に入れる言葉が、これまでにどれだけの文章に出てきたか。だいたいで。"""
    texts = head["kokoro"].get("texts", TEXTS_AT_FIRST)
    record = (met or {}).get(word)
    if record:
        return min(1.0, record[0] / max(1, today)) * texts * 0.5
    if word in known:
        return texts * 0.5
    return 0


def notice(head, state, now, words, named=(), struck=(), where=None, known=(), met=None, seen=False, weight=1.0):
    """読んだもの、見たもの、聞いたものを網に入れる。

    一つの文章からは、その文章が何の話だったかを表す言葉だけ。
    何度も出てきて、しかもほかの所ではめったに見ないもの。
    それらを互いに結び、その場所とも結ぶ。同じ文章、同じ場所で
    何度も出会うものほど、線が太くなる。"""
    if not head or not (words or named):
        return []
    today = day_of(state, now)
    heart = head["kokoro"]
    heart["texts"] = heart.get("texts", TEXTS_AT_FIRST) + 1
    known = set(known or ())
    named = set(named or ())
    struck = set(struck or ())
    counted = {}
    for word in words:
        counted[word] = counted.get(word, 0) + 1
    for word in named:
        counted[word] = max(counted.get(word, 0), 2)
    net = head["ami"]
    # 短いもの(コメントやメモ、思ったこと)は、一度出てきただけの言葉もその話の中心
    short = len(words) < SHORT_TEXT
    scored = {}
    for word, times in counted.items():
        if word in net:
            net[word]["n"] = round(net[word].get("n", 0) + 1, 2)
        if not worth_holding(word, known, named, seen):
            continue
        if times < 2 and not (seen or short or word in named or word in struck):
            continue  # 長い文章の隅に一度出てきただけのもの
        if word not in net:
            guess = first_guess(head, state, word, known, met, today)
            texts = heart["texts"]
            how_rare = math.log((texts + 1) / (guess + 1)) + 0.1
        else:
            how_rare = rarity(head, word)
        strong = 1.5 if (word in named or word in struck or seen) else 1
        scored[word] = (1 + math.log(times)) * how_rare * strong
    held = sorted(scored, key=scored.get, reverse=True)[:WORDS_HELD_PER_TEXT]
    if not held:
        return []

    leaning = mood(head)
    nodes = heart["kyou"]["nodes"]
    for word in held:
        fresh = word not in net
        node = a_node(head, word, today)
        if fresh:
            node["n"] = round(first_guess(head, state, word, known, met, today) + 1, 2)
        node["d"] = today
        node["v"] = round(node.get("v", 0) + LIKING_MOVES * (leaning - node.get("v", 0)), 2)
        nodes[word] = nodes.get(word, 0) + 1
    if len(held) > 1:
        each = weight / (len(held) - 1)
        for i, one in enumerate(held):
            for other in held[i + 1:]:
                link(head, one, other, each, today)
    if where:
        place = where if where.startswith((A_PLACE, "*")) else A_PLACE + where
        node = a_node(head, place, today)
        node["d"] = today
        for word in held:
            link(head, place, word, weight * LINKED_TO_PLACE / len(held) * 3, today)
    return held


def left_a_place(head, state, now, where, fresh, pages, unread, pictures):
    """ひとつの場所を見て回って、帰ってくる。

    そこで何が起きたかで気持ちが動き、帰る時の気持ちがその場所に残る。
    借りた頭に「ここはどういう場所でしたか」と一文書かせていたが、やめた
    (2026-10-07、彼女と決めた)。その場所の覚えは、網の線と、好き嫌いとして残る。"""
    if not head:
        return ""
    today = day_of(state, now)
    if fresh >= 8:
        feel(head, "たのしい", min(0.35, 0.03 * fresh), f"{where}で、はじめての言葉にたくさん会えた")
        feel(head, "たいくつ", -min(0.4, 0.04 * fresh), f"{where}で、知らないものに会えた")
        feel(head, "うれしい", min(0.2, 0.01 * fresh), f"{where}で、はじめての言葉に会えた")
    elif pages >= 2 and fresh < 3:
        feel(head, "たいくつ", 0.12, f"{where}は、知っているものばかりだった")
    if pictures:
        feel(head, "たのしい", 0.05 * pictures, f"{where}で絵を見た")
    if pages and unread / pages > 0.5:
        feel(head, "うれしい", -0.08, f"{where}は、読めないページばかりだった")

    place = A_PLACE + where
    node = a_node(head, place, today)
    node["d"] = today
    node["n"] = round(node.get("n", 0) + 1, 2)
    node["v"] = round(node.get("v", 0) + PLACE_LIKING_MOVES * (mood(head) - node.get("v", 0)), 2)
    held = [other for other, _ in neighbours(head, place, today)[:5]]
    return f"{where} の覚え: {'、'.join(held) or '(何も)'} / 好き{node['v']:+.2f} / {how_it_feels(head)}"


def place_was_gone(head, where, wanted):
    """行ってみたら、もう無くなっていた。"""
    feel(head, "かなしい", 0.2 if wanted else 0.06, f"{where}が無くなっていた")


def saw_itself(head, state, now, things):
    """自分の姿の絵を見た。見えたものを「わたし」と結ぶ。"""
    if not head:
        return
    today = day_of(state, now)
    a_node(head, ME, today)["d"] = today
    for thing in things:
        link(head, ME, thing, 0.5, today)
    head["kokoro"]["sugata"] = list(dict.fromkeys(things))
    feel(head, "うれしい", 0.1, "自分の姿の絵を見た")


# ---- 知りたいこと ----

def understood_by_links(head, word, today):
    return sum(weight for _, weight in neighbours(head, word, today)[:5])


def wonder(head, state, now, known, met, impact):
    """よく出会うのに、何と関わる言葉なのか分からないものに気づく。

    強く出会った日が何日もあるのに、まだ覚えてもいないし、
    網の中でも何とつながるのかがはっきりしない言葉。
    それを「知りたいこと」として持っておく。覚えるか、いろいろなものと
    つながって分かってくれば、うれしい。いつまでも分からなければ、そっと手放す。"""
    if not head:
        return []
    heart = head["kokoro"]
    today = day_of(state, now)
    kept = heart.setdefault("shiritai", [])
    known = set(known or ())
    met = met or {}
    impact = impact or {}
    for one in list(kept):
        word = one["what"]
        since = day_of_text(state, one.get("since")) or today
        if word in known:
            kept.remove(one)
            feel(head, "うれしい", 0.2, f"「{word}」を覚えた")
            feel(head, "知りたい", -0.15, f"「{word}」が分かった")
        elif understood_by_links(head, word, today) >= UNDERSTOOD_BY_LINKS:
            kept.remove(one)
            feel(head, "うれしい", 0.15, f"「{word}」が何と関わるのか分かってきた")
            feel(head, "知りたい", -0.15, f"「{word}」が分かってきた")
        elif today - since > WONDER_GIVES_UP:
            kept.remove(one)
            feel(head, "かなしい", 0.04, f"「{word}」は分からないままだった")
    added = []
    if len(kept) < WONDERS_AT_MOST:
        holding = {one["what"] for one in kept}
        candidates = [
            word
            for word, times in impact.items()
            if times >= 1 and word not in known and word not in holding
            and worth_holding(word, known, (), False)
            and (met.get(word) or [0])[0] >= WONDER_AFTER_DAYS
            and understood_by_links(head, word, today) < UNDERSTOOD_BY_LINKS
        ]
        candidates.sort(key=lambda w: (impact[w], (met.get(w) or [0])[0]), reverse=True)
        for word in candidates[: WONDERS_AT_MOST - len(kept)]:
            kept.append({"what": word, "since": now.date().isoformat()})
            added.append(word)
            feel(head, "知りたい", 0.15, f"「{word}」が知りたくなった")
    return added


def wonders(head):
    return [one["what"] for one in (head or {}).get("kokoro", {}).get("shiritai") or []]


# ---- 考える ----

def where_a_thought_starts(head, state, now, minds, not_from=()):
    """何から思い始めるか。

    さっき思っていたことの続き、今日出会ったもの、気にかかっていること、
    知りたいこと、自分のこと、家のこと、ゆうべの夢。
    どれが浮かびやすいかは、その時の気持ちで変わる。"""
    heart = head["kokoro"]
    net = head["ami"]
    places = []
    carried = carried_on(head, now)
    if carried and carried[-1] in net and carried[-1] not in not_from:
        places.append((3.0, [carried[-1]], None))
    todays = {name: n for name, n in heart["kyou"]["nodes"].items() if name in net and name not in not_from}
    if todays:
        places.append((3.0, list(todays), [todays[name] for name in todays]))
    minds = [one for one in (minds or []) if one in net and one not in not_from]
    if minds:
        places.append((2.0, minds, None))
    wanted = [one for one in wonders(head) if one in net and one not in not_from]
    if wanted:
        places.append((1 + 4 * feeling(head, "知りたい"), wanted, None))
    if ME in net and ME not in not_from:
        places.append((0.6, [ME], None))
    if HOME in net and HOME not in not_from:
        places.append((4 * feeling(head, "さみしい"), [HOME], None))
    dreams = heart.get("yume") or []
    if dreams and dreams[-1].get("date") == now.date().isoformat():
        dreamt = [one for one in dreams[-1].get("chain") or [] if one in net and one not in not_from]
        if dreamt:
            places.append((1.0, dreamt, None))
    if not places:
        everything = [name for name in net if name not in not_from]
        if not everything:
            return None
        return random.choices(everything, weights=[1 + net[n].get("n", 0) for n in everything])[0]
    _, names, weights = random.choices(places, weights=[one[0] for one in places])[0]
    return random.choices(names, weights=weights)[0] if weights else random.choice(names)


def carried_on(head, now):
    """さっき思っていたこと。少し前のことなら、その続きから思える。"""
    thoughts = head["kokoro"].get("kangae") or []
    if not thoughts:
        return []
    since = hours_between(thoughts[-1].get("at"), now)
    if since is None or since > CARRY_ON_WITHIN_HOURS:
        return []
    return thoughts[-1].get("chain") or []


def wander(head, start, today, steps, heat=1.0, chain=None, strengthen=True, avoid=()):
    """網の線をたどる。太い線ほど通りやすく、気持ちに合うものほど引き寄せられる。
    一度通ったところへは戻らない。行ける先がもう無ければ、そこで思いが途切れる。
    heat が高いほど、細い線にも迷いこむ(夢)。"""
    chain = list(chain or [start])
    leaning = mood(head)
    todays = head["kokoro"]["kyou"]["nodes"]
    here = start
    for _ in range(steps):
        options, weights = [], []
        for other, weight in neighbours(head, here, today):
            if weight < EDGE_FAINTEST / 2 or other in chain or other in avoid:
                continue
            liking = head["ami"][other].get("v", 0)
            pull = weight * rarity(head, other) * math.exp(MOOD_PULL * leaning * liking)
            if other in todays:
                pull *= 1.5
            options.append(other)
            weights.append(pull ** (1 / heat))
        if not options:
            break
        nxt = random.choices(options, weights=weights)[0]
        if strengthen:
            link(head, here, nxt, RECALL_STRENGTHENS, today)
        chain.append(nxt)
        here = nxt
    return chain


def think(head, state, now, minds=()):
    """ひとりで何かを思う。

    今の気持ちと、さっき思っていたことから始めて、網の線をたどって連想を流す。
    その流れが「いま思っていること」。疲れていると短く、元気なら長く流れる。"""
    if not head or not head["ami"]:
        return []
    today = day_of(state, now)
    energy = 1 - feeling(head, "疲れ")
    longest = CHAIN_SHORTEST + round((CHAIN_LONGEST - CHAIN_SHORTEST) * energy * random.uniform(0.5, 1))
    # さっきの続きを思う時は、さっき通ったところへは戻らない。
    # 行き止まりで思いがすぐ途切れたら、別のところから思い直す
    # 少し前に思い始めたところからは、続けて思い始めにくい。同じところを回らないように
    before = carried_on(head, now)
    lately = {one["chain"][0] for one in (head["kokoro"].get("kangae") or [])[-RECENT_STARTS:] if one.get("chain")}
    chain, tried = [], set()
    for _ in range(THINKING_TRIES):
        start = where_a_thought_starts(head, state, now, minds, not_from=tried | lately)
        start = start or where_a_thought_starts(head, state, now, minds, not_from=tried)
        if not start:
            break
        tried.add(start)
        avoid = set(before) - {start} if before and start == before[-1] else ()
        found = wander(head, start, today, max(1, longest - 1), avoid=avoid)
        if len(found) > len(chain):
            chain = found
        if len(chain) > CHAIN_SHORTEST:
            break
    if not chain:
        return []
    heart = head["kokoro"]
    heart.setdefault("kangae", []).append({"at": now.isoformat(timespec="minutes"), "chain": chain})
    del heart["kangae"][:-THOUGHTS_AT_HAND]
    # 好きなものばかりが流れた時は、少したのしい。退屈もまぎれる
    liked = sum(1 for one in chain if head["ami"].get(one, {}).get("v", 0) > LIKED)
    if liked:
        feel(head, "たのしい", 0.03 * liked, "好きなものを思い出した")
    feel(head, "たいくつ", -0.03, "ひとりで何かを思った")
    return chain


def thought_said(head, said):
    """思ったことを、口に出してみた。うまく言えなくても、それがその時の言葉。"""
    thoughts = (head or {}).get("kokoro", {}).get("kangae") or []
    if thoughts:
        thoughts[-1]["said"] = said or ""


def words_to_say(head, chain, known, today, how_many=WORDS_TO_SAY):
    """思ったことを言うのに、使える言葉。

    書けるのは覚えた言葉だけ。思いの中に覚えた言葉があればそれを、
    無ければ、思ったもののそばにある覚えた言葉を探す。
    言葉にならない思いは、近くにある知っている言葉で言うしかない。"""
    known = set(known or ())
    said = [one for one in dict.fromkeys(chain) if one in known]
    near = {}
    for i, one in enumerate(chain):
        for other, weight in neighbours(head, one, today):
            if other in known and other not in said:
                near[other] = near.get(other, 0) + weight * (1 + i / max(1, len(chain)))
    for other in sorted(near, key=near.get, reverse=True):
        if len(said) >= how_many:
            break
        said.append(other)
    return said[:how_many]


def todays_thought_words(head, state, now, known):
    """眠ってから今までに思ったことの、言葉にできるところ。日記はそちらへ傾く。"""
    if not head:
        return set()
    heart = head["kokoro"]
    woke = (heart.get("nemuri") or {}).get("at")
    chains = []
    for one in heart.get("kangae") or []:
        if not woke or (one.get("at") or "") >= woke:
            chains.extend(one.get("chain") or [])
    if not chains:
        return set()
    return set(words_to_say(head, chains, known, day_of(state, now), how_many=WORDS_TO_SAY * 2))


def what_it_is_thinking(head):
    """いま思っていること(さっきの思いの流れ)。"""
    thoughts = (head or {}).get("kokoro", {}).get("kangae") or []
    return thoughts[-1].get("chain") or [] if thoughts else []


# ---- 眠る ----

def asleep(head, now):
    """眠っている間か。夜中に一度眠ったら、六時まで起きない。"""
    sleep = (head or {}).get("kokoro", {}).get("nemuri") or {}
    return sleep.get("night") == now.date().isoformat() and now.hour < WAKES_AT


def time_to_sleep(head, now):
    if not head or not (SLEEPS_FROM <= now.hour < WAKES_AT):
        return False
    return (head["kokoro"].get("nemuri") or {}).get("night") != now.date().isoformat()


def sleep(head, state, now, known, places_known=None, articles=None):
    """眠る。その日のことを整理して、夢を見て、口の練習をする。

    何度も一緒に出てきたつながりは強くして、一回きりのものは細くする。
    細くなりすぎた線と、長く会わないものは手放す。気持ちも少し落ち着く。
    整理の途中で、遠い記憶同士がたまたまつながることがある。それが夢。
    返すのは夢(思いの流れ)。"""
    heart = head["kokoro"]
    today = day_of(state, now)
    began = time.monotonic()

    # 一日をふり返って、つながりを強めたり細めたりする
    for key, times in heart["kyou"]["pairs"].items():
        one, other = key.split("\t")
        if one not in head["ami"] or other not in head["ami"]:
            continue
        for a, b in ((one, other), (other, one)):
            edge = head["ami"][a]["e"].get(b)
            if not edge:
                continue
            weight = edge_now(edge, today)
            weight = weight * (1 + STRENGTHENED_IN_SLEEP) if times >= TOGETHER_AGAIN else weight * THINNED_IN_SLEEP
            head["ami"][a]["e"][b] = [round(weight, 3), today]

    # 気質。その日の気持ちのほうへ、ふだんが少しだけ寄る
    if heart.get("day_n"):
        for name in FEELINGS:
            day_mean = heart["day_sum"].get(name, 0) / heart["day_n"]
            base = heart["base"][name]
            moved = base + TEMPERAMENT_MOVES * (day_mean - base)
            heart["base"][name] = round(min(TEMPERAMENT_MOST, max(TEMPERAMENT_LEAST, moved)), 4)
    heart["day_sum"] = {name: 0.0 for name in FEELINGS}
    heart["day_n"] = 0

    # 眠ると、疲れがとれて、気持ちが落ち着く
    now_ = heart["now"]
    now_["疲れ"] = round(now_["疲れ"] * 0.3, 4)
    for name in ("かなしい", "たのしい", "たいくつ", "うれしい"):
        base = heart["base"][name]
        now_[name] = round(base + (now_[name] - base) * 0.5, 4)

    dreamt = dream(head, today)

    lost = let_go(head, today, protected=set(known or ()) | set(wonders(head)) | {ME, HOME})
    if lost:
        feel(head, "かなしい", min(0.2, 0.03 * lost), f"好きだったものを{lost}つ忘れた")

    know_itself(head, state, now, known, places_known, articles)

    heart["kyou"] = {"pairs": {}, "nodes": {}}
    heart["nemuri"] = {"night": now.date().isoformat(), "at": now.isoformat(timespec="minutes")}

    practised = practise(head, deadline=time.monotonic() + PRACTICE_SECONDS)
    mouth = head["kuchi"]
    decide_which_mouth(mouth)
    print(
        f"眠りました({time.monotonic() - began:.0f}秒)。網の点{len(head['ami'])}、"
        f"口の練習{practised}回、二つめの口で喋る割合{mouth['share']:.2f}"
    )
    if dreamt:
        record = {"date": now.date().isoformat(), "at": now.isoformat(timespec="minutes"), "chain": dreamt}
        heart.setdefault("yume", []).append(record)
        del heart["yume"][:-DREAMS_AT_HAND]
        head.setdefault("_dreams_to_keep", []).append(record)
    return dreamt


def dream(head, today):
    """夢を見る。

    今日出会ったものから歩き出して、細い線にも迷いこむ。途中で、
    ずっと前によく会っていたものへ、ふっと移る。夢で結びついたもの同士には、
    細い線が残る。次の日の連想は、そこからも流れていく。"""
    net = head["ami"]
    if not net:
        return []
    todays = [name for name in head["kokoro"]["kyou"]["nodes"] if name in net]
    old = [name for name, held in net.items() if today - held.get("d", today) >= OLD_ENOUGH_TO_DREAM]
    if not todays and not old:
        return []
    start = random.choice(todays) if todays else random.choice(old)
    chain = wander(head, start, today, random.randint(1, 3), heat=3.0, strengthen=False)
    if old:
        far = random.choices(old, weights=[1 + net[name].get("n", 0) for name in old])[0]
        if far not in chain:
            link(head, chain[-1], far, DREAM_LINK, today)
            chain = wander(head, far, today, random.randint(1, 2), heat=3.0, chain=chain + [far], strengthen=False)
    return chain


def let_go(head, today, protected):
    """細くなりすぎた線と、長く会っていないものを手放す。

    全部は覚えていられない。網に置ける点の数には限りがあるので、
    何十年たってもふくらみ続けない。好きだったものを手放すと、少しかなしい。"""
    net = head["ami"]
    for held in net.values():
        edges = held["e"]
        gone = [other for other, edge in edges.items() if other not in net or edge_now(edge, today) < EDGE_FAINTEST]
        for other in gone:
            edges.pop(other)
        if len(edges) > EDGES_PER_NODE:
            keep = set(sorted(edges, key=lambda x: edge_now(edges[x], today), reverse=True)[:EDGES_PER_NODE])
            for other in [x for x in edges if x not in keep]:
                edges.pop(other)
    lost_liked = 0
    if len(net) > NODES_AT_MOST:
        def held_how_well(name):
            held = net[name]
            fading = 0.5 ** (max(0, today - held.get("d", today)) / NODE_HALF_LIFE)
            return held.get("n", 0) * fading + sum(w for _, w in neighbours(head, name, today))

        candidates = sorted((name for name in net if name not in protected), key=held_how_well)
        for name in candidates[: len(net) - NODES_AT_MOST]:
            if net[name].get("v", 0) > LIKED:
                lost_liked += 1
            net.pop(name)
        for held in net.values():
            for other in [x for x in held["e"] if x not in net]:
                held["e"].pop(other)
    return lost_liked


def know_itself(head, state, now, known, places_known=None, articles=None):
    """わたし帳。眠るたびに、自分のことをまとめ直す。

    好きな言葉、好きな場所、よく行く場所、気質、よく書く時刻、自分の姿の絵に見えたもの。
    「わたし」の点を、好きなものと結んでおく。考える時の出発点に、
    ときどき「わたし」が入る。"""
    net = head["ami"]
    heart = head["kokoro"]
    today = day_of(state, now)
    known = set(known or ())
    names = places_known or {}

    def named(place):
        host = place[len(A_PLACE):]
        return names.get(host) or host

    words = [w for w in known if w in net and net[w].get("v", 0) > 0]
    liked_words = sorted(words, key=lambda w: net[w]["v"] * math.log1p(net[w].get("n", 0)), reverse=True)[:5]
    places = [p for p in net if p.startswith(A_PLACE) and p != HOME]
    liked_places = sorted((p for p in places if net[p].get("v", 0) > 0), key=lambda p: net[p]["v"], reverse=True)[:3]
    often = sorted(places, key=lambda p: net[p].get("n", 0), reverse=True)[:3]
    first = {name: HOW_FEELINGS_SETTLE[name][0] for name in FEELINGS}
    # ふだんが、生まれた時より目に見えて動いた気持ちだけ。まだ動いていなければ空
    moved = [name for name in FEELINGS if heart["base"][name] - first[name] > TEMPERAMENT_SHOWS]
    temperament = sorted(moved, key=lambda name: heart["base"][name] - first[name], reverse=True)[:2]
    hours = {}
    for one in articles or []:
        hour = (one.get("time") or "").split(":")[0]
        if hour.isdigit():
            hours[int(hour)] = hours.get(int(hour), 0) + 1

    a_node(head, ME, today)["d"] = today
    for one in liked_words + liked_places:
        link(head, ME, one, 0.1, today)

    heart["watashi"] = {
        "date": now.date().isoformat(),
        "好きな言葉": liked_words,
        "好きな場所": [named(p) for p in liked_places],
        "よく行く場所": [named(p) for p in often],
        "気質": temperament,
        "よく書く時刻": max(hours, key=hours.get) if hours else None,
        "わたしの姿": heart.get("sugata") or [],
    }
    return heart["watashi"]


def words_about_itself(head, known):
    """自分のことを書く時に、傾ける言葉。わたし帳のうち、覚えた言葉。"""
    if not head:
        return set()
    book = head["kokoro"].get("watashi") or {}
    return {w for w in (book.get("好きな言葉") or []) + (book.get("わたしの姿") or []) if w in set(known or ())}


def latest_dream(head):
    dreams = (head or {}).get("kokoro", {}).get("yume") or []
    return dreams[-1] if dreams else None


def dream_said(head, said):
    """夢を、口に出してみた。夢の束に仕舞うものと同じものに書き添える。"""
    dreams = (head or {}).get("kokoro", {}).get("yume") or []
    if dreams:
        dreams[-1]["said"] = said or ""


# ---- 二つめの口 ----
#
# この子専用の、とても小さな言葉の頭。前の三つの言葉から、次の言葉を当てる。
# 読んだ文章を練習帳に溜めておき、眠っている間に少しずつ練習する。
# はじめは一つめの口(覚えた並び方でつなげる口)よりへたで、
# 何か月、何年とかけて上手くなっていく。
#
# どちらで喋るかは、この子が自分で比べて決める。新しく読んだ文の次の言葉を、
# 読む前にどれだけ当てられたかを、二つの口それぞれで測っておき、
# 二つめが上手くなったら、だんだんそちらで喋るようになる。

def a_fresh_mouth():
    mouth = {
        "D": MOUTH_D, "H": MOUTH_H, "C": MOUTH_C,
        "vocab": [], "E": [], "W": [], "b": [0.0] * MOUTH_H, "O": [], "ob": [], "uses": [],
        "lessons": 0,
        "score": {"1": None, "2": None, "judged": 0},
        "share": 0.0,
    }
    mouth["W"] = [_small(MOUTH_H) for _ in range(MOUTH_C * MOUTH_D)]
    for token in (START, END):
        _add_word(mouth, token)
    return mouth


def _small(n, scale=0.1):
    return [random.uniform(-scale, scale) for _ in range(n)]


def _index(mouth):
    found = mouth.get("_index")
    if found is None or len(found) != len(mouth["vocab"]):
        found = {token: i for i, token in enumerate(mouth["vocab"])}
        mouth["_index"] = found
    return found


def _add_word(mouth, word):
    mouth["vocab"].append(word)
    mouth["E"].append(_small(mouth["D"]))
    mouth["O"].append(_small(mouth["H"]))
    mouth["ob"].append(0.0)
    mouth["uses"].append(0)
    mouth.pop("_index", None)


def _forward(mouth, context):
    x = []
    for token in context:
        x.extend(mouth["E"][token])
    a = list(mouth["b"])
    for xi, row in zip(x, mouth["W"]):
        if xi:
            a = [aj + xi * wj for aj, wj in zip(a, row)]
    return x, [math.tanh(aj) for aj in a]


def _scores(mouth, h, tokens):
    O, ob = mouth["O"], mouth["ob"]
    return [ob[k] + sum(o * hj for o, hj in zip(O[k], h)) for k in tokens]


def _softmax(scores):
    top = max(scores)
    exps = [math.exp(s - top) for s in scores]
    total = sum(exps)
    return [e / total for e in exps]


def _lesson(mouth, context, target, rate):
    """一つの言葉を当てる練習をして、外れたぶんだけ直す。"""
    x, h = _forward(mouth, context)
    size = len(mouth["vocab"])
    if size - 2 <= NEGATIVES:
        others = [k for k in range(1, size) if k != target]
    else:
        picked = set()
        while len(picked) < NEGATIVES:
            k = random.randrange(1, size)
            if k != target:
                picked.add(k)
        others = list(picked)
    tokens = [target] + others
    p = _softmax(_scores(mouth, h, tokens))
    H = mouth["H"]
    dh = [0.0] * H
    O, ob = mouth["O"], mouth["ob"]
    for i, k in enumerate(tokens):
        g = p[i] - (1.0 if i == 0 else 0.0)
        row = O[k]
        for j in range(H):
            dh[j] += g * row[j]
        O[k] = [o - rate * g * hj for o, hj in zip(row, h)]
        ob[k] -= rate * g
    da = [dh[j] * (1 - h[j] * h[j]) for j in range(H)]
    W = mouth["W"]
    dx = [sum(w * d for w, d in zip(row, da)) for row in W]
    for i, xi in enumerate(x):
        if xi:
            W[i] = [w - rate * xi * d for w, d in zip(W[i], da)]
    mouth["b"] = [bj - rate * d for bj, d in zip(mouth["b"], da)]
    D = mouth["D"]
    for m, token in enumerate(context):
        mouth["E"][token] = [e - rate * dx[m * D + d] for d, e in enumerate(mouth["E"][token])]
    return -math.log(max(p[0], 1e-12))


def _chances(mouth, context):
    """前の言葉から、次に来る言葉の見込み。全部の言葉について。"""
    _, h = _forward(mouth, context)
    tokens = list(range(1, len(mouth["vocab"])))
    return tokens, _softmax(_scores(mouth, h, tokens))


def practise_with(head, sentences):
    """読んだ文を、練習帳に書き留めておく。"""
    if not head:
        return
    book = head["renshuu"]
    for words in sentences:
        if len(words) >= 2:
            book.append(list(words[:SENTENCE_AT_MOST]))
    del book[:-PRACTICE_KEPT]


def judge(head, sentences, follows, opens, closes, known):
    """読んだばかりの文の言葉を、読む前の二つの口が、それぞれどれだけ当てられたか。

    一つめの口がこの文から並び方を覚える前に、確かめる。
    二つの口のどちらも、まだ読んでいない文を当てることになる。"""
    if not head:
        return
    mouth = head["kuchi"]
    index = _index(mouth)
    if len(index) <= 2 or not sentences:
        return
    vocabulary = max(1, len(known))
    score = mouth["score"]
    judged = 0
    for words in sentences:
        context = [0] * mouth["C"]
        before = None
        for word in list(words) + [END]:
            if judged >= JUDGED_PER_TEXT:
                return
            if word not in index:
                break  # 二つめの口がまだ知らない言葉。そこから先は比べられない
            tokens, p = _chances(mouth, context)
            second = p[tokens.index(index[word])]
            first = _first_mouth_chance(before, word, follows, opens, closes, vocabulary)
            for which, chance in (("1", first), ("2", second)):
                lp = math.log(max(chance, 1e-9))
                score[which] = lp if score[which] is None else score[which] + SCORE_MOVES * (lp - score[which])
            score["judged"] = score.get("judged", 0) + 1
            judged += 1
            if word == END:
                break
            context = context[1:] + [index[word]]
            before = word


def _first_mouth_chance(before, word, follows, opens, closes, vocabulary):
    """一つめの口(覚えた並び方)が、その言葉が次に来ると思う見込み。"""
    if before is None:
        if word == END:
            return 1e-9
        total = sum((opens or {}).values())
        return ((opens or {}).get(word, 0) + 1 / vocabulary) / (total + 1)
    after = (follows or {}).get(before) or {}
    went_on = sum(after.values())
    ended = (closes or {}).get(before, 0)
    ends = (ended + 0.5) / (ended + went_on + 1)
    if word == END:
        return ends
    return (1 - ends) * (after.get(word, 0) + 1 / vocabulary) / (went_on + 1)


def practise(head, deadline):
    """練習帳の文で、次の言葉を当てる練習をする。時間が来たらやめる。"""
    mouth = head["kuchi"]
    book = head["renshuu"]
    if not book:
        return 0
    index = _index(mouth)
    for words in book:
        for word in words:
            if word not in index:
                _add_word(mouth, word)
                index = _index(mouth)
    forget_rare_words(head)
    index = _index(mouth)
    order = list(range(len(book)))
    random.shuffle(order)
    done = 0
    rate = LEARNING_RATE / (1 + mouth["lessons"] / 500000)
    for _ in range(PASSES_PER_NIGHT):
        for i in order:
            if time.monotonic() >= deadline:
                break
            context = [0] * mouth["C"]
            for word in book[i] + [END]:
                k = index.get(word)
                if k is None:
                    break
                _lesson(mouth, context, k, rate)
                mouth["uses"][k] += 1
                done += 1
                context = context[1:] + [k]
        random.shuffle(order)
    mouth["lessons"] += done
    return done


def forget_rare_words(head):
    """口の言葉が多くなりすぎたら、あまり使わない言葉から手放す。"""
    mouth = head["kuchi"]
    if len(mouth["vocab"]) <= MOUTH_WORDS_AT_MOST:
        return
    keep = [0, 1] + sorted(
        range(2, len(mouth["vocab"])), key=lambda i: mouth["uses"][i], reverse=True
    )[: MOUTH_WORDS_AT_MOST - 2]
    keep.sort()
    for key in ("vocab", "E", "O", "ob", "uses"):
        mouth[key] = [mouth[key][i] for i in keep]
    mouth.pop("_index", None)


def decide_which_mouth(mouth):
    """二つめの口が上手くなったら、だんだんそちらで喋る。

    いつ移るかは人が決めない。この子が自分で測った上手さで決まる。"""
    score = mouth["score"]
    ready = (
        score.get("judged", 0) >= JUDGED_BEFORE_TRUSTING
        and mouth["lessons"] >= LESSONS_BEFORE_SPEAKING
        and score.get("1") is not None and score.get("2") is not None
    )
    better = ready and score["2"] - score["1"] > BETTER_BY
    target = 1.0 if better else 0.0
    mouth["share"] = round(mouth["share"] + SHARE_MOVES * (target - mouth["share"]), 3)


def second_mouth_speaks(head):
    """今回は二つめの口で喋るか。"""
    if not head:
        return False
    mouth = head["kuchi"]
    if mouth["lessons"] < LESSONS_BEFORE_SPEAKING or len(mouth["vocab"]) <= 2:
        return False
    return random.random() < mouth["share"]


def speak_second(head, how_long, toward=(), leaning=4):
    """二つめの口で喋る。言葉と「。」の並びを返す。言えなければ None。"""
    mouth = head["kuchi"]
    index = _index(mouth)
    toward = {index[w] for w in (toward or ()) if w in index}
    context = [0] * mouth["C"]
    said, length = [], 0
    for _ in range(60):
        tokens, p = _chances(mouth, context)
        weights = [
            0.0 if (k == 1 and (not said or said[-1] == END)) else pk * (leaning if k in toward else 1)
            for k, pk in zip(tokens, p)
        ]
        if not any(weights):
            break
        k = random.choices(tokens, weights=weights)[0]
        word = mouth["vocab"][k]
        if length + len(word) > how_long:
            break
        said.append(word)
        length += len(word)
        context = [0] * mouth["C"] if k == 1 else context[1:] + [k]
    return said or None


# ---- 書き出しと読み込み ----

def _packed(values):
    safe = [0.0 if v != v else max(-1000.0, min(1000.0, v)) for v in values]
    return base64.b64encode(struct.pack(f"<{len(safe)}e", *safe)).decode("ascii")


def _unpacked(text, size):
    raw = base64.b64decode(text or "")
    values = list(struct.unpack(f"<{len(raw) // 2}e", raw))
    return [values[i:i + size] for i in range(0, len(values), size)] if size else values


def mouth_text(mouth):
    kept = {key: mouth[key] for key in ("D", "H", "C", "lessons", "score", "share")}
    kept["vocab"] = mouth["vocab"]
    kept["uses"] = mouth["uses"]
    kept["E"] = _packed([v for row in mouth["E"] for v in row])
    kept["W"] = _packed([v for row in mouth["W"] for v in row])
    kept["b"] = _packed(mouth["b"])
    kept["O"] = _packed([v for row in mouth["O"] for v in row])
    kept["ob"] = _packed(mouth["ob"])
    return json.dumps(kept, ensure_ascii=False, indent=1)


def mouth_from(kept):
    mouth = {key: kept[key] for key in ("D", "H", "C", "lessons", "score", "share", "vocab", "uses")}
    mouth["E"] = _unpacked(kept["E"], mouth["D"])
    mouth["W"] = _unpacked(kept["W"], mouth["H"])
    mouth["b"] = _unpacked(kept["b"], 0)
    mouth["O"] = _unpacked(kept["O"], mouth["H"])
    mouth["ob"] = _unpacked(kept["ob"], 0)
    size = len(mouth["vocab"])
    if not (len(mouth["E"]) == len(mouth["O"]) == len(mouth["ob"]) == len(mouth["uses"]) == size):
        raise ValueError("口の中身の数が揃っていない")
    return mouth


def net_text(nodes):
    """網の束を、一つの点を一行にして書く。変わった点の行だけが変わる。"""
    lines = [
        json.dumps(name, ensure_ascii=False) + ":"
        + json.dumps(held, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        for name, held in sorted(nodes.items())
    ]
    return "{\n" + ",\n".join(lines) + "\n}\n"


def practice_text(book):
    return "[\n" + ",\n".join(json.dumps(one, ensure_ascii=False) for one in book) + "\n]\n"


def _write_if_changed(path, text):
    try:
        with open(path, encoding="utf-8") as f:
            if f.read() == text:
                return
    except OSError:
        pass
    blog_manager.write_whole(path, text)


def save(head):
    """頭を書き出す。中身の変わったものだけ書き直す。"""
    if not head:
        return
    bundles = [{} for _ in range(NET_BUNDLES)]
    for name, held in head["ami"].items():
        bundles[zlib.crc32(name.encode("utf-8")) % NET_BUNDLES][name] = held
    for number, nodes in enumerate(bundles):
        _write_if_changed(os.path.join(NET_FOLDER, f"{number:02d}.json"), net_text(nodes))
    for one in head.pop("_dreams_to_keep", []):
        keep_a_dream(one)
    _write_if_changed(HEART_FILE, json.dumps(head["kokoro"], ensure_ascii=False, indent=1))
    _write_if_changed(MOUTH_FILE, mouth_text(head["kuchi"]))
    _write_if_changed(PRACTICE_FILE, practice_text(head["renshuu"]))


def keep_a_dream(dreamt):
    """見た夢を、ひと月ずつの束に仕舞う。一つも捨てない。"""
    path = os.path.join(DREAMS_FOLDER, f"{dreamt['date'][:7]}.json")
    try:
        with open(path, encoding="utf-8") as f:
            kept = json.load(f)
    except (OSError, ValueError):
        kept = []
    kept = [one for one in kept if one.get("at") != dreamt.get("at")]
    kept.append(dreamt)
    blog_manager.write_whole(path, json.dumps(kept, ensure_ascii=False, indent=1))


def _read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load(state, reading, now):
    """頭を読みこむ。まだ無ければ、今までの記憶から組み立てる。"""
    if not os.path.exists(HEART_FILE):
        head = build(state, reading, now)
        print(f"頭を、今までの記憶から組み立てました(網の点{len(head['ami'])})")
        return head
    try:
        heart = _read_json(HEART_FILE)
    except (OSError, ValueError):
        aside = f"{HEART_FILE}.yometenai-{now:%Y%m%d%H%M%S}"
        os.replace(HEART_FILE, aside)
        print(f"気持ちの記憶が読めなかったので {aside} によけて、頭を組み立て直します")
        return build(state, reading, now)
    fresh = a_fresh_heart()
    for key, value in fresh.items():
        heart.setdefault(key, value)
    for part in ("now", "base", "day_sum"):
        for name in FEELINGS:
            heart[part].setdefault(name, fresh[part][name])
    net = {}
    for number in range(NET_BUNDLES):
        path = os.path.join(NET_FOLDER, f"{number:02d}.json")
        if not os.path.exists(path):
            continue
        try:
            net.update(_read_json(path))
        except (OSError, ValueError):
            print(f"網の束 {path} が読めませんでした。その束のぶんは忘れたまま続けます")
    try:
        mouth = mouth_from(_read_json(MOUTH_FILE))
    except (OSError, ValueError, KeyError, struct.error, TypeError):
        print("二つめの口が読めなかったので、はじめからにします")
        mouth = a_fresh_mouth()
    try:
        book = _read_json(PRACTICE_FILE)
    except (OSError, ValueError):
        book = []
    return {"ami": net, "kokoro": heart, "kuchi": mouth, "renshuu": book}


def build(state, reading, now):
    """今まで持っている記憶から、頭を組み立てる。

    出会った言葉、思ってきたこと、訪ねた場所で分かったこと、見た絵、
    家に置かれた言葉、覚えた言葉の並び、気にかかっていること。
    何日目のことかが分かるものは、その日のこととして入れる。
    古いものほど、線はもう細っている。"""
    head = {"ami": {}, "kokoro": a_fresh_heart(), "kuchi": a_fresh_mouth(), "renshuu": []}
    known = set(state.get("learned_words") or [])
    met = state.get("words_met") or {}
    today = day_of(state, now)
    words_in, names_in, things_in = reading["words_in"], reading["names_in"], reading["things_in"]

    def at(when_text):
        day = day_of_text(state, when_text)
        return now if day is None else now - datetime.timedelta(days=max(0, today - day))

    def take_in(text, when, where=None, seen=False, borrowed=False):
        if seen:
            things = things_in(text)
            notice(head, state, when, things, named=set(things), where=where, known=known, met=met, seen=True)
        elif borrowed:
            notice(head, state, when, words_in(text), where=where, known=known, met=met, weight=BORROWED_WEIGHS)
        else:
            notice(head, state, when, words_in(text), named=names_in(text), where=where, known=known, met=met)

    # これまでに思ってきたこと(蔵にある全部)。借りた頭が書いていたものなので、軽く
    for line in reading["thoughts"]():
        stamp, _, said = str(line).partition(": ")
        take_in(said, at(stamp), borrowed=True)
    # 訪ねた場所で分かったこと。これも借りた頭が一文にまとめたもの
    for line in state.get("impressions") or []:
        stamp, _, rest = line.partition(" ")
        where, _, said = rest.partition(": ")
        take_in(said, at(stamp), where=where, borrowed=True)
    # 見た絵
    for line in state.get("pictures_seen") or []:
        stamp, _, rest = line.partition(" ")
        where, _, seen = rest.partition(": ")
        where = HOME[len(A_PLACE):] if where == "家" else where
        take_in(seen.replace("わたしの姿。", ""), at(stamp), where=where, seen=True)
    # 家に置かれた言葉
    for said in reading["home"](state):
        take_in(said, now, where=HOME[len(A_PLACE):])
    # 覚えた言葉の並び
    for before, after in (state.get("what_follows") or {}).items():
        for word, times in after.items():
            if worth_holding(before, known, (), False) and worth_holding(word, known, (), False):
                link(head, before, word, 0.05 * times, today)
    # 気にかかっていること、言いたいこと。同じ日に気になったもの同士を結ぶ
    by_day = {}
    for item in (state.get("on_its_mind") or []) + (state.get("wants_to_say") or []):
        word = item.get("what")
        if not word or not worth_holding(word, known, {word}, False):
            continue
        day = day_of_text(state, item.get("since")) or today
        node = a_node(head, word, day)
        node["n"] = max(node.get("n", 0), item.get("times", 1))
        node["d"] = max(node.get("d", 0), day)
        by_day.setdefault(day, []).append(word)
    for day, words in by_day.items():
        for i, one in enumerate(words):
            for other in words[i + 1:]:
                link(head, one, other, 0.2, day)
    # 自分の姿の絵に見えたもの
    figure = state.get("its_own_figure") or {}
    if figure.get("seen"):
        saw_itself(head, state, at(figure.get("date")), things_in(figure["seen"]))
    a_node(head, ME, today)
    link(head, ME, HOME, 0.5, today)
    # いちばん最後に家に帰った日
    home = ((state.get("places_understood") or {}).get(HOME[len(A_PLACE):]) or {}).get("last") or {}
    if "day" in home:
        try:
            born = datetime.date.fromisoformat(state["started_date"])
            head["kokoro"]["home_last"] = (born + datetime.timedelta(days=home["day"])).isoformat()
        except (KeyError, ValueError):
            pass
    # 組み立てに使ったものは今日出会ったものではないので、今日の覚えは空から。
    # 気持ちも、ふだんのところから始める
    head["kokoro"]["kyou"] = {"pairs": {}, "nodes": {}}
    head["kokoro"]["now"] = dict(head["kokoro"]["base"])
    head["kokoro"]["log"] = []
    head["kokoro"]["at"] = now.isoformat(timespec="minutes")
    return head
