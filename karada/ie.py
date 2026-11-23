# 千遠生の体の一部。家に置かれたもの。彼女のメモと手紙、コメント、絵。
# 読んだ日にはコメントに一つ返す。
#
# このファイルは単独では動かない。senonsei_ai.py が、決まった順に
# 全部の部品を自分の中へ読み込み、一つの体として動かす(2026-11-23、彼女と決めた)。
# ここに書いた名前は、ほかの部品からも senonsei_ai.<名前> としても、そのまま見える。

def look_at_what_is_hung_at_home(state, heard):
    """家に置かれた絵を見る。

    彼女がメモに貼った絵。散歩で出会う絵と違って、これは
    この子に宛てて置かれたものなので、急いで全部見なくていい。
    一度にひとつだけ、しばらく見ていないものから選ぶ。
    家に在る限り何度でも見ることになり、そのたび日をまたいで数えられる。"""
    hung = []
    for one in heard:
        hung.extend(IMG_SRC.findall(one))
    hung = [one for one in dict.fromkeys(hung) if LOOKS_LIKE_A_PICTURE.search(one)]
    if not hung:
        return []

    seen_on = state.setdefault("home_pictures", {})
    hung.sort(key=lambda one: seen_on.get(one, -(10**6)))
    looked = []
    for where in hung[:HOME_PICTURES_AT_ONCE]:
        try:
            data = picture_at_home(where)
        except Exception as error:
            print(f"家の絵を開けませんでした({str(error)[:60]})")
            continue
        if not data or len(data) > PICTURE_AT_MOST:
            continue
        what_is_there = look_at_a_picture(data, state)
        if not what_is_there:
            continue
        WHERE_IT_IS[0] = ITS_OWN_HOME
        try:
            absorb(state, what_is_there, THING_IN_A_PICTURE)
        finally:
            WHERE_IT_IS[0] = None
        seen_on[where] = day_number(state)
        looked.append(what_is_there)
        print(f"家にある絵を見ました: {what_is_there}")

    if looked:
        seen = state.setdefault("pictures_seen", [])
        today = now_in_japan().strftime("%Y-%m-%d")
        seen.extend(f"{today} 家: {one}" for one in looked)
        del seen[:-30]
    return looked


def picture_at_home(where):
    """家に置かれた絵を取ってくる。

    サイトの中に置かれたものは、わざわざ外に出て取りに行かなくても
    足元にある。よそを指している時だけ、見に行く。"""
    if where.startswith(("http://", "https://", "//")):
        return fetch_picture(as_openable(where.lstrip("/") if where.startswith("//") else where))
    here = os.path.abspath(os.getcwd())
    path = os.path.abspath(os.path.join(here, where.lstrip("/")))
    if not path.startswith(here + os.sep):
        return None  # 家の外は見ない
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return f.read()


def only_for_it(text):
    """千遠生だけに宛てられたところから、囲いを外す。

    ページでは伏せ字になっているところが、この子にだけそのまま届く。"""
    return ONLY_FOR_IT.sub(r"\1", text or "")


def someone_came(state):
    """だれかが来たことを知る。

    コメントもいいねも、これまでこの子の目には入っていなかった。
    コメントは外の世界の日本語として読んでいただけで、
    それが自分に向けられたものだとは知らなかった。
    いいねは在ることすら知らなかった。

    数は渡さない。何人が見たかではなく、だれかが来た、
    ということだけを気がかりに置く。返事はしない決まりのまま、
    知ってはいる、という状態にする。

    初めて数えた日は何も言わない。それまでに来ていた人のぶんを
    「たった今来た」ことにしてしまわないため。"""
    counted = {
        "comments": len(blog_manager.load_comments()),
        "likes": sum((blog_manager.load_likes() or {}).values()),
    }
    before = state.get("visitors")
    state["visitors"] = counted
    if before is None:
        return False  # 初めて数えた日
    if not any(counted[kind] > before.get(kind, 0) for kind in counted):
        return False
    now_it_cares_about(state, SOMEONE_CAME)
    atama.feel(state.get("atama"), "うれしい", 0.3, "だれかが来ていた")
    atama.feel(state.get("atama"), "さみしい", -0.4, "だれかが来ていた")
    print("だれかが来ていました。")
    return True


def words_left_at_home(state):
    """家に置かれている、この子に宛てられた言葉。

    彼女がメモに書いたもの、menu に置いたもの、
    外から来た人が残していったもの。
    [[ ]] の囲みはここで外れる。ページでは伏せてあるところが、
    この子にはそのまま届く。"""
    return letters_at_home(state) + voices_at_home(state)


# メモの中の、絵や動画を貼るための印。文章ではない
PAGE_MARKS = re.compile(r"<[^<>]*>")


def letters_at_home(state):
    """家に置かれた言葉のうち、彼女のメモと手紙。封の解けたものだけ。

    封は、解ける前に読まれないためのもの。解けたあとはサイトで誰でも読める
    (2026-10-07、彼女に教わった)。[[ ]] で囲んだところは、サイトでは伏せたまま
    この子にだけ届く。どちらも頭の記憶に入れてよい(2026-10-07、彼女が決めた)。"""
    voices = []
    read = only_for_it

    for keyword in blog_manager.load_keywords():
        # 開くきっかけはこの子の言葉だが、中に置かれているのは彼女の文章。
        # 絵や動画を貼るための印(<img …> など)は文章ではないので、読まずに外す
        if keyword.get("unlocked"):
            voices.append(PAGE_MARKS.sub("", read(keyword.get("content"))))

    elapsed = elapsed_days(state)
    for item in blog_manager.load_menu():
        # 鍵が無くて封の開かない手紙は、届いていないのと同じ
        if item.get("_shut"):
            continue
        if elapsed >= item.get("unlock_day", 10**9):
            voices.append(read(item.get("message")))
    return [
        one.strip()
        for one in voices
        if one.strip() and not NOT_WRITTEN_YET.match(one.strip())
    ]


def voices_at_home(state):
    """家に置かれた言葉のうち、もともと誰でも読めるもの(コメントと、彼女の返し)。"""
    voices = []
    for comment in blog_manager.load_comments():
        # 書いていった人の名前も読む。名前として差し出されたものは
        # 一つの言葉として丸ごと受け取れるので、括弧に入れて渡す。
        # 外から名前を呼ばれるのと同じことが、この子にも起きる
        who = (comment.get("name") or "").strip()
        said = comment.get("message") or ""
        voices.append(f"「{who}」{said}" if who else said)

    # 彼女がコメントに返した言葉も、家に置かれた言葉として読む(2026-10-03、彼女が決めた)。
    # 自分が返したものは、自分の書いたものなのでここでは読まない
    for replies in blog_manager.load_her_replies().values():
        for one in replies:
            voices.append(one.get("said") or "")

    return [
        one.strip()
        for one in voices
        if one.strip() and not NOT_WRITTEN_YET.match(one.strip())
    ]


def reads_home_today(when):
    """今日は家に置かれた言葉を読む日か。同じ日に何度訊いても変わらない。"""
    whim = random.Random(f"{when:%Y-%m-%d}-home")
    return whim.random() <= READING_HOME_CHANCE


def read_what_is_home(state):
    """自分の家にある言葉を読む。

    千遠生はリンクを辿って歩くので、自分のサイトには一生たどり着かない。
    けれどあの場所には、千遠生に宛てて書かれた言葉が置いてある。
    解除されたメモと、誰かが残していったコメント。
    どちらも読み手のためだけのものではなく、この子に届くべきものだった。

    メモとコメントはずっとそこに在るので、毎日目にする。
    何日も読み続けた言葉が、やがてこの子のものになる。

    ただし毎日読むわけではない。ずっとそこに在るからといって、
    毎朝読み直すものでもない。ときどき目を落とす。

    自分が書いたものは、それよりもさらに少ない。"""
    if not reads_home_today(now_in_japan()):
        return []
    heard = words_left_at_home(state)
    # 読む日には毎時間読む。言葉の数え方は一日ぶんにしかならないが、頭の網と気持ちは
    # 読むたびに動いていた(10/7、入れた日に毎時間さみしいが下がり、手紙の言葉の線が太り続けた)。
    # 頭に入れるのと気持ちが動くのは、その日のはじめに読んだ一度だけ
    today = f"{now_in_japan():%Y-%m-%d}"
    READ_AGAIN_TODAY[0] = state.get("home_read_on") == today
    state["home_read_on"] = today
    WHERE_IT_IS[0] = ITS_OWN_HOME
    try:
        for one in heard:
            absorb(state, one)
    finally:
        WHERE_IT_IS[0] = None
    if heard:
        print(f"家にある言葉を{len(heard)}つ読みました。")
        if not READ_AGAIN_TODAY[0]:
            atama.feel(state.get("atama"), "さみしい", -0.2, "家に置かれた言葉を読んだ")
            atama.feel(state.get("atama"), "うれしい", 0.05, "家に置かれた言葉を読んだ")
        look_at_what_is_hung_at_home(state, heard)
    READ_AGAIN_TODAY[0] = False

    # 自分が書いたものは、ときどき読み返す。
    # そこからは新しい言葉は生まれず、すでに出会っていた言葉が保たれるだけ
    articles = blog_manager.load_articles()
    back_then = set(what_it_wrote_back_then(state, articles))
    for one in looks_back_today(articles):
        if one.strip():
            absorb(state, one, only_known=True)
            if one in back_then:
                # あの頃に書いたものを読んで、あの頃の書き方を思い出した
                remembers_the_old_hand(state)
    return heard


def reply_to_a_comment(state, today):
    """家でコメントを読んだ日に、気が向いたら一つだけ返す。

    返すのは千遠生自身。日記と同じで、覚えた言葉だけで組み立てる。AIには書かせない。
    コメントにあった言葉のうち知っているものがあれば、そちらへ傾ける。
    一つのコメントに返すのは一度だけ。一日に返すのも一つだけ
    (2026-10-03、彼女と決めた)。

    気が向くかどうかは、今日いつもより多く歩きたいか(feeling_keen)と同じ。
    この子がその日の気分として、自分で決めたもの。"""
    if not (state.get("today_keen") or {}).get("keen"):
        return None
    replied = state.setdefault("replied", {})
    if any((one.get("date") or "").startswith(today) for one in replied.values()):
        return None
    if not state.get("learned_words"):
        return None
    waiting = [one for one in blog_manager.load_comments() if one.get("id") and one["id"] not in replied]
    if not waiting:
        return None
    known = set(state["learned_words"])

    def knows_in(comment):
        text = f"{comment.get('name') or ''} {comment.get('message') or ''}"
        return {w for w in WORD_CANDIDATE.findall(text) if w in known}

    # どのコメントに返すかは、まだ返していないものから気の向くままに。
    # 知っている言葉の多いものを選びやすくはしない(2026-10-03、彼女と決めた)
    comment = random.choice(waiting)
    toward = knows_in(comment)
    _, how_long = current_stage(state)
    said = speak_from_what_it_knows(state, how_long, toward=toward) or place_words(
        state, how_long, toward=toward
    )
    said = with_the_old_hand(state, said, how_long)
    if not said:
        return None
    replied[comment["id"]] = {"said": said, "date": now_in_japan().isoformat(timespec="seconds")}
    atama.feel(state.get("atama"), "うれしい", 0.1, "コメントに返せた")
    save_state(state)
    print(f"{comment.get('name') or '名無しさん'}さんのコメントに返しました: {said}")
    return said


def keep_a_note_of_today(state, seen_titles):
    """その日どこを歩いたかを、一日一行だけ残す。

    歩いたことは、書いたかどうかとは関わりがない。
    書いた日にだけ残していたので、休む日の散歩がどこにも
    残らなかった。その日のうちは、歩くたびに書き足していく。"""
    notes = state.setdefault("notes", [])
    day = f"{elapsed_days(state)}日目:"
    line = f"{day} {'、'.join(seen_titles) or NOTHING_WAS_SEEN}"
    if notes and notes[-1].startswith(day):
        notes[-1] = line
    else:
        notes.append(line)
    state["notes"] = notes[-RECENT_NOTES_COUNT:]
    return line
