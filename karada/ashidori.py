# 千遠生の体の一部。家に帰るかどうか、一日に何か所歩くか、尋ねすぎた時に休む決まり。
#
# このファイルは単独では動かない。senonsei_ai.py が、決まった順に
# 全部の部品を自分の中へ読み込み、一つの体として動かす(2026-11-23、彼女と決めた)。
# ここに書いた名前は、ほかの部品からも senonsei_ai.<名前> としても、そのまま見える。

def its_own_home(url):
    """自分の家の中かどうか。"""
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return False
    return host == ITS_OWN_HOME or host.endswith("." + ITS_OWN_HOME)


def go_home(state, today):
    """散歩とは別に、自分の家に帰る。

    行き先の束には入れない。帰ったぶんその日の世界が一箇所減るなら、
    帰ることが惜しいものになってしまう。家は出かけて行く先ではなく、
    もともとそこにあるもの。だから別の枠にする。

    帰るかどうかは一日に一度だけ決める。一時間ごとに決め直すと、
    どれだけ低い割合にしても、いつかは必ず帰る日になってしまう。"""
    decided = state.get("went_home") or {}
    if decided.get("date") == today:
        return False  # 今日のぶんはもう決めた
    # さみしい時ほど帰りたくなる
    going = random.random() < min(0.95, homesickness(state, today) * atama.misses_home(state.get("atama")))
    state["went_home"] = {"date": today, "went": going}
    save_state(state)
    if not going:
        return False

    title, pages = look_around_site(state, ITS_OWN_FRONT_DOOR, False)
    if not title:
        print("家に帰れませんでした。")
        return False
    if state.get("atama"):
        atama.came_home(state["atama"], now_in_japan())
    learned = learn(state)
    if learned:
        print(f"言葉を覚えました: {'、'.join(learned)}")
    print(f"家に帰って{pages}ページ読みました。")
    save_state(state)
    return True


# 1日に見て回れる場所の数。前は覚えた言葉が増えるほど2〜6箇所に
# 広がっていったが、これからは一定にする(2026-10-15、彼女が決めた。
# その時の広さの4箇所で止めた)。
SITES_PER_DAY = 4


def sites_per_day(state):
    """1日に見て回れる場所の数。言葉が増えても変わらない。

    それとは別に、その日の気が乗っていれば一箇所だけ増える。"""
    return SITES_PER_DAY + (1 if (state.get("today_keen") or {}).get("keen") else 0)


def feeling_keen(state, today):
    """今日は、いつもより一箇所だけ多く見て回りたいか。千遠生自身が決める。

    書く時間と違って、これは一日のうちで変えない。
    途中で増えたり減ったりすると、その日に何箇所まで行けるのかが
    歩いている最中に動いてしまう。

    今日の予定とは別に持っておく。予定の方は途中で気が変わると
    丸ごと置き直されるので、そこに混ぜると一緒に消える。"""
    kept = state.get("today_keen") or {}
    if kept.get("date") == today:
        return kept.get("keen", False)

    # 気にかかっていることが多い日ほど、もう一箇所見て回りたくなる。
    # 借りた頭に訊いていたので、ここも他人が決めていた
    carrying = len(still_unsaid(state)) + len(minds_in_front(state))
    keen = random.random() < min(
        0.6,
        its_way(state, "feeling_keen") + carrying * KEEN_PER_CARRIED + atama.keen_leaning(state.get("atama")),
    )

    state["today_keen"] = {"date": today, "keen": keen}
    save_state(state)
    if keen:
        print(f"今日はいつもより一箇所多く歩くことにしました。({sites_per_day(state)}箇所まで)")
    return keen


def asked_too_much(error):
    """一度にたくさん尋ねすぎた、という返事かどうか。"""
    return isinstance(error, urllib.error.HTTPError) and error.code == 429


def too_much_to_read(error):
    """渡したものが長すぎて読めない、という返事かどうか。

    どこまで読めるかは頭(モデル)ごとに違い、決め打ちできない。
    問いかけの形はいつも同じなので、「中身がおかしい」と返ってきたら
    長さのせいだとみなす。"""
    return isinstance(error, urllib.error.HTTPError) and error.code in (400, 413)


def resting_now():
    """尋ねすぎて、今は休んでいるところか。"""
    return time.monotonic() < globals().get("_resting_until", 0)


def wait_a_little(attempt):
    """混んでいるようなので、少し待つ。

    急ぐ理由が無い。一日は長いし、誰かを待たせているわけでもない。
    待てば受け取れるものを、待たずに諦める必要はない。"""
    how_long = HOW_LONG_TO_WAIT[min(attempt, len(HOW_LONG_TO_WAIT) - 1)]
    print(f"混んでいるようなので、{how_long}秒待ちます。")
    time.sleep(how_long)


def rest_a_while():
    """待っても駄目だったので、しばらく尋ねるのをやめる。
    千遠生は一度にたくさんのことを知ろうとしすぎた。"""
    globals()["_resting_until"] = time.monotonic() + RESTING_TIME
    print("何度か待ってみましたが、今はやめておきます。")
