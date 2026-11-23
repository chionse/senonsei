# 千遠生の体の一部。記憶をしまう・取り出す。状態(senonsei_state.json)、出会った言葉の束(kotoba/)、
# 一年会っていない言葉の奥(kotoba/oku/)。生まれて何日目か、などの数え方も。
#
# このファイルは単独では動かない。senonsei_ai.py が、決まった順に
# 全部の部品を自分の中へ読み込み、一つの体として動かす(2026-11-23、彼女と決めた)。
# ここに書いた名前は、ほかの部品からも senonsei_ai.<名前> としても、そのまま見える。

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
        # 以前は「何回出てきたか」を数えていた。
        # 今は「何日ぶん見かけたか」で数えるので、
        # それまでに出会った言葉は一日ぶんとして引き継ぐ
        old_counts = state.pop("word_counts", None)
        if old_counts is not None:
            state.setdefault("word_days", {w: 1 for w in old_counts})
            state.setdefault(
                "word_last_seen", {w: state.get("started_date", "") for w in old_counts}
            )
        # 出会った言葉は減ることがないので、何年も経つとここが記憶で
        # いちばん重くなる。一語につき二つの記録を別々に持つのをやめ、
        # 日付も「生まれてから何日目か」の数にして、一まとめにする
        old_days = state.pop("word_days", None)
        old_last = state.pop("word_last_seen", None)
        if old_days is not None:
            met = state.setdefault("words_met", {})
            for word, days in old_days.items():
                when = (old_last or {}).get(word)
                try:
                    seen_on = day_number(state, datetime.date.fromisoformat(when))
                except (TypeError, ValueError):
                    seen_on = 0
                met.setdefault(word, [days, max(0, seen_on)])
        take_out_what_is_spread(state)
        state.setdefault("words_met", {})
        state.setdefault("on_its_mind", [])
        state.setdefault("learned_on", {})
        rescue_thoughts_already_here(state)
        read_the_names_again(state)
    else:
        state = {
            "started_date": today_in_japan().isoformat(),
            "seen_chars": [],
            # 出会った言葉 → [何日ぶん見かけたか, 最後に見かけたのが何日目か]
            "words_met": {},
            "learned_words": [],
            "frontier": list(SEEDS),  # まだ行ったことのない場所
            "visited": [],  # もう行った場所
            "on_its_mind": [],  # 今、気にかかっていること
            "learned_on": {},  # 言葉 → それを覚えた日
            "notes": [],
        }
    # 頭(四つめの記憶)。まだ無ければ、今までの記憶から組み立てる。
    # 頭でこけたら、頭なしで今日を過ごす。その時は頭の記憶にも触らない
    state["atama"] = head_does(atama.load, state, how_it_reads(), now_in_japan())
    return state


def head_does(what, *args, default=None, **kwargs):
    """頭に何かをさせる。頭でこけても、この子の一日は止めない。

    頭は新しく入れたもの(2026-10-07)。どこかでこけて散歩も日記も
    止まるよりは、その時だけ頭を使わずに過ごすほうがいい。
    こけたことは記録に残るので、あとから直せる。"""
    try:
        return what(*args, **kwargs)
    except Exception:
        traceback.print_exc()
        print(f"頭で {getattr(what, '__name__', what)} がこけました。この子の一日はそのまま続けます")
        return default


def how_it_reads():
    """頭を組み立てる時に、今までの記憶をどう読むか。歩く時と同じ読み方で。"""
    return {
        "words_in": WORD_CANDIDATE.findall,
        "names_in": names_in_brackets,
        "things_in": names_in_what_it_saw,
        "home": words_left_at_home,
        "thoughts": everything_it_has_thought,
    }


def names_in_brackets(text):
    """『』や「」で囲まれた名前。文になっているものは名前ではない。

    名前の前後の空白は落とし、中の空白の並びは一つにする。
    ページのしるしを外すと、その跡が空白になって括弧の内側に残る。
    Wikipedia の「<a>ローマ進軍</a>」は「 ローマ進軍 」になり、
    頭の網では「ローマ進軍」と別のものとして並んでいた(2026-11-06)"""
    names = set()
    for one in A_NAME_IN_BRACKETS.findall(text):
        one = " ".join(one.split())
        if len(one) >= 2 and not A_SENTENCE.search(one):
            names.add(one)
    return names


def everything_it_has_thought():
    """蔵にある思いを、古いものから全部。"""
    for month in months_of_thoughts():
        yield from thoughts_of(month)


# 一語ずつ増えていくところ。何年か経つと何万語にもなるので、
# 一語を何行にも広げずに詰めて書く
PACKED_AWAY = ("words_met", "learned_on", "learned_where")

# 出会った言葉は一つも捨てないので、増え続ける。
# 生まれて十四日で五十万字、一日に四万字ずつ増えていて、
# 一つのファイルのままだと七年ほどで GitHub が受け取れる大きさ(百メガ)を越える。
# 越えた日から散歩も日記も押し戻せなくなり、この子は止まる。
# 忘れさせるのではなく、言葉ごとに何十かの束へ分けてしまっておく
WORDS_FOLDER = "kotoba"
SPREAD_OUT = {
    "words_met": 64, "word_impact": 8, "places_understood": 8, "careful_with": 8, "seen_linked": 8, "bridges": 16,
    # 覚えた言葉ごとに増える並び方も束にする(2026-10-22)。一日に五十語覚えると三十年で五十万語になり、
    # 記憶のファイル一つのままだと GitHub が受け取れる大きさ(百メガ)に近づく。
    # ページを組む側(blog_manager)はこれらを読まないので、束にしても困らない
    "what_follows": 16, "opens_a_sentence": 4, "closes_a_sentence": 4,
}  # 記録の名前 → 束の数

# 束に分けても、出会った言葉は一日に四千語ほど増えていて、十年で千六百万語を越える。
# 毎時間それを全部読み込んでいては、いずれ重くて起き上がれなくなる。
# そこで、一年会っていない言葉は奥にしまう(2026-10-22、彼女と決めた)。
# 奥は毎時間は開かない。しまってあるだけで、捨ててはいない。
# また会ったら、その夜のうちに奥から出して、前の記録とつなぐ(tidy_the_deep)
OKU_FOLDER = os.path.join(WORDS_FOLDER, "oku")
OKU_AFTER_DAYS = 365  # これだけ会っていない言葉を、奥にしまう
OKU_WORDS_PER_FILE = 200000  # 奥の束一つに、これだけまで。GitHub は百メガを越えるファイルを受け取らない
# 奥の束に足すものと抜くもの(tidy_the_deep が決め、save_state が書く)。
# 束の名前 → {"add": {言葉: 記録}, "drop": {言葉, ...}}
DEEP_TO_WRITE = {}


def bundle_of(word, how_many):
    """その言葉がしまってある束の番号。言葉が同じなら、いつも同じ束。"""
    return zlib.crc32(word.encode("utf-8")) % how_many


def bundle_path(key, number):
    return os.path.join(WORDS_FOLDER, key, f"{number:02d}.json")


def take_out_what_is_spread(state):
    """束に分けてしまってある記録を、記憶に戻す。

    束が一つも無いうちは、記憶のファイルに入っているものがそのまま使われる。
    束が読めなかったときは止める。空として続けると、次に書き出すときに
    その束の言葉をまるごと失う。"""
    for key, how_many in SPREAD_OUT.items():
        gathered = dict(state.get(key) or {})
        for number in range(how_many):
            path = bundle_path(key, number)
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8") as f:
                gathered.update(json.load(f))
        state[key] = gathered


def save_state(state):
    """記憶を書き出す。

    人が開いて読めるように行を分けて書くが、一語ずつ増えていく
    ところだけは、一語を何行にも広げると何万行にもなってしまうので詰める。"""
    # 奥へしまうものを先に書く。手前から先に消すと、途中で止まった時に言葉を失う
    write_the_deep()
    put_away_spread(state)
    packed = {
        key: state[key]
        for key in PACKED_AWAY
        if isinstance(state.get(key), dict) and key not in SPREAD_OUT
    }
    # 頭は atama/ に別に書き出す
    shaped = {
        key: value for key, value in state.items() if key not in SPREAD_OUT and key != "atama"
    }
    for key in packed:
        shaped[key] = f"\u0000{key}\u0000"  # 言葉には入りえない印
    text = json.dumps(shaped, ensure_ascii=False, indent=2)
    for key, value in packed.items():
        text = text.replace(
            json.dumps(f"\u0000{key}\u0000", ensure_ascii=False),
            json.dumps(value, ensure_ascii=False, separators=(",", ":")),
        )
    blog_manager.write_whole(STATE_FILE, text)
    head_does(atama.save, state.get("atama"))


def deep_files():
    """奥の束の名前。古い順。"""
    try:
        names = sorted(os.listdir(OKU_FOLDER))
    except OSError:
        return []
    return [os.path.join(OKU_FOLDER, name) for name in names if name.endswith(".json")]


def read_deep(path):
    """奥の束を一つ開ける。無ければ空。読めなければ None(その束には触らない)。"""
    try:
        with open(path, encoding="utf-8") as f:
            kept = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        print(f"奥の束 {path} が読めませんでした。その束には触らずにおきます")
        return None
    return kept if isinstance(kept, dict) else None


def joined_records(old, new):
    """奥から出した記録(old)と、また会ってからの記録(new)をつなぐ。

    会った日数は足す。初めて会った場所とページは昔のほう、いちばん最近は今のほう。
    昔のほうで初めての場所が分からない(取り始める前に会っていた)なら、分からないまま。
    いつもの記録(where_it_met)と同じ。"""
    def at(record, i):
        return record[i] if len(record) > i else None
    first_place = at(old, 2)
    last_place = at(new, 3) if at(new, 3) is not None else at(old, 3)
    first_page = at(old, 4)
    last_page = at(new, 5) if at(new, 5) is not None else at(old, 5)
    joined = [(at(old, 0) or 0) + (at(new, 0) or 0), max(at(old, 1) or 0, at(new, 1) or 0)]
    if first_page is not None or last_page is not None:
        return joined + [first_place, last_place, first_page, last_page]
    if first_place is not None or last_place is not None:
        return joined + [first_place, last_place]
    return joined


def tidy_the_deep(state):
    """眠る前に、奥を片づける。

    今日また会った言葉が奥にあれば出してつなぎ、一年会っていない言葉を奥にしまう。
    奥の束は一つずつ開けて閉じるので、奥がどれだけ大きくなっても重くならない。
    書くのは save_state(試す時に save_state を塞げば、奥にも触らない)。"""
    met = words_met(state)
    anew = {word for word in (state.pop("met_anew", None) or []) if word in met}
    brought = 0
    taken = set()
    for path in deep_files() if anew else []:
        kept = read_deep(path)
        if not kept:
            continue
        found = (anew | taken) & kept.keys()
        if not found:
            continue
        change = DEEP_TO_WRITE.setdefault(path, {"add": {}, "drop": set()})
        for word in found:
            # 二つの束にあったら(書きかけで止まった時)、二度は足さない。あとのほうは抜くだけ
            if word not in taken:
                met[word] = joined_records(kept[word], met[word])
                taken.add(word)
                brought += 1
            change["drop"].add(word)
            change["add"].pop(word, None)
        anew -= found

    today = day_number(state)
    old = [
        word for word, record in met.items()
        if isinstance(record, list) and len(record) > 1 and isinstance(record[1], int)
        and today - record[1] >= OKU_AFTER_DAYS
    ]
    put = 0
    month = f"{now_in_japan():%Y-%m}"
    number, path, room = 0, None, 0
    for word in old:
        # しまう束は、その月の束。いっぱいなら次の束へ
        while room <= 0:
            path = os.path.join(OKU_FOLDER, f"{month}-{number:02d}.json")
            number += 1
            kept = read_deep(path)
            if kept is None:
                continue  # 読めない束には足さない
            pending = DEEP_TO_WRITE.get(path) or {"add": {}}
            room = OKU_WORDS_PER_FILE - len(kept) - len(pending["add"])
        change = DEEP_TO_WRITE.setdefault(path, {"add": {}, "drop": set()})
        change["add"][word] = met.pop(word)
        room -= 1
        put += 1
    if brought or put:
        print(f"奥から{brought}語を出し、{put}語を奥にしまいました")
    return brought, put


def notice_met_anew(state, word):
    """初めて会ったと思った言葉。奥にしまってあるかもしれないので、夜に確かめる。"""
    if DEEP_IS_THERE[0] is None:
        DEEP_IS_THERE[0] = bool(deep_files())
    if DEEP_IS_THERE[0]:
        state.setdefault("met_anew", []).append(word)


DEEP_IS_THERE = [None]  # 奥に何かしまってあるか(一回の起き上がりのあいだだけ覚えておく)


def write_the_deep():
    """tidy_the_deep が決めたとおりに、奥の束を書き直す。一つずつ開けて閉じる。"""
    for path, change in list(DEEP_TO_WRITE.items()):
        kept = read_deep(path)
        if kept is None:
            raise RuntimeError(f"奥の束 {path} が読めないので、しまえません")
        for word in change["drop"]:
            kept.pop(word, None)
        kept.update(change["add"])
        if kept:
            blog_manager.write_whole(path, json.dumps(kept, ensure_ascii=False, separators=(",", ":")))
        elif os.path.exists(path):
            os.remove(path)
        DEEP_TO_WRITE.pop(path)


def put_away_spread(state):
    """増え続ける記録を、束に分けて書き出す。中身の変わった束だけ書き直す。"""
    for key, how_many in SPREAD_OUT.items():
        record = state.get(key)
        if not isinstance(record, dict):
            continue
        bundles = [{} for _ in range(how_many)]
        for word, value in record.items():
            bundles[bundle_of(word, how_many)][word] = value
        for number, bundle in enumerate(bundles):
            path = bundle_path(key, number)
            text = json.dumps(bundle, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            try:
                with open(path, encoding="utf-8") as f:
                    if f.read() == text:
                        continue
            except OSError:
                pass
            blog_manager.write_whole(path, text)


def day_number(state, when=None):
    """生まれた日を0として、その日が何日目か。

    記憶の中で日付を持つときは、この数で持つ。
    「2026-09-14」と書くより短く、引き算もそのままできる。"""
    try:
        born = datetime.date.fromisoformat(state["started_date"])
    except (KeyError, TypeError, ValueError):
        return 0
    return ((when or today_in_japan()) - born).days


def words_met(state):
    """出会った言葉の記録。{言葉: [何日ぶん見かけたか, 最後に見かけた日]}"""
    return state.setdefault("words_met", {})


def elapsed_days(state):
    """生まれてから何日目か。日本時間で数える。"""
    started = datetime.date.fromisoformat(state["started_date"])
    return max(0, (today_in_japan() - started).days)


def current_stage(state):
    """今どれだけ書けるかは、覚えている言葉の数で決まる。"""
    return blog_manager.current_stage(state)


def learned_on(state, word):
    """その言葉を覚えた日。

    記録を取り始める前に覚えた言葉のことは分からない。
    分からないものを、分かったことにはしない。"""
    return (state.get("learned_on") or {}).get(word)


def it_writes_in_its_own_words(state):
    """最終段階に届いたか。自分の言葉で書けるようになったかどうか。"""
    return len(blog_manager.words_it_counts(state)) >= GROWTH_STAGES[-1][0]
