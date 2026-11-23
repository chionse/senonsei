# 千遠生の体の一部。気にかかっていること、言いたいこと、興味の育ち方、知っている言葉の数え方。
#
# このファイルは単独では動かない。senonsei_ai.py が、決まった順に
# 全部の部品を自分の中へ読み込み、一つの体として動かす(2026-11-23、彼女と決めた)。
# ここに書いた名前は、ほかの部品からも senonsei_ai.<名前> としても、そのまま見える。

def how_long_it_holds(state):
    """覚えかけの言葉を、どれだけの間抱えていられるか。

    知っている言葉が増えるほど、記憶は長く持つようになる。
    言葉を知っていること自体が、新しい言葉を引っ掛ける釘になる。"""
    return FADE_AFTER_DAYS + len(blog_manager.words_it_counts(state)) // MEMORY_GROWS_EVERY


def days_held(state, word):
    """その言葉を、今どれだけ抱えているか。

    見かけた日数から、見かけなくなってからの時間ぶんを引く。
    覚えかけたまま放っておかれた言葉は、だんだん薄れていく。

    ただし何度も見た言葉ほど忘れにくい。二十日ぶん見た言葉は
    二十倍長く抱えていられる。十年ぶりの言葉を思い出せるのは、
    昔たくさん聞いたからで、一度しか聞いていない言葉はすぐ消える。

    そして一度出会ったことだけは、身につき具合が尽きても消えない。
    覚えていなくても「見たことがある」という感じは残る。
    それが無いと、二度目に出会う前に必ず忘れてしまい、
    珍しい言葉は永遠に一度目を繰り返すことになる。

    この子は、出会った言葉を一つも捨てない。
    十年会わないままの一度きりの出会いを手放す決まりを置いていたが、
    それが捨てるものを数えたら、「ぶどう」「懺悔」「信号機」「探検」
    のような本物の言葉が混ざっていた。二度と会えないほど珍しいものに
    一度だけ会えた、ということでもあるので、置いておくことにした。
    四十万語まで増えても五メガバイトにしかならない。"""
    record = words_met(state).get(word)
    if not record:
        return 0
    days, last = record[0], record[1]
    gap = max(0, day_number(state) - last)
    holds_for = how_long_it_holds(state) * max(1, days + struck_by(state, word))
    faded = days - gap // holds_for
    return max(1, faded) if days >= 1 else faded


def on_its_mind(state):
    """気にかかっていること。ぜんぶ。

    一つも捨てない。触れないでいれば後ろへ下がるが、消えはしない。
    忘れないことと、握りしめたままでいることは違う。
    下がったものも、ふとまた前に出てくることがある。"""
    kept = state.get("on_its_mind") or []
    for item in kept:
        item.setdefault("first", item.get("since"))
    state["on_its_mind"] = kept
    return kept


def minds_in_front(state, how_many=MINDS_IN_FRONT):
    """いま前に出ている気がかり。最後に触れたものから。

    何十年ぶんを一度に頭へ載せたら、一つひとつが意味を失う。
    前に出ているのがこれ、というだけで、
    後ろのものを抱えていないわけではない。"""
    kept = sorted(
        on_its_mind(state),
        key=lambda item: (item.get("since") or "", item.get("times", 1)),
    )
    return kept[-how_many:] if how_many else kept


def minds_from_before(state, how_many=MINDS_SURFACING):
    """ずっと前に気にかかっていたことが、ふと浮かぶ。

    もう一年も触れていないことが、何かの拍子に戻ってくる。
    戻ってきたものにまた触れれば、それはまた前に出る。
    一度後ろへ行ったら二度と戻れない、ということにはしない。"""
    front = {id(one) for one in minds_in_front(state)}
    older = [one for one in on_its_mind(state) if id(one) not in front]
    if not older or random.random() > SURFACING_CHANCE:
        return []
    return random.sample(older, min(len(older), how_many))


def now_it_cares_about(state, word):
    """何かが気にかかった。

    すでに気にかかっていたなら、その日を新しくする。
    何度も戻ってくることは、それだけ長く離れないということ。"""
    kept = on_its_mind(state)
    today = f"{now_in_japan():%Y-%m-%d}"
    for item in kept:
        if item.get("what") == word:
            item["since"] = today
            item["times"] = item.get("times", 1) + 1
            break
    else:
        kept.append({"what": word, "since": today, "first": today, "times": 1})
    state["on_its_mind"] = kept
    return word


def wants_to_say(state):
    """言いたいこと。ぜんぶ。一つも捨てない。"""
    return state.setdefault("wants_to_say", [])


def now_it_wants_to_say(state, word):
    """何かに強く出会った。言いたいことが増える。

    気がかりとは別に持つ。気になっていることと、
    それについて何か言いたいことがあるかどうかは、同じではない。"""
    today = f"{now_in_japan():%Y-%m-%d}"
    kept = wants_to_say(state)
    for item in kept:
        if item.get("what") == word:
            item["since"] = today
            item["times"] = item.get("times", 1) + 1
            return word
    kept.append(
        {"what": word, "since": today, "first": today, "times": 1, "said": ""}
    )
    return word


def still_unsaid(state):
    """まだ言えていないこと。

    最後に強く出会ってから、まだそれについて書いていないもの。
    書けば後ろに下がる。消えはしない。
    また強く出会えば、また前に出てくる。
    言った、だから無くなった、ではなく、
    言った、だから今は落ち着いている。"""
    return [
        one
        for one in wants_to_say(state)
        if (one.get("said") or "") < (one.get("since") or "")
    ]


def what_it_wants_to_say(state, how_many=WANTS_IN_FRONT):
    """言いたいことを、訊くときの一行にする。"""
    burning = still_unsaid(state)
    if not burning:
        return "(いまは特に無い)"
    burning.sort(key=lambda one: (one.get("since") or "", one.get("times", 1)))
    return "、".join(one["what"] for one in burning[-how_many:])


def it_said_them(state, written):
    """書いたものに出てきたことは、言えたことになる。

    出てこなかったことは、まだ言えていないまま残る。
    三文字しか書けないうちは、ほとんど何も言えない。
    長く書けるようになるほど、一度に多くのことが言える。
    それがこの子にとっての、書けるようになるということ。"""
    today = f"{now_in_japan():%Y-%m-%d}"
    said = []
    for one in wants_to_say(state):
        word = one.get("what")
        if word and word in (written or ""):
            one["said"] = today
            said.append(word)
    return said


def struck_by(state, word):
    """その言葉に、どれだけ強く出会ったか。

    ページの隅に一度出てきた言葉と、そのページ全体がその話だった
    言葉は、同じではない。絵を見て受け取った言葉や、名前として
    差し出された言葉も強い。

    一年に一度しか出会わなくても、強く出会えば残る。"""
    return (state.get("word_impact") or {}).get(word, 0) * STRUCK_IS_WORTH


JAPANESE_KNOWN = [0, None, -1]  # 数えた数、どの記憶の、何語の時に数えたか


def japanese_words_known(state):
    """身についた言葉のうち、日本語の字で書かれたものの数。"""
    learned = state.get("learned_words") or []
    if JAPANESE_KNOWN[1] != id(learned) or JAPANESE_KNOWN[2] != len(learned):
        JAPANESE_KNOWN[0] = sum(1 for word in learned if JAPANESE.search(word))
        JAPANESE_KNOWN[1], JAPANESE_KNOWN[2] = id(learned), len(learned)
    return JAPANESE_KNOWN[0]


def script_of(word):
    """よその字で書かれた言葉なら、その字の名前。日本語・数字・記号なら None。"""
    if not word or JAPANESE.search(word):
        return None
    for name, shape in A_WORD_IN_SCRIPT.items():
        if shape.fullmatch(word):
            return name
    return None


def interest_in(state, script):
    """その字の言葉への興味。0 から 1。日本語が身につくまでは 0。"""
    if japanese_words_known(state) < FOREIGN_INTEREST_BEGINS:
        return 0.0
    return min(1.0, (state.get("foreign_interest") or {}).get(script, 0.0))


def cares_for(state, word):
    """その言葉を、今のこの子が気にかけるか。日本語はいつも。よその言葉は興味が育ってから。"""
    script = script_of(word)
    return script is None or interest_in(state, script) >= INTEREST_TO_CARE


def interest_grows(state, words):
    """出会った言葉の字ごとに、その日のぶんだけ興味が育つ。日本語が身についてから。"""
    if japanese_words_known(state) < FOREIGN_INTEREST_BEGINS:
        return
    today = day_number(state)
    grown_on = state.setdefault("foreign_interest_on", {})
    interest = state.setdefault("foreign_interest", {})
    for script in {script_of(word) for word in words} - {None}:
        if grown_on.get(script) != today:
            grown_on[script] = today
            interest[script] = min(1.0, round(interest.get(script, 0.0) + INTEREST_GROWS_A_DAY, 4))


# 数字だけの言葉も覚える。ただし言葉の数には入れず、辞典にも出さない(2026-11-03、彼女が決めた)。
# 一度は覚えないようにしたが、「数字を使うのを縛りたいわけではない」と言われて戻した。
# 言葉の数を使うところ(育ちの段、覚えかけを抱えていられる日数)は、数字を数えない
ONLY_DIGITS = blog_manager.ONLY_DIGITS


def days_needed_for(state, word):
    """その言葉を覚えるまでに、あと何日ぶん必要か。

    強く出会った言葉は、少ない日数で身につく。
    一年に一度しか出会わなくても、そのたび深く刻まれるなら、
    いつかはその子のものになる。"""
    strikes = min(STRIKES_THAT_COUNT, (state.get("word_impact") or {}).get(word, 0))
    needed = max(FEWEST_DAYS_TO_LEARN, DAYS_BEFORE_LEARNING - strikes * A_STRIKE_SHORTENS)
    # よその言葉は、興味が育つまでぐんと覚えにくい
    script = script_of(word)
    if script is not None:
        harder = FOREIGN_AT_BEST + (FOREIGN_HARDER - FOREIGN_AT_BEST) * (1 - interest_in(state, script))
        needed = round(needed * harder)
    return needed
