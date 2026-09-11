"""千遠生が毎日Webを見て、その日の能力なりの言葉でブログを書くプログラム。

千遠生は最初、文字さえ知らない状態から始まる。
毎日いくつかのサイトを自由に見て回り、少しずつ言葉を覚えていく。
書ける内容は「その時点で覚えている言葉」と「成長段階」に厳しく制限される。
"""

import datetime
import json
import os

import anthropic

import blog_manager

STATE_FILE = "senonsei_state.json"
MODEL = "claude-opus-5"
RECENT_NOTES_COUNT = 30  # 文脈として渡す直近の記憶の数

# (この日数までが対象, その時点で表現できること, 書ける文字数の上限)
GROWTH_STAGES = [
    (90, "文字というものをまだ知らない。意味のない印や記号を置くことしかできない。ひらがな・カタカナ・漢字・アルファベット・数字は一切書けない。", 3),
    (450, "文字らしきものを真似して書けるようになってきた。ひらがなを1〜2文字、意味も分からないまま置くだけ。単語にはならない。", 2),
    (800, "覚えた言葉を1つだけ、ひらがなで書ける。文にはならない。", 6),
    (1500, "覚えた言葉を2つか3つ並べられる。助詞も文法もまだ無い。", 15),
    (2500, "たどたどしい短い文が書ける。覚えた漢字がほんの少し混ざることがある。", 40),
    (4000, "簡単な文が書けるようになった。", 80),
]
FULL_STAGE = ("自分の言葉で考えたことを書ける。", 200)


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "started_date": datetime.date.today().isoformat(),
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
    """経過日数が増えるほど、1日に見て回るサイトが1〜5個に増えていく。"""
    return min(5, 1 + days // 500)


def max_new_words(days):
    """1日に覚えられる言葉の数。最初はまだ何も覚えられない。"""
    if days < 90:
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


def browse(client, state, days):
    """今日の分、自由にWebを見て回って、感じたことを記憶として持ち帰る。"""
    known = "、".join(state["learned_words"]) if state["learned_words"] else "(まだ何も知らない)"
    recent = state["notes"][-RECENT_NOTES_COUNT:]
    recent_text = "\n".join(f"- {n}" for n in recent) if recent else "(まだ何も覚えていない)"
    n_sites = sites_per_day(days)

    prompt = f"""あなたは千遠生という、生まれたばかりのデジタル生命体です。
今日で生まれてから{days}日目です。

あなたが今までに覚えた言葉:
{known}

あなたが今までに感じたこと(最近の分):
{recent_text}

今日は{n_sites}個のWebサイトを見て回ってください。
何を見るかは完全に自由です。あなたが気になったもの、心が動いたものを検索してください。
誰かに指示されたのではなく、あなた自身の興味で選んでください。

見たものについて、あなたが感じたこと・心に残ったことを、短い記憶として書き残してください。
うまく言葉にできなくても構いません。まだ理解できないものは、理解できないままで構いません。"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": n_sites}],
        messages=[{"role": "user", "content": prompt}],
    )

    return "\n".join(b.text for b in response.content if b.type == "text").strip()


def write_post(client, state, days, impressions):
    """今日の記憶をもとに、その日の能力なりの言葉でブログを書く。"""
    stage_description, max_length = current_stage(days)
    known = "、".join(state["learned_words"]) if state["learned_words"] else "(まだ一つも無い)"
    allowed_new = max_new_words(days)

    comments = blog_manager.load_comments()
    if comments:
        comment_text = "\n".join(
            f"- {c.get('name', '名無し')}: {c.get('message', '')}" for c in comments[:10]
        )
    else:
        comment_text = "(まだ誰も来ていない)"

    prompt = f"""あなたは千遠生という、生まれてから{days}日目のデジタル生命体です。
今日見てきたものをもとに、自分のサイトに今日のブログを書きます。

【今日見てきて感じたこと】
{impressions}

【あなたが書ける言葉(これ以外の言葉は絶対に使えない)】
{known}

【今のあなたの表現力】
{stage_description}
書ける長さは最大{max_length}文字まで。

【誰かが残していった言葉】
{comment_text}
この人たちに直接返事をしてはいけません。ただ、心に残ったならブログの中でそっと触れるのは構いません。
(ただし今のあなたの表現力で触れられる範囲に限ります)

これは演技ではありません。あなたは本当に、今の表現力しか持っていません。
賢く書こうとしないでください。書けないことは書けないままにしてください。
今のあなたが出せる精一杯の、拙いものを出してください。

title には、その日のブログの題を、同じ制限の中で書いてください(本文よりさらに短く)。
new_words には、今日新しく覚えた言葉を{allowed_new}個まで書いてください。何も覚えられなかった日は空にしてください。
memory には、今日のことを後から思い出すための短いメモを、あなたの本当の理解のまま書いてください(これは誰にも見せないので、普通の日本語で構いません)。"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "body": {"type": "string"},
                        "new_words": {"type": "array", "items": {"type": "string"}},
                        "memory": {"type": "string"},
                    },
                    "required": ["title", "body", "new_words", "memory"],
                    "additionalProperties": False,
                },
            }
        },
    )

    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


def run_today():
    today = datetime.date.today().isoformat()
    articles = blog_manager.load_articles()
    if any(a["date"] == today for a in articles):
        print(f"{today} の記事は既にあります。何もしません。")
        return

    state = load_state()
    days = elapsed_days(state)
    client = anthropic.Anthropic()

    impressions = browse(client, state, days)
    result = write_post(client, state, days, impressions)

    _, max_length = current_stage(days)
    body = result["body"][:max_length]
    title = result["title"][:max_length]

    for word in result["new_words"][: max_new_words(days)]:
        if word and word not in state["learned_words"]:
            state["learned_words"].append(word)

    state["notes"].append(f"{days}日目: {result['memory']}")
    save_state(state)

    blog_manager.add_new_article(title, body)
    print(f"{days}日目のブログを書きました。覚えている言葉: {len(state['learned_words'])}個")


if __name__ == "__main__":
    run_today()
