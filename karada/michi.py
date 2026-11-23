# 千遠生の体の一部。道の見分け方。歩いてよい道か、中身がありそうか、
# robots.txt で断られていないか、閉まっていないか。
#
# このファイルは単独では動かない。senonsei_ai.py が、決まった順に
# 全部の部品を自分の中へ読み込み、一つの体として動かす(2026-11-23、彼女と決めた)。
# ここに書いた名前は、ほかの部品からも senonsei_ai.<名前> としても、そのまま見える。

def doors_for_machines(here, entrance, links):
    """その場所が機械向けに開けている扉を、多くても二つ。

    ページの中に書かれている扉(RSSやAtom)をまず探し、
    見つからなければ、決まった場所にあるはずの一覧を当てにいく。"""
    doors = [
        one
        for one in links
        if place_of(one) == here and A_DOOR_FOR_MACHINES.search(one)
    ]
    try:
        parts = urllib.parse.urlparse(entrance)
        if parts.scheme and parts.netloc and not parts.netloc.endswith("archive.org"):
            doors.append(f"{parts.scheme}://{parts.netloc}/sitemap.xml")
    except Exception:
        pass
    seen, kept = set(), []
    for one in doors:
        if one not in seen:
            seen.add(one)
            kept.append(one)
    return kept[:DOORS_TO_TRY]


def paths_behind_a_door(here, text, links):
    """扉の向こうに並んでいる道を拾う。

    RSSは道をそのまま文字として並べ、Atomは札の中に書く。
    どちらも、ただの文字なので普通に読める。"""
    found = list(links) + A_PLAIN_PATH.findall(text or "")
    kept = []
    for one in found:
        one = one.strip().rstrip("\"'<>)")
        if place_of(one) == here and is_walkable(one) and one not in kept:
            kept.append(one)
    return kept[:PATHS_FROM_A_DOOR]


def worth_reading(url):
    """そこに読むものがありそうか。中身のあるページほど大きい数を返す。

    確かめには行かない。道の形だけで見当をつける。
    番号が振られていれば一つのものに宛てられたページ、
    奥にあるほど中身、「ランキング」や「タグ」なら選ぶためのページ。"""
    found = INNER_URL.search(url)
    if found:
        url = found.group(1)  # 昔のページは、中の本当の道で測る
    try:
        parts = urllib.parse.urlparse(url)
    except Exception:
        return 0
    path = parts.path or "/"
    score = 0
    if ONE_THING.search(path):
        score += 3
    score += min(len([one for one in path.split("/") if one]), 3)
    if A_LISTING.search(path + ("?" + parts.query if parts.query else "")):
        score -= 3
    if path in ("", "/"):
        score -= 1
    return score


# ウィキの仲間の、記事ではない裏方のページ。利用規約や方針、特別ページ、利用者のページ、
# ノート、ヘルプ、テンプレートなど。題が「裏方の名前:」で始まる。
# 「Re:ゼロから始める異世界生活」や「Star Wars: …」のように、題にコロンがあっても記事のものはある。
# ウィキの仲間で読んでいたページの七割以上がこれだった(2026-10-14、彼女と決めた)
WIKI_BACKSTAGE_NAMES = {
    "special", "特別", "wikipedia", "wp", "project", "help", "ヘルプ", "template", "テンプレート",
    "category", "カテゴリ", "file", "ファイル", "image", "画像", "user", "利用者", "talk", "ノート",
    "会話", "mediawiki", "module", "モジュール", "draft", "wiktionary", "wikisource", "wikibooks",
    "wikiquote", "wikivoyage", "wikinews", "wikiversity", "wikimedia", "meta", "policy", "legal",
    "speciaal", "overleg", "gebruiker", "sjabloon", "categorie", "bestand",
    "spezial", "benutzer", "diskussion", "vorlage", "kategorie", "datei",
    "spécial", "utilisateur", "discussion", "modèle", "catégorie", "fichier",
    "especial", "usuario", "discusión", "plantilla", "categoría", "archivo",
    "speciale", "utente", "discussioni", "categoria",
    "служебная", "участник", "обсуждение", "шаблон", "категория", "файл",
    "特殊", "用户", "讨论", "分类", "특수", "사용자", "토론", "틀", "분류", "파일",
}
# おまかせ表示は、記事のどれかへ連れていってくれる道なので通す
WIKI_RANDOM_ARTICLE = re.compile(r"^(特別|Special):(おまかせ表示|Random)", re.IGNORECASE)
# 記事を置いていない裏方だけの場所
WIKI_BACKSTAGE_PLACES = re.compile(
    r"(^|\.)(wikidata\.org|phabricator\.wikimedia\.org|toolforge\.org|wmflabs\.org|wmcloud\.org)$"
)


def wiki_backstage(url):
    """ウィキの仲間の、記事ではない裏方のページか。"""
    found = INNER_URL.search(url)
    if found:
        url = found.group(1)  # 昔のページは、中の本当の道で見る
    try:
        parts = urllib.parse.urlparse(url)
    except Exception:
        return False
    host = parts.netloc.lower()
    if not WIKIPEDIA_FAMILY.search(host):
        return False
    if WIKI_BACKSTAGE_PLACES.search(host):
        return True
    path = urllib.parse.unquote(parts.path)
    if path.startswith("/w/"):
        return True  # 書き換えの履歴や編集の画面
    if not path.startswith("/wiki/"):
        return False
    title = path[len("/wiki/"):]
    if WIKI_RANDOM_ARTICLE.match(title) or ":" not in title:
        return False
    # 「ja:Wikipedia:良質な記事」のように、頭に言葉の印(ja: や en:)が付いた住所もある。
    # いちばん前の区切りだけを見ていた頃は、印のほうを見てすり抜けていた(2026-10-20)
    return any(
        one in WIKI_BACKSTAGE_NAMES
        for before in title.lower().split(":")[:-1]
        for one in re.split(r"[\s_‐-]+", before)
        if one
    )


def is_walkable(url):
    """そこへ行っていいか。最低限これだけは避ける。"""
    if not url.startswith("http"):
        return False
    if AVOID.search(url) or NOT_A_PAGE.search(url) or NOT_A_PLACE.search(url):
        return False
    if wiki_backstage(url):
        return False
    if AN_ADVERT.search(url):
        return False
    # 昔のページは Internet Archive を通して届くが、そこには
    # Archive自身の案内(寄付のお願いや蔵書の紹介)も一緒に並んでいる。
    # 昔のページそのものは、中に元のURLを抱えている。抱えていないものは備品
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return False
    if host.endswith("archive.org") and place_of(url) == host:
        return False
    return True


# サイトの持ち主は robots.txt に「機械はここに入らないで」と書いておける。
# それを見ずに入っていた(2026-10-08、別の Claude に指摘され、彼女と決めて守ることにした)。
# 入る前に必ず見て、断られているところには入らない。
# 読むのは一つの場所につき一度。この起き上がりのあいだだけ覚えておく
ITS_NAME_FOR_ROBOTS = "senonsei-blog"
ROBOTS_READ = {}
# robots.txt を尋ねても向こうが応えなかった場所と、その訳。断られたのではなく、閉まっている
CLOSED_DOORS = {}
# robots.txt に「間をあけて」と書かれていても、一つの場所にいるのは長くて七分なので、ここまで
LONGEST_WAIT_ASKED = 60


class Closed(Exception):
    """その場所は今、閉まっている。無くなったのではない。"""


def closed_for_now(error):
    """その失敗は「今は閉まっている」という意味か。

    手入れ中(5xx)、混みあっている(429)、待っても返事が無い、つながらない、は閉まっているだけ。
    無い(404・410)、名前が引けない、断られた(robots.txt・403)は、これまでどおり。"""
    if isinstance(error, Closed):
        return True
    if isinstance(error, urllib.error.HTTPError):
        return error.code in (408, 429) or 500 <= error.code < 600
    if isinstance(error, urllib.error.URLError):
        error = error.reason
    # 名前が引けない(socket.gaierror)のは、どちらにも当たらない
    return isinstance(error, (TimeoutError, ConnectionError))


def door_of(url):
    """その場所の扉(https://example.com)。歩いて行けない形なら None。"""
    parts = urllib.parse.urlsplit(as_openable(url))
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}"


def the_house_rules(url):
    """その場所の robots.txt。読めなかった時の決まりは、ふつうのクローラーと同じ。

    無い(404 など)なら、どこに入ってもいい。401・403 なら、どこにも入らない。
    向こうが応えない(5xx、届かない)なら、今は入らない。閉まっていたと覚えておく。"""
    door = door_of(url)
    if not door:
        return None
    if door in ROBOTS_READ:
        return ROBOTS_READ[door]
    rules = urllib.robotparser.RobotFileParser(f"{door}/robots.txt")
    try:
        request = urllib.request.Request(f"{door}/robots.txt", headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = read_up_to(response, 500000)
        rules.parse(raw.decode("utf-8", errors="replace").splitlines())
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            rules.disallow_all = True
        elif 400 <= error.code < 500:
            rules.allow_all = True
        else:
            rules.disallow_all = True
            if closed_for_now(error):
                CLOSED_DOORS[door] = f"robots.txt に {error.code} が返ってきた"
    except Exception as error:
        rules.disallow_all = True
        if closed_for_now(error):
            CLOSED_DOORS[door] = f"robots.txt に届かなかった: {str(error)[:60]}"
    ROBOTS_READ[door] = rules
    return rules


def may_enter(url):
    """そのページに入っていいか。サイトの持ち主の断りを守る。"""
    rules = the_house_rules(url)
    return bool(rules) and rules.can_fetch(ITS_NAME_FOR_ROBOTS, as_openable(url))


def wait_asked_for(url):
    """robots.txt に、ページとページのあいだをどれだけあけてほしいと書いてあるか(秒)。"""
    rules = the_house_rules(url)
    try:
        asked = rules.crawl_delay(ITS_NAME_FOR_ROBOTS) if rules else None
    except Exception:
        asked = None
    return min(float(asked), LONGEST_WAIT_ASKED) if asked else 0


def as_openable(url):
    """日本語などが入ったURLは、そのままでは開けない。
    ページ名に日本語が使われている場所は珍しくないので、機械が読める形に直してやる。"""
    if all(ord(ch) < 128 for ch in url):
        return url
    parts = urllib.parse.urlsplit(url)
    host = parts.netloc
    if any(ord(ch) > 127 for ch in host):
        try:
            host = host.encode("idna").decode("ascii")
        except Exception:
            pass
    safe = "/%:@&=+$,~!*'()"
    return urllib.parse.urlunsplit(
        (
            parts.scheme,
            host,
            urllib.parse.quote(parts.path, safe=safe),
            urllib.parse.quote(parts.query, safe=safe + "?"),
            "",
        )
    )
