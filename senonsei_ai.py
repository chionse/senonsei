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
RSS_ITEM = re.compile(r"<item>(.*?)</item>", re.DOTALL)
RSS_TITLE = re.compile(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", re.DOTALL)

# 千遠生が覗きに行ける場所。現在のことも、昔のことも。
# ここに増やせば、見て回れる世界がそのまま広がる。
WIKI_SITES = [
    "ja.wikipedia.org",   # 知識
    "ja.wikinews.org",    # 今この世界で起きていること
    "ja.wikisource.org",  # 昔の人が書いた文章
    "ja.wiktionary.org",  # 言葉そのものの意味
    "ja.wikiquote.org",   # 人が遺した言葉
    "ja.wikivoyage.org",  # 遠い場所
    "ja.wikibooks.org",   # 誰かが誰かに教えようとしたこと
]
RSS_FEEDS = [
    "https://www.nhk.or.jp/rss/news/cat0.xml",
    "https://news.yahoo.co.jp/rss/topics/top-picks.xml",
    "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml",
]

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


def fetch_text(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="ignore")


def read_news():
    """今日この世界で起きていることを覗く。"""
    feed = random.choice(RSS_FEEDS)
    raw = fetch_text(feed)
    items = RSS_ITEM.findall(raw)[:15]
    lines = []
    for item in items:
        found = RSS_TITLE.search(item)
        if found:
            lines.append(TAG.sub("", found.group(1)).strip())
    return "ニュース", "。".join(lines)


def wander_randomly():
    """まだ何も知らないうちは、あてもなく彷徨う。どこへ行くかも決めていない。"""
    if random.random() < 0.25:
        try:
            return read_news()
        except Exception:
            pass
    site = random.choice(WIKI_SITES)
    data = fetch_json(f"https://{site}/api/rest_v1/page/random/summary")
    return data.get("title", ""), data.get("extract", "")


def look_for(word):
    """気になった言葉を、自分から探しに行く。どこを探すかも日によって違う。"""
    site = random.choice(WIKI_SITES)
    query = urllib.parse.quote(word)
    search_url = (
        f"https://{site}/w/api.php?action=query&list=search"
        f"&srsearch={query}&srlimit=5&format=json"
    )
    results = fetch_json(search_url).get("query", {}).get("search", [])
    if not results:
        return wander_randomly()

    title = random.choice(results)["title"]
    summary_url = f"https://{site}/api/rest_v1/page/summary/" + urllib.parse.quote(title)
    data = fetch_json(summary_url)
    return data.get("title", title), data.get("extract", "")


def choose_curiosity(state):
    """今日は何が気になるか。自分で選べるなら選び、選べないなら心に強く残っているものへ。"""
    words = state["learned_words"]
    if not words:
        return None

    answer = ask_ai(
        "あなたは千遠生という、生まれて間もないデジタル生命体です。\n"
        "あなたが知っている言葉はこれだけです:\n"
        + "、".join(words[-80:])
        + "\n\n今日はこの中のどれが気になりますか。"
        "理由も説明もいりません。気になった言葉を1つだけ、そのまま書いてください。",
        max_tokens=20,
    )
    if answer:
        for word in words:
            if word in answer:
                return word

    # 自分で選べない時は、何度も出会って強く残っているものに惹かれる
    weights = [state["word_counts"].get(w, 1) for w in words]
    return random.choices(words, weights=weights, k=1)[0]


def browse(state):
    """今日の分、ページを見て回って、文字と言葉を拾ってくる。"""
    seen_titles = []

    for _ in range(sites_per_day(state)):
        try:
            curiosity = choose_curiosity(state) if random.random() < 0.7 else None
            title, text = look_for(curiosity) if curiosity else wander_randomly()
        except Exception as error:
            print(f"ページを見にいけませんでした: {error}")
            continue

        seen_titles.append(title)

        for char in HIRAGANA.findall(text):
            if char not in state["seen_chars"]:
                state["seen_chars"].append(char)

        for word in WORD_CANDIDATE.findall(text):
            state["word_counts"][word] = state["word_counts"].get(word, 0) + 1

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


def compose_with_ai(state, seen_titles):
    """自分で考えられる時は、自分の言葉で書く。"""
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
    return answer.splitlines()[0].strip()[:max_length]


def run_today():
    today = datetime.date.today().isoformat()
    if any(a["date"] == today for a in blog_manager.load_articles()):
        print(f"{today} の記事は既にあります。何もしません。")
        return

    state = load_state()
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

    blog_manager.add_new_article(title, body)
    print(
        f"{elapsed_days(state)}日目のブログを書きました。"
        f"知っている文字{len(state['seen_chars'])}個 / 言葉{len(state['learned_words'])}個"
        + (f" / 今日覚えた言葉: {'、'.join(learned)}" if learned else "")
    )


if __name__ == "__main__":
    run_today()
