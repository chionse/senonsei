"""PDF を読む(2026-10-20、彼女と決めた)。

論文や資料は PDF で置かれていることが多い。今までは「読める形をしていない」と
引き返していた。外の道具は使わない決まりなので、標準の部品だけで、
PDF の中から文字を取り出す。

読めるのは、文字が文字として入っている PDF。
- 紙をスキャンしただけのもの(字が絵になっている)は読めない
- 鍵がかかっているものは開けない
- 字の対応表が入っていないもの(日本語の字の番号だけが並んでいるもの)は読めない
読めなかった時は、空の文を返す。読めたふりはしない。

取り出し方のあらまし:
1. 中の部品(「12 0 obj … endobj」)を探して、番号で引けるようにする。
   部品をまとめて詰めた箱(ObjStm)も開ける
2. 目次(Catalog → Pages)を辿って、ページを順に並べる
3. ページごとに、書き込みの手順(content stream)を読む。
   字を置く命令(Tj、TJ、'、")のところで、字の番号を字に戻す。
   戻し方は字ごとの対応表(ToUnicode)、なければ決まった並び(WinAnsi、Shift_JIS など)
4. 行が変わったところで改行を入れる
"""

import re
import time
import unicodedata
import zlib

# 読むページの数と字の数には上限を置く。何百ページもある本を、一度に全部は読まない
PAGES_AT_MOST = 80
CHARS_AT_MOST = 200000
SECONDS_AT_MOST = 30


class NotReadable(Exception):
    """この PDF は読めない(鍵がかかっている、壊れている、など)。"""


class Name(str):
    """/Font のような名前。ただの文字列と区別する。"""


class Keyword(str):
    """BT や Tj のような命令の言葉。"""


class Ref(tuple):
    """「12 0 R」のような、ほかの部品への道。"""


class Stream:
    """辞書と、その後ろに続く中身(圧縮されたまま)。"""

    def __init__(self, info, raw):
        self.info = info
        self.raw = raw


# ---- 字の並びを、ひとつずつの言葉に切る ----

_WS = b"\x00\t\n\x0c\r "
TOKEN = re.compile(
    rb"(?P<ws>[\x00\t\n\x0c\r ]+|%[^\r\n]*)"
    rb"|(?P<dict_open><<)|(?P<dict_close>>>)"
    rb"|(?P<arr_open>\[)|(?P<arr_close>\])"
    rb"|(?P<name>/[^\x00\t\n\x0c\r ()<>\[\]{}/%]*)"
    rb"|(?P<num>[+-]?(?:\d+\.?\d*|\.\d+)(?![^\x00\t\n\x0c\r ()<>\[\]{}/%]))"
    rb"|(?P<hex><[0-9A-Fa-f\x00\t\n\x0c\r ]*>)"
    rb"|(?P<lit>\()"
    rb"|(?P<brace>[{}])"
    rb"|(?P<kw>[^\x00\t\n\x0c\r ()<>\[\]{}/%]+)"
    rb"|(?P<other>.)",
    re.DOTALL,
)
REF_TAIL = re.compile(rb"[\x00\t\n\x0c\r ]+(\d+)[\x00\t\n\x0c\r ]+R(?=[\x00\t\n\x0c\r ()<>\[\]{}/%]|$)")
NAME_ESCAPE = re.compile(rb"#([0-9A-Fa-f]{2})")
LITERAL_ESCAPES = {
    ord("n"): b"\n", ord("r"): b"\r", ord("t"): b"\t", ord("b"): b"\b", ord("f"): b"\f",
    ord("("): b"(", ord(")"): b")", ord("\\"): b"\\",
}


def _literal(buf, pos):
    """( の次から、対応する ) までの文字列。入れ子の () と、\\ の書き方をほどく。"""
    out = bytearray()
    depth = 1
    end = len(buf)
    while pos < end:
        c = buf[pos]
        if c == 0x5C:  # バックスラッシュ
            pos += 1
            if pos >= end:
                break
            c = buf[pos]
            if c in LITERAL_ESCAPES:
                out += LITERAL_ESCAPES[c]
                pos += 1
            elif 0x30 <= c <= 0x37:
                digits = buf[pos:pos + 3]
                n = 0
                used = 0
                for d in digits:
                    if 0x30 <= d <= 0x37:
                        n = n * 8 + d - 0x30
                        used += 1
                    else:
                        break
                out.append(n & 0xFF)
                pos += used
            elif c == 0x0D:  # 行の続き
                pos += 2 if buf[pos + 1:pos + 2] == b"\n" else 1
            elif c == 0x0A:
                pos += 1
            else:
                out.append(c)
                pos += 1
            continue
        if c == 0x28:
            depth += 1
        elif c == 0x29:
            depth -= 1
            if depth == 0:
                return bytes(out), pos + 1
        out.append(c)
        pos += 1
    return bytes(out), pos


def parse(buf, pos, refs=True):
    """buf の pos から、ひとつの値を読む。返り値は (値, 次の位置)。

    読めるものが無ければ (None, len(buf))。"""
    end = len(buf)
    while pos < end:
        m = TOKEN.match(buf, pos)
        if not m:
            return None, end
        kind = m.lastgroup
        if kind == "ws":
            pos = m.end()
            continue
        pos = m.end()
        if kind == "dict_open":
            found = {}
            while True:
                pos = _skip(buf, pos)
                if pos >= end:
                    return found, pos
                if buf.startswith(b">>", pos):
                    return found, pos + 2
                key, pos = parse(buf, pos, refs)
                if key is None:
                    return found, pos
                if not isinstance(key, Name):
                    continue  # 壊れた辞書。鍵でないものは飛ばす
                value, pos = parse(buf, pos, refs)
                found[str(key)] = value
        if kind == "arr_open":
            items = []
            while True:
                pos = _skip(buf, pos)
                if pos >= end:
                    return items, pos
                if buf[pos:pos + 1] == b"]":
                    return items, pos + 1
                value, pos = parse(buf, pos, refs)
                if value is None and pos >= end:
                    return items, pos
                items.append(value)
        if kind == "name":
            raw = NAME_ESCAPE.sub(lambda e: bytes([int(e.group(1), 16)]), m.group()[1:])
            return Name(raw.decode("latin-1")), pos
        if kind == "num":
            text = m.group()
            if b"." in text:
                try:
                    return float(text), pos
                except ValueError:
                    return 0.0, pos
            number = int(text)
            if refs and number >= 0:
                tail = REF_TAIL.match(buf, pos)
                if tail:
                    return Ref((number, int(tail.group(1)))), tail.end()
            return number, pos
        if kind == "hex":
            digits = re.sub(rb"[^0-9A-Fa-f]", b"", m.group()[1:-1])
            if len(digits) % 2:
                digits += b"0"
            return bytes.fromhex(digits.decode("ascii")), pos
        if kind == "lit":
            return _literal(buf, pos)
        if kind == "kw":
            word = m.group()
            if word == b"true":
                return True, pos
            if word == b"false":
                return False, pos
            if word == b"null":
                return None, pos
            return Keyword(word.decode("latin-1")), pos
        if kind in ("dict_close", "arr_close", "brace", "other"):
            return Keyword(m.group().decode("latin-1")), pos
    return None, end


def _skip(buf, pos):
    """空白と書き込み(%…)を飛ばす。"""
    end = len(buf)
    while pos < end:
        c = buf[pos]
        if c in _WS:
            pos += 1
        elif c == 0x25:
            nl = re.compile(rb"[\r\n]").search(buf, pos)
            pos = nl.end() if nl else end
        else:
            break
    return pos


# ---- 圧縮をほどく ----

def _flate(data):
    for wbits in (zlib.MAX_WBITS, -zlib.MAX_WBITS):
        try:
            return zlib.decompressobj(wbits).decompress(data)
        except zlib.error:
            continue
    # 途中で壊れていても、ほどけたところまでは使う
    out = bytearray()
    d = zlib.decompressobj()
    for i in range(0, len(data), 256):
        try:
            out += d.decompress(data[i:i + 256])
        except zlib.error:
            break
    return bytes(out)


def _ascii_hex(data):
    digits = re.sub(rb"[^0-9A-Fa-f]", b"", data.split(b">", 1)[0])
    if len(digits) % 2:
        digits += b"0"
    return bytes.fromhex(digits.decode("ascii"))


def _ascii85(data):
    data = re.sub(rb"[\x00\t\n\x0c\r ]", b"", data)
    if data.startswith(b"<~"):
        data = data[2:]
    data = data.split(b"~>", 1)[0]
    out = bytearray()
    group = []
    for c in data:
        if c == ord("z") and not group:
            out += b"\0\0\0\0"
            continue
        if not 33 <= c <= 117:
            continue
        group.append(c - 33)
        if len(group) == 5:
            n = 0
            for g in group:
                n = n * 85 + g
            out += (n & 0xFFFFFFFF).to_bytes(4, "big")
            group = []
    if group:
        missing = 5 - len(group)
        group += [84] * missing
        n = 0
        for g in group:
            n = n * 85 + g
        out += (n & 0xFFFFFFFF).to_bytes(4, "big")[:4 - missing]
    return bytes(out)


def _lzw(data, early=1):
    out = bytearray()
    table = [bytes([i]) for i in range(256)] + [b"", b""]
    bits = 9
    buffer = 0
    have = 0
    previous = None
    for c in data:
        buffer = (buffer << 8) | c
        have += 8
        while have >= bits:
            have -= bits
            code = (buffer >> have) & ((1 << bits) - 1)
            if code == 256:
                table = table[:258]
                bits = 9
                previous = None
                continue
            if code == 257:
                return bytes(out)
            if previous is None:
                entry = table[code] if code < len(table) else b""
            elif code < len(table):
                entry = table[code]
                table.append(previous + entry[:1])
            else:
                entry = previous + previous[:1]
                table.append(entry)
            out += entry
            previous = entry
            if len(table) + early >= (1 << bits) and bits < 12:
                bits += 1
    return bytes(out)


def _run_length(data):
    out = bytearray()
    i = 0
    while i < len(data):
        n = data[i]
        if n == 128:
            break
        if n < 128:
            out += data[i + 1:i + 2 + n]
            i += 2 + n
        else:
            out += data[i + 1:i + 2] * (257 - n)
            i += 2
    return bytes(out)


def _unpredict(data, parms):
    """PNG の並べ方(Predictor 10 以上)をほどく。xref の流れでよく使われる。"""
    predictor = (parms or {}).get("Predictor", 1)
    if not isinstance(predictor, int) or predictor < 10:
        return data
    columns = parms.get("Columns", 1) or 1
    colors = parms.get("Colors", 1) or 1
    bits = parms.get("BitsPerComponent", 8) or 8
    pixel = max(1, colors * bits // 8)
    row = (columns * colors * bits + 7) // 8
    out = bytearray()
    previous = bytearray(row)
    for start in range(0, len(data), row + 1):
        kind = data[start]
        line = bytearray(data[start + 1:start + 1 + row])
        line += bytes(row - len(line))
        for i in range(row):
            left = line[i - pixel] if i >= pixel else 0
            up = previous[i]
            corner = previous[i - pixel] if i >= pixel else 0
            if kind == 1:
                line[i] = (line[i] + left) & 0xFF
            elif kind == 2:
                line[i] = (line[i] + up) & 0xFF
            elif kind == 3:
                line[i] = (line[i] + (left + up) // 2) & 0xFF
            elif kind == 4:
                p = left + up - corner
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - corner)
                guess = left if pa <= pb and pa <= pc else (up if pb <= pc else corner)
                line[i] = (line[i] + guess) & 0xFF
        out += line
        previous = line
    return bytes(out)


FILTERS = {
    "FlateDecode": _flate, "Fl": _flate,
    "ASCIIHexDecode": _ascii_hex, "AHx": _ascii_hex,
    "ASCII85Decode": _ascii85, "A85": _ascii85,
    "RunLengthDecode": _run_length, "RL": _run_length,
}


# ---- 字の番号を、字に戻す ----

GLYPH_NAMES = {
    "space": " ", "exclam": "!", "quotedbl": '"', "numbersign": "#", "dollar": "$",
    "percent": "%", "ampersand": "&", "quotesingle": "'", "parenleft": "(", "parenright": ")",
    "asterisk": "*", "plus": "+", "comma": ",", "hyphen": "-", "period": ".", "slash": "/",
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
    "seven": "7", "eight": "8", "nine": "9", "colon": ":", "semicolon": ";", "less": "<",
    "equal": "=", "greater": ">", "question": "?", "at": "@", "bracketleft": "[",
    "backslash": "\\", "bracketright": "]", "asciicircum": "^", "underscore": "_",
    "grave": "`", "braceleft": "{", "bar": "|", "braceright": "}", "asciitilde": "~",
    "quoteleft": "‘", "quoteright": "’", "quotedblleft": "“",
    "quotedblright": "”", "quotesinglbase": "‚", "quotedblbase": "„",
    "endash": "–", "emdash": "—", "bullet": "•", "ellipsis": "…",
    "fi": "fi", "fl": "fl", "ff": "ff", "ffi": "ffi", "ffl": "ffl", "dagger": "†",
    "daggerdbl": "‡", "degree": "°", "copyright": "©", "registered": "®",
    "trademark": "™", "section": "§", "paragraph": "¶", "minus": "−",
    "multiply": "×", "divide": "÷", "plusminus": "±", "periodcentered": "·",
    "nbspace": " ", "sfthyphen": "-", "dotlessi": "ı", "germandbls": "ß",
    "guillemotleft": "«", "guillemotright": "»", "Euro": "€", "yen": "¥",
}
ACCENTED = {
    "acute": "́", "grave": "̀", "dieresis": "̈", "circumflex": "̂",
    "tilde": "̃", "ring": "̊", "cedilla": "̧", "caron": "̌",
}


def glyph_to_text(name):
    """字の形の名前(a、quoteright、uni3042 など)から、その字。分からなければ空。"""
    base = name.split(".", 1)[0].split("_", 1)[0]
    if len(base) == 1:
        return base
    if base in GLYPH_NAMES:
        return GLYPH_NAMES[base]
    m = re.fullmatch(r"uni((?:[0-9A-Fa-f]{4})+)", base)
    if m:
        try:
            return bytes.fromhex(m.group(1)).decode("utf-16-be")
        except (ValueError, UnicodeDecodeError):
            return ""
    m = re.fullmatch(r"u([0-9A-Fa-f]{4,6})", base)
    if m:
        try:
            return chr(int(m.group(1), 16))
        except (ValueError, OverflowError):
            return ""
    # Aacute、eacute のような、文字と飾りの組み合わせ
    for mark, combining in ACCENTED.items():
        if len(base) > len(mark) and base.endswith(mark) and len(base) - len(mark) == 1:
            return unicodedata.normalize("NFC", base[0] + combining)
    return ""


# 決まった並びの名前と、それをほどく読み方。字ごとの対応表が無い時に使う
CMAP_ENCODINGS = [
    (re.compile(r"UCS2|UTF16"), "utf-16-be"),
    (re.compile(r"UTF32"), "utf-32-be"),
    (re.compile(r"UTF8"), "utf-8"),
    (re.compile(r"RKSJ"), "cp932"),
    (re.compile(r"GB-EUC|GBK|GBpc|GBT"), "gbk"),
    (re.compile(r"KSC"), "euc_kr"),
    (re.compile(r"B5|ETen|HKscs|CNS"), "big5"),
    (re.compile(r"EUC"), "euc_jp"),
    (re.compile(r"^[HV]$"), "jis"),  # JIS X 0208 の番号そのまま。上の位を立てると EUC-JP になる
]
SIMPLE_ENCODINGS = {
    "WinAnsiEncoding": "cp1252",
    "MacRomanEncoding": "mac_roman",
    "MacExpertEncoding": "mac_roman",
    "StandardEncoding": "latin-1",
    "PDFDocEncoding": "latin-1",
}


def _utf16(raw):
    try:
        return raw.decode("utf-16-be")
    except UnicodeDecodeError:
        return raw.decode("utf-16-be", errors="ignore")


class Font:
    """ひとつの字の形(フォント)。字の番号を字に戻す。"""

    def __init__(self, pdf, info):
        info = info if isinstance(info, dict) else {}
        self.subtype = str(pdf.resolve(info.get("Subtype")) or "")
        self.composite = self.subtype == "Type0"
        self.unicode = {}  # 番号(bytes) → 字
        self.code_lengths = []  # 番号の長さ(バイト)
        self.codec = None  # 決まった並びの読み方
        self.simple = None  # 一バイトの番号 → 字(256)
        self.no_way = False  # 戻し方が分からない

        to_unicode = pdf.resolve(info.get("ToUnicode"))
        if isinstance(to_unicode, Stream):
            self._read_cmap(pdf.data_of(to_unicode))

        encoding = pdf.resolve(info.get("Encoding"))
        if self.composite:
            name = str(encoding) if isinstance(encoding, Name) else ""
            if isinstance(encoding, Stream):
                name = str(pdf.resolve(encoding.info.get("CMapName")) or "")
            for pattern, codec in CMAP_ENCODINGS:
                if name and pattern.search(name):
                    self.codec = codec
                    break
            if not self.code_lengths:
                self.code_lengths = [1, 2] if self.codec in ("cp932", "euc_jp", "gbk", "big5", "euc_kr") else [2]
                if self.codec == "utf-32-be":
                    self.code_lengths = [4]
            if not self.unicode and not self.codec:
                self.no_way = True  # Identity-H などで、対応表が無い
        else:
            if not self.code_lengths:
                self.code_lengths = [1]
            self.simple = self._simple_table(pdf, encoding)

    def _simple_table(self, pdf, encoding):
        base = "latin-1"
        differences = []
        if isinstance(encoding, Name):
            base = SIMPLE_ENCODINGS.get(str(encoding), "latin-1")
        elif isinstance(encoding, dict):
            base = SIMPLE_ENCODINGS.get(str(pdf.resolve(encoding.get("BaseEncoding")) or ""), "cp1252")
            differences = pdf.resolve(encoding.get("Differences")) or []
        table = []
        for code in range(256):
            try:
                table.append(bytes([code]).decode(base))
            except UnicodeDecodeError:
                table.append("")
        code = 0
        for item in differences if isinstance(differences, list) else []:
            item = pdf.resolve(item)
            if isinstance(item, int):
                code = item
            elif isinstance(item, Name):
                if 0 <= code < 256:
                    table[code] = glyph_to_text(str(item))
                code += 1
        return table

    def _read_cmap(self, data):
        """字ごとの対応表(ToUnicode)を読む。"""
        pos = 0
        end = len(data)
        lengths = set()
        operands = []
        while pos < end:
            value, pos = parse(data, pos, refs=False)
            if value is None and pos >= end:
                break
            if isinstance(value, Keyword):
                word = str(value)
                if word == "endcodespacerange":
                    for lo in operands[0::2]:
                        if isinstance(lo, bytes) and lo:
                            lengths.add(len(lo))
                elif word == "endbfchar":
                    for src, dst in zip(operands[0::2], operands[1::2]):
                        if isinstance(src, bytes):
                            lengths.add(len(src))
                            if isinstance(dst, bytes):
                                self.unicode[src] = _utf16(dst)
                            elif isinstance(dst, Name):
                                self.unicode[src] = glyph_to_text(str(dst))
                elif word == "endbfrange":
                    for i in range(0, len(operands) - 2, 3):
                        lo, hi, dst = operands[i:i + 3]
                        if not (isinstance(lo, bytes) and isinstance(hi, bytes) and lo):
                            continue
                        lengths.add(len(lo))
                        a = int.from_bytes(lo, "big")
                        b = int.from_bytes(hi, "big")
                        if b < a or b - a > 65535:
                            continue
                        for offset in range(b - a + 1):
                            src = (a + offset).to_bytes(len(lo), "big")
                            if isinstance(dst, list):
                                if offset < len(dst) and isinstance(dst[offset], bytes):
                                    self.unicode[src] = _utf16(dst[offset])
                            elif isinstance(dst, bytes) and dst:
                                start = int.from_bytes(dst, "big") + offset
                                try:
                                    self.unicode[src] = _utf16(start.to_bytes(len(dst), "big"))
                                except OverflowError:
                                    pass
                operands = []
            else:
                operands.append(value)
        self.code_lengths = sorted(lengths) or self.code_lengths

    def _by_codec(self, raw):
        if self.codec == "jis":
            return bytes(b | 0x80 for b in raw).decode("euc_jp", errors="ignore")
        return raw.decode(self.codec, errors="ignore")

    def decode(self, raw):
        """字の番号の並びを、字の並びに。"""
        if not raw:
            return ""
        if self.codec and not self.unicode:
            return self._by_codec(raw)
        if not self.composite and not self.unicode:
            return "".join(self.simple[b] for b in raw)
        out = []
        pos = 0
        lengths = self.code_lengths or [1]
        while pos < len(raw):
            for n in lengths:
                piece = raw[pos:pos + n]
                if piece in self.unicode:
                    out.append(self.unicode[piece])
                    pos += n
                    break
            else:
                n = lengths[-1] if self.composite else lengths[0]
                piece = raw[pos:pos + n]
                if self.codec:
                    out.append(self._by_codec(piece))
                elif self.simple and len(piece) == 1:
                    out.append(self.simple[piece[0]])
                pos += max(1, n)
        return "".join(out)


# ---- 本体 ----

OBJ_START = re.compile(rb"(?<![0-9])(\d{1,10})[\x00\t\n\x0c\r ]+(\d{1,5})[\x00\t\n\x0c\r ]+obj\b")


class Pdf:
    def __init__(self, data):
        if b"%PDF-" not in data[:1024]:
            raise NotReadable("PDF ではない")
        self.data = data
        self.offsets = {}
        for m in OBJ_START.finditer(data):
            self.offsets[int(m.group(1))] = m.end()
        self.cache = {}
        self.packed = None  # 箱(ObjStm)に詰められた部品
        self.fonts = {}
        if re.search(rb"/Encrypt[\x00\t\n\x0c\r ]*(\d+[\x00\t\n\x0c\r ]+\d+[\x00\t\n\x0c\r ]+R|<<)", data):
            raise NotReadable("鍵がかかっている")

    # 部品を引く
    def get(self, number):
        if number in self.cache:
            return self.cache[number]
        value = None
        if number in self.offsets:
            value = self._read_at(self.offsets[number])
        else:
            value = self._from_packed(number)
        self.cache[number] = value
        return value

    def resolve(self, value, depth=0):
        while isinstance(value, Ref) and depth < 20:
            value = self.get(value[0])
            depth += 1
        return value

    def _read_at(self, pos):
        value, pos = parse(self.data, pos)
        if isinstance(value, dict):
            after = _skip(self.data, pos)
            if self.data.startswith(b"stream", after):
                start = after + 6
                if self.data[start:start + 2] == b"\r\n":
                    start += 2
                elif self.data[start:start + 1] in (b"\n", b"\r"):
                    start += 1
                length = value.get("Length")
                if isinstance(length, Ref):
                    length = self._read_direct_number(length[0])
                end = None
                if isinstance(length, int) and length >= 0:
                    probe = self.data[start + length:start + length + 30]
                    if b"endstream" in probe:
                        end = start + length
                if end is None:
                    found = self.data.find(b"endstream", start)
                    end = found if found >= 0 else len(self.data)
                    while end > start and self.data[end - 1:end] in (b"\n", b"\r"):
                        end -= 1
                return Stream(value, self.data[start:end])
        return value

    def _read_direct_number(self, number):
        if number in self.offsets:
            value, _ = parse(self.data, self.offsets[number])
            if isinstance(value, int):
                return value
        return None

    def _from_packed(self, number):
        if self.packed is None:
            self.packed = {}
            for at in re.finditer(rb"/ObjStm", self.data):
                begin = self.data.rfind(b"obj", 0, at.start())
                head = OBJ_START.search(self.data, max(0, begin - 30), begin + 3)
                if not head:
                    continue
                box = self._read_at(head.end())
                if not isinstance(box, Stream):
                    continue
                try:
                    self._unpack(box)
                except Exception:
                    continue
        return self.packed.get(number)

    def _unpack(self, box):
        data = self.data_of(box)
        count = box.info.get("N", 0)
        first = box.info.get("First", 0)
        if not isinstance(count, int) or not isinstance(first, int):
            return
        pos = 0
        pairs = []
        for _ in range(count):
            num, pos = parse(data, pos, refs=False)
            off, pos = parse(data, pos, refs=False)
            if isinstance(num, int) and isinstance(off, int):
                pairs.append((num, off))
        for num, off in pairs:
            if num not in self.packed:
                value, _ = parse(data, first + off)
                self.packed[num] = value

    def data_of(self, stream):
        """流れの中身を、圧縮をほどいて。ほどけないもの(絵など)は空。"""
        data = stream.raw
        filters = self.resolve(stream.info.get("Filter"))
        parms = self.resolve(stream.info.get("DecodeParms"))
        if filters is None:
            return data
        if not isinstance(filters, list):
            filters = [filters]
            parms = [parms]
        elif not isinstance(parms, list):
            parms = [parms] * len(filters)
        for name, parm in zip(filters, parms + [None] * (len(filters) - len(parms))):
            name = str(self.resolve(name))
            parm = self.resolve(parm)
            if name in ("LZWDecode", "LZW"):
                early = (parm or {}).get("EarlyChange", 1) if isinstance(parm, dict) else 1
                data = _unpredict(_lzw(data, early), parm if isinstance(parm, dict) else None)
            elif name in FILTERS:
                data = FILTERS[name](data)
                if name in ("FlateDecode", "Fl"):
                    data = _unpredict(data, parm if isinstance(parm, dict) else None)
            else:
                return b""  # 絵の圧縮など。字は入っていない
        return data

    # 目次
    def catalog(self):
        roots = re.findall(rb"/Root[\x00\t\n\x0c\r ]+(\d+)[\x00\t\n\x0c\r ]+\d+[\x00\t\n\x0c\r ]+R", self.data)
        for number in reversed(roots):
            found = self.get(int(number))
            if isinstance(found, dict) and found.get("Pages") is not None:
                return found
        for number in sorted(self.offsets):
            value = self.get(number)
            if isinstance(value, dict) and value.get("Type") == "Catalog":
                return value
        return None

    def pages(self):
        """ページを順に。(ページの辞書, 引き継いだ持ち物) の並び。"""
        found = []
        root = self.catalog()
        tree = self.resolve(root.get("Pages")) if isinstance(root, dict) else None
        seen = set()

        def walk(node, resources, depth):
            if len(found) >= PAGES_AT_MOST or depth > 30 or not isinstance(node, dict):
                return
            key = id(node)
            if key in seen:
                return
            seen.add(key)
            here = self.resolve(node.get("Resources"))
            resources = here if isinstance(here, dict) else resources
            kids = self.resolve(node.get("Kids"))
            if isinstance(kids, list) and node.get("Type") != "Page":
                for kid in kids:
                    walk(self.resolve(kid), resources, depth + 1)
            else:
                found.append((node, resources or {}))

        walk(tree, {}, 0)
        if not found:
            for number in sorted(self.offsets):
                value = self.get(number)
                if isinstance(value, dict) and value.get("Type") == "Page":
                    found.append((value, self.resolve(value.get("Resources")) or {}))
                    if len(found) >= PAGES_AT_MOST:
                        break
        return found

    def font(self, ref, info):
        key = ref if isinstance(ref, Ref) else id(info)
        if key not in self.fonts:
            self.fonts[key] = Font(self, info)
        return self.fonts[key]

    def title(self):
        infos = re.findall(rb"/Info[\x00\t\n\x0c\r ]+(\d+)[\x00\t\n\x0c\r ]+\d+[\x00\t\n\x0c\r ]+R", self.data)
        for number in reversed(infos):
            info = self.get(int(number))
            if isinstance(info, dict):
                raw = self.resolve(info.get("Title"))
                if isinstance(raw, bytes):
                    return text_string(raw).strip()
        return ""

    def links(self):
        """ページに貼られた、よその場所への道(URI)。"""
        found = []
        for m in re.finditer(rb"/URI[\x00\t\n\x0c\r ]*\(", self.data):
            raw, _ = _literal(self.data, m.end())
            try:
                url = raw.decode("ascii")
            except UnicodeDecodeError:
                continue
            if url.startswith("http"):
                found.append(url)
        return list(dict.fromkeys(found))


def text_string(raw):
    """題などの文字列。UTF-16 の印があればそれで、なければ UTF-8、Shift_JIS、latin-1 の順に試す。"""
    if raw[:2] == b"\xfe\xff":
        return _utf16(raw[2:])
    if raw[:3] == b"\xef\xbb\xbf":
        return raw[3:].decode("utf-8", errors="ignore")
    for codec in ("utf-8", "cp932"):
        try:
            return raw.decode(codec)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


# ---- ページに書かれた字を、順に拾う ----

def _wide(ch):
    """日本語や中国語の字、かな、全角の記号か。"""
    return bool(ch) and ord(ch) >= 0x2E80


class Reader:
    """書き込みの手順を頭から辿って、字を置く命令のところで字を拾う。

    字の置き場所(行列)も追いかけて、上下に動いたら改行を入れる。
    英字の文字の形で横に飛んだところには、空白を入れる。日本語の字の間には入れない。"""

    def __init__(self, pdf, until):
        self.pdf = pdf
        self.until = until
        self.out = []
        self.chars = 0
        self.last_y = None

    def say(self, text):
        if text:
            self.out.append(text)
            self.chars += len(text)

    def new_line(self):
        if self.out and not self.out[-1].endswith("\n"):
            self.out.append("\n")

    def space(self, coming=""):
        """空白を入れる。日本語の字のあいだには入れない(字ごとに置いてある PDF も多い)。"""
        if not self.out or self.out[-1].endswith((" ", "\n")):
            return
        if _wide(self.out[-1][-1:]) or _wide(coming[:1]):
            return
        self.out.append(" ")

    def read(self, data, resources, depth=0):
        if depth > 6:
            return
        fonts = self.pdf.resolve(resources.get("Font")) if isinstance(resources, dict) else None
        fonts = fonts if isinstance(fonts, dict) else {}
        xobjects = self.pdf.resolve(resources.get("XObject")) if isinstance(resources, dict) else None
        xobjects = xobjects if isinstance(xobjects, dict) else {}
        font = None
        size = 10.0
        leading = 0.0
        line = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]  # 行の頭の置き場所(Tm の a b c d e f)
        moved = False  # 前に字を置いてから、横に動いたか
        operands = []
        pos = 0
        end = len(data)
        while pos < end:
            if self.chars >= CHARS_AT_MOST or time.monotonic() > self.until:
                return
            value, pos = parse(data, pos, refs=False)
            if value is None and pos >= end:
                break
            if not isinstance(value, Keyword):
                operands.append(value)
                if len(operands) > 64:
                    operands = operands[-64:]
                continue
            op = str(value)
            numbers = [n for n in operands if isinstance(n, (int, float)) and not isinstance(n, bool)]
            if op == "BI":
                found = re.compile(rb"[\x00\t\n\x0c\r ]EI(?=[\x00\t\n\x0c\r ]|$)").search(data, pos)
                pos = found.end() if found else end
            elif op == "BT":
                line = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
            elif op == "Tf" and len(operands) >= 2:
                ref = fonts.get(str(operands[-2]))
                info = self.pdf.resolve(ref)
                font = self.pdf.font(ref, info) if isinstance(info, dict) else None
                if isinstance(operands[-1], (int, float)):
                    size = abs(float(operands[-1])) or size
            elif op == "TL" and numbers:
                leading = float(numbers[-1])
            elif op in ("Td", "TD") and len(numbers) >= 2:
                tx, ty = float(numbers[-2]), float(numbers[-1])
                a, b, c, d, e, f = line
                line = [a, b, c, d, e + tx * a + ty * c, f + tx * b + ty * d]
                if op == "TD":
                    leading = -ty
                moved = moved or tx != 0
            elif op == "Tm" and len(numbers) >= 6:
                line = [float(n) for n in numbers[-6:]]
                moved = True
            elif op == "T*":
                a, b, c, d, e, f = line
                line = [a, b, c, d, e - leading * c, f - leading * d]
            elif op == "Tj" and operands:
                moved = self._show(font, operands[-1], line, size, moved)
            elif op in ("'", '"') and operands:
                a, b, c, d, e, f = line
                line = [a, b, c, d, e - leading * c, f - leading * d]
                moved = self._show(font, operands[-1], line, size, moved)
            elif op == "TJ" and operands and isinstance(operands[-1], list):
                for item in operands[-1]:
                    if isinstance(item, bytes):
                        moved = self._show(font, item, line, size, moved)
                    elif isinstance(item, (int, float)) and item < -250 and font and not font.composite:
                        self.space("a")
            elif op == "Do" and operands:
                form = self.pdf.resolve(xobjects.get(str(operands[-1])))
                if isinstance(form, Stream) and form.info.get("Subtype") == "Form":
                    inner = self.pdf.resolve(form.info.get("Resources"))
                    self.read(self.pdf.data_of(form), inner if isinstance(inner, dict) else resources, depth + 1)
            operands = []

    def _show(self, font, raw, line, size, moved):
        """字を置く。上下に動いていたら改行、英字の形で横に飛んでいたら空白。返り値は「横に動いた」の消し。"""
        if not isinstance(raw, bytes) or font is None or font.no_way:
            return moved
        text = font.decode(raw)
        if not text:
            return moved
        a, b, c, d, e, f = line
        y = f
        height = size * max(abs(d), abs(b), 0.01)
        if self.last_y is not None and abs(y - self.last_y) > height * 0.5:
            self.new_line()
        elif moved and not font.composite:
            self.space(text)
        self.last_y = y
        self.say(text)
        return False


CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f\ufffd]")
KANGXI = re.compile(r"[\u2e80-\u2fdf]")
# 部首の補いの字(U+2E80〜)には、ふつうの字への決まった対応が無い。よく出るものだけ手で並べる
RADICAL_SUPPLEMENT = str.maketrans({
    "\u2e9f": "母", "\u2ea0": "民", "\u2ec1": "虎", "\u2ec4": "西", "\u2ec6": "角",
    "\u2ec7": "角", "\u2ed1": "長", "\u2ed8": "青", "\u2edd": "食", "\u2ee4": "鬼",
    "\u2ee8": "麦", "\u2ee9": "黄", "\u2eeb": "斉", "\u2eed": "歯", "\u2eef": "竜",
    "\u2ef1": "龜", "\u2ef2": "亀",
})


def read(data):
    """PDF のバイトの並びから (題, 文)。読めなければ NotReadable。"""
    pdf = Pdf(data)
    until = time.monotonic() + SECONDS_AT_MOST
    reader = Reader(pdf, until)
    for page, resources in pdf.pages():
        contents = pdf.resolve(page.get("Contents"))
        parts = contents if isinstance(contents, list) else [contents]
        streams = [pdf.resolve(one) for one in parts]
        data_here = b"\n".join(pdf.data_of(one) for one in streams if isinstance(one, Stream))
        try:
            reader.read(data_here, resources)
        except RecursionError:
            pass
        reader.new_line()
        if reader.chars >= CHARS_AT_MOST or time.monotonic() > until:
            break
    text = CONTROL.sub("", "".join(reader.out))
    # 部首の形の字(「⽣」U+2F63 など)で入っていることがある。見た目は同じでも別の字なので、
    # ふつうの字(「生」)にそろえる。そうしないと、知っている言葉なのに知らない言葉に見える
    text = KANGXI.sub(lambda m: unicodedata.normalize("NFKC", m.group()), text.translate(RADICAL_SUPPLEMENT))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text).strip()
    return pdf.title(), text


def links_in(data):
    """PDF に貼られた、よその場所への道。"""
    try:
        return Pdf(data).links()
    except NotReadable:
        return []
