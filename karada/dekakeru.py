# 千遠生の体の一部。これから行く場所の並びと、場所の名前。一日の散歩に出る。
#
# このファイルは単独では動かない。senonsei_ai.py が、決まった順に
# 全部の部品を自分の中へ読み込み、一つの体として動かす(2026-11-23、彼女と決めた)。
# ここに書いた名前は、ほかの部品からも senonsei_ai.<名前> としても、そのまま見える。

def where_it_will_go(state, how_many=PLACES_SHOWN):
    """これから行くつもりの場所を、人に見える形にする。

    一度行った場所は名前で、まだ行っていない場所は住所のまま。
    行ったことのない場所の名前は、この子には分かりようがない。

    どの場所がどこなのかを知っているのは歩く側なので、
    ここで形にしてから残す。ページを組む側は並べるだけにする。

    束の頭から六つ取っていた。頭がめったに動かないので、
    何日見に来ても同じ六つが並んでいた。三百も先があるのに、
    そこだけしか無いように見える。

    そもそも頭が次に行く所ではない。行き先は choose_destination が
    束全体から散らして選び、その中から今いちばん惹かれる所を引く。
    頭から六つというのは、並べる順が偶然そうだったというだけ。

    束から散らして取る。覗くたびに違う六つが出る。"""
    named = state.get("places_known") or {}
    shown, already = [], set()
    # 惹かれる強さで運を引いて並べる。行き先を選ぶ時と同じ惹かれ方なので、
    # めったに見かけない場所ほど並びやすい(2026-10-08)
    close = evened_out(words_it_holds_close(state))
    bundle = [
        url
        for _, url in sorted(
            (
                (random.random() ** (1 / max(what_draws_it(state, url, close), 0.01)), url)
                for url in state.get("frontier") or []
            ),
            reverse=True,
        )
    ]
    for one in bundle:
        place = place_of(one)
        if not place or place in already:
            continue
        already.add(place)
        shown.append(named.get(place, place))
        if len(shown) >= how_many:
            break
    return shown


def read_the_name_again(name):
    """読み方を間違えて、化けたまま覚えた名前を読み直す。

    化けた名前は、元のバイトを間違った読み方で文字にしたもの。
    同じ読み方で文字をバイトに戻せば、元の並びがそのまま戻ってくる。

    一つは UTF-8 を Shift_JIS で読んだもの(「•」が「窶｢」になる)。
    戻したバイトが UTF-8 として最後まで読めた時だけ直す。
    正しく覚えた日本語の名前を Shift_JIS のバイトに戻しても、
    UTF-8 としてはまず読めない。

    もう一つは日本語を西洋の読み方で読んだもの(「¥¸¥ª」のような並び)。
    読み直して、かなが出てこなければ、元から西洋の名前なのでそのままにする。"""
    if not name or KANA.search(name):
        return name
    try:
        again = name.encode("cp932").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        again = name
    if again != name:
        return again
    for western in ("latin-1", "cp1252"):
        try:
            raw = name.encode(western)
        except UnicodeEncodeError:
            continue
        if max(raw, default=0) < 0x80:
            return name
        again = read_as_japanese(raw, "")
        if KANA.search(again) and "\ufffd" not in again:
            return again
    return name


def read_the_names_again(state):
    """覚えている場所の名前のうち、化けたままのものを読み直す。

    読み方の間違いを直しても(2026-10-19)、前に覚えた名前は化けたまま残る。
    その場所にまた行くまで直らないので、起きるたびに見直す。
    行き先の並び(where_it_will_go)は、歩いたあとにこの名前から作り直される。"""
    named = state.get("places_known") or {}
    for place, name in list(named.items()):
        again = read_the_name_again(name)
        if again != name:
            named[place] = again
            print(f"化けていた場所の名前を読み直しました: {again}")


def remember_the_name(state, url, title):
    """行った場所の名前を覚えておく。

    行き先には住所しか書かれていない。一度行った場所なら、
    そこが何という名前だったかを知っている。次に行き先として
    並んだ時、住所ではなく名前で思い出せる。

    行ったことのない場所の名前は、この子には分かりようがない。
    そこは住所のまま並ぶ。"""
    place = place_of(url)
    if not place or not title:
        return
    named = state.setdefault("places_known", {})
    named[place] = title.strip()[:PLACE_NAME_LENGTH]


def take_a_walk(state, today, now):
    """一日かけて、少しずつ歩く。気が向いた時に一箇所だけ。
    書かない日でも、世界を見ることはやめない。
    歩かない時間も、ただ起きてひとりで何かを思っている。"""
    walk = state.get("today_walk") or {}
    if walk.get("date") != today:
        walk = {"date": today, "seen": []}
        state["today_walk"] = walk
    if len(walk["seen"]) >= sites_per_day(state):
        be_alone(state, now)
        return walk["seen"]  # 今日はもう十分歩いた
    # 出かけたいかどうかは、その時の気持ちでも変わる。退屈だと出たくなり、疲れていると出たくない
    if random.random() > WALK_CHANCE_PER_HOUR * atama.wants_to_walk(state.get("atama")):
        be_alone(state, now)
        return walk["seen"]  # 今はまだ、その気にならない

    title = walk_once(state)
    if title:
        walk["seen"].append(title)
        brought = walk.setdefault("brought", [])
        brought.append(WHAT_A_WALK_BROUGHT[0])
        # 気が乗って一か所多く歩いた日の、その一か所まで歩き終えた
        if (
            (state.get("today_keen") or {}).get("keen")
            and len(walk["seen"]) == sites_per_day(state)
            and len(brought) == len(walk["seen"])
        ):
            was_it_worth_the_extra(state, brought)
        learned = learn(state)
        if learned:
            print(f"言葉を覚えました: {'、'.join(learned)}")
        print(f"{title} を見てきました。")
        # 歩いて帰ってきたら、よく出会うのに分からない言葉に気づくことがある
        if state.get("atama"):
            added = head_does(
                atama.wonder, state["atama"], state, now, state.get("learned_words") or [],
                words_met(state), state.get("word_impact") or {}, default=[],
            )
            if added:
                print(f"知りたくなった: {'、'.join(added)}")
    save_state(state)
    return walk["seen"]
