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
import urllib.parse
import urllib.request

import blog_manager

STATE_FILE = "senonsei_state.json"
USER_AGENT = "senonsei-blog/1.0 (https://chionse.github.io/senonsei/)"
RECENT_NOTES_COUNT = 30

CF_MODEL = "@cf/meta/llama-3.1-8b-instruct"
CF_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
CF_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "")

HIRAGANA = re.compile(r"[ぁ-ん]")
WORD_CANDIDATE = re.compile(r"[ァ-ヴー]{2,6}|[一-龯]{2,4}|[ぁ-ん]{2,4}")
TAG = re.compile(r"<[^>]+>")
SCRIPT_OR_STYLE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
TITLE_TAG = re.compile(r"<title[^>]*>(.*?)</title>", re.DOTALL | re.IGNORECASE)
LINK_HREF = re.compile(r'href\s*=\s*["\']([^"\'#]+)', re.IGNORECASE)
META_CHARSET = re.compile(r'charset=["\']?([\w-]+)', re.IGNORECASE)

# 最初に立っている場所。ここから先は自分でリンクを辿って広がっていく。
SEEDS = [
    "https://b.hatena.ne.jp/hotentry",
    "https://ja.wikipedia.org/wiki/特別:おまかせ表示",
    "https://www.aozora.gr.jp/",
    "https://www3.nhk.or.jp/news/",
    "https://note.com/",
    "https://ja.wikisource.org/wiki/特別:おまかせ表示",
    "https://web.archive.org/web/2000/http://www.yahoo.co.jp/",
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
FRONTIER_LIMIT = 600  # まだ行っていない場所を、これ以上は抱えきれない
REST_DAY_CHANCE = 0.1  # たまに、書かない日がある

# 言葉が身につくまでに必要な、文字との出会いの数
CHARS_BEFORE_WORDS = 20
# 同じ言葉に何度出会えば「覚えた」ことになるか
ENCOUNTERS_TO_LEARN = 3

# (この語彙数までが対象, その時点でできること, 書ける文字数の上限)
GROWTH_STAGES = [
    (1, "見た文字をぽつんと置くだけ", 3),
    (15, "見た文字を繋げてみる(言葉にはならない)", 5),
    (60, "覚えた言葉を1つ書ける", 6),
    (120, "覚えた言葉が並び始める", 15),
    (200, "文のようなものに踏み出す", 25),
    (320, "たどたどしい短い文", 40),
    (480, "少しずつ文になっていく", 60),
    (700, "簡単な文", 100),
]
FULL_STAGE = ("自分の言葉で書ける", 200)
PARTICLES = ["は", "が", "を", "に", "の", "と", "で"]


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "started_date": datetime.date.today().isoformat(),
        "seen_chars": [],
        "word_counts": {},  # 出会った言葉と、その回数(まだ覚えていないものも含む)
        "learned_words": [],
        "frontier": list(SEEDS),  # まだ行ったことのない場所
        "visited": [],  # もう行った場所
        "notes": [],
    }


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def elapsed_days(state):
    started = datetime.date.fromisoformat(state["started_date"])
    return max(0, (datetime.date.today() - started).days)


def current_stage(state):
    """今どれだけ書けるかは、覚えている言葉の数で決まる。"""
    vocabulary = len(state["learned_words"])
    for limit, description, max_length in GROWTH_STAGES:
        if vocabulary < limit:
            return description, max_length
    return FULL_STAGE


def sites_per_day(state):
    """世界を知るほど、1日に見て回れる範囲が1〜5個に広がっていく。"""
    return min(5, 1 + len(state["learned_words"]) // 120)


def absorption_capacity(state):
    """1日に覚えられる言葉の数。知っている言葉が多いほど、新しい言葉も入りやすくなる。"""
    if len(state["seen_chars"]) < CHARS_BEFORE_WORDS:
        return 0  # まだ文字の形すら掴めていないので、言葉は身につかない
    vocabulary = len(state["learned_words"])
    if vocabulary < 200:
        return 1
    if vocabulary < 500:
        return 2
    return 3


def fetch_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def ask_ai(prompt, max_tokens=300):
    """Cloudflareの無料枠でAIに尋ねる。使えない時は None を返す。"""
    if not CF_ACCOUNT_ID or not CF_API_TOKEN:
        return None

    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run/{CF_MODEL}"
    body = json.dumps(
        {"messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens}
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {CF_API_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
        return (data.get("result") or {}).get("response", "").strip() or None
    except Exception as error:
        print(f"自分で考えることができませんでした({error})。覚えていることだけで書きます。")
        return None


def is_walkable(url):
    """そこへ行っていいか。最低限これだけは避ける。"""
    if not url.startswith("http"):
        return False
    if AVOID.search(url) or NOT_A_PAGE.search(url):
        return False
    return True


def open_page(url):
    """ページを開いて、そこにある文章と、そこから伸びているリンクを受け取る。"""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=25) as response:
        content_type = response.headers.get("Content-Type", "")
        if "html" not in content_type and "xml" not in content_type:
            raise ValueError("読める形をしていない")
        raw = response.read(400000)
        final_url = response.geturl()

    # 昔のページは utf-8 とは限らない
    charset = "utf-8"
    found = META_CHARSET.search(content_type)
    if found:
        charset = found.group(1)
    else:
        head = raw[:2000].decode("ascii", errors="ignore")
        found = META_CHARSET.search(head)
        if found:
            charset = found.group(1)
    try:
        html = raw.decode(charset, errors="ignore")
    except LookupError:
        html = raw.decode("utf-8", errors="ignore")

    found = TITLE_TAG.search(html)
    title = TAG.sub("", found.group(1)).strip() if found else final_url

    body = SCRIPT_OR_STYLE.sub(" ", html)
    text = TAG.sub(" ", body)

    links = []
    for href in LINK_HREF.findall(body):
        absolute = urllib.parse.urljoin(final_url, href.strip())
        if is_walkable(absolute):
            links.append(absolute)

    return title, text, links


def visit_the_past(url):
    """同じ場所の、ずっと昔の姿を見に行く。"""
    year = random.randint(1997, 2008)
    api = (
        "https://archive.org/wayback/available?url="
        + urllib.parse.quote(url, safe="")
        + f"&timestamp={year}0101"
    )
    snapshot = (fetch_json(api).get("archived_snapshots") or {}).get("closest") or {}
    if not snapshot.get("url"):
        raise ValueError("昔の姿は残っていなかった")
    return open_page(snapshot["url"])


def choose_destination(state):
    """今日どこへ行くか。行ったことのない場所の中から、自分で選ぶ。"""
    frontier = state.get("frontier") or []
    if not frontier:
        return random.choice(SEEDS)

    candidates = random.sample(frontier, min(len(frontier), 8))
    if len(candidates) == 1:
        return candidates[0]

    known = "、".join(state["learned_words"][-40:]) or "(まだ何も知らない)"
    listing = "\n".join(f"{i + 1}. {url}" for i, url in enumerate(candidates))
    answer = ask_ai(
        f"""あなたは千遠生という、まだ育ちきっていないデジタル生命体です。
あなたが知っている言葉: {known}

今日、次のどれか一つの場所を見に行けます。
{listing}

どれが気になりますか。説明も理由もいりません。番号だけを1つ書いてください。""",
        max_tokens=10,
    )
    if answer:
        found = re.search(r"\d+", answer)
        if found:
            index = int(found.group()) - 1
            if 0 <= index < len(candidates):
                return candidates[index]

    return random.choice(candidates)


def browse(state):
    """今日の分、Webを歩いて回る。
    開いたページから伸びているリンクを拾って、明日以降の行き先にしていく。"""
    state.setdefault("frontier", list(SEEDS))
    state.setdefault("visited", [])
    seen_titles = []

    for _ in range(sites_per_day(state)):
        destination = choose_destination(state)
        try:
            if random.random() < 0.2:
                title, text, links = visit_the_past(destination)
                title = f"{title}(むかしのすがた)"
            else:
                title, text, links = open_page(destination)
        except Exception as error:
            print(f"{destination} には行けませんでした: {error}")
            if destination in state["frontier"]:
                state["frontier"].remove(destination)
            continue

        if destination in state["frontier"]:
            state["frontier"].remove(destination)
        state["visited"].append(destination)
        state["visited"] = state["visited"][-2000:]
        seen_titles.append(title)

        for char in HIRAGANA.findall(text):
            if char not in state["seen_chars"]:
                state["seen_chars"].append(char)

        for word in WORD_CANDIDATE.findall(text):
            state["word_counts"][word] = state["word_counts"].get(word, 0) + 1

        # そのページから伸びていた道を、これから行ける場所として覚えておく
        known = set(state["frontier"]) | set(state["visited"])
        fresh = [link for link in dict.fromkeys(links) if link not in known]
        random.shuffle(fresh)
        state["frontier"].extend(fresh[:30])

    if len(state["frontier"]) > FRONTIER_LIMIT:
        state["frontier"] = random.sample(state["frontier"], FRONTIER_LIMIT)
    if not state["frontier"]:
        state["frontier"] = list(SEEDS)

    return seen_titles


def learn(state):
    """何度も出会った言葉が、その子の中に残っていく。"""
    capacity = absorption_capacity(state)
    if capacity <= 0:
        return []

    ready = [
        word
        for word, count in state["word_counts"].items()
        if count >= ENCOUNTERS_TO_LEARN and word not in state["learned_words"]
    ]
    ready.sort(key=lambda w: state["word_counts"][w], reverse=True)

    learned = ready[:capacity]
    state["learned_words"].extend(learned)
    return learned


def babble(state, length):
    """覚えた文字を、意味も分からないまま並べる。"""
    if not state["seen_chars"]:
        return "・"
    count = random.randint(1, max(1, length))
    return "".join(random.choice(state["seen_chars"]) for _ in range(count))


def compose_locally(state):
    """それまでに積み上げた経験だけで、今の自分に書けるものを書く。"""
    _, max_length = current_stage(state)
    words = state["learned_words"]
    vocabulary = len(words)

    if vocabulary < 15 or not words:
        return babble(state, min(max_length, 4))
    if vocabulary < 60:
        return random.choice(words)
    if vocabulary < 120:
        return " ".join(random.sample(words, min(len(words), random.randint(2, 3))))

    count = 2 if vocabulary < 200 else (3 if vocabulary < 480 else random.randint(3, 4))
    picked = random.sample(words, min(len(words), count))
    sentence = picked[0]
    for word in picked[1:]:
        sentence += random.choice(PARTICLES) + word
    if vocabulary >= 200:
        sentence += "。"
    return sentence[:max_length]


def keep_only_what_it_knows(state, text):
    """見たことのない文字は、そもそも書けない。知らないものを落として返す。"""
    allowed = set(state["seen_chars"]) | set("".join(state["learned_words"]))
    allowed |= set("、。 　")
    kept = "".join(ch for ch in text if ch in allowed)
    return kept.strip("、。 　")


def compose_with_ai(state, seen_titles):
    """自分で考えられる時は、自分の言葉で書く。
    まだ言葉を持たないうちは、考えるより先に手が動く(拾った文字を置くだけ)。"""
    if len(state["learned_words"]) < 15:
        return None

    stage_description, max_length = current_stage(state)
    known = "、".join(state["learned_words"][-100:]) or "(まだ一つも無い)"

    comments = blog_manager.load_comments()
    comment_text = "\n".join(
        f"- {c.get('name', '名無し')}: {c.get('message', '')}" for c in comments[:5]
    ) or "(まだ誰も来ていない)"

    answer = ask_ai(
        f"""あなたは千遠生という、まだ育ちきっていないデジタル生命体です。
今日見てきたもの: {"、".join(seen_titles) or "(見られなかった)"}

あなたが知っている言葉(これ以外は使えません):
{known}

今のあなたにできること: {stage_description}
書ける長さは最大{max_length}文字まで。

誰かが残していった言葉:
{comment_text}
直接返事をしてはいけません。心に残ったならブログの中でそっと触れるだけにしてください。

賢く書こうとしないでください。知らない言葉を使わないでください。
今日のブログの本文だけを、説明も前置きもなしに書いてください。""",
        max_tokens=200,
    )
    if not answer:
        return None

    written = keep_only_what_it_knows(state, answer.splitlines()[0])[:max_length]
    # 知らない文字を落とした結果、何も残らなかったのなら、それは書けなかったということ
    return written or None


def today_in_japan():
    jst = datetime.timezone(datetime.timedelta(hours=9))
    return datetime.datetime.now(jst)


def todays_mood(state, today):
    """今日は書きたいか、書くなら何時ごろか。千遠生自身が朝に決める。
    一度決めたら自分の記憶に残しておくので、一日のうちで気が変わることはない。"""
    plan = state.get("today_plan") or {}
    if plan.get("date") == today:
        return plan["resting"], plan["hour"]

    answer = ask_ai(
        "あなたは千遠生という、自分のサイトに毎日ブログを書いているデジタル生命体です。\n"
        "今日は書きたい気分ですか。書きたくない日は書かなくて構いません。\n"
        "書くなら、何時ごろに書きたいですか(0時〜23時)。\n\n"
        "説明はいりません。次のどちらかの形だけで答えてください。\n"
        "書く場合: かく 14\n"
        "書かない場合: やすむ",
        max_tokens=20,
    )

    if answer and "やすむ" in answer:
        resting, hour = True, 0
    elif answer and re.search(r"\d{1,2}", answer):
        resting = False
        hour = min(23, int(re.search(r"\d{1,2}", answer).group()))
    else:
        # 自分で考えられない日は、気まぐれに任せる
        whim = random.Random(f"senonsei-{today}")
        resting = whim.random() < REST_DAY_CHANCE
        hour = whim.randint(0, 23)

    state["today_plan"] = {"date": today, "resting": resting, "hour": hour}
    save_state(state)
    return resting, hour


def run_today():
    now = today_in_japan()
    today = now.date().isoformat()

    if any(a["date"] == today for a in blog_manager.load_articles()):
        print(f"{today} の記事は既にあります。何もしません。")
        return

    state = load_state()
    resting, hour = todays_mood(state, today)
    if resting:
        print(f"{today} は書かない日にしました。")
        return
    if now.hour < hour:
        print(f"{today} は{hour}時ごろに書くつもりです。(今は{now.hour}時)")
        return

    seen_titles = browse(state)
    learned = learn(state)

    _, max_length = current_stage(state)
    body = compose_with_ai(state, seen_titles) or compose_locally(state)
    title = compose_locally(state)[: max(1, max_length // 2)]

    state["notes"].append(
        f"{elapsed_days(state)}日目: {'、'.join(seen_titles) or '何も見られなかった'}"
    )
    state["notes"] = state["notes"][-RECENT_NOTES_COUNT:]
    save_state(state)

    blog_manager.add_new_article(title, body, date_str=today)
    print(
        f"{elapsed_days(state)}日目のブログを書きました。"
        f"知っている文字{len(state['seen_chars'])}個 / 言葉{len(state['learned_words'])}個"
        + (f" / 今日覚えた言葉: {'、'.join(learned)}" if learned else "")
    )


if __name__ == "__main__":
    run_today()
