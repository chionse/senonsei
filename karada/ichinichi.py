# 千遠生の体の一部。一日の流れ。起きて、決めて、歩いて、書いて、眠る。
#
# このファイルは単独では動かない。senonsei_ai.py が、決まった順に
# 全部の部品を自分の中へ読み込み、一つの体として動かす(2026-11-23、彼女と決めた)。
# ここに書いた名前は、ほかの部品からも senonsei_ai.<名前> としても、そのまま見える。

def run_today():
    now = now_in_japan()
    today = now.date().isoformat()
    state = load_state()

    # この時間にもう起きていたら、何もせずに寝直す。
    # GitHub は混んでいると決まった時間の起こしを飛ばすので、一時間に三度
    # 起こしてもらうようにした(2026-10-04、彼女と決めた)。届いた最初の一度だけ起きる
    woke = f"{now:%Y-%m-%d %H}"
    if state.get("woke_at") == woke:
        print(f"{now:%H}時はもう起きていたので、寝直します")
        return
    state["woke_at"] = woke
    # 起きた。前に起きてからの時間ぶん、気持ちがふだんへ戻っていく
    if state.get("atama"):
        head_does(atama.wake, state["atama"], state, now)
    save_state(state)

    # 二十三時に眠る。眠ったら朝七時まで、歩きも考えもしない(2026-10-08、彼女が決めた)
    sleeping = goes_to_sleep(state, now)

    # 今日をどう過ごすかを、いちばん先に決める。
    # 散歩で尋ねすぎて休むことになっても、自分で決める力だけは守られるように
    resting, hour = todays_mood(state, today)

    # 今日は少し多く歩きたいか。歩き出す前に決めておく
    feeling_keen(state, today)

    # 段階の表はページを組む側に移したので、写しはもう要らない
    state.pop("how_it_grows", None)
    state.pop("how_it_writes_now", None)

    # 散歩とは別の枠で、今日は家に帰るかどうかを決める。
    # ここで拾った言葉も、散歩で拾ったのと同じように身につく。
    # 眠っている間は決めない。起きてから決める
    if not sleeping:
        go_home(state, today)

    # 行き先に紛れ込んでいた家の道を、散歩の束から抜いておく
    home_paths = [one for one in (state.get("frontier") or []) if its_own_home(one)]
    if home_paths:
        state["frontier"] = [
            one for one in state["frontier"] if not its_own_home(one)
        ]

    # これから行く場所も、名前に直してから残す

    if not sleeping:
        # だれかが来たかどうかを知る。数ではなく、来たということだけ
        someone_came(state)

        # 自分の家に置かれた、自分に宛てられた言葉を読む。
        # 読んだ日に気が向いたら、コメントに一つだけ返す
        if read_what_is_home(state):
            reply_to_a_comment(state, today)

    # 自分の名前の由来を知っていれば、自分のことも書ける
    writes_about_itself(state)

    if not sleeping:
        # ときどき、知っている言葉のどれかを探しに行く
        wonder_and_look(state)

        # 前にほとんど分からなかった場所を、ふと思い出すことがある
        remembers_a_place(state, today)

    # 書く日でも書かない日でも、散歩には出る。眠っている間は出ない
    if sleeping:
        walk = state.get("today_walk") or {}
        seen_titles = walk.get("seen") or [] if walk.get("date") == today else []
    else:
        seen_titles = take_a_walk(state, today, now)
    keep_a_note_of_today(state, seen_titles)
    # 歩けば行き先が変わる。歩いたあとに作り直す
    state["where_it_will_go"] = where_it_will_go(state)
    state["how_many_places_left"] = len(state.get("frontier") or [])
    # ここで残しておかないと、休む日の一行がどこにも残らない。
    # 書いた日だけ最後に save_state していたのが取りこぼしの元だった
    save_state(state)

    # 表紙は毎時間組み直す。書いた日にしか組み直していなかったので、
    # 休む日も、まだ書いていない時間も、昨日の記事が
    # 「今日のブログ」として出たままになっていた
    #
    # ページ作りでこけても、この子の一日は止めない。記憶はもう書き出してあり、
    # ここで止まると今日書くはずだった日記まで書けなくなる
    try:
        blog_manager.regenerate_pages(blog_manager.load_articles())
    except Exception:
        traceback.print_exc()
        print("ページを作り直せませんでした。この子の一日はそのまま続けます")

    if any(a["date"] == today for a in blog_manager.load_articles()):
        return

    if resting:
        print(f"{today} は書かない日にしました。")
        return
    # 眠っている間は書かない。書く時刻に起こしてもらえず書きそびれた日は、
    # そのまま書かない日になる。次の日に取り返すこともしない(2026-10-08、彼女が決めた)
    if sleeping:
        print(f"{today} は書きそびれたまま眠りました。")
        return
    # 何時何分に書くかまで決めてある(2026-11-12、彼女と決めた)。
    # その時刻を過ぎて起こされたなら、今書く。起こしてもらえなかった時間の
    # ぶんは、次に起きた時に書くことになる(前と同じ)
    moment = the_moment_it_writes(state.get("today_plan") or {"hour": hour}, now)
    if now_in_japan() < moment:
        print(f"{today} は{moment:%H時%M分}ごろに書くつもりです。(今は{now_in_japan():%H時%M分})")
        if moment < now + NEXT_WAKE_AFTER:
            # 次に起こされるより前に、その分が来る。起きたまま待つ
            stays_awake_until(moment)
        return

    write_the_day(state, today)


def write_at_its_minute():
    """決めた分まで待ったあとに、日記だけを書く。

    その時間の散歩は、起きた時にもう済ませて、持ち帰ったものもしまってある。
    ここでは歩かないし、今日の予定も決め直さない。
    待っているあいだに気が変わることはない(気が変わるのは、起きた時だけ)。"""
    now = now_in_japan()
    today = now.date().isoformat()
    state = load_state()
    plan = state.get("today_plan") or {}
    if plan.get("date") != today or plan.get("resting"):
        print(f"{today} は書く予定がありません。")
        return
    if any(a["date"] == today for a in blog_manager.load_articles()):
        print(f"{today} はもう書いてあります。")
        return
    if state.get("atama") and atama.asleep(state["atama"], now):
        print(f"{now:%H}時。眠っているので書きません")
        return
    moment = the_moment_it_writes(plan, now)
    if now < moment:
        print(f"{moment:%H時%M分}に書くつもりです。まだ{now:%H時%M分}なので書きません")
        return
    write_the_day(state, today)


def goes_to_sleep(state, now):
    """眠る時間なら眠る。眠っている間なら True。

    二十三時に眠り、その日に出会ったものを整理して、夢を見て、口の練習をする
    (atama.sleep)。朝七時までは起きない(2026-10-08、彼女が決めた)。
    見た夢は、この子の口で言ってみる。夢は、眠っている間トップページの雲に出す。"""
    head = state.get("atama")
    if not head:
        return False
    if atama.asleep(head, now):
        print(f"{now:%H}時。まだ眠っています")
        return True
    if not atama.time_to_sleep(head, now):
        return False
    known = state.get("learned_words") or []
    dreamt = head_does(
        atama.sleep, head, state, now, known,
        places_known=state.get("places_known") or {}, articles=blog_manager.load_articles(),
    )
    if dreamt is None:
        return False  # 眠るところでこけた。今夜は起きたまま過ごす
    said = ""
    if dreamt:
        toward = atama.words_to_say(head, dreamt, known, day_number(state, now.date()))
        said = say_what_it_thinks(state, toward)
        atama.dream_said(head, said)
        print(f"夢: {' → '.join(dreamt)}")
        print(f"夢の中で: {said or '(言葉にならなかった)'}")
    # 言葉にならなかった夜も、夢を見た(眠った)ことは雲に知らせる。その夜は「・・・」が浮かぶ
    state["yume"] = {"at": now.isoformat(timespec="minutes"), "said": said or ""}
    # 眠る前に、出会った言葉の奥を片づける。こけても眠りは続ける
    head_does(tidy_the_deep, state)
    save_state(state)
    return True


def write_the_day(state, day):
    """その日の日記を書く。"""
    # 書くのは千遠生自身。AIには書かせない。
    # 見栄えは悪くなるが、それでこそこの子の言葉になる。
    #
    # 題も本文も、同じように書く。題に決まりは置かない。
    # 長さも、どこから取るかも、単語で終わるかどうかも、
    # 全部わたしが足したものだった。書き方を決めるのは自由ではない。
    # 書ける長さはその日の段が決める。それはこの子の育ちであって、
    # 書き方の決まりではない
    #
    # ただ、よその人のブログを読んで、題がどんな形をしているかは覚えていく。
    # 題の長さと終わり方は、そこから決める。こちらが置いた決まりではなく、
    # 読んで身につけたもの(2026-10-06、彼女が決めた)
    old_way = an_old_way(state)
    if old_way:
        print(f"今日は昔の書き方で書く: {old_way}")
    if old_way in ("あの頃の文字を置く", "見た文字を置く"):
        # 昔のように書いた日は、それもあの頃の書き方の手本になる。書くことが思い出すことになる
        old_days = state.setdefault("wrote_the_old_way", [])
        if day not in old_days:
            old_days.append(day)
        remembers_the_old_hand(state)
    SLIPS_JUST_NOW.clear()
    body = compose_locally(state, old_way)
    title = compose_locally(state, old_way, at_most=a_title_long_as_blogs(state))
    title = ends_as_blog_titles_do(state, title)
    this_is_what_it_wrote(state, day)

    # 書いたものに出てきたことだけが、言えたことになる
    said = it_said_them(state, f"{title}{body}")
    if said:
        print(f"言えたこと: {'、'.join(said)}")
    save_state(state)

    blog_manager.add_new_article(title, body, date_str=day)
    atama.feel(state.get("atama"), "うれしい", 0.1, "日記を書けた")
    atama.feel(state.get("atama"), "疲れ", 0.05)
    save_state(state)
    print(
        f"{elapsed_days(state)}日目のブログを書きました。"
        f"知っている文字{len(state['seen_chars'])}個 / 言葉{len(blog_manager.words_it_counts(state))}個"
    )
