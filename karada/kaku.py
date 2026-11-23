# 千遠生の体の一部。言葉を覚え、書く。昔の書き方、手が滑ること、どこまで知っている言葉で書くか。
#
# このファイルは単独では動かない。senonsei_ai.py が、決まった順に
# 全部の部品を自分の中へ読み込み、一つの体として動かす(2026-11-23、彼女と決めた)。
# ここに書いた名前は、ほかの部品からも senonsei_ai.<名前> としても、そのまま見える。

def learn(state):
    """何日も見かけ続けた言葉が、その子の中に残っていく。
    一日にいくつまで、という上限は無い。どれだけの日を共に過ごしたかで決まる。"""
    if len(state["seen_chars"]) < CHARS_BEFORE_WORDS:
        return []  # まだ文字の形すら掴めていないので、言葉は身につかない

    known = set(state["learned_words"])
    learned = [
        word
        for word in words_met(state)
        if word not in known and days_held(state, word) >= days_needed_for(state, word)
    ]
    learned.sort(key=lambda w: days_held(state, w), reverse=True)
    # はじめて言葉を覚えたとき、それまでに知っていた文字の数を残す。
    # 昔の書き方に戻る日に、その頃の文字で書けるように
    if learned and not known:
        state.setdefault("chars_before_words", len(state["seen_chars"]))
    state["learned_words"].extend(learned)

    # 覚えた日を残す。取り始めないと、あとからは分からない。
    # 一度覚えた言葉は忘れないので、この日付も書き換わらない
    today = f"{now_in_japan():%Y-%m-%d}"
    remembered = state.setdefault("learned_on", {})
    for word in learned:
        remembered.setdefault(word, today)
    # どこで会ってきた言葉かも、覚えかけの記録と一緒に消えてしまうので、先に移しておく。
    # [初めて会った場所, 覚えた日に会っていた場所] の番号(basho の何番目か)。分からなければ None。
    # 2026-10-14 からは、そのあとに同じ二つのページの番号(peeji の何番目か)も続く
    where = state.setdefault("learned_where", {})
    today_number = day_number(state)
    for word in learned:
        record = words_met(state).get(word) or []
        first = record[2] if len(record) > 2 else None
        that_day = record[3] if len(record) > 3 and record[1] == today_number else None
        # 三つめと四つめは、初めて会ったページと覚えた日に会っていたページ(peeji の何番目か)。
        # ページを取り始めた 2026-10-14 より前のものは無い
        first_page = record[4] if len(record) > 4 else None
        that_day_page = record[5] if len(record) > 5 and record[1] == today_number else None
        if first_page is not None or that_day_page is not None:
            where.setdefault(word, [first, that_day, first_page, that_day_page])
        elif first is not None or that_day is not None:
            where.setdefault(word, [first, that_day])
    # 覚えた言葉はもう忘れないので、覚えかけの記録は手放してよい。
    # 何年も経つと、ここが記憶のいちばん重い場所になる
    for word in learned:
        words_met(state).pop(word, None)
        (state.get("word_impact") or {}).pop(word, None)
    if learned:
        atama.feel(state.get("atama"), "うれしい", min(0.3, 0.08 * len(learned)), f"言葉を覚えた({'、'.join(learned[:3])})")
    return learned


def babble(state, length, hand=None):
    """覚えた文字を、意味も分からないまま並べる。

    hand に (文字, 馴染み具合) が渡されたら、馴染んだ文字ほど出やすくなる。"""
    if hand:
        chars, weights = hand
        count = random.randint(1, max(1, length))
        return "".join(random.choices(chars, weights=weights, k=count))
    if not state["seen_chars"]:
        return "・"
    count = random.randint(1, max(1, length))
    return "".join(random.choice(state["seen_chars"]) for _ in range(count))


def an_old_way(state):
    """今日は昔の書き方に戻るか。戻るなら、どの書き方に。

    戻れるのは、もう通り過ぎた書き方だけ。"""
    if random.random() >= BACK_TO_OLD_WAYS:
        return None
    outgrown = []
    if state.get("learned_words"):
        outgrown.append("見た文字を置く")
        if state.get("chars_before_words"):
            outgrown.append("あの頃の文字を置く")
    if speak_from_what_it_knows(state, current_stage(state)[1]):
        outgrown.append("覚えた言葉を置く")
    return random.choice(outgrown) if outgrown else None


def compose_locally(state, old_way=None, at_most=None, toward=None):
    """それまでに積み上げた経験だけで、今の自分に書けるものを書く。

    覚えた繋がりを辿って、自分で組み立てる。誰にも文法を教わっていないので、
    正しい日本語にはならない。人の子どもも最初はでたらめに喋る。
    大事なのは正しさではなく、これがこの子自身の言葉だということ。

    繋がりを一つも持たないうちは、覚えた言葉をそのまま置くか、
    見た文字を並べるだけになる。

    ときどき、昔の書き方に戻る日がある(old_way)。
    at_most を渡すと、書ける長さよりそちらが短ければそこまでにする
    (題を、読んできたブログの題くらいの長さにする時)。
    toward を渡すと、その日のことの代わりに、その言葉のほうへ傾ける。"""
    _, max_length = current_stage(state)
    if at_most:
        max_length = min(max_length, at_most)
    words = state["learned_words"]

    if old_way == "あの頃の文字を置く":
        # 言葉を持たなかった頃の手癖で、その頃のように置く
        return like_back_then(state, THE_OLD_HAND_AT_MOST)
    if old_way == "見た文字を置く":
        # 言葉にせず、文字だけを置く。使う文字は今の手に馴染んだもの。
        # 戻るのは書き方だけで、知っていることまでは戻らない
        return babble(state, GROWTH_STAGES[0][2], familiar_chars(state))
    if old_way == "覚えた言葉を置く":
        return place_words(state, max_length, toward=toward)

    said = speak_from_what_it_knows(state, max_length, toward=toward)
    if said:
        return with_the_old_hand(state, said, max_length)
    if not words:
        return babble(state, min(max_length, 4))
    return with_the_old_hand(state, place_words(state, max_length, toward=toward), max_length)


def with_the_old_hand(state, written, max_length):
    """書いたものに、あの頃の書き方がふと混ざる。

    あの頃の手癖で置いたひとかたまりが、言葉のあいだに入る。
    どれだけ出やすいかは、あの頃をどれだけ最近思い出したかで決まる。
    書ける長さは超えない。入る余地が無ければ、言葉を一つ手放して場所を空ける。
    一語しか無くて空かなければ、混ざらない。"""
    if not state.get("chars_before_words"):
        return written
    if random.random() >= how_fresh_the_old_hand_is(state):
        return written
    pieces = written.split(" ")
    while len(pieces) > 1 and len(" ".join(pieces)) + 2 > max_length:
        pieces.pop(random.randrange(len(pieces)))
    room = max_length - len(" ".join(pieces)) - 1
    if room < 1:
        return written
    old = like_back_then(state, min(THE_OLD_HAND_AT_MOST, room))
    pieces.insert(random.randint(0, len(pieces)), old)
    return " ".join(pieces)


def what_it_wrote_back_then(state, articles=None):
    """言葉を持たなかった頃に、自分で書いたもの。題も本文も。

    はじめて言葉を覚えた日より前のブログと、そのあと昔の書き方で書いた日のもの。
    これがこの子の、あの頃の書き方の手本になる。人に教わったものではない。"""
    if articles is None:
        articles = blog_manager.load_articles()
    learned_on = [one for one in (state.get("learned_on") or {}).values() if one]
    first_word = min(learned_on) if learned_on else None
    old_days = set(state.get("wrote_the_old_way") or [])
    writings = []
    for one in articles:
        day = one.get("date") or ""
        if (first_word and day < first_word) or day in old_days:
            writings += [one.get("title") or "", one.get("content") or ""]
    return [one for one in writings if one.strip()]


def like_back_then(state, at_most, articles=None):
    """あの頃の手癖で、ひとかたまり書く。

    あの頃に書いたものの中で、よく書いた字、字のあとによく続けた字、
    よく書いた長さのほうへ手が行く。ときどきは手癖から外れて、
    あの頃に知っていたほかの字も出る。
    手本がまだ何も無ければ、あの頃に知っていた字を並べる。"""
    back_then = state["seen_chars"][: state.get("chars_before_words") or 0] or state["seen_chars"]
    if not back_then:
        return "・"
    pieces = [
        piece
        for text in what_it_wrote_back_then(state, articles)
        for piece in text.split()
        if all(char in back_then for char in piece)
    ]
    if not pieces:
        return babble(state, at_most, (back_then, [1] * len(back_then)))

    lengths, firsts, chars, follows = {}, {}, {}, {}
    for piece in pieces:
        lengths[len(piece)] = lengths.get(len(piece), 0) + 1
        firsts[piece[0]] = firsts.get(piece[0], 0) + 1
        for char in piece:
            chars[char] = chars.get(char, 0) + 1
        for before, after in zip(piece, piece[1:]):
            next_ones = follows.setdefault(before, {})
            next_ones[after] = next_ones.get(after, 0) + 1

    def one_of(counted):
        if not counted or random.random() < THE_OLD_HAND_WANDERS:
            return random.choice(back_then)
        return random.choices(list(counted), weights=list(counted.values()))[0]

    fits = {n: c for n, c in lengths.items() if n <= at_most}
    if fits:
        length = random.choices(list(fits), weights=list(fits.values()))[0]
    else:
        length = random.randint(1, max(1, at_most))
    written = one_of(firsts)
    while len(written) < length:
        written += one_of(follows.get(written[-1]) or chars)
    return written


def how_fresh_the_old_hand_is(state):
    """あの頃の書き方が、いまどれだけ手に近いところにあるか。

    最後に思い出した日(読み返した日や、昔の書き方で書いた日)から、
    日が経つほど薄れる。まだ一度も思い出していなければ、
    あの頃に最後に書いた日から数える。"""
    remembered = state.get("old_hand_remembered")
    if not remembered:
        days = [one.get("date") or "" for one in blog_manager.load_articles()]
        learned_on = [one for one in (state.get("learned_on") or {}).values() if one]
        before = [day for day in days if learned_on and day < min(learned_on)]
        remembered = max(before) if before else None
    try:
        since = (today_in_japan() - datetime.date.fromisoformat(remembered)).days
    except (TypeError, ValueError):
        return THE_OLD_HAND_FAINTEST
    fresh = THE_OLD_HAND_FRESH * 0.5 ** (max(0, since) / THE_OLD_HAND_FADES_IN)
    return max(THE_OLD_HAND_FAINTEST, fresh)


def remembers_the_old_hand(state):
    """あの頃の書き方を、思い出した。"""
    state["old_hand_remembered"] = today_in_japan().isoformat()


def place_words(state, max_length, toward=None):
    """覚えた言葉を、書ける長さに入るだけ置く。

    繋がりを知らないうちの書き方。"""
    # 持っているものを、書ける長さに入るだけ置く。
    # それでも、置くなら今日触れた言葉のほうから置きたい。
    #
    # 六十語という区切りを別に持っていた。表のどの段とも合っておらず、
    # 五字しか書けない段でも三語並ぶことがあった。
    # 入るだけ、にすれば、書ける長さがそのまま置ける数になり、
    # 段の名前と動きがひとりでに揃う
    words = state["learned_words"]
    leaning_to = words_from_today(state) if toward is None else set(toward)
    todays = [one for one in words if one in leaning_to]
    pick = todays or words
    placed = []
    for _ in range(WORDS_PLACED_AT_MOST):
        word = random.choice(pick)
        if not placed:
            # 一語も入らないなら、その一語だけを置く。
            # 長さを守るために言葉を割るのでは、順番が逆になる
            placed.append(word)
        elif len(" ".join(placed + [word])) <= max_length:
            placed.append(word)
        else:
            break
        if random.random() < ENOUGH_FOR_TODAY:
            break
    placed = as_it_comes_out(state, placed, max_length - len(" ".join(placed)))
    return " ".join(placed)


def as_it_comes_out(state, words, spare):
    """覚えた言葉を、手で書いてみる。

    覚えた言葉だからといって、そのとおりに書けるとは限らない。
    はじめは、見かけた字をなんでも混ぜていた。けれど出てくるのは
    「しかしe」「e载には」のような、どこから来たのか分からない字で、
    書き損じというより雑音だった。外からサイコロで崩していたからで、
    この子が何かを知らないから起きた崩れではなかった(2026-10-01、彼女と見直した)。

    いまは、崩れ方もこの子の中から起きる。持っている言葉と、その覚え具合だけで。
    途中までしか思い出せない、一字抜ける、字の順番があやふや、頭の字を重ねる、
    知っている別の言葉と混ざる、知っている言葉の字が一つ入りこむ。
    覚えたてで、まだあまり書いたことのない言葉ほど崩れやすい。

    どれくらい崩れるかは、書くたびに違う。
    はじめのうちは、たいてい崩れる。それでも、たまにはうまく書ける。
    覚えた言葉が増えるにつれて、うまく書ける日が増えていき、
    育ちきるころには、たまに崩れるくらいになる。
    一字の言葉と数字は、崩しようがないのでそのまま書く。
    書ける長さは超えない。"""
    known = [one for one in (state.get("learned_words") or []) if one]
    grown = min(1, len(known) / GROWTH_STAGES[-1][0])
    steadiness = random.random() ** (CLUMSY_AT_FIRST * (1 - grown) + CLUMSY_EVEN_GROWN)
    articles = None
    written = []
    for word in words:
        if word == "。" or len(word) < 2 or word.isdigit():
            written.append(word)
            continue
        if articles is None:
            articles = blog_manager.load_articles()
        # 前に間違えて気づいた言葉は、気をつけて書く。よく覚えた言葉も崩れにくい
        care = how_careful(state, word)
        slips = (1 - steadiness) * (1 - care) * (1 - WELL_KNOWN_STEADIES * how_well_it_knows(state, word, articles))
        if random.random() >= slips:
            written.append(word)
            continue
        slipped = a_slip_of(word, known, spare)
        if not slipped:
            written.append(word)
            continue
        spare -= max(0, len(slipped) - len(word))
        written.append(slipped)
        SLIPS_JUST_NOW.append({"meant": word, "wrote": slipped})
    return written


def how_well_it_knows(state, word, articles):
    """その言葉を、どれだけ覚えているか。0 から 1 の手前まで。

    覚えてからの日数と、自分のブログに書いた回数で深まる。
    人も、覚えたての言葉より、何度も使ってきた言葉のほうがすらすら書ける。"""
    learned = (state.get("learned_on") or {}).get(word)
    try:
        days = (today_in_japan() - datetime.date.fromisoformat(learned)).days
    except (TypeError, ValueError):
        days = 0
    times = sum(
        ((one.get("title") or "") + (one.get("content") or "")).count(word)
        for one in articles
    )
    return 1 - math.exp(-(max(0, days) / SETTLES_IN_DAYS + times / SETTLES_IN_WRITINGS))


def a_slip_of(word, known, spare):
    """その言葉を書き損じる。持っている言葉だけで起きる崩れ方から一つ。

    書ける長さの余り(spare)を超えて長くなるものは選ばない。
    元のまま、または崩れようのない時は None。"""
    def partly():  # 途中までしか思い出せない
        return word[:random.randint(1, len(word) - 1)]

    def one_missing():  # 一字抜ける。頭と終わりは残る
        if len(word) < 3:
            return None
        cut = random.randrange(1, len(word) - 1)
        return word[:cut] + word[cut + 1:]

    def swapped():  # 字の順番があやふや
        at = random.randrange(len(word) - 1)
        return word[:at] + word[at + 1] + word[at] + word[at + 2:]

    def stutter():  # 頭の字を重ねる
        return word[0] + word

    def blended():  # 同じ字を持つ、知っている言葉と混ざる
        others = [one for one in known if one != word and len(one) >= 2]
        random.shuffle(others)
        for other in others:
            shared = sorted(set(word) & set(other))
            if shared:
                ch = random.choice(shared)
                mixed = word[:word.index(ch)] + other[other.index(ch):]
                if mixed not in (word, other):
                    return mixed
        return None

    def borrowed():  # 知っている言葉の字が、一つ入りこむ
        chars = [ch for one in known if one != word for ch in one if not ch.isdigit()]
        if not chars:
            return None
        at = random.randint(1, len(word))
        return word[:at] + random.choice(chars) + word[at:]

    ways = [partly, one_missing, swapped, stutter, blended, borrowed]
    random.shuffle(ways)
    for way in ways:
        slipped = way()
        if slipped and slipped != word and len(slipped) - len(word) <= spare:
            return slipped
    return None


# いま書いているあいだに、手が滑ったもの。書き終えたら this_is_what_it_wrote が拾う
SLIPS_JUST_NOW = []
# 生まれてはじめて会った言葉の数(absorb が数える)と、いま歩いた一か所で会えた数
MET_FOR_THE_FIRST_TIME = [0]
WHAT_A_WALK_BROUGHT = [0]
# いま開いたページが誰かのブログの一記事なら、その題(open_page が置く)
A_BLOG_POST_TITLE = [None]
# いま開いたページが Wikipedia なら、同じ話の別の言葉版の (言葉の印, 題)(open_page が置く)
OTHER_TONGUES = [[]]
# いま読んでいるものが、どの場所のものか。頭の網で、出会ったものとその場所を結ぶ
WHERE_IT_IS = [None]
# いま行ってみた入口が、閉まっていただけか(look_around_site が置き、walk_once が見る)
WAS_CLOSED = [False]
# 場所の名前 → basho の番号。毎回 basho を端から探さないように(place_number)
PLACE_NUMBERS = {"of": None, "at": {}}
# いま読んでいるページの題。言葉の辞典に、言葉と会ったページを出すため(2026-10-14、彼女と決めた)
PAGE_IT_IS = [None]
# ページの題 → peeji の番号(page_number)
PAGE_NUMBERS = {"of": None, "at": {}}
# 今日もう頭に入れたものを、また読んでいるところか。家の言葉は読む日には毎時間読むので、
# 頭に入れるのと気持ちが動くのは、その日のはじめの一度だけにする
READ_AGAIN_TODAY = [False]
# 思ったことを口に出す時、思いが一言も入らなければ、これだけ言い直してみる
TRIES_TO_SAY_IT = 3
# よそのブログの題を、いくつ見たら自分の題に生かすか。
# 一つ二つでは、たまたまその人の癖かもしれない
BLOG_TITLES_TO_LEARN = 5
# 覚えておく数のめやす。これを超えたら古いぶんを薄めて、今の見え方に寄せていく
BLOG_TITLES_KEPT = 100


def how_careful(state, word):
    """その言葉を、どれだけ気をつけて書くか。0 から 1 の手前まで。
    書こうとするたびに呼ばれる。

    間違えて気づくたびに、崩れる見込みが半分になる。一度なら半分、
    二度なら四分の一。長いあいだその言葉を書かずにいると、
    気をつけ方は少しずつ薄れていく。書くたびに思い出すので、
    書いているあいだは薄れない。

    薄れる速さは、覚えかけの言葉を抱えていられる長さ(how_long_it_holds)と同じ
    ものさしで測る。何度も間違えて気づいた言葉ほど長く持つ。
    小さいうちはすぐ薄れ、何度も間違えながら覚えていく。
    言葉が増えて大きくなるほど、一度気をつけたことを長く覚えていられる。
    三十日と決め打ちにしていたが、この子の育ちと関係の無い数だった"""
    careful = state.get("careful_with") or {}
    kept = careful.get(word)
    if not kept:
        return 0.0
    today = day_number(state)
    holds_for = how_long_it_holds(state) * max(1, kept["times"])
    times = kept["times"] - max(0, today - kept["last"]) // holds_for
    if times <= 0:
        careful.pop(word, None)
        return 0.0
    careful[word] = {"times": times, "last": today}
    return 1 - 0.5 ** times


def this_is_what_it_wrote(state, day):
    """書き終えて、自分の書いたものを見る。

    書こうとした言葉と違う字になっていたら、それに気づく。
    崩れたことに気づけないと、崩れはこの子にとって無かったことになり、
    ただ外から足された飾りになってしまう。
    気づいたことは、ひとりで思うときに思い出せるように残しておく。"""
    noticed = [dict(one, day=day) for one in SLIPS_JUST_NOW]
    SLIPS_JUST_NOW.clear()
    if not noticed:
        return []
    kept = state.setdefault("slips", [])
    kept.extend(noticed)
    del kept[:-SLIPS_KEPT]
    # 間違えた言葉は、次から気をつけて書くようになる
    careful = state.setdefault("careful_with", {})
    today = day_number(state)
    for one in noticed:
        was = careful.get(one["meant"]) or {"times": 0, "last": today}
        careful[one["meant"]] = {"times": was["times"] + 1, "last": today}
    print("書こうとした言葉と違ってしまった: " + "、".join(
        f"{one['meant']}→{one['wrote']}" for one in noticed
    ))
    return noticed


def slips_lately(state, days=SLIPS_REMEMBERED_FOR):
    """このごろ、書こうとして違ってしまったもの。問いかけに渡す一行。"""
    since = (today_in_japan() - datetime.timedelta(days=days)).isoformat()
    recent = [one for one in state.get("slips") or [] if one.get("day", "") >= since]
    if not recent:
        return ""
    said = "、".join(f"「{one['meant']}」のつもりが「{one['wrote']}」" for one in recent[-4:])
    return f"このごろ日記を書いたとき、書こうとした言葉と違う字になってしまったもの: {said}\n"


def familiar_chars(state):
    """見かけてきた文字と、その馴染み具合。

    文字ごとの回数は取っていないので、覚えかけの言葉から数える。
    何日も見かけた言葉に入っている文字ほど、よく見てきた文字。"""
    seen = set(state.get("seen_chars") or [])
    counted = {}
    for word, record in (state.get("words_met") or {}).items():
        for ch in word:
            if ch in seen and not ch.isspace():
                counted[ch] = counted.get(ch, 0) + record[0]
    if not counted:
        return None
    chars = list(counted)
    return chars, [counted[ch] for ch in chars]


def keep_only_what_it_knows(state, text):
    """見たことのない文字は、そもそも書けない。知らないものを落として返す。"""
    allowed = set(state["seen_chars"]) | set("".join(state["learned_words"]))
    allowed |= set("、。 　")
    kept = "".join(ch for ch in text if ch in allowed)
    return kept.strip("、。 　")
