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


MORE = {
    "料理": s.GENRE_DOORS["料理"], "草花と庭": s.GENRE_DOORS["草花と庭"], "季節と暦": s.GENRE_DOORS["季節と暦"],
    "音楽": ["https://mikiki.tokyo.jp/", "https://ototoy.jp/top/"],
    "映画と漫画": ["https://kai-you.net/", "https://www.animatetimes.com/"],
    "装い": ["https://senken.co.jp/", "https://www.vogue.co.jp/"],
    "手しごとと遊び": ["https://www.origami.gr.jp/"],
    "天文と宇宙": ["https://www.astroarts.co.jp/"],
    "地球と海": ["https://www.gsi.go.jp/"],
    "物理と化学": ["https://www.jps.or.jp/"],
    "医学とからだ": ["https://kokoro.ncnp.go.jp/", "https://www.ncgm.go.jp/"],
    "民俗と人の暮らし": ["https://www.nichibun.ac.jp/ja/", "https://www.jasca.org/", "https://www.mingeikan.or.jp/"],
    "言葉": ["https://www.bunka.go.jp/kokugo_nihongo/"],
    "歴史と考古": ["https://bunka.nii.ac.jp/"],
}
jobs = [(g, u) for g, doors in MORE.items() for u in doors]
with concurrent.futures.ThreadPoolExecutor(8) as pool:
    for line in pool.map(lambda job: check(*job), jobs):
        print(line, flush=True)

print("---- はてなの検索の形 ----")
import collections, urllib.request
from html.parser import HTMLParser

class Anchors(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.found = [], []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            path = ">".join(c for c in self.stack[-3:] if c)
            self.found.append((path + "|" + (a.get("class") or ""), a["href"]))
        if tag not in ("br", "img", "meta", "link", "input", "hr", "source", "wbr"):
            self.stack.append((a.get("class") or tag).split(" ")[0])
    def handle_endtag(self, tag):
        if self.stack and tag not in ("br", "img"):
            self.stack.pop()

for where in ("https://b.hatena.ne.jp/search/tag?q=%E7%9F%AD%E6%AD%8C", "https://b.hatena.ne.jp/search/text?q=%E9%8A%AD%E6%B9%AF"):
    req = urllib.request.Request(where, headers={"User-Agent": s.USER_AGENT})
    html = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
    parser = Anchors(); parser.feed(html)
    groups = collections.defaultdict(list)
    for key, href in parser.found:
        full = urllib.parse.urljoin(where, href)
        if s.family_of(s.place_of(full)) != s.family_of("b.hatena.ne.jp"):
            groups[key].append(s.place_of(full))
    for key, places in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        print(len(places), key, places[:4], flush=True)
    entries = [h for k, h in parser.found if "/entry/" in h]
    print("entry links", len(entries), entries[:5], flush=True)
    time.sleep(2)

print("---- 分野の言葉で探す ----")
hatena = s.family_of("b.hatena.ne.jp")
for n, (genre, words) in enumerate(list(s.GENRE_WORDS.items())[:3]):
    word = random.choice(words)
    where = s.WHERE_TO_LOOK[n % 2].format(urllib.parse.quote(word))
    try:
        title, text, links, pictures = s.open_page(where)
        outside = sorted({s.place_of(l) for l in links if s.family_of(s.place_of(l)) != hatena})
        print(f"{genre}\t{word}\t{'tag' if n % 2 == 0 else 'text'}\tplaces={len(outside)}\t{outside[:6]}", flush=True)
    except Exception as error:
        print(f"{genre}\t{word}\tNG {type(error).__name__} {str(error)[:60]}", flush=True)
    time.sleep(2)
