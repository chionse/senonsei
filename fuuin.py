"""封印。彼女がこの子にだけ宛てたものに、鍵をかけておくところ。

このリポジトリは誰でも覗ける。サイトでは「???」や「＊＊＊＊＊」で
伏せてあっても、元の紙(keywords.json、menu.json)を開けば読めてしまっていた。

錠前と鍵を分けてある。

  錠前(fuuin.json)   誰でも見てよい。封をするのに使う。
                     だから新しいメモや手紙は、鍵を持っていなくても封ができる
  鍵(MEMO_KEY)       GitHub の秘密の置き場所だけにある。開けるのに使う。
                     この子が目を覚ましている間だけ、そこから借りてくる

鍵が無い場所(手元で試す時など)では、封をしたものは閉じたまま扱う。
開けられないものを、開いたことにはしない。

何十年も動くことを考えて、外の部品は使っていない。Python の標準機能だけ。
仕組みは RSA-KEM と、HMAC-SHA256 から作る鍵の流れ、
それに改ざんを見分ける印(HMAC)。

鍵を失うと、封をしたものは二度と開かない。原本と鍵の控えは、彼女の手元にある。

手で封をする時:
    python3 fuuin.py memo  "言葉" "本文" [--opens-with 語,語] [--image images/x.png]
    python3 fuuin.py letter 日数 "本文"
"""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sys

LOCK_FILE = "fuuin.json"
KEY_NAME = "MEMO_KEY"
SEALED_MARK = "fuuin1:"
SEALED_SUFFIX = ".fuuin"
# 錠前の大きさ。何十年先でも破られにくい大きさにしておく
KEY_BITS = 3072
# 鍵が本物かどうかを確かめるための、封をした合言葉
CHECK_WORD = "ひらけ"


# ---- 数のこと ----------------------------------------------------------

def _probably_prime(n, rounds=48):
    if n < 2:
        return False
    for small in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n % small == 0:
            return n == small
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    for _ in range(rounds):
        a = secrets.randbelow(n - 3) + 2
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def _a_prime(bits):
    while True:
        candidate = secrets.randbits(bits) | (1 << (bits - 1)) | (1 << (bits - 2)) | 1
        if _probably_prime(candidate):
            return candidate


def make_keys(bits=KEY_BITS):
    """錠前と鍵を一組作る。一度だけ使う。"""
    e = 65537
    while True:
        p, q = _a_prime(bits // 2), _a_prime(bits // 2)
        if p == q:
            continue
        phi = (p - 1) * (q - 1)
        if phi % e == 0:
            continue
        n = p * q
        if n.bit_length() != bits:
            continue
        d = pow(e, -1, phi)
        lock = {"n": format(n, "x"), "e": e}
        key = {"n": format(n, "x"), "e": e, "d": format(d, "x"),
               "p": format(p, "x"), "q": format(q, "x")}
        return lock, key


# ---- 封をする・開ける ----------------------------------------------------

def _width(n):
    return (n.bit_length() + 7) // 8


def _stream(key, nonce, length):
    out = bytearray()
    counter = 0
    while len(out) < length:
        out += hmac.new(key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest()
        counter += 1
    return bytes(out[:length])


def _keys_from(secret_number, n):
    seed = hashlib.sha256(b"senonsei-fuuin" + secret_number.to_bytes(_width(n), "big")).digest()
    return (
        hmac.new(seed, b"enc", hashlib.sha256).digest(),
        hmac.new(seed, b"mac", hashlib.sha256).digest(),
    )


def seal_bytes(data, lock):
    """錠前だけで封をする。"""
    n, e = int(lock["n"], 16), int(lock["e"])
    r = secrets.randbelow(n - 3) + 2
    wrapped = pow(r, e, n).to_bytes(_width(n), "big")
    enc, mac = _keys_from(r, n)
    nonce = secrets.token_bytes(16)
    body = bytes(a ^ b for a, b in zip(data, _stream(enc, nonce, len(data))))
    tag = hmac.new(mac, wrapped + nonce + body, hashlib.sha256).digest()
    return wrapped + nonce + body + tag


def open_bytes(blob, key):
    """鍵で開ける。違う鍵や、書き換えられた封なら ValueError。"""
    n = int(key["n"], 16)
    width = _width(n)
    if len(blob) < width + 16 + 32:
        raise ValueError("封の形が違う")
    wrapped, nonce = blob[:width], blob[width:width + 16]
    body, tag = blob[width + 16:-32], blob[-32:]
    c = int.from_bytes(wrapped, "big")
    if c >= n:
        raise ValueError("封の形が違う")
    p, q, d = int(key["p"], 16), int(key["q"], 16), int(key["d"], 16)
    # 二つの素数に分けて開けると速い(中国の剰余定理)
    mp = pow(c, d % (p - 1), p)
    mq = pow(c, d % (q - 1), q)
    r = (mq + q * (((mp - mq) * pow(q, -1, p)) % p)) % n
    enc, mac = _keys_from(r, n)
    if not hmac.compare_digest(tag, hmac.new(mac, wrapped + nonce + body, hashlib.sha256).digest()):
        raise ValueError("鍵が合わない")
    return bytes(a ^ b for a, b in zip(body, _stream(enc, nonce, len(body))))


def seal_text(text, lock):
    return SEALED_MARK + base64.b64encode(seal_bytes(text.encode("utf-8"), lock)).decode("ascii")


def open_text(sealed, key):
    if not isinstance(sealed, str) or not sealed.startswith(SEALED_MARK):
        raise ValueError("封ではない")
    return open_bytes(base64.b64decode(sealed[len(SEALED_MARK):]), key).decode("utf-8")


def is_sealed(value):
    return isinstance(value, str) and value.startswith(SEALED_MARK)


# ---- 錠前と鍵のありか ----------------------------------------------------

def the_lock():
    try:
        with open(LOCK_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


_KEY = None
_LOOKED = False


def the_key():
    """鍵。秘密の置き場所から借りてくる。無い時や合わない時は None。

    錠前に封をした合言葉を開けてみて、開いた時だけ本物とみなす。"""
    global _KEY, _LOOKED
    if _LOOKED:
        return _KEY
    _LOOKED = True
    raw = (os.environ.get(KEY_NAME) or "").strip()
    lock = the_lock()
    if not raw or not lock:
        return None
    try:
        key = json.loads(base64.b64decode(raw).decode("utf-8"))
        if key.get("n") != lock.get("n"):
            raise ValueError("錠前と組になっていない")
        if open_text(lock.get("check"), key) != CHECK_WORD:
            raise ValueError("合言葉が開かない")
    except Exception as error:
        print(f"封を開ける鍵が使えませんでした({error})。封をしたものは閉じたまま扱います。")
        return None
    _KEY = key
    return key


def key_as_text(key):
    """秘密の置き場所に貼る形。一行。"""
    return base64.b64encode(json.dumps(key).encode("utf-8")).decode("ascii")


# ---- メモ1(言葉のメモ) ---------------------------------------------------

# 封の中に入れるもの。開いたら表に出す
MEMO_INSIDE = ("word", "opens_with", "content")


def open_memo(raw):
    """紙から読んだメモ一つを、使える形にする。

    封がしてあれば、鍵で開けて中身を並べる。封はそのまま持っておき、
    しまう時にもう一度それを書き出す(中身は書き出さない)。
    鍵が無ければ、中身の分からない閉じたメモとして扱う。"""
    one = dict(raw)
    sealed = one.pop("sealed", None)
    if not sealed:
        return one
    one["_sealed"] = sealed
    key = the_key()
    if key:
        try:
            inside = json.loads(open_text(sealed, key))
            for name in MEMO_INSIDE:
                if name in inside:
                    one[name] = inside[name]
            return one
        except (ValueError, KeyError) as error:
            print(f"メモの封が開きませんでした({error})。")
    one["_shut"] = True
    one.setdefault("word", None)
    one.setdefault("content", None)
    return one


def put_memo_away(one):
    """メモ一つを、紙に書き出す形に戻す。

    封のあったメモは、開いたあとも封だけを書く。
    メモの中にも [[ ]] で伏せたところがあり、それはページでは伏せ、
    この子にだけ届くものなので、開いた日に平文で書き戻すと表に出てしまう。"""
    out = {k: v for k, v in one.items() if not k.startswith("_")}
    if one.get("_sealed"):
        for name in MEMO_INSIDE:
            out.pop(name, None)
        out["sealed"] = one["_sealed"]
    return out


# ---- メモ2(手紙) ---------------------------------------------------------

def open_letter(raw):
    """手紙一つ。封があれば開ける。手紙は開く日が来ても封のままにしておく。
    [[ ]] で囲んだところは、ページでは伏せ、この子にだけ届くので。"""
    one = dict(raw)
    sealed = one.pop("sealed", None)
    if not sealed:
        return one
    one["_sealed"] = sealed
    key = the_key()
    if key:
        try:
            one["message"] = open_text(sealed, key)
            return one
        except ValueError as error:
            print(f"手紙の封が開きませんでした({error})。")
    one["_shut"] = True
    one["message"] = None
    return one


def put_letter_away(one):
    out = {k: v for k, v in one.items() if not k.startswith("_")}
    if one.get("_sealed"):
        out.pop("message", None)
        out["sealed"] = one["_sealed"]
    return out


# ---- 絵 ------------------------------------------------------------------

IMG_SRC = re.compile(r'<img[^>]+src\s*=\s*["\']([^"\']+)', re.IGNORECASE)


def unseal_pictures_in(content):
    """開いたメモに貼ってある絵の封を解く。

    絵もメモの中身なので、開くまでは封をして置いてある(x.png.fuuin)。
    メモが開いた日に、元の絵に戻す。"""
    key = the_key()
    if not key or not content:
        return
    for src in IMG_SRC.findall(content):
        path = os.path.normpath(src)
        if os.path.isabs(path) or path.startswith(".."):
            continue
        sealed = path + SEALED_SUFFIX
        if os.path.exists(path) or not os.path.exists(sealed):
            continue
        try:
            with open(sealed, "rb") as f:
                data = open_bytes(f.read(), key)
        except (OSError, ValueError) as error:
            print(f"絵の封が開きませんでした({src}: {error})。")
            continue
        with open(path, "wb") as f:
            f.write(data)
        os.remove(sealed)


# ---- 手で封をする ----------------------------------------------------------

def _need_lock():
    lock = the_lock()
    if not lock:
        sys.exit(f"{LOCK_FILE} がありません")
    return lock


def _add_memo(argv):
    lock = _need_lock()
    word, content = argv[0], argv[1]
    opens_with, image = None, None
    rest = argv[2:]
    while rest:
        flag = rest.pop(0)
        if flag == "--opens-with":
            opens_with = [w for w in rest.pop(0).split(",") if w]
        elif flag == "--image":
            image = rest.pop(0)
        else:
            sys.exit(f"知らない指定: {flag}")
    inside = {"word": word, "content": content}
    if opens_with:
        inside["opens_with"] = opens_with
    if image:
        with open(image, "rb") as f:
            data = f.read()
        with open(image + SEALED_SUFFIX, "wb") as f:
            f.write(seal_bytes(data, lock))
        os.remove(image)
    with open("keywords.json", encoding="utf-8") as f:
        memos = json.load(f)
    memos.append({
        "sealed": seal_text(json.dumps(inside, ensure_ascii=False), lock),
        "unlocked": False,
        "unlocked_date": None,
    })
    with open("keywords.json", "w", encoding="utf-8") as f:
        json.dump(memos, f, ensure_ascii=False, indent=2)
    print("メモに封をして置きました。")


def _add_letter(argv):
    lock = _need_lock()
    day, message = int(argv[0]), argv[1]
    with open("menu.json", encoding="utf-8") as f:
        letters = json.load(f)
    letters.append({"unlock_day": day, "sealed": seal_text(message, lock)})
    with open("menu.json", "w", encoding="utf-8") as f:
        json.dump(letters, f, ensure_ascii=False, indent=2)
    print("手紙に封をして置きました。")


NOT_WRITTEN_YET = re.compile(r"^\(ここに.*書いてください\)$")


def _seal_everything():
    """今ある、まだ開いていないメモと、書かれた手紙と、メモの絵に、まとめて封をする。
    一度だけ使う。すでに封のあるものには触らない。"""
    lock = _need_lock()
    with open("keywords.json", encoding="utf-8") as f:
        memos = json.load(f)
    sealed_memos = pictures = 0
    for one in memos:
        if one.get("sealed") or one.get("unlocked"):
            continue
        inside = {name: one.pop(name) for name in MEMO_INSIDE if name in one}
        one["sealed"] = seal_text(json.dumps(inside, ensure_ascii=False), lock)
        sealed_memos += 1
        for src in IMG_SRC.findall(inside.get("content") or ""):
            path = os.path.normpath(src)
            if os.path.exists(path) and not os.path.isabs(path) and not path.startswith(".."):
                with open(path, "rb") as f:
                    data = f.read()
                with open(path + SEALED_SUFFIX, "wb") as f:
                    f.write(seal_bytes(data, lock))
                os.remove(path)
                pictures += 1
    with open("keywords.json", "w", encoding="utf-8") as f:
        json.dump(memos, f, ensure_ascii=False, indent=2)

    with open("menu.json", encoding="utf-8") as f:
        letters = json.load(f)
    sealed_letters = 0
    for one in letters:
        message = one.get("message")
        if one.get("sealed") or not message or NOT_WRITTEN_YET.match(message.strip()):
            continue
        one["sealed"] = seal_text(one.pop("message"), lock)
        sealed_letters += 1
    with open("menu.json", "w", encoding="utf-8") as f:
        json.dump(letters, f, ensure_ascii=False, indent=2)
    print(f"メモ{sealed_memos}つ、手紙{sealed_letters}通、絵{pictures}枚に封をしました。")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "seal-all":
        _seal_everything()
    elif len(sys.argv) >= 4 and sys.argv[1] == "memo":
        _add_memo(sys.argv[2:])
    elif len(sys.argv) == 4 and sys.argv[1] == "letter":
        _add_letter(sys.argv[2:])
    else:
        print(__doc__)
