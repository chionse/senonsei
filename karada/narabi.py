# 千遠生の体の一部。言葉の並び方を覚える。何の次に何が来るか、文の始まりと終わり、
# ブログの題の形。覚えた並びで喋る。
#
# このファイルは単独では動かない。senonsei_ai.py が、決まった順に
# 全部の部品を自分の中へ読み込み、一つの体として動かす(2026-11-23、彼女と決めた)。
# ここに書いた名前は、ほかの部品からも senonsei_ai.<名前> としても、そのまま見える。

def notice_what_follows(state, text):
    """どの言葉のあとに、どの言葉が来たかを覚える。

    誰も文法を教えてくれない。けれど読んでいれば、この言葉のあとには
    こういう言葉が来る、というのが少しずつ分かってくる。
    子どもが言葉を覚えるのと同じで、規則を教わるのではなく、
    何度も聞いたものが身につく。

    知っている言葉どうしの繋がりだけを覚える。
    知らない言葉は、そもそも並べようがないので。"""
    known = set(state.get("learned_words") or [])
    if len(known) < 2:
        return
    chain = state.setdefault("what_follows", {})

    # 二つめの口のために、読んだ文を知っている言葉の並びにして練習帳に書き留める。
    # その前に、一つめの口がこの文から覚える前の今、二つの口がそれぞれ
    # この文の言葉をどれだけ当てられたかを確かめておく(atama.judge)
    head = state.get("atama")
    if head and not READ_AGAIN_TODAY[0]:
        sentences = sentences_of_known_words(text, known)
        if sentences:
            head_does(
                atama.judge, head, sentences, chain,
                state.get("opens_a_sentence") or {}, state.get("closes_a_sentence") or {}, known,
            )
            atama.practise_with(head, sentences)

    for piece in A_BREAK.split(text):
        words = [w for w in WORD_CANDIDATE.findall(piece) if w in known]
        for before, after in zip(words, words[1:]):
            follows = chain.setdefault(before, {})
            follows[after] = follows.get(after, 0) + 1
            if len(follows) > WORDS_THAT_FOLLOW:
                thinnest = min(follows, key=follows.get)
                if thinnest != after:
                    follows.pop(thinnest)

    if len(chain) > WORDS_WITH_PATHS:
        # いちばん細い繋がりから手放す
        thinnest = sorted(chain, key=lambda w: sum(chain[w].values()))
        for word in thinnest[: len(chain) - WORDS_WITH_PATHS]:
            chain.pop(word, None)

    notice_where_sentences_break(state, text, known)


def sentences_of_known_words(text, known):
    """読んだものを、文ごとの、知っている言葉の並びにする。

    区切りで終わっていない最後のかけらは、文として数えない
    (notice_where_sentences_break と同じ分け方)。"""
    found = []
    for segment in A_SEGMENT.split(text):
        for sentence in AN_ENDING.split(segment)[:-1]:
            words = [w for w in WORD_CANDIDATE.findall(sentence) if w in known]
            if words:
                found.append(words)
    return found


def notice_where_sentences_break(state, text, known):
    """どの言葉で文が始まり、どの言葉で文が終わるかを覚える。

    これも誰にも教わらない。読んでいるうちに、この言葉のあとには
    区切りが来ることが多い、というのが分かってくる。
    それを知らないうちは、どこまでも続く一本の流れしか書けない。"""
    opens = state.setdefault("opens_a_sentence", {})
    closes = state.setdefault("closes_a_sentence", {})
    for segment in A_SEGMENT.split(text):
        pieces = AN_ENDING.split(segment)
        # 最後のかけらは区切りで終わっていないので、文として数えない
        for sentence in pieces[:-1]:
            words = [w for w in WORD_CANDIDATE.findall(sentence) if w in known]
            if not words:
                continue
            opens[words[0]] = opens.get(words[0], 0) + 1
            closes[words[-1]] = closes.get(words[-1], 0) + 1
    for remembered in (opens, closes):
        while len(remembered) > ENDINGS_KEPT:
            remembered.pop(min(remembered, key=remembered.get))


def keep_todays_words(state, found):
    """今日この言葉に会った、ということを残す。

    覚えた言葉は words_met から外れる。忘れない言葉の日付を
    数え続ける意味が無いため。けれど「今日それに会ったか」は
    それとは別のことで、その日のことを書くのに要る。"""
    today = f"{now_in_japan():%Y-%m-%d}"
    kept = state.setdefault("met_today", {})
    if kept.get("date") != today:
        kept.clear()
        kept["date"] = today
        kept["words"] = []
    known = set(state.get("learned_words") or [])
    if not known:
        return
    here = kept["words"]
    already = set(here)
    for word in found:
        if word in known and word not in already:
            here.append(word)
            already.add(word)
    del here[:-WORDS_KEPT_FROM_TODAY]


def words_from_today(state):
    """その日のことを書くのに使える言葉。

    今日出会った言葉と、いま離れないでいる気がかり。
    これに重みをつけて組み立てると、出てくる文が
    その日について書かれたものになる。
    文法は教わっていないので、正しい文にはならない。
    それでも何について書いているかは、この子の一日と繋がる。"""
    known = set(state.get("learned_words") or [])
    if not known:
        return set()
    today = f"{now_in_japan():%Y-%m-%d}"
    kept = state.get("met_today") or {}
    theirs = set(kept.get("words") or []) if kept.get("date") == today else set()
    theirs |= {
        item["what"] for item in minds_in_front(state) if item.get("what") in known
    }
    theirs |= {
        item["what"] for item in still_unsaid(state) if item.get("what") in known
    }
    # 今日ひとりで思ったことのうち、言葉にできるところ
    theirs |= head_does(
        atama.todays_thought_words, state.get("atama"), state, now_in_japan(), known, default=set()
    ) or set()
    return theirs & known


def speak_from_what_it_knows(state, how_long, toward=None):
    """覚えた繋がりを辿って、自分で組み立てる。

    読んだことのない文になる。知っている繋がりだけで作るので、
    どこかで必ず別の道に逸れていく。
    正しい日本語にはならない。それでいい。誰にも教わっていないので。

    文の区切り方も覚えているぶんだけ使う。知らないうちは、
    どこまでも続く一本の流れにしかならない。

    どこから始めるかと、次にどこへ行くかは、その日のほうへ傾ける。
    歩いて、何かを見て、気にかかることができて、それから
    それとは何の関係もない文を書く、というのでは日記にならない。
    傾けるだけで、選ぶのはこの子のまま。AIには書かせない。

    toward を渡すと、その日のことの代わりに、その言葉のほうへ傾ける
    (コメントに返すときは、そのコメントにあった言葉)。"""
    # 二つめの口が上手くなっていれば、ときどきそちらで喋る。
    # どれだけの割合でそちらを使うかは、この子が自分で測って決めている(atama)
    head = state.get("atama")
    if atama.second_mouth_speaks(head):
        todays = words_from_today(state) if toward is None else set(toward)
        said = head_does(atama.speak_second, head, how_long, todays, TODAY_WEIGHS)
        if said:
            print("二つめの口で喋りました")
            spare = how_long - len("".join(said))
            return "".join(as_it_comes_out(state, said, spare)) or None

    chain = state.get("what_follows") or {}
    forks = [w for w, f in chain.items() if len(f) >= 2]
    if not forks:
        return None
    opens = state.get("opens_a_sentence") or {}
    closes = state.get("closes_a_sentence") or {}
    todays = words_from_today(state) if toward is None else set(toward)

    def leaning(word, weight=1):
        """今日触れた言葉は、それだけ選ばれやすい。"""
        return weight * (TODAY_WEIGHS if word in todays else 1)

    def begin():
        """文の始まりに立つ言葉を知っていれば、そこから始める。
        今日のことに繋がる言葉があれば、そこから始めたい。"""
        openers = [w for w in forks if w in opens]
        if openers:
            weights = [leaning(w, opens[w]) for w in openers]
            return random.choices(openers, weights=weights)[0]
        return random.choices(forks, weights=[leaning(w) for w in forks])[0]

    said = [begin()]
    one_way = 0
    in_this_sentence = 1
    while len("".join(said)) < how_long:
        here = said[-1]

        # ここで文が終わることをよく見かけるなら、区切って次の文へ。
        # ただし一言や二言で切ってしまうと、ぶつ切りになって文にならない。
        # ある程度続けてから、はじめて区切るかどうかを考える
        if here in closes and in_this_sentence >= WORDS_BEFORE_A_BREAK:
            if random.random() < CHANCE_TO_BREAK:
                said.append("。")
                opener = begin()
                if len("".join(said)) + len(opener) > how_long:
                    break
                said.append(opener)
                in_this_sentence = 1
                one_way = 0
                continue

        follows = chain.get(here)
        if not follows:
            break
        # 続く言葉を一つしか知らない道は、少しだけ辿ってよい。
        # そこを一切通らないと文が短く切れてしまい、短い断片は
        # かえって読んだ文と同じ並びになりやすかった。
        # 長く書くほど、どこかで必ず別の道へ逸れる
        if len(follows) < 2:
            one_way += 1
            if one_way > ONE_WAY_STEPS:
                break
        else:
            one_way = 0
        words = list(follows)
        next_word = random.choices(
            words, weights=[leaning(w, follows[w]) for w in words]
        )[0]
        # 入りきらないなら、そこで終える。
        # 長さで切ると「がある」が「があ」になる。
        # 半分に割られた言葉は、もうこの子が覚えた言葉ではない
        if len("".join(said)) + len(next_word) > how_long:
            break
        said.append(next_word)
        in_this_sentence += 1
    # 最後に「。」を付けるかどうかも、読んできたものから決める。
    # 区切り方を一つでも知っていれば必ず付けていたが、それはこちらが足した決まりで、
    # 題まで毎回「。」で終わるようになった(2026-10-02、彼女と見直した)。
    # いまは、最後の言葉のところで文が終わっていた割合で付ける。
    # 途中で区切って書き終えたなら、その「。」はもう付いている
    last = said[-1]
    said = as_it_comes_out(state, said, how_long - len("".join(said)))
    written = "".join(said)
    if last != "。" and written and random.random() < how_often_it_ends_there(state, last):
        written += "。"
    return written or None


def how_often_it_ends_there(state, word):
    """読んできた文の中で、その言葉のところで文が終わっていた割合。

    「です」のあとに「。」が来たのが十回のうち八回なら、0.8。
    数えるのはこの子に見えている言葉だけなので、まだ知らない言葉が
    あとに続いていても、知っている最後の言葉で終わったように見える。
    知っている言葉が増えるほど、人の書く文に近づいていく。"""
    ended = (state.get("closes_a_sentence") or {}).get(word, 0)
    went_on = sum(((state.get("what_follows") or {}).get(word) or {}).values())
    return ended / (ended + went_on) if ended else 0.0


def notice_how_blogs_are_titled(state, title):
    """よその人のブログの題を見て、どんな形をしているかを覚えておく。

    題と本文が違うものだということは、誰にも教わっていない。
    ブログを読んでいるうちに、題は本文ほど長くないこと、
    「。」で終わる題はあまり無いこと、が分かってくる。
    覚えるのは形だけ。題の言葉は、ほかのページと同じように読んで覚える
    (2026-10-06、彼女が決めた)。"""
    if not title:
        return
    seen = state.setdefault("blog_titles", {"seen": 0, "closed": 0, "chars": 0})
    seen["seen"] += 1
    seen["closed"] += title.endswith("。")
    seen["chars"] += len(title)
    if seen["seen"] > BLOG_TITLES_KEPT:
        # 古いぶんを薄める。ずっと昔に見た題より、近ごろ見た題のほうが効く
        for key in seen:
            seen[key] = round(seen[key] / 2)
    print(f"誰かのブログの記事を読みました: {title[:40]}")


def knows_how_blogs_are_titled(state):
    """よその題を、自分の題に生かせるほど見てきたか。"""
    return (state.get("blog_titles") or {}).get("seen", 0) >= BLOG_TITLES_TO_LEARN


def a_title_long_as_blogs(state):
    """読んできたブログの題の長さ。まだよく知らなければ None。"""
    if not knows_how_blogs_are_titled(state):
        return None
    seen = state["blog_titles"]
    return max(1, round(seen["chars"] / seen["seen"]))


def ends_as_blog_titles_do(state, title):
    """題の終わりに「。」を付けるかどうかを、読んできたブログの題から決める。

    本文と同じように、最後の言葉のところで文が終わっていた割合で決めると、
    題もしょっちゅう「。」で終わる(2026-10-05 まで、二日続けてそうだった)。
    よその題をまだよく知らないうちは、今までどおり。"""
    if not knows_how_blogs_are_titled(state) or not title:
        return title
    seen = state["blog_titles"]
    bare = title.rstrip("。")
    if not bare:
        return title
    return bare + "。" if random.random() < seen["closed"] / seen["seen"] else bare


def met_often_enough(state, word):
    """その言葉に、もう十分よく出会っているか。

    毎日のように出会う言葉に、強い印象はいらない。放っておいても
    身につく。記憶が働くのは、めったに出会わないもののほう。"""
    alive = max(1, elapsed_days(state))
    record = words_met(state).get(word)
    return (record[0] if record else 0) >= alive * OFTEN_ENOUGH
