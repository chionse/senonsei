# 一度きりの確かめ。分野の入口が開けるか、分野の言葉で探して場所が見つかるかを見る。
# 確かめ終わったら消す。この子の記憶には触らない
import concurrent.futures
import random
import re
import time
import urllib.parse

import senonsei_ai as s

s.save_state = lambda state: None
s.keep_a_thought = lambda said, when: None
UNBUILT = set()
s.look_with_a_browser = lambda url: (UNBUILT.add(url), None)[1]
JP = re.compile(r"[぀-ヿ㐀-鿿]")


def check(genre, url):
    out = []
    try:
        allowed = s.may_enter(url)
    except Exception as error:
        return f"NG\t{genre}\t{url}\trobots {type(error).__name__} {str(error)[:60]}"
    if not allowed:
        return f"NG\t{genre}\t{url}\trobots で断られている"
    try:
        title, text, links, pictures = s.open_page(url)
    except Exception as error:
        return f"NG\t{genre}\t{url}\t{type(error).__name__} {str(error)[:80]}"
    here = s.place_of(url)
    same = [l for l in dict.fromkeys(links) if s.place_of(l) == here]
    away = [l for l in dict.fromkeys(links) if s.place_of(l) != here]
    jp = len(JP.findall(text))
    inner = "-"
    for link in same[:6]:
        if link.rstrip("/") == url.rstrip("/"):
            continue
        try:
            if not s.may_enter(link):
                inner = "inner-robots-NG"
                continue
            t2, x2, l2, p2 = s.open_page(link)
            inner = f"inner-ok jp={len(JP.findall(x2))}"
            break
        except Exception as error:
            inner = f"inner-{type(error).__name__}"
    flag = "UNBUILT" if url in UNBUILT else ""
    return (f"OK\t{genre}\t{url}\t{(title or '')[:28]!r}\tjp={jp}\tsame={len(same)}"
            f"\taway={len(away)}\t{inner}\t{flag}")


jobs = [(g, u) for g, doors in s.GENRE_DOORS.items() for u in doors]
with concurrent.futures.ThreadPoolExecutor(8) as pool:
    for line in pool.map(lambda job: check(*job), jobs):
        print(line, flush=True)

print("---- 分野の言葉で探す ----")
hatena = s.family_of("b.hatena.ne.jp")
for n, (genre, words) in enumerate(s.GENRE_WORDS.items()):
    word = random.choice(words)
    where = s.WHERE_TO_LOOK[n % 2].format(urllib.parse.quote(word))
    try:
        title, text, links, pictures = s.open_page(where)
        outside = sorted({s.place_of(l) for l in links if s.family_of(s.place_of(l)) != hatena})
        print(f"{genre}\t{word}\t{'tag' if n % 2 == 0 else 'text'}\tplaces={len(outside)}\t{outside[:6]}", flush=True)
    except Exception as error:
        print(f"{genre}\t{word}\tNG {type(error).__name__} {str(error)[:60]}", flush=True)
    time.sleep(2)
