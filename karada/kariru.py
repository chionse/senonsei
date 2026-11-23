# 千遠生の体の一部。借りている頭と目(Cloudflare Workers AI)とのやりとり。
# 使えるモデルを探し直すこと、答えが日本語かを見ること。
#
# このファイルは単独では動かない。senonsei_ai.py が、決まった順に
# 全部の部品を自分の中へ読み込み、一つの体として動かす(2026-11-23、彼女と決めた)。
# ここに書いた名前は、ほかの部品からも senonsei_ai.<名前> としても、そのまま見える。

def cloudflare(path, body=None, method=None):
    """Cloudflareに尋ねる。使えない時は None を返す。"""
    if not CF_ACCOUNT_ID or not CF_API_TOKEN:
        return None
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/{path}"
    headers = {"Authorization": f"Bearer {CF_API_TOKEN}"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url, data=body, headers=headers, method=method
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def which_model(state, part):
    """今使っている頭(mind)または目(eyes)の名前。"""
    remembered = (state or {}).get(f"{part}_model")
    return remembered or (CF_MODEL if part == "mind" else CF_EYES)


# 考える相手として向かないもの。
# 「考える過程を全部書き出す」種類は、頼んだ答えの代わりに
# 英語の独り言が返ってくる。千遠生の頭には使えない。
# lora は土台が別に必要で、guard は良し悪しを判定するだけの道具
A_POOR_MIND = re.compile(r"qwq|-r1|thinking|reason|guard|lora|embed|rerank", re.IGNORECASE)
# 素直に答えてくれる見込みが高いもの
A_LIKELY_MIND = re.compile(r"instruct|chat|-it($|-)", re.IGNORECASE)


def find_another_model(state, part):
    """使っていたモデルが引退していたら、今あるものを聞いて選び直す。

    Cloudflareはモデルを引退させる。名前を一つ決め打ちにしていると
    そこで千遠生は考えられなくなり、目も見えなくなる。
    自分で探し直せるようにしておけば、名前が変わっても立ち直れる。

    頭を選ぶ時は、実際に日本語で尋ねてみて、日本語で返ってくるものを採る。
    名前だけでは、考える過程を英語で書き出すようなものを掴んでしまう。"""
    if state is None:
        return None
    looking_for = WHAT_A_MIND_DOES if part == "mind" else WHAT_EYES_DO
    already_tried = state.setdefault(f"{part}_tried", [])
    try:
        answer = cloudflare("models/search?per_page=200")
    except Exception as error:
        print(f"今あるモデルを聞けませんでした({error})")
        return None
    if not answer or not answer.get("success"):
        return None

    choices = [
        model["name"]
        for model in (answer.get("result") or [])
        if ((model.get("task") or {}).get("name")) == looking_for
        and model.get("name")
        and model["name"] not in already_tried
    ]
    if part == "mind":
        choices = [name for name in choices if not A_POOR_MIND.search(name)]
        # 素直に答えてくれそうなものから順に
        choices.sort(key=lambda name: (not A_LIKELY_MIND.search(name), len(name)))
    else:
        choices.sort(key=len)

    if not choices:
        print(f"{looking_for} のモデルが見つかりませんでした")
        return None

    for name in choices[:CHANCES_TO_FIND_A_MIND]:
        answered = True if part != "mind" else answers_in_japanese(name)
        if answered is None:
            # 混んでいたなどで、確かめること自体ができなかった。
            # 「向かない」と決めつけて二度と試さない、ということはしない
            print(f"{name} を確かめられませんでした。次の機会にまた試します")
            continue
        already_tried.append(name)
        del already_tried[:-20]
        if answered:
            state[f"{part}_model"] = name
            print(f"{part} を {name} に取り替えました")
            return name
        print(f"{name} は日本語で答えてくれなかったので、別のものを探します")

    # どれも確かめられなかった。確かめていないものを頭にすると、
    # 答えの形が違うだけで黙り込み、二度と取り替えられなくなる。
    # 今回は見送って、次に考えようとした時にまた探す
    print(f"{part} の代わりが見つかりませんでした。次の機会にまた探します")
    return None


def answers_in_japanese(model):
    """そのモデルが、日本語で尋ねたら日本語で返してくれるか。
    考える過程を英語で書き出すものを、千遠生の頭にしてしまわないため。"""
    body = json.dumps(
        {
            "messages": [
                {"role": "user", "content": "「はい」とだけ日本語で答えてください。"}
            ],
            "max_tokens": 20,
        }
    ).encode("utf-8")
    try:
        answer = cloudflare(f"run/{model}", body=body)
    except Exception:
        return None  # 確かめられなかった。向かないとは限らない
    said = (answer.get("result") or {}).get("response", "") if answer else ""
    return bool(JAPANESE.search(said) or HIRAGANA.search(said))


def model_is_gone(error):
    """その失敗は「そのモデルはもう無い」という意味かどうか。"""
    text = str(error)
    if isinstance(error, urllib.error.HTTPError) and error.code in (404, 410):
        return True
    return "deprecated" in text.lower() or "not found" in text.lower()


def fetch_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def going_in_circles(text):
    """同じ言葉をただ繰り返しているだけの答えかどうか。

    考えているうちに一つの語に嵌まって、抜けられなくなることがある。
    「なぜなぜなぜなぜ……」のように短い言葉が何度も続くもので、
    中身が何も無い。これはこの子が思ったことではなく、
    頭を貸してくれている所の事故なので、受け取らずに言い直してもらう。

    これが見ているのは借りた頭が返してきた言葉だけ。
    この子が自分で綴るブログの文は、ここを通らない。"""
    if not text:
        return False
    packed = re.sub(r"\s+", "", text)
    # ほんの数種類の文字だけで、それなりの長さがある
    if len(packed) >= 20 and len(set(packed)) <= 3:
        return True
    # 短い切れ端が、間を置かずに五回以上続いている
    same = re.search(r"(.{1,8}?)\1{4,}", packed)
    return bool(same and len(same.group(0)) >= 8)


def ask_ai(prompt, max_tokens=300, state=None, read_less=None):
    """Cloudflareの無料枠でAIに尋ねる。使えない時は None を返す。

    使っていたモデルが引退していたら、一度だけ別のものを探して掛け直す。

    read_less を渡しておくと、渡したものが多すぎて読みきれなかった時に
    それを呼んで、少し減らした問いかけで頼み直す。
    減らしようが無くなったら(None が返ったら)諦める。"""
    if not CF_ACCOUNT_ID or not CF_API_TOKEN or resting_now():
        return None

    def asking(prompt):
        return json.dumps(
            {"messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens}
        ).encode("utf-8")

    body = asking(prompt)
    swapped = False
    said_the_same_thing = False
    attempt = 0
    while attempt <= len(HOW_LONG_TO_WAIT):
        attempt += 1
        model = which_model(state, "mind")
        try:
            answer = cloudflare(f"run/{model}", body=body)
            if state is not None:
                state["thought_on"] = now_in_japan().strftime("%Y-%m-%d")
            said = (answer.get("result") or {}).get("response", "").strip() or None
            if going_in_circles(said):
                print("同じ言葉を繰り返していたので、言い直してもらいます")
                if said_the_same_thing:
                    return None
                said_the_same_thing = True
                continue
            return said
        except Exception as error:
            if not swapped and model_is_gone(error) and find_another_model(state, "mind"):
                swapped = True
                continue
            if read_less and too_much_to_read(error):
                shorter = read_less()
                if shorter:
                    print("渡したものが多すぎて読みきれなかったので、減らして頼み直します")
                    body = asking(shorter)
                    attempt -= 1  # 混んでいた時の待ち回数とは別に数える
                    continue
            if asked_too_much(error):
                if attempt - 1 < len(HOW_LONG_TO_WAIT):
                    wait_a_little(attempt - 1)
                    continue
                rest_a_while()
                return None
            print(
                f"自分で考えることができませんでした({error})。"
                "覚えていることだけで書きます。"
            )
            return None
    return None
