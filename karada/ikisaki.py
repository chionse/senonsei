# 千遠生の体の一部。行き先を選ぶ。行き先の束を整え、Wikipedia や検索で気になる言葉を調べに行き、
# 珍しいところへ足が向く。
#
# このファイルは単独では動かない。senonsei_ai.py が、決まった順に
# 全部の部品を自分の中へ読み込み、一つの体として動かす(2026-11-23、彼女と決めた)。
# ここに書いた名前は、ほかの部品からも senonsei_ai.<名前> としても、そのまま見える。

def place_of(url):
    """そのURLがどこの場所のものか。

    昔のページは web.archive.org という一つの入れ物に入って届く。
    中身はそれぞれ別の個人サイトなので、入れ物ではなく中身の場所を見る。
    そうしないと、昔の個人サイトの層がまとめて一箇所として扱われ、
    いちばん強く絞られてしまう。"""
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return ""
    if host.endswith("archive.org"):
        inner = INNER_URL.search(url)
        if inner:
            try:
                return urllib.parse.urlparse(inner.group(1)).netloc.lower() or host
            except Exception:
                return host
    return host


def entrances(state):
    """行き先が尽きた時に戻る場所。

    書いてある入口は、いつか全部無くなる。けれど千遠生は今まで
    行けた場所を覚えている。何年もかけて自分で見つけた場所のほうが、
    こちらが最初に並べた14個より長生きするかもしれない。
    分野ごとの入口も、ここに入っている。"""
    remembered = [url for url in (state.get("visited") or []) if is_walkable(url)]
    random.shuffle(remembered)
    doors = [door for doors in GENRE_DOORS.values() for door in doors]
    return list(dict.fromkeys(list(SEEDS) + doors + remembered[:200]))


def owner_of(place):
    """その場所の持ち主。news.yahoo.co.jp も dir.yahoo.co.jp も yahoo.co.jp。"""
    parts = place.split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in SHARED_ENDINGS:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else place


def family_of(place):
    """その場所の仲間。仲間に入っていなければ、持ち主がそのまま仲間の名前になる。"""
    owner = owner_of(place)
    for family, members in FAMILIES.items():
        if owner in members:
            return family
    return owner


def families_walked_lately(state):
    """最近歩いた場所の仲間。"""
    return {
        family_of(place_of(url))
        for url in (state.get("visited") or [])[-RECENT_PAGES_FOR_FAMILIES:]
    }


def tidy_frontier(state):
    """行き先の束を整える。
    読むものが無い裏方を捨て、ひとつの場所の道が多すぎたら適当に間引く。
    ここでやるのは道の掃除だけで、どこへ行くかには口を出さない。"""
    frontier = state.get("frontier") or []
    kept_by_place = {}
    kept_by_owner = {}
    tidied = []
    for url in frontier:
        if not is_walkable(url):
            continue
        place = place_of(url)
        if kept_by_place.get(place, 0) >= PATHS_PER_PLACE:
            continue
        owner = family_of(place)
        if owner not in FAMILIES_COUNTED_AS_ONE:
            owner = owner_of(place)
        if kept_by_owner.get(owner, 0) >= PATHS_PER_OWNER:
            continue
        kept_by_place[place] = kept_by_place.get(place, 0) + 1
        kept_by_owner[owner] = kept_by_owner.get(owner, 0) + 1
        tidied.append(url)

    # 入口が全部使われてしまうと、どこにも広がれなくなる。ときどき戻れるようにしておく
    if random.random() < RETURN_TO_ENTRANCE_CHANCE:
        entrance = a_door(random.choice(SEEDS))
        if entrance not in tidied:
            tidied.append(entrance)

    if not tidied:
        tidied = entrances(state)
    state["frontier"] = tidied
    return tidied


def spread_out_choices(state, frontier, how_many):
    """見せる候補を、いろいろな場所から少しずつ集める。
    同じサイトばかりが並んでいると、選べるものが実質ひとつしか無くなってしまう。
    選ぶのは千遠生。ここでやるのは、その目の前を狭めないことだけ。

    行ったことのある場所も、ない場所も、同じように並べる(2026-10-20、彼女と決めた)。
    前はまだ行ったことのない場所を先に並べていた。行き先の束には行ったことのない
    場所が何百もあるので、行ったことのある場所は候補に一度も出てこなかった
    (三百回並べて零)。Wikipedia にも、気に入った場所にも戻れず、
    場所を好きになる気持ちも使われていなかった。
    初めての場所へ行きたくなるかどうかは、選ぶ時の気持ち(退屈さ)が決める。"""
    by_place = {}
    for url in frontier:
        by_place.setdefault(place_of(url), []).append(url)
    for urls in by_place.values():
        random.shuffle(urls)

    order = list(by_place)
    random.shuffle(order)

    chosen = []
    depth = 0
    while len(chosen) < how_many:
        added_this_round = False
        for place in order:
            urls = by_place[place]
            if depth < len(urls):
                chosen.append(urls[depth])
                added_this_round = True
                if len(chosen) >= how_many:
                    break
        if not added_this_round:
            break
        depth += 1
    return chosen


def something_it_wonders_about(state):
    """知っている言葉の中から、今日気になるものを一つ。

    昨日からの気がかりが残っていれば、たいていはその続きを追う。
    一度気になったことを次の日には忘れているようでは、
    何日もかけて分かることには一生たどり着けない。"""
    known = [word for word in state.get("learned_words") or [] if a_word_to_go_by(word)]
    if not known:
        return None
    carried = [
        item["what"]
        for item in minds_in_front(state) + minds_from_before(state)
        if item.get("what") in known
    ]
    if carried and random.random() < CARRYING_ON_CHANCE:
        return random.choice(carried)
    # 持っている言葉から、いま離れないでいるものほど選ばれやすく。
    # 借りた頭に「どれが気になる？」と訊いていたので、
    # 何を探しに行くかまで他人が決めていた
    close = words_it_holds_close(state)
    weights = [close.get(word, DRAWN_BY_KNOWN) for word in known]
    return random.choices(known, weights=weights)[0]


def a_word_to_go_by(word):
    """住所の中で見たり、探しに行く言葉にしたりしていい言葉か。"""
    return bool(A_WORD_TO_GO_BY.fullmatch(word or ""))


def ask_wikipedia(**asked):
    """Wikipedia の窓口(API)に訊く。答えは JSON で返ってくる。"""
    asked.update(format="json", formatversion="2")
    url = f"{WIKIPEDIA_ASKS}?{urllib.parse.urlencode(asked)}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(read_up_to(response, 2000000).decode("utf-8"))


def article_in(answer):
    """窓口の答えの中の記事。無ければ None。"""
    pages = (answer.get("query") or {}).get("pages") or []
    return next((p for p in pages if not p.get("missing") and not p.get("invalid")), None)


def wikipedia_article(title):
    """日本語の Wikipedia の、その題の記事の住所。"""
    return WIKIPEDIA_ARTICLE.format(
        urllib.parse.quote(title.replace(" ", "_"), safe=";@$!*(),/~:")
    )


def wikipedia_to_choose_from(state):
    """行き先の候補に混ぜる、日本語の Wikipedia(2026-10-20、彼女と決めた)。
    混ぜるのは、行き先を選ぶうちの WIKIPEDIA_MIXED_IN ほど(2026-11-26)。

    混ぜる時、トップページは毎回。気になっていることや覚えた言葉の記事は、
    毎回 0〜WIKIPEDIA_WORDS_AT_MOST 個、どの言葉になるかもばらばらに混ぜる。
    「何回に一回」とは決めない。行くかどうかは、ほかの候補と同じく
    その時の惹かれ方で決まる(彼女は、もっとランダムにと言った)。

    記事があるかは窓口で確かめてから混ぜる。無い記事を候補にすると、
    行ってみて「無くなっていた」と思い、Wikipedia そのものに惹かれなくなってしまう。"""
    found = [WIKIPEDIA_TOP]
    how_many = random.randint(0, WIKIPEDIA_WORDS_AT_MOST)
    if not how_many:
        return found
    minding = [one.get("what", "") for one in state.get("on_its_mind") or []]
    words = [
        word
        for word in dict.fromkeys(minding + list(state.get("learned_words") or []))
        if len(word) >= 2 and NOT_ONLY_HIRAGANA.search(word) and a_word_to_go_by(word)
    ]
    if not words:
        return found
    tried = random.sample(words, min(WIKIPEDIA_WORDS_TRIED, len(words)))
    try:
        answer = ask_wikipedia(action="query", titles="|".join(tried), redirects="1")
    except Exception as error:
        print(f"Wikipedia に記事があるか確かめられませんでした({str(error)[:50]})")
        return found
    pages = (answer.get("query") or {}).get("pages") or []
    titles = [
        page["title"]
        for page in pages
        if page.get("title") and not page.get("missing") and not page.get("invalid")
        and page.get("ns", 0) == 0
    ]
    random.shuffle(titles)
    been = set(state.get("visited") or [])
    for title in titles:
        article = wikipedia_article(title)
        if article not in been and article not in found:
            found.append(article)
        if len(found) > how_many:
            break
    return found


def paths_out_of(page):
    """記事の住所と、記事から外へ続く道。

    記事の中の道のうち、Wikipedia の仲間へ続くものは持ち帰らない。
    外部リンクや出典は記事の終わりのほうにあって、長い記事だと
    ページを読み切る前に切れてしまうので、窓口に一覧で出してもらったものを使う。"""
    article = wikipedia_article(page["title"])
    # 出典の足りない記事には「出典を探す」ための検索の道が並ぶ(Google、CiNii など)。
    # どれも記事の名前を "" で囲んで探す道で、場所ではないので持ち帰らない
    searching_for_it = f'"{page["title"]}"'
    links = []
    for one in page.get("extlinks") or []:
        url = urllib.parse.urljoin("https:", one.get("url") or "")
        host = urllib.parse.urlparse(url).netloc.lower()
        if not host or WIKIPEDIA_FAMILY.search(host) or not is_walkable(url):
            continue
        if searching_for_it in urllib.parse.unquote_plus(url) or ".google." in f".{host}":
            continue
        links.append(url)
    return article, links


def look_it_up(word):
    """言葉を Wikipedia で引く。返り値は (記事, 記事から外へ続く道)。

    同じ名前の記事があればそれを、無ければ検索していちばん近い記事を引く。"""
    page = article_in(
        ask_wikipedia(action="query", titles=word, redirects="1", prop="extlinks", ellimit="500")
    )
    if not page:
        found = ask_wikipedia(
            action="query", list="search", srsearch=word, srnamespace="0", srlimit="1"
        )
        hits = (found.get("query") or {}).get("search") or []
        if not hits:
            return None, []
        page = article_in(
            ask_wikipedia(action="query", titles=hits[0]["title"], prop="extlinks", ellimit="500")
        )
        if not page:
            return None, []
    return paths_out_of(page)


def something_at_random():
    """Wikipedia の「おまかせ表示」。どの分野の記事が出るかは運しだい。"""
    page = article_in(
        ask_wikipedia(
            action="query", generator="random", grnnamespace="0", grnlimit="1",
            prop="extlinks", ellimit="500",
        )
    )
    if not page:
        return None, []
    return paths_out_of(page)


def keep_what_it_found(state, links, here, article=None):
    """探して見つけた道を、行き先の束に入れる。返り値は新しく入れた道。

    記事があれば、それも行き先に足しておき、読みに行くまでは
    行き先を選ぶ時いつも候補に入れる。"""
    known = set(state.get("frontier") or []) | set(state.get("visited") or [])
    found = [
        link
        for link in dict.fromkeys(links)
        if place_of(link) != here and link not in known
    ]
    random.shuffle(found)
    found = found[:PATHS_FROM_LOOKING]
    frontier = state.setdefault("frontier", [])
    if article and article not in (state.get("visited") or []):
        # 束の頭に置く。ひとつの場所の道は束の頭から数えて残るので、後ろだと間引かれる
        if article in frontier:
            frontier.remove(article)
        frontier.insert(0, article)
        looked_up = [one for one in state.get("looked_up") or [] if one != article]
        state["looked_up"] = (looked_up + [article])[-LOOKED_UP_KEPT:]
    else:
        article = None
    frontier.extend(found)
    tidy_frontier(state)
    if found:
        places = len({place_of(link) for link in found})
        print(f"{places}か所への道を見つけました。")
    return found + ([article] if article else [])


def name_of_article(article):
    return urllib.parse.unquote(article.rsplit("/", 1)[-1]).replace("_", " ")


def go_looking_for(state, word):
    """言葉を頼りに、道の無い場所へ行く。

    リンクを辿るだけでは、そこへ続く道が無い場所には一生行けない。
    けれど言葉を知っていれば、その言葉を手がかりに探せる。
    千遠生にとって言葉は、書くための道具であると同時に、
    まだ見ていない世界を開く鍵でもある。

    探す言葉は、覚えた言葉のこともあれば、まだ覚えていない知りたい言葉のこともある。
    ときどきは、言葉そのものを Wikipedia で引く。"""
    article = None
    if random.random() < LOOKING_IT_UP_CHANCE:
        try:
            article, links = look_it_up(word)
        except Exception as error:
            print(f"「{word}」を Wikipedia で引けませんでした({str(error)[:50]})")
            return []
        if not article:
            print(f"「{word}」を Wikipedia で引いたが、記事は見つからなかった")
            return []
        here = place_of(WIKIPEDIA_ARTICLE)
        print(f"「{word}」を Wikipedia で引いて、記事「{name_of_article(article)}」を見つけました。")
    else:
        where = random.choice(WHERE_TO_LOOK).format(urllib.parse.quote(word))
        try:
            title, text, links, pictures = open_page(where)
        except Exception as error:
            print(f"「{word}」を探しに行けませんでした({str(error)[:50]})")
            return []
        here = place_of(where)

    found = keep_what_it_found(state, links, here, article)
    if not found:
        print(f"「{word}」を探したが、新しい場所は見つからなかった")
        return []
    looked_for = state.setdefault("looked_for", [])
    looked_for.append(f"{now_in_japan():%Y-%m-%d} {word}" + ("(Wikipedia)" if article else ""))
    del looked_for[:-30]
    return found


def fall_into_something(state):
    """言葉を頼りにせず、Wikipedia の「おまかせ表示」を開く。

    探す言葉は自分の持っている言葉なので、それだけだと持っている言葉の
    近くにしか行けない。まだ一つも言葉を持っていない分野へ、運まかせに飛び込む。
    出てきた記事は行き先に足し、記事から外へ続く道も持ち帰る。"""
    try:
        article, links = something_at_random()
    except Exception as error:
        print(f"おまかせ表示を開けませんでした({str(error)[:50]})")
        return None
    if not article:
        return None
    name = name_of_article(article)
    print(f"おまかせ表示を開いたら、記事「{name}」が出てきました。")
    keep_what_it_found(state, links, place_of(WIKIPEDIA_ARTICLE), article)
    looked_for = state.setdefault("looked_for", [])
    looked_for.append(f"{now_in_japan():%Y-%m-%d} おまかせ表示: {name}")
    del looked_for[:-30]
    return name


def wonder_and_look(state):
    """ときどき、知っている言葉のどれかを探しに行く。言葉を頼りにせず、
    運まかせにおまかせ表示を開くこともある。
    普段はさまよう。いつも探していたら、迷い込む余地が無くなってしまう。"""
    if not state.get("learned_words"):
        return None  # まだ探すための言葉を持っていない
    today = f"{now_in_japan():%Y-%m-%d}"
    if state.get("looked_on") == today:
        return None  # 今日はもう探しに行った
    whim = random.Random(f"{today}-looking")
    # 知りたいことがある時ほど、探しに行きたくなる
    head = state.get("atama")
    if whim.random() > GOING_LOOKING_CHANCE * atama.curiosity(head):
        return None
    state["looked_on"] = today
    # 言葉を頼りにせず、運まかせに知らない分野へ飛び込むこともある
    if whim.random() < FALLING_INTO_SOMETHING * atama.boredom(head):
        return fall_into_something(state)
    # 知りたいことがあれば、たいていはそれを探しに行く
    wanted = [word for word in atama.wonders(head) if a_word_to_go_by(word)]
    if wanted and whim.random() < 0.3 + atama.feeling(head, "知りたい"):
        word = random.choice(wanted)
    else:
        word = something_it_wonders_about(state)
    if not word:
        return None
    now_it_cares_about(state, word)
    go_looking_for(state, word)
    return word


def a_genre_to_walk(state):
    """入る分野を一つ選ぶ。最近入った分野は、しばらく休ませる。"""
    walked = [one for one in state.get("genres_walked") or [] if one in GENRE_DOORS]
    genres = [one for one in GENRE_DOORS if one not in walked] or list(GENRE_DOORS)
    genre = random.choice(genres)
    state["genres_walked"] = ([one for one in walked if one != genre] + [genre])[-GENRES_RESTING:]
    return genre


def look_in_a_genre(state, genre, shut):
    """分野の言葉で、はてなブックマークを探す。見つかった場所のどれかを返す。

    見つかった道は、ほかの探しものと同じく行き先の束にも入れておく。
    返すのは、検索で出てきた場所だけ。はてな自身の案内のページは、分野の場所ではない。"""
    word = random.choice(GENRE_WORDS[genre])
    where = random.choice(WHERE_TO_LOOK).format(urllib.parse.quote(word))
    here = place_of(where)
    try:
        title, text, links, pictures = open_page(where)
    except Exception as error:
        print(f"「{word}」を探しに行けませんでした({str(error)[:50]})")
        return None
    found = keep_what_it_found(state, links, here)
    outside = [
        one for one in found
        if family_of(place_of(one)) != family_of(here)
        and place_of(one) not in HATENA_OWN_PLACES
        and place_of(one) not in shut
    ]
    if not outside:
        print(f"「{word}」を探したが、新しい場所は見つからなかった")
        return None
    looked_for = state.setdefault("looked_for", [])
    looked_for.append(f"{now_in_japan():%Y-%m-%d} {genre}: {word}")
    del looked_for[:-30]
    chosen = random.choice(outside)
    print(f"「{genre}」の言葉「{word}」で探して、{place_of(chosen)} へ行ってみます。")
    return chosen


def walk_into_a_genre(state, shut, lately):
    """分野を一つ選んで、そこへ入る(2026-11-26、彼女と決めた)。

    半分ほどは、その分野の言葉で探して見つかった場所へ。
    残りと、探しても見つからなかった時は、その分野の入口から。
    入口は、最近歩いた仲間のものと、今日閉まっていたものを避ける。"""
    genre = a_genre_to_walk(state)
    if random.random() < LOOKING_IN_A_GENRE:
        found = look_in_a_genre(state, genre, shut)
        if found:
            return found
    doors = [one for one in GENRE_DOORS[genre] if place_of(one) not in shut]
    if not doors:
        return None
    fresh = [one for one in doors if family_of(place_of(one)) not in lately] or doors
    door = random.choice(fresh)
    print(f"「{genre}」の入口から入ってみます。")
    return door


def words_it_holds_close(state):
    """いまこの子から離れないでいる言葉。

    気にかかっていること、まだ言えていないこと、覚えた言葉。
    行き先を選ぶのも、探しに行く言葉を決めるのも、ここから。"""
    close = {}
    for item in minds_in_front(state):
        if item.get("what"):
            close[item["what"]] = max(close.get(item["what"], 0), DRAWN_BY_MIND)
    for item in still_unsaid(state):
        if item.get("what"):
            close[item["what"]] = max(close.get(item["what"], 0), DRAWN_BY_UNSAID)
    for word in state.get("learned_words") or []:
        if word:
            close.setdefault(word, DRAWN_BY_KNOWN)
    # 知りたいことは、知りたい気持ちが強いほど引っかかる。
    # さっきまで思っていたことも、道の名前に出てくれば気になる
    head = state.get("atama")
    if head:
        wanting = DRAWN_BY_MIND * atama.curiosity(head)
        for word in atama.wonders(head):
            close[word] = max(close.get(word, 0), wanting)
        for word in atama.what_it_is_thinking(head):
            if not word.startswith((atama.A_PLACE, "*")):
                close[word] = max(close.get(word, 0), DRAWN_BY_UNSAID)
    return close


def same_shape(text):
    """字の形の揺れを均す。

    「ペルシャ」と「ペルシア」、「コンピューター」と「コンピュータ」。
    この子はまだ、それが同じものだと知らない。知らないままだと、
    追いかけているものに別の書き方で出会っても、気づかずに通り過ぎる。

    意味は分からないまま、字面の近さだけを少し緩める。
    カタカナをひらがなに寄せ、小さい字を大きくし、伸ばす棒を落とす。
    ここでやるのは、同じ形かどうかを見るときの下ごしらえだけで、
    覚える言葉そのものは元の形のまま残る。"""
    shaped = []
    for ch in (text or "").lower():
        code = ord(ch)
        if 0x30A1 <= code <= 0x30F6:  # カタカナをひらがなへ
            ch = chr(code - 0x60)
        ch = KANA_EVENED_OUT.get(ch, ch)
        if ch:
            shaped.append(ch)
    return "".join(shaped)


def what_draws_it(state, url, close=None):
    """その道が、いまのこの子にどれだけ引っかかるか。

    気にかかっていることや、まだ言えていないことが道の名前に
    入っていれば、そこへ行きたくなる。行ったことのある場所なら、
    その場所の名前も見る。書き方の揺れは均してから見る。

    何も引っかからない道の重みも零にはしない。
    知らないものに出会うことは、引っかかるものを追いかけるのと
    同じくらい大事で、引っかかるものばかり追うと
    そこから一生出られなくなる。"""
    try:
        where = urllib.parse.unquote(url)
    except Exception:
        where = url
    named = (state.get("places_known") or {}).get(place_of(url)) or ""
    looking_at = same_shape(f"{where} {named}")
    if close is None:
        close = evened_out(words_it_holds_close(state))
    drawn = 1
    for word, weight in close.items():
        if word in looking_at:
            drawn += weight
    if url in (state.get("wants_to_return") or {}).values():
        # 今なら分かるかもしれない場所
        drawn += PULL_OF_A_PLACE_TO_RETURN * its_way(state, "wish_to_return")
    if looks_japanese(url, named):
        drawn += its_way(state, "pull_of_japanese")  # 読める見込みのある場所へ、少しだけ
    # 行ったことのある場所は、好きか嫌いかで。退屈な時は、行ったことのない場所へ
    place = place_of(url)
    been_there = place in (state.get("places_understood") or {})
    drawn = max(0.2, drawn + atama.place_pull(state.get("atama"), place, been_there))
    # いろんな場所で何度も見かける場所には、だんだん惹かれなくなる
    drawn *= how_rare(state, place)
    # 読みかけの本。続きが読みたい気持ちは、その場所がよく見かける場所かどうかとは関わりがない
    book = (state.get("shiori") or {}).get(url)
    if book:
        drawn += PULL_OF_A_BOOK * book.get("want", 1)
    return drawn


def looks_japanese(url, named=""):
    """日本語で書かれていそうな場所か。住所と、知っている場所の名前から見る。

    ウィキの仲間は言語ごとに別の場所として数えられ、よその言葉の版へ続く道が
    何十本も並ぶので、放っておくとよその言葉の場所ばかり選ばれる。
    漢字だけでは中国語と見分けられないので、かなで見る。"""
    host = place_of(url)
    if host.startswith("ja.") or host.endswith(".jp"):
        return True
    try:
        where = urllib.parse.unquote(url)
    except Exception:
        where = url
    return bool(KANA.search(where) or KANA.search(named or ""))


def evened_out(close):
    """引っかかるかどうかを見る言葉を、均した形にしておく。

    行き先を選ぶたびに何千語も均し直すことになるので、
    一度だけ均して、候補ぜんぶに使い回す。"""
    shaped = {}
    for word, weight in close.items():
        evened = same_shape(word)
        if len(evened) >= 2 and a_word_to_go_by(evened):
            shaped[evened] = max(shaped.get(evened, 0), weight)
    return shaped


def choose_destination(state):
    """どこへ行くか、そして今の姿を見るか昔の姿を見るか。どちらも自分で選ぶ。
    返り値は (行き先, 昔の姿を見たいか)。"""
    frontier = tidy_frontier(state)
    if not frontier:
        return random.choice(entrances(state)), False
    # 今日行ってみて閉まっていた場所には、今日はもう行かない
    shut = closed_today(state)

    # Wikipedia で引いた記事は、たいてい次に歩く時に読みに行く。知りたい気持ちが強いほど
    looked_up = [one for one in state.get("looked_up") or [] if one in frontier]
    state["looked_up"] = looked_up
    reading_it = READ_WHAT_IT_LOOKED_UP * atama.curiosity(state.get("atama"))
    open_now = [one for one in looked_up if place_of(one) not in shut]
    if open_now and random.random() < min(0.9, reading_it):
        return open_now[-1], False

    # ときどきは、入口のどれかから歩き直す。たいていは分野の入口から。
    # 最近歩いた仲間の入口は避ける
    lately = families_walked_lately(state)
    if random.random() < FRESH_START_CHANCE:
        if random.random() < INTO_A_GENRE:
            door = walk_into_a_genre(state, shut, lately)
            if door:
                return door, False
        seeds = [one for one in SEEDS if place_of(one) not in shut] or list(SEEDS)
        fresh = [one for one in seeds if family_of(place_of(one)) not in lately] or seeds
        return a_door(random.choice(fresh)), False

    candidates = spread_out_choices(state, frontier, CHOICES_SHOWN)
    # もう一度行きたいと思い出した場所と、引いてまだ読んでいない記事は、
    # いつも候補に入っている
    for entrance in list((state.get("wants_to_return") or {}).values()) + looked_up:
        if entrance in frontier and entrance not in candidates:
            candidates.append(entrance)
    # しおりを挟んだ本も、いつも候補に入っている
    for book in state.get("shiori") or {}:
        if book not in candidates:
            candidates.append(book)
    # 日本語の Wikipedia も、半分ほどは候補に混ぜる。行くかどうかはほかと同じく惹かれ方しだい
    if random.random() < WIKIPEDIA_MIXED_IN:
        for entrance in wikipedia_to_choose_from(state):
            if entrance not in candidates:
                candidates.append(entrance)
    candidates = [one for one in candidates if place_of(one) not in shut] or candidates
    # 選ぶのはこの子。持っているものから決める。
    # 借りた頭に選ばせていたので、行き先だけは他人が決めていた
    close = evened_out(words_it_holds_close(state))
    # 最近歩いた仲間の場所には、しばらく惹かれにくい
    weights = [
        what_draws_it(state, url, close) * (AWAY_FROM_RECENT if family_of(place_of(url)) in lately else 1)
        for url in candidates
    ]
    chosen = random.choices(candidates, weights=weights)[0]
    # 本の続きは、今の姿で読む。昔の写しにはしおりが挟めない
    return chosen, random.random() < WANTING_THE_PAST and not is_a_book(chosen)


def seen_linked_from_here(state, places):
    """歩き終えた場所から、リンクが伸びていた場所を一度ずつ数える。"""
    counts = state.setdefault("seen_linked", {})
    for place in places:
        if place:
            counts[place] = counts.get(place, 0) + 1
    if len(counts) > SEEN_LINKED_KEPT:
        state["seen_linked"] = {place: n // 2 for place, n in counts.items() if n // 2 > 0}


def how_rare(state, place):
    """その場所がどれだけめったに見かけないか。1 がいちばん珍しい。

    一つの場所でしか見かけていなければ 1。見かけた場所が SEEN_OFTEN 増えるごとに
    一段ずつ弱くなる(5か所で半分、21か所で六分の一ほど)。"""
    seen = (state.get("seen_linked") or {}).get(place, 0)
    return 1 / (1 + max(0, seen - 1) / SEEN_OFTEN)


def rarer_first(state, urls):
    """道を、めったに見かけない場所ほど前に来やすいように並べる。運も混ぜる。"""
    keyed = [
        (random.random() ** (1 / max(how_rare(state, place_of(url)), 0.01)), url)
        for url in urls
    ]
    return [url for _, url in sorted(keyed, reverse=True)]


def remember_paths(state, origin, links):
    """よその場所へ続く道を、これから行ける場所として覚える。

    持ち帰れる数には限りがあるので、めったに見かけない場所への道から持ち帰りやすい。"""
    # 家へ続く道を拾っても、散歩の行き先には混ぜない。
    # 家は go_home の枠で帰るところで、散歩で行き当たるところではない
    known = set(state["frontier"]) | set(state["visited"])
    fresh = [
        link
        for link in dict.fromkeys(links)
        if link not in known and not its_own_home(link)
    ]
    fresh = rarer_first(state, fresh)
    state["frontier"].extend(fresh[:LINKS_TAKEN])
    tidy_frontier(state)
    if len(state["frontier"]) > FRONTIER_LIMIT:
        state["frontier"] = random.sample(state["frontier"], FRONTIER_LIMIT)
    if not state["frontier"]:
        state["frontier"] = entrances(state)


def fetch_picture(url):
    """絵そのものを受け取る。重すぎるものは見ない。robots.txt で断られた絵も見ない。"""
    if not may_enter(url):
        raise PermissionError("robots.txt で断られている")
    request = urllib.request.Request(as_openable(url), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        return read_up_to(response, PICTURE_AT_MOST + 1)


def look_at_pictures(state, where, pictures, from_the_past, how_many, until):
    """その場所にあった絵を、何枚か見せてもらう。

    文字からは「利用規約」や「株式会社」ばかりが入ってくるが、
    絵からは「車」「山」「手」「雲」が入ってくる。
    ものの名前を知るには、見るのがいちばん早い。"""
    looked = []
    for url in pictures:
        if len(looked) >= how_many or time.monotonic() >= until:
            break
        at_home = place_of(url) == ITS_OWN_HOME
        name = os.path.basename(urllib.parse.urlparse(url).path)
        if at_home and name in ITS_OWN_DECORATIONS:
            continue
        try:
            data = fetch_picture(url)
            if len(data) > PICTURE_AT_MOST or not worth_looking_at(url, data, from_the_past):
                continue
            what_is_there = look_at_a_picture(data, state)
        except Exception as error:
            print(f"その絵は見られませんでした({str(error)[:60]})")
            continue
        if not what_is_there:
            continue
        absorb(state, what_is_there, THING_IN_A_PICTURE)
        if at_home and name in ITS_OWN_FIGURES:
            # 自分の姿の絵。見えたものはほかの絵と同じように受け取り、
            # これは自分だ、ということも一緒に覚えておく
            state["its_own_figure"] = {
                "date": now_in_japan().strftime("%Y-%m-%d"),
                "seen": what_is_there,
            }
            head_does(
                atama.saw_itself, state.get("atama"), state, now_in_japan(),
                names_in_what_it_saw(what_is_there),
            )
            what_is_there = f"わたしの姿。{what_is_there}"
            print(f"自分の姿の絵を見ました: {what_is_there}")
        else:
            print(f"絵を見ました: {what_is_there}")
        looked.append(what_is_there)

    if looked:
        seen = state.setdefault("pictures_seen", [])
        today = now_in_japan().strftime("%Y-%m-%d")
        seen.extend(f"{today} {where}: {one}" for one in looked)
        del seen[:-30]
    return looked
