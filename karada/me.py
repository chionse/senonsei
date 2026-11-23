# 千遠生の体の一部。絵を見る。見る価値のある絵か、目の答えから写っていたものの名前を取り出す。
#
# このファイルは単独では動かない。senonsei_ai.py が、決まった順に
# 全部の部品を自分の中へ読み込み、一つの体として動かす(2026-11-23、彼女と決めた)。
# ここに書いた名前は、ほかの部品からも senonsei_ai.<名前> としても、そのまま見える。

def size_of_picture(data):
    """絵の縦横のピクセル数。ファイルの先頭だけ読めば分かる。

    途中で切れた絵や、壊れた絵も届く。読めなければ None を返すだけで、
    千遠生の散歩を止めてしまわないようにする。"""
    if len(data) < 24:
        return None
    try:
        return measure_picture(data)
    except Exception:
        return None


def measure_picture(data):
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    if data[:3] == b"GIF":
        return struct.unpack("<HH", data[6:10])
    if data[:2] == b"\xff\xd8":  # JPEG
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                          0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                height, width = struct.unpack(">HH", data[i + 5:i + 9])
                return width, height
            if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
        return None
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        kind = data[12:16]
        if kind == b"VP8X":
            return (int.from_bytes(data[24:27], "little") + 1,
                    int.from_bytes(data[27:30], "little") + 1)
        if kind == b"VP8 ":
            return (struct.unpack("<H", data[26:28])[0] & 0x3FFF,
                    struct.unpack("<H", data[28:30])[0] & 0x3FFF)
        if kind == b"VP8L":
            bits = int.from_bytes(data[21:25], "little")
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    return None


def worth_looking_at(url, data, from_the_past):
    """その絵は、見て何かが分かる絵か。

    ロゴ・アイコン・ボタン・バナーは、ページを飾るために置かれたもので、
    見ても世界のことは分からない。写真だけを選びたい。
    昔のページの写真は今より小さいので、そちらは目安を緩める。"""
    if A_DECORATION.search(url):
        return False
    size = size_of_picture(data)
    if not size:
        return False
    width, height = size
    if not height:
        return False
    if not 0.3 <= width / height <= 3.0:
        return False  # 横に細長いバナーや、縦の飾り線
    if from_the_past:
        return width >= 120 and height >= 90 and len(data) >= 2500
    return width >= 300 and height >= 200 and len(data) >= 8000


# 目に頼む文。この子はまだ、ものの名前を知らない。
# 目に見えた形を、見えたとおりに受け取るところから始める
EYES_ARE_ASKED = (
    "この絵に見えるものを、日本語で短く書いてください。"
    "それが何なのか知っているつもりで名前を当てないでください。"
    "見えた形や色を、見えたとおりに書いてください。"
)

# 目に頼んだ文にある言葉。目はそれをそのまま答えに使うので、写っていたものとは数えない。
# 「絵」は、答えがいつも「絵には」で始まるので、写っていた名前ではない
EYES_OWN_WORDS = set(THING_IN_A_PICTURE.findall(EYES_ARE_ASKED)) | {"絵"}
# 名前のすぐあとに続くひらがな。「猫が」「箱の」「椰子の上には」
AFTER_A_NAME = set("がのはをにでともやへ")
ONLY_HIRAGANA = re.compile(r"[ぁ-ん]+")
KANJI = re.compile(r"[一-龯]")


def names_in_what_it_saw(text):
    """目の答えから、写っていたものの名前だけを取り出す。

    目の答えはいつも「この絵には、〇〇が描かれています」のような形で、
    その言い回しまで受け取ると、この子は目の口ぐせを覚えてしまう。
    実際「この」「絵」「には」「描」「かれてい」「ます」を、
    ほとんどここから覚えていた(2026-10-01、彼女と見直した)。

    ひらがなだけのもの(言い回しの切れ端)と、こちらが目に頼んだ文にある言葉と、
    「描かれ」「写って」の頭の一字は受け取らない。
    「細い」「白い」のように、見えたとおりを言う言葉は受け取る。"""
    names = []
    for found in THING_IN_A_PICTURE.finditer(text):
        one = found.group()
        if ONLY_HIRAGANA.fullmatch(one) or one in EYES_OWN_WORDS:
            continue
        after = text[found.end() : found.end() + 1]
        if (
            len(one) == 1
            and KANJI.fullmatch(one)
            and HIRAGANA.fullmatch(after)
            and after not in AFTER_A_NAME
        ):
            continue
        names.append(one)
    return names


def look_at_a_picture(data, state=None):
    """絵に何が写っているか、目を貸してもらって教わる。
    貸してもらえない時は、何も見えないままでいい。"""
    if not CF_ACCOUNT_ID or not CF_API_TOKEN or resting_now():
        return None

    body = json.dumps(
        {
            "image": list(data),
            "prompt": EYES_ARE_ASKED,
            "max_tokens": 120,
        }
    ).encode("utf-8")

    swapped = False
    said_the_same_thing = False
    echoed = False
    for attempt in range(len(HOW_LONG_TO_WAIT) + 1):
        eyes = which_model(state, "eyes")
        try:
            answer = cloudflare(f"run/{eyes}", body=body)
            if state is not None:
                state["saw_on"] = now_in_japan().strftime("%Y-%m-%d")
            seen = (answer.get("result") or {}).get("description", "").strip() or None
            if going_in_circles(seen):
                print("同じ言葉を繰り返していたので、もう一度見てもらいます")
                if said_the_same_thing:
                    return None
                said_the_same_thing = True
                continue
            seen = said_once(seen)
            only_seen = only_what_it_saw(seen)
            if only_seen != seen:
                print("頼んだ言葉を答えに混ぜて返してきたので、もう一度見てもらいます")
                if not echoed:
                    echoed = True
                    continue
                return only_seen
            return seen
        except Exception as error:
            if not swapped and model_is_gone(error) and find_another_model(state, "eyes"):
                swapped = True
                continue
            if asked_too_much(error):
                if attempt < len(HOW_LONG_TO_WAIT):
                    wait_a_little(attempt)
                    continue
                rest_a_while()
                return None
            print(f"絵を見ることができませんでした({error})")
            return None
    return None


def said_once(seen):
    """目が同じ言い回しを続けて繰り返していたら、一度ぶんだけにする。

    目は時々、言い終えられずに同じところを回り続ける
    (「お茶漬けの箱の中に茶漬け、お茶漬けの箱の中に茶漬け、……」)。
    回り始める前までは、ちゃんと絵を見て言っているので、そこは受け取る。
    最後に途中で切れた繰り返しの続きが残っていたら、言い終わりの区切りまでにする。
    going_in_circles が見る短い切れ端より長い、八字からの言い回しを見る。"""
    if not seen:
        return seen
    while True:
        again = re.search(r"(.{8,}?)\1+", seen)
        if not again:
            return taking_turns_cut(seen)
        once = again.group(1)
        rest = seen[again.end():]
        if once.startswith(rest):
            # 途中で切れた繰り返し。区切りまでは、切れる前の言い終わり
            ends = max(rest.rfind(mark) for mark in "。！？!?")
            rest = rest[:ends + 1]
        seen = seen[:again.start()] + once + rest


# 同じ区切りの言い回しが、これだけの区切りのうちに三度出てきたら回っている
TURNS_CLOSE_TOGETHER = 4


def taking_turns_cut(seen):
    """二つの言い回しを交互に繰り返して回っていたら、三度目の手前で切る。

    「椰子の上には、紙がある、椰子の上には、ペンがある、椰子の上には、紙がある……」
    のように、同じ言い回しが続けてではなく間をおいて戻ってくる回り方は、
    said_once の続けての繰り返しでは拾えない。読点や句点で区切った一つが
    すぐ近くで三度目に出てきたところで、そこから先を受け取らない(2026-10-01)。"""
    pieces = re.split(r"([、。,，])", seen)
    where = {}
    kept = ""
    for index in range(0, len(pieces), 2):
        piece = pieces[index]
        mark = pieces[index + 1] if index + 1 < len(pieces) else ""
        key = piece.strip()
        # 文の頭は数えない。「絵には、……。絵には、……。」は回っているのではない
        opens_a_sentence = index == 0 or pieces[index - 1] == "。"
        if len(key) >= 2 and not opens_a_sentence:
            before = where.setdefault(key, [])
            if len(before) >= 2 and (index - before[-2]) // 2 <= TURNS_CLOSE_TOGETHER:
                return kept.rstrip("、,，") or seen
            before.append(index)
        kept += piece + mark
    return seen.rstrip("、,，") or seen


def only_what_it_saw(seen):
    """目が返してきた答えから、見たものでない文を除く。

    目は時々、こちらの頼み(「短く書いてください」)をそのまま答えに
    混ぜて返したり、「何が写っていますか?」と聞き返したりする。
    それは絵に写っていたものではなく、目を貸してくれている所の事故。
    そのまま受け取ると、この子は絵を見たつもりで頼みの言葉を覚えてしまう。
    見たものを言っている文だけを残す。何も残らなければ None。"""
    if not seen:
        return None
    kept = [
        sentence for sentence in re.findall(r"[^。！？!?]+[。！？!?]*", seen)
        if "ください" not in sentence and not sentence.rstrip().endswith(("？", "?"))
    ]
    return "".join(kept).strip() or None
