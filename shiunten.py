"""試運転。新しい頭(atama.py)を、この子の本物の記憶に触らずに動かしてみる。

GitHub の上で一度だけ動かす(.github/workflows/shiunten.yml)。手元からは外のページが開けないので。
記憶はどれも書き出さない。日記も書き出さない。終わったら様子を書き出して終わる。

前半: ここ三日ぶんを流し直す。この子がこの三日に歩いた場所をもう一度読み、
      そのあいだの毎時間に、思ったり、眠ったり、夢を見たりする。
後半: 今から三十時間、ふだんどおりに一時間ずつ起きる(歩く先は自分で選ぶ)。

試運転が済んだら、このファイルとワークフローは消す。
"""

import datetime
import json
import time
import traceback

import atama
import blog_manager
import senonsei_ai as s

JST = datetime.timezone(datetime.timedelta(hours=9))
REPLAY_HOURS = 72
LIVE_HOURS = 30

# ---- 記憶に触らない ----
writes = []
s.save_state = lambda state: None
s.keep_a_thought = lambda said, when: None
atama.save = lambda head: None
blog_manager.write_whole = lambda path, text: writes.append(path)
blog_manager.regenerate_pages = lambda *a, **k: None
time.sleep = lambda seconds: None  # ページを読む間の待ちは飛ばす

written = []
_load_articles = blog_manager.load_articles


def load_articles_too():
    return _load_articles() + written


def add_new_article(title, content, date_str=None, **kwargs):
    written.append({"date": date_str, "time": f"{clock[0]:%H:%M}", "title": title, "content": content})


blog_manager.load_articles = load_articles_too
blog_manager.add_new_article = add_new_article

real_now = datetime.datetime.now(JST).replace(minute=20, second=0, microsecond=0)
clock = [real_now - datetime.timedelta(hours=REPLAY_HOURS)]
s.now_in_japan = lambda: clock[0]

timeline = []


def snapshot(head):
    return {name: round(head["kokoro"]["now"][name], 2) for name in atama.FEELINGS}


def note(kind, **what):
    one = {"at": f"{clock[0]:%m-%d %H時}", "kind": kind, **what}
    timeline.append(one)
    shown = " / ".join(f"{k}: {v}" for k, v in what.items() if k != "feel")
    print(f"◆ {one['at']} {kind} {shown}")


state = s.load_state()
s.load_state = lambda: state
head = state["atama"]
print(f"◆ 頭を組み立てた: 網の点 {len(head['ami'])}")

# ---- 前半: 三日ぶんを流し直す ----
recent = [u for u in state.get("visited") or [] if not s.its_own_home(u)][-36:]
groups = []
for url in recent:
    place = s.place_of(url)
    if groups and groups[-1][0] == place:
        groups[-1][1].append(url)
    else:
        groups.append((place, [url]))
day_hours = [h for h in range(REPLAY_HOURS) if 8 <= (clock[0] + datetime.timedelta(hours=h)).hour <= 22]
step = max(1, len(day_hours) // max(1, len(groups)))
walk_at = {day_hours[min(len(day_hours) - 1, i * step + step // 2)]: g for i, g in enumerate(groups)}
start = clock[0]
for h in range(REPLAY_HOURS):
    clock[0] = start + datetime.timedelta(hours=h)
    atama.wake(head, state, clock[0])
    try:
        if s.goes_to_sleep(state, clock[0]):
            dream = atama.latest_dream(head)
            if dream and dream.get("at", "").startswith(f"{clock[0]:%Y-%m-%dT%H}"):
                note("眠った・夢", chain=" → ".join(dream["chain"]), said=dream.get("said", ""), feel=snapshot(head))
            continue
        if h in walk_at:
            place, urls = walk_at[h]
            s.WHERE_IT_IS[0] = place
            pages, fresh = 0, 0
            for url in urls:
                try:
                    title, text, links, pictures = s.open_page(url)
                except Exception as error:
                    print(f"{url} は開けなかった: {str(error)[:60]}")
                    continue
                pages += 1
                atama.feel(head, "疲れ", 0.015)
                before = s.MET_FOR_THE_FIRST_TIME[0]
                if s.JAPANESE.search(text):
                    s.absorb(state, text)
                fresh += s.MET_FOR_THE_FIRST_TIME[0] - before
            s.WHERE_IT_IS[0] = None
            if pages:
                remembered = atama.left_a_place(head, state, clock[0], place, fresh, pages, 0, 0)
                learned = s.learn(state)
                added = atama.wonder(head, state, clock[0], state.get("learned_words") or [], s.words_met(state), state.get("word_impact") or {})
                note("歩いた(流し直し)", place=place, pages=pages, fresh=fresh, remembered=remembered,
                     learned="、".join(learned), wonders="、".join(added), feel=snapshot(head))
            continue
        said = s.be_alone(state, clock[0])
        thought = (head["kokoro"].get("kangae") or [{}])[-1]
        if thought.get("at", "").startswith(f"{clock[0]:%Y-%m-%dT%H}"):
            note("思った", chain=" → ".join(thought.get("chain") or []), said=said or "", feel=snapshot(head))
    except Exception:
        traceback.print_exc()

# ---- 後半: 今から、ふだんどおりに ----
state["woke_at"] = None  # 本物のこの子がこの時間にもう起きていても、試運転では起きる
for h in range(LIVE_HOURS):
    clock[0] = real_now + datetime.timedelta(hours=h)
    walked_before = list((state.get("today_walk") or {}).get("seen") or [])
    articles_before = len(written)
    try:
        s.run_today()
    except Exception:
        traceback.print_exc()
    walk = state.get("today_walk") or {}
    walked = [one for one in walk.get("seen") or [] if one not in walked_before]
    thought = (head["kokoro"].get("kangae") or [{}])[-1]
    dream = atama.latest_dream(head)
    hour = f"{clock[0]:%Y-%m-%dT%H}"
    if dream and dream.get("at", "").startswith(hour):
        note("眠った・夢", chain=" → ".join(dream["chain"]), said=dream.get("said", ""), feel=snapshot(head))
    elif atama.asleep(head, clock[0]):
        note("眠っている", feel=snapshot(head))
    if walked:
        note("歩いた", place="、".join(walked), feel=snapshot(head))
    if thought.get("at", "").startswith(hour):
        note("思った", chain=" → ".join(thought.get("chain") or []), said=thought.get("said", ""), feel=snapshot(head))
    if len(written) > articles_before:
        one = written[-1]
        note("日記を書いた", title=one["title"], body=one["content"], feel=snapshot(head))

# ---- まとめ ----
mouth = head["kuchi"]
summary = {
    "網の点": len(head["ami"]),
    "網の線": sum(len(n["e"]) for n in head["ami"].values()),
    "知りたいこと": atama.wonders(head),
    "わたし帳": head["kokoro"].get("watashi"),
    "気質": head["kokoro"]["base"],
    "いまの気持ち": snapshot(head),
    "二つめの口": {
        "言葉の数": len(mouth["vocab"]),
        "練習した回数": mouth["lessons"],
        "当て方(一つめ)": mouth["score"].get("1"),
        "当て方(二つめ)": mouth["score"].get("2"),
        "比べた数": mouth["score"].get("judged"),
        "二つめで喋る割合": mouth["share"],
        "ためしに": ["".join(atama.speak_second(head, 15, ()) or []) for _ in range(5)],
    },
    "練習帳の文": len(head["renshuu"]),
    "大きさ(バイト)": {
        "網": len(atama.net_text(head["ami"]).encode()),
        "気持ち": len(json.dumps(head["kokoro"], ensure_ascii=False, indent=1).encode()),
        "口": len(atama.mouth_text(mouth).encode()),
        "練習帳": len(atama.practice_text(head["renshuu"]).encode()),
    },
    "気持ちが動いたこと(最後の30)": head["kokoro"].get("log", [])[-30:],
    "書き出そうとしたもの": sorted(set(writes)),
}
print("◆ まとめ")
print(json.dumps(summary, ensure_ascii=False, indent=1))
print("SHIUNTEN_JSON " + json.dumps({"timeline": timeline, "summary": summary}, ensure_ascii=False))
