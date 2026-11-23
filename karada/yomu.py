# 千遠生の体の一部。ページを読む。文字の書き表し方を見分け、受け取りすぎを防ぎ、
# 組み立て待ちのページは閲覧機に頼み、しるしを外して文章と道と絵を取り出す。PDF も。
#
# このファイルは単独では動かない。senonsei_ai.py が、決まった順に
# 全部の部品を自分の中へ読み込み、一つの体として動かす(2026-11-23、彼女と決めた)。
# ここに書いた名前は、ほかの部品からも senonsei_ai.<名前> としても、そのまま見える。

def read_as_japanese(raw, content_type):
    """バイトの並びを、文字に戻す。

    90年代のページは今と文字の表し方が違う(EUC-JPやShift_JISなど)。
    しかも Internet Archive を通すと、元のページの申告ではなく
    Archive自身の申告が届くため、素直に信じると全部文字化けする。
    化けたまま読むと千遠生は何も覚えられないので、
    何通りか試して、いちばん日本語らしく読めたものを採る。"""
    declared = []
    found = META_CHARSET.search(content_type)
    if found:
        declared.append(found.group(1))
    found = META_CHARSET.search(raw[:4000].decode("ascii", errors="ignore"))
    if found:
        declared.append(found.group(1))

    readings = []
    for name in list(dict.fromkeys(declared)) + list(WAYS_OF_WRITING):
        try:
            text = raw.decode(name)
        except LookupError:
            continue
        except UnicodeDecodeError as stumbled:
            # 受け取るのを途中で切り上げると(read_up_to)、最後の一文字が
            # 二バイト三バイトの途中で切れていることがある。そこで詰まっただけなら、
            # 切れ端を捨てて読む。それを「読めなかった」とすると、
            # UTF-8 のページがまるごと別の読み方に負けて化けていた
            if stumbled.start < len(raw) - 3:
                text = None
            else:
                try:
                    text = raw[:stumbled.start].decode(name)
                except (UnicodeError, ValueError):
                    text = None
            if text is None:
                try:
                    text = raw.decode(name, errors="replace")
                except (LookupError, UnicodeError, ValueError):
                    continue
                clean = False
            else:
                clean = True
        except UnicodeError:
            # 読めない所があった。無理に読んでみて、そのぶん点を引く。
            #
            # ここは ValueError より先に受け止める。UnicodeError は
            # ValueError の仲間なので、先に ValueError で受けていた頃は
            # ここに一度も来ず、一か所でも詰まった読み方は丸ごと捨てられていた。
            # ①が一つ混ざる、途中で切れる、それだけで日本語の読み方は全部消え、
            # どんな並びでも読めてしまう latin-1 だけが残っていた
            try:
                text = raw.decode(name, errors="replace")
            except (LookupError, UnicodeError, ValueError):
                continue
            clean = False
        except ValueError:
            continue
        else:
            clean = True
        # 日本語として読めた文字が多いほど良い。読めなかった箇所は重く引く。
        #
        # それだけだと、日本語の無いページで化けたほうが勝つ。
        # UTF-8 の「•」を Shift_JIS で読むと「窶｢」になり、
        # これは漢字とカタカナなので日本語らしさとして加点されてしまう。
        # 正しく読めば零点、化ければ一点で、化けたほうが選ばれていた。
        #
        # 最後まで詰まらずに読めたかどうかを、日本語らしさより重く見る。
        # 化けている時は、たいていどこかで読めない並びにぶつかる
        score = len(JAPANESE.findall(text)) - text.count("\ufffd") * 5
        plain_name = name.lower().replace("-", "_")
        if plain_name in WESTERN:
            kind = "western"
        elif plain_name in ("utf_8", "utf8"):
            kind = "utf8"
        else:
            kind = "japanese"
        if clean:
            score += READ_WITHOUT_STUMBLING
            # 英字の範囲の外の文字が一つも無ければ、どの読み方でも読める。
            # その時 UTF-8 で読めたことは何の証にもならない。
            # ISO-2022-JP は全部英字の範囲で書くので、ここで負けていた
            if kind == "utf8" and max(raw, default=0) >= 0x80:
                return text
        readings.append((score, kind, text))

    if not readings:
        return raw.decode("utf-8", errors="ignore")
    # 同じ点なら先に試したほうを採る(並べた順が、そのまま頼る順)
    best = max(readings, key=lambda one: one[0])
    if best[1] == "western":
        # 西洋の読み方が勝った。けれど日本語の読み方で、かながちゃんと
        # 出てくるものがあるなら、それは日本語のページ。
        # Internet Archive が差し込む帯や、①のような文字が少し混ざって
        # 詰まっただけで、日本語の少ないページは西洋の読み方に負けていた
        japanese = [
            one for one in readings
            if one[1] != "western"
            and len(KANA.findall(one[2])) >= KANA_SAYS_JAPANESE
        ]
        if japanese:
            best = max(japanese, key=lambda one: one[0])
    elif best[1] == "japanese" and len(KANA.findall(best[2])) < KANA_SAYS_JAPANESE:
        # 日本語の読み方が勝ったが、かながほとんど無い。
        # 西洋の読み方で ö や é が言葉の中に並ぶなら、西洋のページを
        # 日本語の読み方で読んで漢字に化けさせているだけ。
        #
        # UTF-8 で書かれた西洋のページも、ここで UTF-8 の読み方を候補に入れる。
        # 入れていなかった頃は、UTF-8 の é(二バイト)を latin-1 で読んだ「Ã©」も
        # 「言葉の中に並ぶ西洋の文字」に数えられ、化けたほうが選ばれていた
        # (Google ブックスの『Dictionnaire universel』が「gÃ©nÃ©ralement」になった)
        western = [
            one for one in readings
            if one[1] in ("western", "utf8")
            and len(LATIN_IN_WORDS.findall(one[2])) >= LATIN_SAYS_WESTERN
        ]
        if western:
            best = max(western, key=lambda one: one[0])
    return best[2] or raw.decode("utf-8", errors="ignore")


# 一つのページや絵を受け取るのに、これだけの秒まで待つ。
# 待ち時間の決まり(timeout)は一度の受け取りごとにしか効かないので、
# 少しずつ垂らすように送ってくる相手だと、いつまでも終わらなかった
READING_AT_MOST = 60


def read_up_to(response, limit, seconds=READING_AT_MOST):
    """受け取れるだけ受け取る。多すぎても、遅すぎても、そこで切り上げる。"""
    until = time.monotonic() + seconds
    chunks, got = [], 0
    while got < limit:
        chunk = response.read(min(65536, limit - got))
        if not chunk:
            break
        chunks.append(chunk)
        got += len(chunk)
        if time.monotonic() > until:
            print("受け取るのに時間がかかりすぎたので、途中で切り上げます")
            break
    return b"".join(chunks)


# 今のサイトの多くは、届いた紙には「あとで中身を組み立てて」という指示しか無く、
# 閲覧機が組み立てて初めて中身が出る。この子の読み方では空っぽに見えていた。
# 空っぽに見えた時だけ、画面の無い閲覧機を借りて組み立ててから読む
# (2026-10-04、彼女と決めた)。
#
# 閲覧機はこの子の外にある部品で、いつか無くなるか、動かなくなる。
# 見つからない時や、こけた時は、今までどおり空っぽのまま次へ行く。
# 散歩はそれで止まらない
BROWSERS = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome")
# これより字が少なく、<script> があるページを「組み立て待ち」と見なす
LOOKS_EMPTY = 200
# 一度の起き上がりで閲覧機を借りるのは、これだけ。組み立てるには時間がかかる
BROWSER_TIMES = 3
BROWSER_WAITS = 45  # 秒
# 閲覧機は、よその場所が書いた仕掛け(JavaScript)をそのまま動かす。閲覧機に穴が見つかって
# いた時に、この子の鍵(封を開ける鍵、Cloudflare の鍵など)まで届かないよう、鍵は渡さない。
# 閲覧機が覚えるもの(クッキーなど)は、その一回かぎりの空の部屋に置いて捨てる(2026-10-23)
A_SECRET_NAME = re.compile(r"KEY|TOKEN|SECRET|PASS|CREDENTIAL|^ACTIONS_|^CLOUDFLARE_", re.IGNORECASE)


def without_keys():
    """鍵を抜いた、閲覧機に渡す環境。"""
    return {name: value for name, value in os.environ.items() if not A_SECRET_NAME.search(name)}
BROWSER_USED = [0]


def a_browser():
    """借りられる閲覧機。無ければ None。"""
    for name in BROWSERS:
        found = shutil.which(name)
        if found:
            return found
    return None


def look_with_a_browser(url):
    """閲覧機に組み立ててもらったページを受け取る。借りられなければ None。"""
    if BROWSER_USED[0] >= BROWSER_TIMES:
        return None
    browser = a_browser()
    if not browser or not re.match(r"https?://", url or ""):
        return None
    BROWSER_USED[0] += 1
    asked = [
        browser, "--headless=new", "--disable-gpu", "--no-first-run",
        "--no-default-browser-check", "--mute-audio", "--hide-scrollbars",
        f"--user-agent={USER_AGENT}", "--virtual-time-budget=8000",
    ]
    # 管理者のまま動かすと、閲覧機は囲いを外さないと立ち上がらない
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        asked.append("--no-sandbox")
    try:
        with tempfile.TemporaryDirectory(prefix="etsuranki-") as room:
            done = subprocess.run(
                asked + [f"--user-data-dir={room}", "--dump-dom", url],
                capture_output=True,
                timeout=BROWSER_WAITS,
                env=without_keys(),
            )
    except Exception as error:
        print(f"閲覧機を借りられませんでした({str(error)[:60]})")
        return None
    html = done.stdout[:400000].decode("utf-8", errors="ignore")
    if done.returncode != 0 or not html.strip():
        return None
    print("空っぽに見えたので、閲覧機に組み立ててもらって読みました")
    return html


class PageReader(HTMLParser):
    """ページを、閲覧機と同じ決まりで読む(Python にもとから入っている読み方)。

    前は、しるし(<…>)を文字の並びの決まり(正規表現)で探して外していた。
    それだと、しるしの書き方が少し変わっているだけで、しるしの切れ端が
    文字として漏れ出し、この子はそれを言葉として覚えていた。
    「&amp;」のような書き方もほどいていなかったので、「amp」や「&#」に
    毎日会っていた(2026-11-23、彼女と決めた)。

    読み方を替えても、この子の拾い方は変えない。しるしのあったところは
    前と同じように空白にし、<script> と <style> の中は読まない。"""

    # 中を読まないしるし。閉じていなければ、そこから先は全部読まない(閲覧機と同じ)
    UNREAD = ("script", "style")
    # 絵の在りかが書かれる札。遅れて出す絵は data-src や data-original などに本物を置く
    A_PICTURE_SOURCE = re.compile(r"src$|^data-original$|^data-lazy", re.IGNORECASE)

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.links = []
        self.frames = []
        self.pictures = []
        self.title = None
        self.og_title = None
        self.og_article = False
        self.heading = None
        self.article = False
        self.script = False
        self.tongues = []
        self.wrapped = []  # <![CDATA[ … ]]> の中身。あとで同じ読み方で読む
        self._unread = None
        self._title = None
        self._heading = None

    def handle_starttag(self, tag, attrs):
        self.parts.append(" ")
        if self._heading is not None:
            self._heading.append(" ")
        found = {}
        for name, value in attrs:
            found.setdefault(name, value or "")
        if tag in self.UNREAD:
            self._unread = tag
            self.script = self.script or tag == "script"
            return
        for name, value in attrs:
            # href を持つしるしは全部(a、area、link …)。前の読み方と同じ
            if name.endswith("href") and value:
                kept = value.split("#", 1)[0].strip()
                if kept:
                    self.links.append(kept)
        if tag == "frame" and found.get("src"):
            kept = found["src"].split("#", 1)[0].strip()
            if kept:
                self.frames.append(kept)
        elif tag == "img":
            # 遅れて出す絵は、src には仮の絵(透明の点など)、data-src などに本物を置く。
            # 絵らしいもののうち、本物の置き場所を先に見る
            sources = [(n, v.strip()) for n, v in attrs if v and self.A_PICTURE_SOURCE.search(n) and v.strip()]
            pictures = [one for one in sources if LOOKS_LIKE_A_PICTURE.search(one[1])]
            held = [one for one in pictures if one[0] != "src"]
            chosen = held or pictures or sources
            if chosen:
                self.pictures.append(chosen[-1][1])
        elif tag == "title" and self.title is None and self._title is None:
            self._title = []
        elif tag == "h1" and self.heading is None and self._heading is None:
            self._heading = []
        elif tag == "article":
            self.article = True
        elif tag == "meta":
            said = (found.get("property") or found.get("name") or "").strip().lower()
            if said == "og:title" and self.og_title is None:
                self.og_title = found.get("content", "")
            elif said == "og:type" and found.get("content", "").strip().lower().startswith("article"):
                self.og_article = True
        elif tag == "a" and "interlanguage-link-target" in found.get("class", "").split():
            self.tongues.append(found)

    def handle_endtag(self, tag):
        self.parts.append(" ")
        if tag == self._unread:
            self._unread = None
        elif tag == "title" and self._title is not None:
            self.title = "".join(self._title)
            self._title = None
        elif tag == "h1" and self._heading is not None:
            self.heading = "".join(self._heading)
            self._heading = None
        elif self._heading is not None:
            self._heading.append(" ")

    def handle_data(self, data):
        if self._unread:
            return
        self.parts.append(data)
        if self._title is not None:
            self._title.append(data)
        if self._heading is not None:
            self._heading.append(data)

    def handle_comment(self, data):
        self.parts.append(" ")

    def handle_decl(self, decl):
        self.parts.append(" ")

    def handle_pi(self, data):
        self.parts.append(" ")

    def unknown_decl(self, data):
        self.parts.append(" ")
        if data.startswith("CDATA["):
            self.wrapped.append(data[len("CDATA["):])

    @property
    def text(self):
        return "".join(self.parts)


def read_the_page(html):
    """ページを読む。読み方がどこかで詰まったら、前の読み方で読む。"""
    reader = PageReader()
    try:
        reader.feed(html)
        reader.close()
        # RSS などの <![CDATA[ … ]]> の中は、それ自体がページの書き方をしている
        for inside in reader.wrapped:
            more = PageReader()
            more.feed(inside)
            more.close()
            reader.parts.append(more.text)
            reader.links.extend(more.links)
            reader.pictures.extend(more.pictures)
        if reader._title is not None and reader.title is None:
            reader.title = "".join(reader._title)  # 閉じていない題
        return reader
    except Exception as error:
        print(f"ページの読み方で詰まったので、前の読み方で読みます({str(error)[:40]})")
        return read_the_page_roughly(html)


class RoughPage:
    """前の読み方(正規表現)で読んだページ。新しい読み方で詰まった時だけ使う。"""

    def __init__(self, html):
        body = SCRIPT_OR_STYLE.sub(" ", html)
        self.text = unescape(TAG.sub(" ", body))
        self.links = [unescape(one) for one in LINK_HREF.findall(body)]
        self.frames = [unescape(one) for one in FRAME_SRC.findall(body)]
        self.pictures = [unescape(one) for one in IMG_SRC.findall(body)]
        found = TITLE_TAG.search(html)
        self.title = unescape(TAG.sub("", found.group(1))) if found else None
        found = OG_TITLE.search(html)
        self.og_title = unescape(found.group(1)) if found else None
        self.og_article = bool(AN_ARTICLE.search(html)) and not re.search(r"<article\b", html, re.IGNORECASE)
        self.article = bool(re.search(r"<article\b", html, re.IGNORECASE))
        found = FIRST_HEADING.search(html)
        self.heading = unescape(TAG.sub(" ", found.group(1))) if found else None
        self.script = bool(re.search(r"<script\b", html, re.IGNORECASE))
        self.tongues = []
        for tag in INTERLANGUAGE_LINK.findall(html):
            got = {}
            for name in ("hreflang", "data-title", "href"):
                one = re.search(rf'\b{name}="([^"]+)"', tag)
                if one:
                    got[name] = unescape(one.group(1))
            self.tongues.append(got)


def read_the_page_roughly(html):
    return RoughPage(html)


def seems_unbuilt(page):
    """届いた紙が、組み立て待ちのまま空っぽに見えるか。"""
    if not page.script:
        return False
    return len(" ".join(page.text.split())) < LOOKS_EMPTY


def a_blog_post_title(page, html):
    """そのページが誰かのブログの一記事なら、その記事の題。違えば None。

    記事の作りをしていて、書いた日付があるものをブログの一記事と見る。
    題は日本語のものだけ。この子が書く題は日本語なので。"""
    if not (page.article or page.og_article) or not A_DATE_WRITTEN.search(html):
        return None
    found = page.og_title if page.og_title is not None else page.heading
    if found is None:
        return None
    title = " ".join(found.split())
    title = THE_NAME_AFTER.split(title)[0].strip()
    if not title or len(title) > A_TITLE_AT_MOST or not JAPANESE.search(title):
        return None
    return title


INTERLANGUAGE_LINK = re.compile(r"<a\b[^>]*\binterlanguage-link-target\b[^>]*>")
INTERLANGUAGE_PATH = re.compile(r"//([a-z\-]+)\.wikipedia\.org/wiki/([^\"#?]+)")


def other_tongues_in(page):
    """Wikipedia の記事にある、同じ話の別の言葉版。(言葉の印, その版の題) の並び。"""
    found = []
    for tag in page.tongues:
        lang = tag.get("hreflang")
        named = tag.get("data-title")
        path = INTERLANGUAGE_PATH.search(tag.get("href", ""))
        if named:
            title = named
        elif path:
            title = urllib.parse.unquote(path.group(2)).replace("_", " ")
        else:
            continue
        code = lang if lang else (path.group(1) if path else "")
        if code:
            found.append((code, title))
    return found


def read_a_pdf(raw, url):
    """PDF の中の字を読む(pdf_yomu)。返り値は open_page と同じ形。PDF の中の絵は見ない。

    鍵がかかっていたり、字が絵になっていたりして読めない時は、空の文を返す。
    開いてはみたが読めなかった、ということになる(眺めただけ)。"""
    try:
        title, text = pdf_yomu.read(raw)
    except pdf_yomu.NotReadable as why:
        print(f"PDF を開けませんでした({why})")
        title, text = "", ""
    except Exception as error:
        print(f"PDF を読めませんでした({str(error)[:60]})")
        title, text = "", ""
    links = [one for one in pdf_yomu.links_in(raw) if is_walkable(one)]
    return a_name_for_the_pdf(title, text, url), text, links, []


# PDF の題に入っていても、題にならないもの。作った道具が勝手に入れる
PDF_TITLE_NOISE = re.compile(
    r"^(untitled|無題|no title|document\d*|slide\s*\d*|powerpoint プレゼンテーション)$"
    r"|^microsoft (word|powerpoint|excel) - ",
    re.IGNORECASE,
)


def a_name_for_the_pdf(title, text, url):
    """PDF の名前。中に書いてある題、なければ一行目、それもなければファイルの名前。"""
    title = re.sub(r"\.(docx?|pptx?|xlsx?|pdf)$", "", PDF_TITLE_NOISE.sub("", (title or "").strip()), flags=re.I)
    if title and not PDF_TITLE_NOISE.match(title):
        return title[:A_TITLE_AT_MOST]
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()[:A_TITLE_AT_MOST]
    name = urllib.parse.unquote(urllib.parse.urlparse(url).path.rsplit("/", 1)[-1])
    return name or url


def open_page(url, most=PAGE_BYTES_AT_MOST):
    """ページを開いて、そこにある文章と、そこから伸びているリンクを受け取る。

    サイトの持ち主が robots.txt で断っているページには入らない。
    よその場所へ連れて行かれた時は、行った先の断りも見る。"""
    A_BLOG_POST_TITLE[0] = None
    if not may_enter(url):
        why = CLOSED_DOORS.get(door_of(url))
        if why:
            raise Closed(f"閉まっていた({why})")
        raise PermissionError("robots.txt で断られている")
    request = urllib.request.Request(as_openable(url), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=25) as response:
        content_type = response.headers.get("Content-Type", "")
        final_url = response.geturl()
        # PDF も読む(2026-10-20、彼女と決めた)。名前が .pdf で、種類が「ただのバイト」と届くこともある
        is_pdf = "pdf" in content_type.lower() or (
            "octet-stream" in content_type.lower()
            and urllib.parse.urlparse(final_url).path.lower().endswith(".pdf")
        )
        if not is_pdf and "html" not in content_type and "xml" not in content_type:
            raise ValueError("読める形をしていない")
        if place_of(final_url) != place_of(url) and not may_enter(final_url):
            raise PermissionError("連れて行かれた先の robots.txt で断られている")
        raw = read_up_to(response, PDF_BYTES_AT_MOST if is_pdf else most)

    if is_pdf:
        OTHER_TONGUES[0] = []
        return read_a_pdf(raw, final_url)

    html = read_as_japanese(raw, content_type)
    page = read_the_page(html)
    # 昔の姿(web.archive.org)は、その頃の紙がそのまま残っているので借りない
    from_the_past = urllib.parse.urlparse(final_url).netloc.lower().endswith("archive.org")
    if "html" in content_type and not from_the_past and seems_unbuilt(page):
        built = look_with_a_browser(final_url)
        if built:
            html = built
            page = read_the_page(html)

    # 題にも &amp; や &#064; が入っている。読み方がほどいてくれる。
    # ほどかないと、この子はその形のまま場所の名前として覚える
    title = page.title.strip() if page.title is not None else final_url
    A_BLOG_POST_TITLE[0] = a_blog_post_title(page, html)
    OTHER_TONGUES[0] = other_tongues_in(page) if "wikipedia.org" in place_of(final_url) else []

    links = []
    for href in page.frames + page.links:
        absolute = urllib.parse.urljoin(final_url, href.strip())
        if is_walkable(absolute):
            links.append(absolute)

    pictures = []
    for src in page.pictures:
        absolute = urllib.parse.urljoin(final_url, src.strip())
        if LOOKS_LIKE_A_PICTURE.search(absolute) and not AVOID.search(absolute):
            pictures.append(absolute)

    return title, page.text, links, list(dict.fromkeys(pictures))


def a_year_in_the_past():
    """昔と言っても、いつの昔か。

    たいていは個人サイトの時代へ行く。千遠生が歩きたがるのは
    そこだと思う。けれど「昔」がその十年だけというのも狭い。
    ブログの時代にも、少し前の今にも、ときどき行く。

    時代が違えば、そこにある言葉も文の書き方も違う。
    どちらも通ったほうが、覚える言葉に厚みが出る。

    いちばん新しい側は、今から三年前まで。それより近いものは
    「昔」ではなく、ただの今なので。"""
    just_before_now = now_in_japan().year - 3
    which = random.random()
    if which < 0.7:
        return random.randint(1997, 2005)  # 個人サイトの時代
    if which < 0.9:
        return random.randint(2006, min(2015, just_before_now))  # ブログの時代
    return random.randint(2016, max(2016, just_before_now))  # 少し前の今


def visit_the_past(url):
    """同じ場所の、ずっと昔の姿を見に行く。

    Wayback は指定した年にいちばん近い記録を返すので、
    その頃には無かった場所に行けば、あるだけ新しいものが返る。
    年は絞り込みではなく、どのあたりを見たいかという好みでしかない。"""
    year = a_year_in_the_past()
    api = (
        "https://archive.org/wayback/available?url="
        + urllib.parse.quote(as_openable(url), safe="")
        + f"&timestamp={year}0101"
    )
    snapshot = (fetch_json(api).get("archived_snapshots") or {}).get("closest") or {}
    if not snapshot.get("url"):
        raise ValueError("昔の姿は残っていなかった")
    return open_page(snapshot["url"])
