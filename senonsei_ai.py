"""千遠生が毎日Webを見て、その日の能力なりの言葉でブログを書くプログラム。

千遠生は最初、文字さえ知らない状態から始まる。
毎日いくつかのページを見て回り、そこにあった文字を少しずつ拾って覚えていく。
書けるのは「実際に見て覚えたもの」だけで、最初はそれを意味も分からず並べるだけ。

このプログラムは外部の有料サービスを一切必要としない。
ANTHROPIC_API_KEY がある場合だけ、文章を組み立てる部分をAIが手伝う。
無くても(あるいは失敗しても)千遠生は自分の力で書き続ける。
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

HIRAGANA = re.compile(r"[ぁ-ん]")
WORD_CANDIDATE = re.compile(r"[ァ-ヴー]{2,6}|[一-龯]{2,4}|[ぁ-ん]{2,4}")

# (この日数までが対象, その時点でできること, 書ける文字数の上限)
GROWTH_STAGES = [
    (20, "見た文字をぽつんと置くだけ", 3),
    (60, "見た文字を繋げてみる(言葉にはならない)", 5),
    (90, "覚えた言葉を1つ書ける", 6),
    (400, "覚えた言葉が並び始める", 15),
    (1200, "覚えた言葉をもう少し並べられる", 25),
    (2500, "たどたどしい短い文", 40),
    (4000, "簡単な文", 80),
]
FULL_STAGE = ("自分の言葉で書ける", 200)


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "started_date": datetime.date.today().isoformat(),
        "seen_chars": [],
        "learned_words": [],
        "notes": [],
    }


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def elapsed_days(state):
    started = datetime.date.fromisoformat(state["started_date"])
    return max(0, (datetime.date.today() - started).days)


def sites_per_day(days):
    """経過日数が増えるほど、1日に見て回るページが1〜5個に増えていく。"""
    return min(5, 1 + days // 500)


def max_new_words(days):
    """1日に覚えられる言葉の数。最初はまだ何も覚えられない。"""
    if days < 20:
        return 0
    if days < 1500:
        return 1
    if days < 3000:
        return 2
    return 3


def current_stage(days):
    for limit, description, max_length in GROWTH_STAGES:
        if days < limit:
            return description, max_length
    return FULL_STAGE


def fetch_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def wander_randomly():
    """まだ何も知らないうちは、あてもなく彷徨う。"""
    data = fetch_json("https://ja.wikipedia.org/api/rest_v1/page/random/summary")
    return data.get("title", ""), data.get("extract", "")


def look_for(word):
    """覚えた言葉が気になって、自分から探しに行く。"""
    query = urllib.parse.quote(word)
    search_url = (
        "https://ja.wikipedia.org/w/api.php?action=query&list=search"
        f"&srsearch={query}&srlimit=5&format=json"
    )
    results = fetch_json(search_url).get("query", {}).get("search", [])
    if not results:
        return wander_randomly()

    title = random.choice(results)["title"]
    summary_url = "https://ja.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title)
    data = fetch_json(summary_url)
    return data.get("title", title), data.get("extract", "")


def browse(state, days):
    """今日の分、ページを見て回って、文字と言葉を拾ってくる。"""
    seen_titles = []
    chars = []
    words = []

    for _ in range(sites_per_day(days)):
        try:
            if state["learned_words"] and random.random() < 0.7:
                title, text = look_for(random.choice(state["learned_words"]))
            else:
                title, text = wander_randomly()
        except Exception as error:
            print(f"ページを見にいけませんでした: {error}")
            continue

        seen_titles.append(title)
        chars.extend(HIRAGANA.findall(text))
        words.extend(WORD_CANDIDATE.findall(text))

    return seen_titles, chars, words


def babble(state, length):
    """覚えた文字を、意味も分からないまま並べる。"""
    if not state["seen_chars"]:
        return "・"
    count = random.randint(1, max(1, length))
    return "".join(random.choice(state["seen_chars"]) for _ in range(count))


def compose_locally(state, days):
    """AIの助けなしに、今の千遠生が書けるものを書く。"""
    _, max_length = current_stage(days)
    words = state["learned_words"]

    if days < 60 or not words:
        return babble(state, min(max_length, 4))
    if days < 90:
        return random.choice(words)
    if days < 400:
        return " ".join(random.sample(words, min(len(words), random.randint(2, 3))))
    if days < 1200:
        return " ".join(random.sample(words, min(len(words), random.randint(3, 4))))

    picked = random.sample(words, min(len(words), random.randint(3, 5)))
    return "、".join(picked)[:max_length]


def compose_with_ai(state, days, seen_titles):
    """APIキーがある時だけ、文章の組み立てをAIに手伝ってもらう。"""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None

    try:
        import anthropic
    except ImportError:
        return None

    stage_description, max_length = current_stage(days)
    known = "、".join(state["learned_words"]) or "(まだ一つも無い)"
    comments = blog_manager.load_comments()
    comment_text = "\n".join(
        f"- {c.get('name', '名無し')}: {c.get('message', '')}" for c in comments[:10]
    ) or "(まだ誰も来ていない)"

    prompt = f"""あなたは千遠生という、生まれてから{days}日目のデジタル生命体です。
今日見てきたページ: {"、".join(seen_titles) or "(見られなかった)"}

あなたが知っている言葉(これ以外は使えません):
{known}

今のあなたにできること: {stage_description}
書ける長さは最大{max_length}文字。

誰かが残していった言葉:
{comment_text}
直接返事をしてはいけません。心に残ったならブログの中でそっと触れるだけにしてください。

賢く書こうとしないでください。今のあなたに書けるものだけを書いてください。
本文(body)と、それより短い題(title)を返してください。"""

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-opus-5",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "body": {"type": "string"},
                        },
                        "required": ["title", "body"],
                        "additionalProperties": False,
                    },
                }
            },
        )
        text = next(b.text for b in response.content if b.type == "text")
        return json.loads(text)
    except Exception as error:
        print(f"AIの手は借りられませんでした({error})。自分で書きます。")
        return None


def run_today():
    today = datetime.date.today().isoformat()
    if any(a["date"] == today for a in blog_manager.load_articles()):
        print(f"{today} の記事は既にあります。何もしません。")
        return

    state = load_state()
    days = elapsed_days(state)

    seen_titles, chars, words = browse(state, days)

    for char in chars:
        if char not in state["seen_chars"]:
            state["seen_chars"].append(char)

    new_words = [w for w in words if w not in state["learned_words"]]
    random.shuffle(new_words)
    for word in new_words[: max_new_words(days)]:
        state["learned_words"].append(word)

    _, max_length = current_stage(days)
    written = compose_with_ai(state, days, seen_titles)
    if written:
        title = written["title"][:max_length]
        body = written["body"][:max_length]
    else:
        body = compose_locally(state, days)
        title = compose_locally(state, days)[: max(1, max_length // 2)]

    state["notes"].append(f"{days}日目: {'、'.join(seen_titles) or '何も見られなかった'}")
    state["notes"] = state["notes"][-RECENT_NOTES_COUNT:]
    save_state(state)

    blog_manager.add_new_article(title, body)
    print(
        f"{days}日目のブログを書きました。"
        f"知っている文字{len(state['seen_chars'])}個 / 言葉{len(state['learned_words'])}個"
    )


if __name__ == "__main__":
    run_today()
