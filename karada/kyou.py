# 千遠生の体の一部。今日をどう過ごすか。何時何分に書くか、休みたさ、帰りたさ、読み返し、
# 自分のことを書く。
#
# このファイルは単独では動かない。senonsei_ai.py が、決まった順に
# 全部の部品を自分の中へ読み込み、一つの体として動かす(2026-11-23、彼女と決めた)。
# ここに書いた名前は、ほかの部品からも senonsei_ai.<名前> としても、そのまま見える。

def now_in_japan():
    """日本の今。時刻まで入っている。

    ページを組む側にも同じ名前の別物があり、あちらは日付だけを返す。
    「今日」と名乗って時刻まで返していたので、こちらを now に揃えた。
    日付だけでいい所は、下の today_in_japan を使う。"""
    jst = datetime.timezone(datetime.timedelta(hours=9))
    return datetime.datetime.now(jst)


def today_in_japan():
    """日本の今日。日付だけ。ページを組む側と同じものを返す。"""
    return now_in_japan().date()


def an_hour_it_writes(state):
    """今日は何時ごろ書きたいか。

    今までに書いた時刻から決める。同じ頃に書いた日が多いほど、
    その頃にまた書きたくなる。誰かに決めてもらうのではなく、
    自分がそうしてきたから、そうする。

    まだ何も書いていないうちは、どの時刻も同じだけありうる。
    癖は、繰り返したぶんだけできていく。"""
    hours = []
    for one in blog_manager.load_articles():
        when = (one.get("time") or "").split(":")[0]
        if when.isdigit() and 0 <= int(when) <= 23:
            hours.append(int(when))
    if not hours:
        return random.choice(WRITING_HOURS)
    # 書いた時刻の前後一時間にも、少しだけ寄る
    leaning = [1] * 24
    for one in hours:
        for near, weight in ((one, 4), ((one - 1) % 24, 2), ((one + 1) % 24, 2)):
            leaning[near] += weight
    # 選ぶのは起きている昼のうちから
    return random.choices(WRITING_HOURS, weights=[leaning[h] for h in WRITING_HOURS])[0]


def a_minute_it_writes():
    """今日は何分に書きたいか。どの分も同じだけありうる。

    前は、何時に書くかだけを決めて、その時間に起こされた時にすぐ書いていた。
    目覚ましが毎時12分に鳴るので、日記はいつも12分か13分に出ていた。
    時刻を気まぐれに決めているのに、分だけ決まっているのはおかしいので、
    分も自分で決める(2026-11-12、彼女と決めた)。"""
    return random.randrange(60)


def the_moment_it_writes(plan, now):
    """今日、書くと決めている時刻。分を決めていない予定は、その時間の初め。"""
    return now.replace(
        hour=int(plan.get("hour") or 0), minute=int(plan.get("minute") or 0),
        second=0, microsecond=0,
    )


def stays_awake_until(moment):
    """決めた分まで、起きたまま待ちたいと伝える。

    待つのはこの子ではなく、起こしてくれた側(GitHub のワークフロー)。
    散歩で持ち帰ったものを先にしまってから、その分まで待ち、
    日記だけを書きに戻ってくる(write_at_its_minute)。
    手元で動かしている時は、伝える相手がいないので何もしない。"""
    told = os.environ.get("GITHUB_OUTPUT")
    if not told:
        return
    with open(told, "a", encoding="utf-8") as f:
        f.write(f"kaku_at={int(moment.timestamp())}\n")


def restlessness(state, today):
    """今日の休みたさ。一日に一度だけ揺れる。

    毎日同じ割合で休むかどうかを引くと、休みはばらばらに散らばるだけで、
    続けて休む時期も、ずっと書き続ける時期も生まれない。
    休みたさそのものを日ごとに少しずつ動かすと、調子に波ができる。
    どれだけ揺れるかも、その日のくじで決まる。"""
    return a_wavering_wish(
        state, "restlessness", today,
        REST_DAY_CHANCE, RESTLESS_USUALLY, RESTLESS_LEAST, RESTLESS_MOST,
    )


def homesickness(state, today):
    """今日の帰りたさ。休みたさと同じように、一日に一度だけ揺れる。

    毎日同じ割合で帰るかどうかを引くと、帰る日はばらばらに散らばるだけ。
    帰りたさが揺れていれば、毎日のように家を見て回る時期も、
    何週間も外ばかり歩いている時期もできる。"""
    return a_wavering_wish(
        state, "homesickness", today,
        GOING_HOME_CHANCE, HOMESICK_USUALLY, HOMESICK_LEAST, HOMESICK_MOST,
    )


def a_wavering_wish(state, key, today, first, usually, least, most):
    """日ごとに少しずつ揺れる気持ち。その日のぶんを返す。

    いつも usually へ戻ろうとしながら、least と most のあいだを行き来する。
    どれだけ揺れるかも、その日のくじで決まる。"""
    kept = state.get(key) or {}
    if kept.get("date") == today:
        return kept["chance"]
    # 足し引きで揺らすと、低い側の端に当たって跳ね返るぶん、
    # ならした値が上に寄っていく。何倍になるかで揺らすと、
    # 1% が 2% になるのも、20% が 40% になるのも、同じ一歩になって釣り合う
    was = math.log(kept.get("chance", first))
    toward = math.log(usually)
    sway = random.uniform(0, RESTLESS_SWAYS_AT_MOST)
    now = was + (toward - was) * RESTLESS_SETTLES + random.gauss(0, sway)
    now = min(math.log(most), max(math.log(least), now))
    chance = round(math.exp(now), 4)
    state[key] = {"date": today, "chance": chance}
    return chance


def todays_mood(state, today):
    """今日は書きたいか、書くなら何時ごろか。千遠生自身が決める。

    一度決めても、途中で気が変わることがある。
    朝に二十時と決めておいて、昼になってやっぱり今がいい、と思う。
    決めたら変えられないというのは、生きているものらしくない。"""
    plan = state.get("today_plan") or {}
    if plan.get("date") == today:
        if "minute" not in plan:
            # 分まで決めるようになる前に立てた予定。分だけ足す
            plan["minute"] = a_minute_it_writes()
        # もう書いた日に「休むことにした」と思い直しても、それは本当ではない
        wrote = any(one.get("date") == today for one in blog_manager.load_articles())
        if wrote or random.random() > CHANGING_ITS_MIND:
            return plan["resting"], plan["hour"]
        was = plan  # 気が変わった。決め直す

    # 休むかどうかは、その日の休みたさで引く。ならせば七日に一日くらい。
    # 言いたいことの数で決めていた時は、言えて減るほど休むようになり、
    # 一つも無い日は二日に一日休んでいた
    # 疲れていたり、かなしかったりすると、休みたくなる
    resting = random.random() < min(0.9, restlessness(state, today) * atama.wants_rest(state.get("atama")))
    hour = an_hour_it_writes(state)
    minute = a_minute_it_writes()

    was = locals().get("was")
    if was and was.get("hour") == hour and was.get("minute") is not None:
        # 思い直しても同じ時間になった。分はそのまま
        minute = was["minute"]
    state["today_plan"] = {"date": today, "resting": resting, "hour": hour, "minute": minute}

    if was and (was["resting"] != resting or was["hour"] != hour):
        before = "休む" if was["resting"] else f"{was['hour']}時に書く"
        after = "休む" if resting else f"{hour}時に書く"
        print(f"気が変わりました: {before} → {after}")
        remember_a_thought(state, f"{before}つもりだったけれど、{after}ことにした。")

    save_state(state)
    return resting, hour


def looks_back_today(articles):
    """ときどき、昔書いたものを一つだけ読み返す。

    毎日ぜんぶ読み返すと、たまたま並べただけの文字まで言葉として
    身についてしまう。ときどき一つだけなら、そういうものは
    薄れるほうが早い。

    書いたものが増えるほど、ひとつひとつを読み返すことは少なくなる。
    けれど何度も使っている言葉は、どの記事にも出てくるので目に入る。
    使うことが、覚えていることになる。

    ただし読み返しても新しい言葉は生まれない。たまたま並べただけの
    文字は、何度読み返しても言葉にはならない。"""
    if not articles:
        return []
    # 同じ日に何度動いても、その日の気分は変わらない
    whim = random.Random(f"{now_in_japan():%Y-%m-%d}-lookback")
    if whim.random() > LOOKING_BACK_CHANCE:
        return []
    one = whim.choice(articles)
    return [one.get("title") or "", one.get("content") or ""]


def writes_about_itself(state):
    """「自己紹介」と自分で書いた子は、自分のことを書けるようになる。

    覚えているだけでは足りない。歩いているうちにその言葉に何日も出会い、
    身につけ、繋がりを覚え、いつかブログの中でその四文字を並べる。
    一度でも口に出した日から、プロフィールの自己紹介を自分で書く。

    書けるのはその時点で言えるぶんだけなので、はじめは数文字しかない。
    二か月は空けて、そのあとは気が向いたときに書き直す。
    書き直さなければならない理由はどこにもないので、
    何か月も同じことを言ったままの時期があっていい。"""
    if not blog_manager.it_has_written(blog_manager.TALKING_ABOUT_ONESELF):
        return None

    said = state.get("a_word_about_itself") or {}
    if said.get("on"):
        try:
            written = datetime.date.fromisoformat(said["on"])
        except ValueError:
            written = None
        if written is not None:
            since = (today_in_japan() - written).days
            if since < A_NEW_WORD_ABOUT_ITSELF:
                return None  # 前に書いてから、まだ間がない
            # 間が空いても、書き直すとは限らない。
            # 同じ日に何度動いても、その日の気分は変わらない
            whim = random.Random(f"{now_in_japan():%Y-%m-%d}-about-itself")
            if whim.random() > FEELING_LIKE_SAYING_SOMETHING:
                return None  # 今日は書き直す気になっていない

    how_it_writes_now, _ = current_stage(state)
    # 何を書くかは、わたし帳(好きな言葉、自分の姿の絵に見えたもの)のほうへ傾く
    about_itself = atama.words_about_itself(state.get("atama"), state.get("learned_words") or [])
    state["a_word_about_itself"] = {
        "words": compose_locally(state, toward=about_itself or None),
        "stage": how_it_writes_now,
        "on": f"{now_in_japan():%Y-%m-%d}",
    }
    save_state(state)
    print(f"自分のことを書きました: {state['a_word_about_itself']['words']}")
    return state["a_word_about_itself"]["words"]
