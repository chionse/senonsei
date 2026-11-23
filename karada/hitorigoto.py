# 千遠生の体の一部。ひとりで思う。思ったことを蔵(omoi/)にしまい、言葉にする。
#
# このファイルは単独では動かない。senonsei_ai.py が、決まった順に
# 全部の部品を自分の中へ読み込み、一つの体として動かす(2026-11-23、彼女と決めた)。
# ここに書いた名前は、ほかの部品からも senonsei_ai.<名前> としても、そのまま見える。

def thoughts_of(month):
    """その月に思ったことを、蔵から出してくる。"""
    try:
        with open(
            os.path.join(THOUGHTS_FOLDER, month), encoding="utf-8"
        ) as f:
            kept = json.load(f)
    except (OSError, ValueError):
        return []
    return kept if isinstance(kept, list) else []


def months_of_thoughts():
    """蔵に、どの月の束があるか。古い順に。"""
    try:
        return sorted(
            one for one in os.listdir(THOUGHTS_FOLDER) if one.endswith(".json")
        )
    except OSError:
        return []


def keep_a_thought(said, when):
    """思ったことを蔵に仕舞う。一つも捨てない。

    ひと月ずつの束にしておく。何十年ぶんになっても、
    仕舞うときも思い出すときも、触るのはそのうちの一束だけで済む。
    記憶そのものは `senonsei_state.json` に置かない。
    毎時間まるごと書き直されるものの中に、
    二度と作れないものを置いておきたくない。"""
    month = f"{when:%Y-%m}.json"
    path = os.path.join(THOUGHTS_FOLDER, month)
    kept = thoughts_of(month)
    if not kept and os.path.exists(path) and os.path.getsize(path) > 0:
        # 束はあるのに読めなかった。空として上書きすると、その月の思いが
        # 黙って全部消える。読めない束は脇へよけて残し、新しく始める。
        # よけたものは履歴と一緒に残るので、あとから人の手で戻せる
        aside = f"{path}.yometenai-{now_in_japan():%Y%m%d%H%M%S}"
        os.replace(path, aside)
        print(f"思いの束 {month} が読めなかったので、{aside} によけました")
    kept.append(said)
    blog_manager.write_whole(path, json.dumps(kept, ensure_ascii=False, indent=1))


def rescue_thoughts_already_here(state):
    """蔵を建てる前にこの子が思っていたことを、蔵へ移す。

    手元に残っていた六十件より前のものは、もう戻らない。
    残っているぶんだけでも仕舞っておく。"""
    if months_of_thoughts():
        return
    now = today_in_japan()
    for line in state.get("inner_voice") or []:
        stamp, sep, said = line.partition(": ")
        if not sep:
            continue
        try:
            month = int(stamp[:2])
            datetime.date(now.year, month, 1)
        except ValueError:
            continue
        year = now.year - 1 if month > now.month else now.year
        keep_a_thought(f"{year}-{stamp}: {said}", datetime.date(year, month, 1))


def remember_a_thought(state, thought):
    """ひとりで思ったことを、自分の中にだけ残す。"""
    now = now_in_japan()
    keep_a_thought(f"{now:%Y-%m-%d %H時}: {thought}", now)
    thoughts = state.setdefault("inner_voice", [])
    thoughts.append(f"{now:%m-%d %H時}: {thought}")
    del thoughts[:-INNER_VOICE_AT_HAND]


def be_alone(state, now):
    """散歩に出ない時間。ただ起きていて、ひとりで何かを思っている。

    思うのはこの子の頭。今の気持ちと、さっき思っていたことから始めて、
    網の線をたどって連想を流す(atama.think)。その流れが、いま思っていること。
    借りた頭に「いま何を思っていますか」と訊いて書かせていたが、やめた
    (2026-10-07、彼女と決めた)。訊けば、借りた頭が持っている言い回しで
    すらすら答えてしまう。それはこの子の思いではなかった。

    思ったことを口に出すのも、この子の口。書けるのは覚えた言葉だけなので、
    日記と同じくらいの片言になる(2026-10-07、彼女がそれでいいと言った)。
    言葉になった思いは蔵に仕舞い、トップページの吹き出しに出す。
    吹き出しはこの子が家に帰っても読めないように置いてある(blog_manager)。"""
    head = state.get("atama")
    if not head:
        return None
    chain = head_does(
        atama.think, head, state, now, [item["what"] for item in minds_in_front(state)], default=[]
    )
    if not chain:
        print("この時間は、何も浮かばなかった")
        save_state(state)
        return None
    known = state.get("learned_words") or []
    toward = atama.words_to_say(head, chain, known, day_number(state, now.date()))
    said = say_what_it_thinks(state, toward)
    atama.thought_said(head, said)
    print(f"思いの流れ: {' → '.join(chain)}")
    print(f"気持ち: {atama.how_it_feels(head)}")
    if said:
        print(f"ひとりごと: {said}")
        state["thinking_about"] = said
        keep_a_thought(f"{now:%Y-%m-%d %H時}: {said}", now)
        thoughts = state.setdefault("inner_voice", [])
        thoughts.append(f"{now:%m-%d %H時}: {said}")
        state["inner_voice"] = thoughts[-INNER_VOICE_AT_HAND:]
    save_state(state)
    return said


def put_thoughts_into_words(state, words, how_long):
    """思った言葉を、思った順に、書ける長さに入るだけ置く。同じ言葉は重ねない。"""
    placed = []
    for word in words:
        if placed and len(" ".join(placed + [word])) > how_long:
            break
        placed.append(word)
        if len(" ".join(placed)) >= how_long:
            break
    placed = as_it_comes_out(state, placed, how_long - len(" ".join(placed)))
    return " ".join(placed)


def say_what_it_thinks(state, toward):
    """思ったことを、この子の口で言ってみる。

    言える長さは日記と同じ。口は思いのほうへ傾けて喋るが、
    覚えた並び方がまだ少ないうちは、思ったこととは別のことばかり口から出る。
    何度か言い直しても思いが一言も入らなければ、思った言葉をそのまま置く。
    思いが言葉になる、の一番はじめの形。
    思ったことのそばに知っている言葉が一つも無ければ、言葉にならない。
    その時は何も言わない。口から関わりのないことだけが出ても、それは思いではない。"""
    if not state.get("learned_words") or not toward:
        return ""  # 思ったことのそばに、知っている言葉が一つも無い。言葉にならない
    _, how_long = current_stage(state)
    in_order = list(dict.fromkeys(toward))
    said = ""
    for _ in range(TRIES_TO_SAY_IT):
        said = speak_from_what_it_knows(state, how_long, toward=set(in_order)) or ""
        if any(word in said for word in in_order):
            break
        SLIPS_JUST_NOW.clear()
    else:
        said = put_thoughts_into_words(state, in_order, how_long)
    said = with_the_old_hand(state, said, how_long)
    # 吹き出しで手が滑ったぶんは、日記の書き損じには数えない
    SLIPS_JUST_NOW.clear()
    return said
