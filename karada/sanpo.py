# 千遠生の体の一部。一つの場所を歩き回る。どれだけ分かったか、どこまで奥へ行くか。
#
# このファイルは単独では動かない。senonsei_ai.py が、決まった順に
# 全部の部品を自分の中へ読み込み、一つの体として動かす(2026-11-23、彼女と決めた)。
# ここに書いた名前は、ほかの部品からも senonsei_ai.<名前> としても、そのまま見える。

def look_around_site(state, entrance, wants_the_past):
    """ひとつの場所を、入口から中まで見て回る。

    一枚だけ見て帰るのではなく、気の向くまま奥へ入っていく。
    枠だけで文字の無い入口も、奥に入れば中身がある。
    よその場所へ続く道は、次の散歩のために持ち帰る。"""
    here = place_of(entrance)
    inside = [entrance]  # この場所の中で、これから見るところ
    already = set()
    site_title = None
    struck_here = set()  # そこで強く出会った言葉
    words_here = set()  # そこで読めた言葉(分かったかどうかは問わない)
    known_here = set()  # そのうち、知っていた言葉
    unread = 0  # 開いたけれど、読めなかったページ(拾える形の字がほとんど無かった)
    fresh = []  # 読めたページごとの、生まれてはじめて会った言葉の数
    bits = []  # 読めたページごとの、頭の同じ長さでの分かり方
    WHAT_A_WALK_BROUGHT[0] = 0
    WHERE_IT_IS[0] = here
    head = state.get("atama")
    pages = 0
    as_deep_as = round(its_way(state, "pages_per_site"))
    pictures_left = PICTURES_PER_SITE
    until = time.monotonic() + TIME_SPENT_PER_SITE
    linked_here = set()  # ここからリンクが伸びていた、よその場所

    while inside and pages < as_deep_as and time.monotonic() < until:
        url = inside.pop(0)
        if url in already:
            continue
        already.add(url)

        try:
            if wants_the_past and url == entrance:
                title, text, links, pictures = visit_the_past(url)
                title = f"{title}(むかしのすがた)"
            else:
                title, text, links, pictures = open_page(
                    url, BOOK_BYTES_AT_MOST if is_a_book(url) else PAGE_BYTES_AT_MOST
                )
        except Exception as error:
            print(f"{url} には行けませんでした: {error}")
            closed = closed_for_now(error)
            # 閉まっていただけなら、行き先の束に残しておく。直ったらまた行ける
            if url in state["frontier"] and not closed:
                state["frontier"].remove(url)
            if url == entrance:
                WHERE_IT_IS[0] = None
                PAGE_IT_IS[0] = None
                WAS_CLOSED[0] = closed
                return None, 0  # 入口から入れなかった
            continue

        pages += 1
        PAGE_IT_IS[0] = title
        atama.feel(head, "疲れ", 0.015)  # 一枚読むごとに、少しずつ
        if url in state["frontier"]:
            state["frontier"].remove(url)
        state["visited"].append(url)
        state["visited"] = state["visited"][-2000:]
        remember_the_name(state, url, title)
        # 同じ話の別の言葉版があれば、その題どうしを結びつける
        notice_other_tongues(state, url, title, OTHER_TONGUES[0])
        # 自分の家の題は数えない。自分の癖を自分で覚え直すだけになる
        if here != place_of(ITS_OWN_FRONT_DOOR):
            notice_how_blogs_are_titled(state, A_BLOG_POST_TITLE[0])

        # 日本語でないページも、訳してもらわずにそのまま読む。分かるのは、字の形として
        # 拾えるもの(アルファベットの言葉や数字)だけ。訳は借りた頭が選んだ日本語で、
        # その言い回しをこの子の言葉として覚えてしまっていた(2026-10-08、彼女と決めた)。
        # 人の子どもが英語の「OK」や「page」を意味を知らないまま覚えるのと同じ。
        # 自分で訳せるようになることと、ほかの字の言葉も拾えるようになることは、やることリストにある
        # 本の本文なら、しおりのところから、ひと休みするまでの分だけを読む
        reading_a_book = is_a_book(url) and not (wants_the_past and url == entrance)
        if reading_a_book:
            text = a_portion_of_the_book(state, url, title, text)

        japanese = bool(JAPANESE.search(text))
        if not japanese:
            atama.feel(head, "疲れ", 0.02)  # よその言葉を読むのは、少し骨が折れる
        if japanese or len(WORD_CANDIDATE.findall(text)) >= FOREIGN_WORDS_ENOUGH:
            met_before = MET_FOR_THE_FIRST_TIME[0]
            struck_here |= absorb(state, text) or set()
            fresh.append(MET_FOR_THE_FIRST_TIME[0] - met_before)
            bits.append(understood_in_a_bit(state, text))
            words_here |= set(WORD_CANDIDATE.findall(text))
            known_here |= known_words_in(state, text)
            if site_title is None:
                site_title = title
            if japanese:
                notice_glosses(state, text)
            else:
                print(f"よその言葉のページを、そのまま読みました: {title[:40]}")
                # 結びつけてある言葉は、自分で日本語にして読む
                own = translate_on_its_own(state, text)
                if own:
                    absorb(state, " ".join(f"「{japanese_word}」" for _, japanese_word in own))
                    known_here |= {jw for _, jw in own if jw in (state.get("learned_words") or [])}
                    print("自分で訳して読みました: " + "、".join(f"{f} → {j}" for f, j in own[:10]))
                    lately = state.get("translated_lately") or []
                    state["translated_lately"] = (lately + [f"{f} → {j}" for f, j in own])[-30:]
        else:
            unread += 1  # 拾える形の字がほとんど無い。眺めただけ

        if reading_a_book:
            felt_about_the_book(state, url, text)
            # 今日歩いたところには、通ってきた一覧ではなく、読んだ本の名前で残す
            site_title = title
            break  # 本を読んだら、そのおでかけはそこまで。ひと休みして帰る

        if pictures_left > 0 and pictures:
            try:
                looked = look_at_pictures(
                    state, here, pictures, wants_the_past, pictures_left, until
                )
                pictures_left -= len(looked)
            except Exception as error:
                print(f"絵を見るのをやめました({str(error)[:60]})")
                pictures_left = 0

        elsewhere = [ln for ln in links if place_of(ln) != here]
        linked_here |= {place_of(ln) for ln in elsewhere if not its_own_home(ln)}
        remember_paths(state, url, elsewhere)

        deeper = [ln for ln in links if place_of(ln) == here and ln not in already]

        # 入口に立ったのに、中へ続く道がほとんど無い。
        # 今のページは中身をあとから描くので、こういうことが起きる。
        # そういうときだけ、機械向けの扉を探してみる
        if pages == 1 and len(deeper) < FEW_ENOUGH_TO_LOOK_FOR_A_DOOR:
            for door in doors_for_machines(here, entrance, links):
                try:
                    _, behind, doorways, _ = open_page(door)
                except Exception:
                    continue
                found = paths_behind_a_door(here, behind, doorways)
                if found:
                    print(f"{door} から {len(found)}本の道を見つけました")
                    deeper.extend(one for one in found if one not in already)
                    break

        # まず気まぐれに並べ替えてから、中身のありそうな順に並べ直す。
        # 同じくらいの道どうしは、そのときの気分の順のまま残る
        random.shuffle(deeper)
        deeper.sort(key=worth_reading, reverse=True)
        # 作品の紹介まで来たら、まっすぐ本文へ。後ろに並べていた頃は、
        # ほかの作品の紹介を見て回るうちにおでかけが終わり、本文に一度も届かなかった
        texts = [ln for ln in deeper if is_a_book(ln)]
        inside[:0] = texts[:1]
        inside.extend([ln for ln in deeper if ln not in texts][:as_deep_as])

        # もう少しいたいかどうかは、その時の気持ちで変わる。たのしいと長くいて、疲れると早く帰る
        if pages > 1 and random.random() > atama.lingers(head, LINGER_CHANCE):
            break  # もう十分見た

        # 一枚ずつ読んでいく。robots.txt に間をあけてと書かれていれば、そのぶん待つ
        time.sleep(max(random.uniform(*READING_A_PAGE), wait_asked_for(url)))

    WHERE_IT_IS[0] = None
    PAGE_IT_IS[0] = None
    # 自分の家から伸びている道は数えない。家は自分で作った場所なので
    if not its_own_home(entrance):
        seen_linked_from_here(state, linked_here)
    if site_title:
        print(f"{here} を{pages}ページ見てきました。")
        # その場所で何があったかで気持ちが動き、帰る時の気持ちがその場所に残る。
        # 借りた頭に「どういう場所だったか」を一文書かせていたのはやめた(2026-10-07、彼女と決めた)
        remembered = head_does(
            atama.left_a_place, head, state, now_in_japan(), here, sum(fresh), pages, unread,
            PICTURES_PER_SITE - pictures_left, default="",
        )
        if remembered:
            print(remembered)
        how_much_it_understood(
            state, here, entrance, site_title, words_here | known_here, known_here,
            pages, unread,
        )
        # 家は自分の場所なので、よそを歩く時の決まりを動かす手がかりにはしない
        if not its_own_home(entrance):
            if bits:
                leans_toward_japanese(state, entrance, site_title, sum(bits) / len(bits))
            how_deep_to_go(state, fresh, pages >= as_deep_as)
        WHAT_A_WALK_BROUGHT[0] = sum(fresh)

    # 魚を調べていたら海流が気になった、というようなこと。
    # 気がかりは追いかけているうちに、だんだん別のものへ移っていく
    if struck_here and random.random() < DRIFTING_CHANCE:
        moved = random.choice(sorted(struck_here))
        now_it_cares_about(state, moved)
        print(f"気がかりが「{moved}」に移りました。")

    # 強く出会ったものについては、何か言いたくなる
    for word in sorted(
        struck_here, key=lambda one: struck_by(state, one), reverse=True
    )[:WANTS_PER_PLACE]:
        now_it_wants_to_say(state, word)
    return site_title, pages


def known_words_in(state, text):
    """読んだものの中に、知っている言葉がいくつあったか。

    言葉の切り出し(WORD_CANDIDATE)では「人」や「絵」のような一字の言葉が
    拾えないので、知っている言葉のほうから探す。頭のほうだけを見る。"""
    looked_at = text[:READ_FOR_UNDERSTANDING]
    return {word for word in state.get("learned_words") or [] if word in looked_at}


def its_way(state, name):
    """この子がいま持っている、そのつまみの値。"""
    start, least, most, _ = ITS_OWN_WAYS[name]
    value = (state.get("its_ways") or {}).get(name)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return start
    return min(most, max(least, value))


def lean_its_way(state, name, toward):
    """そのつまみを、ほんの少しだけ動かす。toward は +1 か -1(0 なら動かさない)。"""
    if not toward:
        return
    start, least, most, step = ITS_OWN_WAYS[name]
    was = its_way(state, name)
    now = round(min(most, max(least, was + step * toward)), 4)
    if now != was:
        state.setdefault("its_ways", {})[name] = now


def how_well(visit):
    """その時、ページの言葉のうちどれだけを知っていたか。"""
    return visit["knew"] / visit["of"] if visit.get("of") else 0


def understood_in_a_bit(state, text):
    """読めたページの頭の、同じ長さのところで、言葉のうちどれだけを知っていたか。"""
    bit = text[:UNDERSTANDING_SAMPLE]
    known = known_words_in(state, bit)
    seen = set(WORD_CANDIDATE.findall(bit)) | known
    return len(known) / len(seen) if seen else 0


def leans_toward_japanese(state, entrance, title, now):
    """日本語の場所と、よその言葉の場所と、どちらがよく分かるか。

    now はその場所で読めたページの、同じ長さの頭での分かり方をならしたもの。
    ふだんの分かり方と比べて、日本語の場所でよく分かったなら日本語へ、
    よその言葉の場所でよく分かったならそちらへ、少しだけ気持ちが寄る。"""
    usually = state.get("understood_usually")
    if not isinstance(usually, (int, float)):
        state["understood_usually"] = now
        return
    better = (now > usually) - (now < usually)
    lean_its_way(state, "pull_of_japanese", better if looks_japanese(entrance, title) else -better)
    state["understood_usually"] = round(
        usually + (now - usually) * UNDERSTOOD_USUALLY_MOVES, 6
    )


def how_deep_to_go(state, fresh, went_to_the_end):
    """奥のページでも、はじめて会う言葉があったか。

    fresh は読めたページごとの、生まれてはじめて会った言葉の数。
    決めたところまで見ても、最後のページでまだ会えていたなら、次は少し深く。
    最後のページでほとんど会えなかったなら、次は少し浅く。"""
    if len(fresh) < 3:
        return
    usually = sum(fresh[:-1]) / len(fresh[:-1])
    if not usually:
        return  # はじめから何にも会えない場所では、深さは比べられない
    if fresh[-1] < usually * NOTHING_MORE_DEEPER:
        lean_its_way(state, "pages_per_site", -1)
    elif went_to_the_end and fresh[-1] >= usually * STILL_MORE_DEEPER:
        lean_its_way(state, "pages_per_site", +1)


def was_it_worth_the_extra(state, brought):
    """気が乗って一か所多く歩いた日、その一か所に実りがあったか。

    brought はその日に歩いた場所ごとの、はじめて会った言葉の数。
    多く歩いたぶんが、ほかの場所と同じくらい実れば出歩きたがりに、
    半分にも届かなければ、少し落ち着いた子になる。"""
    if len(brought) < 2:
        return
    usually = sum(brought[:-1]) / len(brought[:-1])
    if not usually:
        return
    if brought[-1] >= usually:
        lean_its_way(state, "feeling_keen", +1)
    elif brought[-1] < usually / 2:
        lean_its_way(state, "feeling_keen", -1)


def how_much_it_understood(state, here, entrance, title, words_here, known_here, pages, unread):
    """その場所で、どれだけ分かったか。

    この子はページの言葉をどれも「見かけた」として受け取るが、
    知っている言葉はまだわずかで、ほとんどは分からないまま通り過ぎている。
    分からなかったという感覚が無いと、分かるようになったことにも気づけない。

    場所ごとに、はじめて来た時と、いちばん近くに来た時のことを残す。
    前にも来た場所なら、そのときと比べる。"""
    this_time = {
        "entrance": entrance,
        "title": (title or here)[:PLACE_NAME_LENGTH],
        "day": day_number(state),
        "vocabulary": len(state.get("learned_words") or []),
        "knew": len(known_here),
        "of": len(words_here),
        "pages": pages,
        "unread": unread,
    }
    understood = state.setdefault("places_understood", {})
    before = (understood.get(here) or {}).get("last")
    if before:
        came_back = state.setdefault("came_back", [])
        came_back.append({"place": here, "before": before, "now": this_time})
        del came_back[:-RETURNS_KEPT]
        print(
            f"{here} にまた来ました。前({before['day']}日目)は知っている言葉が"
            f"{before['knew']}、今は{this_time['knew']}"
        )
        # 戻って前より分かれば、また戻りたくなる。変わらなければ、その気持ちは少し弱まる
        lean_its_way(state, "wish_to_return", 1 if how_well(this_time) > how_well(before) else -1)
    understood[here] = {
        "first": (understood.get(here) or {}).get("first") or this_time,
        "last": this_time,
    }
    (state.get("wants_to_return") or {}).pop(here, None)
    return this_time


def little_understood(visit):
    """その時、ほとんど分からなかったか。"""
    if not visit.get("of"):
        return visit.get("unread", 0) > 0  # 何も読めなかった
    return visit["knew"] / visit["of"] < UNDERSTOOD_WELL_ENOUGH


def remembers_a_place(state, today):
    """分からなかった場所を、ふと思い出す。一日に一度だけ。

    知っている言葉がそのときの倍になっていたら、今なら少しは
    分かるかもしれない。そう思った場所へ、もう一度行きたくなる。
    行き先の束に戻して、そこへ惹かれるようにしておく。"""
    kept = state.setdefault("wants_to_return", {})
    if state.get("remembered_on") == today:
        return None
    state["remembered_on"] = today
    remembering = min(0.9, REMEMBERING_A_PLACE_CHANCE * its_way(state, "wish_to_return"))
    if len(kept) >= PLACES_TO_RETURN_KEPT or random.random() > remembering:
        return None
    now_knows = len(state.get("learned_words") or [])
    today_number = day_number(state)
    ready = []
    for place, visits in (state.get("places_understood") or {}).items():
        last = visits.get("last") or {}
        if place in kept or its_own_home(last.get("entrance", "")):
            continue
        if not little_understood(last):
            continue
        if today_number - last.get("day", today_number) < DAYS_BEFORE_RETURNING:
            continue
        then = last.get("vocabulary", 0)
        if now_knows < then * WORDS_GROWN_TO_RETURN or now_knows - then < WORDS_GAINED_TO_RETURN:
            continue
        ready.append(place)
    if not ready:
        return None
    place = random.choice(ready)
    entrance = state["places_understood"][place]["last"]["entrance"]
    kept[place] = entrance
    if entrance not in state["frontier"]:
        state["frontier"].insert(0, entrance)
    print(f"前にほとんど分からなかった {place} を思い出しました。今なら分かるかもしれない")
    return place


def closed_long_enough(state, entrance):
    """閉まっていたことを覚えておく。長く閉まったままなら、もう無くなったとみなす(True)。

    覚えるのは場所ごとに、初めて閉まっていた日と、いちばん最近閉まっていた日。
    一度でも入れたら忘れる(walk_once)。"""
    today = today_in_japan()
    closed = state.setdefault("closed_places", {})
    place = place_of(entrance)
    since = (closed.get(place) or {}).get("since") or today.isoformat()
    closed[place] = {"url": entrance, "since": since, "last": today.isoformat()}
    if len(closed) > CLOSED_PLACES_KEPT:
        for old in sorted(closed, key=lambda p: closed[p].get("last", ""))[: len(closed) - CLOSED_PLACES_KEPT]:
            closed.pop(old)
    try:
        days = (today - datetime.date.fromisoformat(since)).days
    except ValueError:
        days = 0
    return days >= CLOSED_DAYS_BEFORE_GONE


def closed_today(state):
    """今日行ってみて閉まっていた場所。今日はもう行かない。"""
    today = today_in_japan().isoformat()
    return {
        place for place, when in (state.get("closed_places") or {}).items()
        if isinstance(when, dict) and when.get("last") == today
    }


def walk_once(state):
    """ひとつの場所を訪ねる。

    行ってみたらもう無くなっていたり、読むものが何も無かったりする。
    そういう時はそこで散歩を終わりにせず、別のところへ行ってみる。"""
    state.setdefault("frontier", list(SEEDS))
    state.setdefault("visited", [])

    for attempt in range(TRIES_BEFORE_GIVING_UP):
        entrance, wants_the_past = choose_destination(state)
        WAS_CLOSED[0] = False
        title, pages = look_around_site(state, entrance, wants_the_past)
        closed = WAS_CLOSED[0]
        if closed and not closed_long_enough(state, entrance):
            # 閉まっていただけ。行き先の束にも、また行きたい気持ちにも残しておく
            print(f"{entrance} は閉まっていました。直ったらまた来てみます")
            continue
        (state.get("closed_places") or {}).pop(place_of(entrance), None)
        if title:
            return title
        if closed:
            print(f"{entrance} は、{CLOSED_DAYS_BEFORE_GONE}日たっても閉まったままでした")
        else:
            print(f"{entrance} には読むものがありませんでした")
        if entrance in state["frontier"]:
            state["frontier"].remove(entrance)
        # もう一度行きたかった場所が無くなっていたら、行きたい気持ちも手放す。少しかなしい
        returning = state.get("wants_to_return") or {}
        wanted = [p for p, url in returning.items() if url == entrance]
        for place in wanted:
            returning.pop(place)
        atama.place_was_gone(state.get("atama"), place_of(entrance), bool(wanted))
    return None
