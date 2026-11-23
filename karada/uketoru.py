# 千遠生の体の一部。読んだものを受け取る。どこで会ったか、別の言葉版とのつながり、本の読み方。
#
# このファイルは単独では動かない。senonsei_ai.py が、決まった順に
# 全部の部品を自分の中へ読み込み、一つの体として動かす(2026-11-23、彼女と決めた)。
# ここに書いた名前は、ほかの部品からも senonsei_ai.<名前> としても、そのまま見える。

def absorb(state, text, pattern=WORD_CANDIDATE, only_known=False):
    """読んだものから、文字と言葉を拾う。

    同じ言葉を一日に何度見かけても、一日ぶんにしか数えない。
    一度にたくさん読んでも、それで早く覚えられるわけではない。
    日をまたいで何度も見かけた言葉が、だんだん身についていく。

    『』や「」で囲まれたものは、丸ごと一つの名前として受け取る。
    そうしないと『銀河鉄道の夜』は「銀河鉄道」で切れてしまい、
    長い名前を持つものの名前を、永久に知ることができない。"""
    today = now_in_japan().strftime("%Y-%m-%d")
    # 何千字も覚えたあとで一字ずつ端から探していると、
    # 一枚読むたびに何百万回も見比べることになる
    seen = state["seen_chars"]
    already = set(seen)
    for char in A_WRITTEN_CHARACTER.findall(text):
        if char not in already:
            seen.append(char)
            already.add(char)
    named = names_in_brackets(text)
    if pattern is THING_IN_A_PICTURE:
        # 絵から受け取るのは、写っていたものの名前だけ
        found = names_in_what_it_saw(text)
        named = {one for one in named if one not in EYES_OWN_WORDS}
    else:
        found = pattern.findall(text)

    # そのページが何の話だったか。繰り返し出てきた言葉は強く残る。
    # 名前として差し出されたものも、絵から受け取ったものも強い
    struck = set(named)
    if not only_known:
        counted = {}
        for word in found:
            counted[word] = counted.get(word, 0) + 1
        struck |= {w for w, n in counted.items() if n >= TIMES_TO_STRIKE}
        if pattern is THING_IN_A_PICTURE:
            struck |= set(found)
    # 興味の育っていない字の言葉は、強く出会ったことにならない
    struck = {word for word in struck if cares_for(state, word)}

    # 言葉の繋がりは、人が書いた文から覚える。目の答えの並びは目の口ぐせなので覚えない
    if not only_known and pattern is not THING_IN_A_PICTURE:
        notice_what_follows(state, text)

    # 頭の網にも入れる。自分の書いたものを読み返す時は入れない。今日のことではないので
    if not only_known and state.get("atama") and not READ_AGAIN_TODAY[0]:
        head_does(
            atama.notice, state["atama"], state, now_in_japan(),
            [word for word in found if cares_for(state, word)],
            named=named, struck=struck, where=WHERE_IT_IS[0],
            known=state.get("learned_words") or [], met=words_met(state),
            seen=pattern is THING_IN_A_PICTURE,
        )

    # 今日この言葉に会った、ということを覚えておく。
    # 覚えた言葉は words_met から外れてしまうので、そこには残らない。
    # 自分の書いたものを読み返す時は数えない。今日のことではないので
    if not only_known:
        keep_todays_words(state, found)
        interest_grows(state, found)

    impact = state.setdefault("word_impact", {})
    met = words_met(state)
    today_number = day_number(state)
    hit_hard = set()  # ここで強く出会った言葉。気がかりが移ることがある
    # どこで会ったか(言葉の辞典のため)。自分の書いたものを読み返す時は、どこでもない
    where = None if only_known else place_number(state, WHERE_IT_IS[0])
    page = None if only_known or where is None else page_number(state, PAGE_IT_IS[0])
    for word in set(found) | named:
        # 自分が書いたものを読み返す時は、新しい言葉は生まれない。
        # 誰にも教わっていない文字列を、自分だけで言葉にすることはできない
        if only_known and word not in met:
            continue
        record = met.get(word)
        if record is None:
            MET_FOR_THE_FIRST_TIME[0] += 1
            notice_met_anew(state, word)
        new_day = record is None or record[1] != today_number
        count = (record[0] if record else 0) + (1 if new_day else 0)
        met[word] = [count, today_number] + where_it_met(record, where, page)
        if new_day and word in struck and not met_often_enough(state, word):
            impact[word] = impact.get(word, 0) + 1
            hit_hard.add(word)
    return hit_hard


def place_number(state, place):
    """その場所の番号。初めての場所なら、場所の並び(basho)の後ろに足す。

    言葉の辞典に「初めて会った場所」「覚えた日に会っていた場所」を出すため、
    言葉ごとにどこで会ったかを取り始めた(2026-10-10、彼女と決めた)。

    言葉ごとに場所の名前を書くと、何万語ぶん同じ名前が並んで重くなる。
    名前は basho に一度だけ書いて、言葉の側は番号で指す。"""
    if not place:
        return None
    places = state.setdefault("basho", [])
    if PLACE_NUMBERS["of"] is not places or len(PLACE_NUMBERS["at"]) != len(places):
        PLACE_NUMBERS["of"] = places
        PLACE_NUMBERS["at"] = {one: number for number, one in enumerate(places)}
    if place not in PLACE_NUMBERS["at"]:
        PLACE_NUMBERS["at"][place] = len(places)
        places.append(place)
    return PLACE_NUMBERS["at"][place]


def page_number(state, title):
    """そのページの番号。初めてのページなら、ページの並び(peeji)の後ろに足す。

    場所(basho)はサイトごとなので、Wikipedia で会った言葉はどれも同じ場所になり、
    辞典ではどの言葉にも、そのサイトで最後に読んだページの題が出ていた。
    言葉と会ったページそのものも取る(2026-10-14、彼女と決めた)。
    題は peeji に一度だけ書いて、言葉の側は番号で指す。"""
    if not title:
        return None
    pages = state.setdefault("peeji", [])
    if PAGE_NUMBERS["of"] is not pages or len(PAGE_NUMBERS["at"]) != len(pages):
        PAGE_NUMBERS["of"] = pages
        PAGE_NUMBERS["at"] = {one: number for number, one in enumerate(pages)}
    if title not in PAGE_NUMBERS["at"]:
        PAGE_NUMBERS["at"][title] = len(pages)
        pages.append(title)
    return PAGE_NUMBERS["at"][title]


def where_it_met(record, where, page=None):
    """覚えかけの記録の三つめと四つめ。初めて会った場所と、いちばん最近会った場所の番号。

    記録を取り始める前から会っていた言葉は、初めての場所が分からないので None のまま。
    どちらも分からないうちは何も足さない(記録が軽いまま)。"""
    first = record[2] if record and len(record) > 2 else (where if record is None else None)
    last = where if where is not None else (record[3] if record and len(record) > 3 else None)
    # 五つめと六つめは、初めて会ったページと、いちばん最近会ったページ(2026-10-14 から)。
    # それより前から会っていた言葉は、初めて会ったページが分からないので None のまま
    first_page = record[4] if record and len(record) > 4 else (page if record is None else None)
    last_page = page if page is not None else (record[5] if record and len(record) > 5 else None)
    if first_page is not None or last_page is not None:
        return [first, last, first_page, last_page]
    return [] if first is None and last is None else [first, last]


A_SIDE_NOTE = re.compile(r"\(.*?\)|（.*?）")
A_GLOSS = re.compile(r"([ぁ-んァ-ヶー一-龯]{1,10})\s?[（(]([^（）()]{1,80})[）)]")
A_FOREIGN_NAME = re.compile(
    rf"[{LATIN_LETTERS}{OTHER_LETTERS}]{{2,}}(?:[ \-'][{LATIN_LETTERS}{OTHER_LETTERS}]+){{0,3}}"
)


def a_name_as_written(title):
    """題から、括弧の書き添え(「(神話)」「(曖昧さ回避)」)を外した名前。"""
    return " ".join(A_SIDE_NOTE.sub(" ", title).split())


def bridge(state, foreign, japanese, weight):
    """外国語と日本語を一つ結びつける。一つの外国語につき、強い結びつきを三つまで持つ。"""
    foreign = " ".join((foreign or "").lower().split())
    japanese = (japanese or "").strip()
    if not (2 <= len(foreign) <= 40) or not japanese or len(japanese) > 20:
        return
    if JAPANESE.search(foreign) or not JAPANESE.search(japanese) or len(foreign.split()) > 4:
        return
    bridges = state.setdefault("bridges", {})
    tied = bridges.setdefault(foreign, {})
    tied[japanese] = tied.get(japanese, 0) + weight
    if len(tied) > 3:
        bridges[foreign] = dict(sorted(tied.items(), key=lambda kv: -kv[1])[:3])
    if len(bridges) > BRIDGES_KEPT:
        weakest = sorted(bridges, key=lambda one: max(bridges[one].values()))
        for one in weakest[: len(bridges) - BRIDGES_KEPT + BRIDGES_KEPT // 10]:
            bridges.pop(one, None)


def notice_other_tongues(state, url, title, tongues):
    """Wikipedia で、同じ話の別の言葉版の題を、日本語の題と結びつける。"""
    here = place_of(url)
    if not here.endswith("wikipedia.org") or not tongues:
        return 0
    own = a_name_as_written(re.split(r"\s+[-–—]\s+", title or "")[0])
    lang_here = here.split(".")[0]
    if lang_here == "ja":
        japanese, foreign = own, [(code, name) for code, name in tongues if code not in TONGUES_READ_AS_JAPANESE]
    else:
        japanese = next((name for code, name in tongues if code == "ja"), None)
        foreign = [(lang_here, own)]
    if not japanese:
        return 0
    japanese = a_name_as_written(japanese)
    for _, name in foreign[:OTHER_TONGUES_PER_PAGE]:
        bridge(state, a_name_as_written(name), japanese, BRIDGE_FROM_WIKIPEDIA)
    return len(foreign[:OTHER_TONGUES_PER_PAGE])


def notice_glosses(state, text):
    """日本語の文で、言葉のすぐあとの括弧に書き添えてある外国語を、その言葉と結びつける。"""
    for japanese, inside in A_GLOSS.findall(text):
        for name in A_FOREIGN_NAME.findall(inside)[:1]:
            bridge(state, name, japanese, BRIDGE_FROM_A_GLOSS)


def translate_on_its_own(state, text):
    """外国語の文を、自分で結びつけた言葉だけ日本語に置き換えて読む。(外国語, 日本語) の並び。"""
    bridges = state.get("bridges") or {}
    if not bridges:
        return []
    low = " ".join(text.lower().split())
    words = {one.lower() for one in WORD_CANDIDATE.findall(text)}
    found = []
    for foreign, tied in bridges.items():
        japanese, strength = max(tied.items(), key=lambda kv: kv[1])
        if strength < BRIDGE_TRUSTED or not cares_for(state, foreign):
            continue
        if foreign in words or (" " in foreign and foreign in low):
            found.append((foreign, japanese))
    return found


def a_door(url):
    """入口から入る時の、本当の入口。青空文庫だけは、作品名の一覧のどこかから入る。"""
    if url == AOZORA_FRONT:
        return f"https://www.aozora.gr.jp/index_pages/sakuhin_{random.choice(AOZORA_ROWS)}1.html"
    return url


def is_a_book(url):
    """青空文庫の本文のページか。昔の姿の写しは除く。"""
    return bool(AOZORA_TEXT.match(url or ""))


def the_work_itself(text):
    """本文のページから、作品のところだけ。終わりの「底本：」からは、本の出どころの書き付け。

    空白の並びは一つにまとめる。しおりの位置が、開くたびにずれないように。"""
    text = re.sub(r"[ \t\u3000]*\n[\s\u3000]*", "\n", text)
    text = re.sub(r"[ \t]+", " ", text).strip()
    ends = text.rfind("底本：")
    return text[:ends].rstrip() if ends > 0 else text


def a_good_place_to_stop(work, around):
    """きりのいいところ。そのあたりで、文の終わりか段落の終わりを探す。"""
    if around >= len(work):
        return len(work)
    found = [at for at in (work.find("。", around), work.find("\n", around)) if 0 <= at < around + 400]
    return min(found) + 1 if found else around


def a_portion_of_the_book(state, url, title, text):
    """本の、しおりのところから、ひと休みするまでの分(2026-10-20、彼女と決めた)。

    読み終わったらしおりを外して、読み終えた本として覚えておく。
    読みかけなら、読んだところまでにしおりを挟む。挟める本は BOOKS_HELD 冊まで。
    いっぱいの時は、いちばん続きを読みたくない本のしおりを抜く。"""
    work = the_work_itself(text)
    shelf = state.setdefault("shiori", {})
    held = shelf.get(url) or {}
    start = held.get("at", 0)
    if start >= len(work):
        start = 0  # 本が書き換わって短くなっていた
    end = a_good_place_to_stop(work, start + READ_AT_ONCE)
    if end >= len(work):
        shelf.pop(url, None)
        finished = state.setdefault("books_read", [])
        finished.append({"title": title, "url": url, "on": today_in_japan().isoformat()})
        state["books_read"] = finished[-BOOKS_READ_KEPT:]
        print(f"『{title}』を読み終えました")
    else:
        if url not in shelf and len(shelf) >= BOOKS_HELD:
            least = min(shelf, key=lambda one: shelf[one].get("want", 1))
            print(f"『{shelf[least].get('title')}』のしおりを抜きました")
            shelf.pop(least)
        shelf[url] = {
            "title": title,
            "at": end,
            "of": len(work),
            "since": held.get("since") or today_in_japan().isoformat(),
            "times": held.get("times", 0) + 1,
            "want": held.get("want", 1.0),
        }
        print(f"『{title}』を{end}字まで読んで、しおりを挟みました(全部で{len(work)}字)")
    return work[start:end]


def usual_understanding(state):
    """ふだん、行った場所の言葉をどれくらい分かっているか。最近行った場所のならし。"""
    visits = sorted(
        (one.get("last") or {} for one in (state.get("places_understood") or {}).values()),
        key=lambda visit: visit.get("day", 0),
    )[-20:]
    known = [how_well(visit) for visit in visits if visit.get("of")]
    return sum(known) / len(known) if known else 0.3


def felt_about_the_book(state, url, portion):
    """読んだところが、ふだんよりよく分かったら続きをもっと読みたくなる。分からなければ少し気が引ける。"""
    held = (state.get("shiori") or {}).get(url)
    if not held:
        return  # 読み終えた
    words = set(WORD_CANDIDATE.findall(portion))
    known = known_words_in(state, portion)
    this_time = len(known) / len(words) if words else 0
    least, most = BOOK_WANT_RANGE
    leaning = BOOK_GROWS_ON_IT if this_time >= usual_understanding(state) else BOOK_LOSES_IT
    held["want"] = round(min(most, max(least, held.get("want", 1.0) * leaning)), 3)
