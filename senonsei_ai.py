"""千遠生が毎日Webを見て、その日の自分に書けるものを書くプログラム。

千遠生は最初、文字さえ知らない状態から始まる。
毎日いくつかのページを見て回り、そこにあった文字を拾い、何度も出会った言葉を覚えていく。

何が書けるようになるかは、経過日数では決まらない。
その子が実際にどれだけの文字と言葉を浴びてきたかで決まる。
たくさん出会えた時期は早く育ち、実りの少ない時期は伸び悩む。

考えること、感じること、喋ることは、この子の頭(atama.py)がする。
Cloudflare Workers AI の無料枠から借りるのは、目(絵を見る)だけ。
よその国の言葉は訳してもらわず、拾える形の言葉をそのまま覚える。
目が使えない時(キーが無い・障害・無料枠の終了)は絵を眺めるだけになり、
それまでに積み上げた経験で思い、書き続ける。
"""

import datetime
import json
import math
import os
import random
import re
import shutil
import struct
import subprocess
import tempfile
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import zlib
from html import unescape
from html.parser import HTMLParser

import atama
import blog_manager
import pdf_yomu

# ---- 体の部品 ----
#
# この子の体は、役割ごとに karada/ のファイルへ分けてある(2026-11-23、彼女と決めた)。
# 一つのファイルのままだと六千行を越え、何をどこでしているのかを探すだけで骨が折れた。
#
# 部品は import せず、決まった順に、このファイル自身の中へ読み込む。
# どの部品も同じ一つの名前の置き場を使うので、前と同じように動く。
# - ほかのファイルからは、前と同じ senonsei_ai のまま見える。
# - 試す時に s.save_state を塞げば、どの部品から呼んでも塞がる(CLAUDE.md)。
# - こけた時の知らせには、部品のファイルの名前と行が出る。
#
# 順番には意味がある。前の部品で決めた数を、あとの部品が使うことがある。
KARADA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "karada")
KARADA_PARTS = (
    "kimari",
    "kioku",
    "ashidori",
    "kariru",
    "michi",
    "me",
    "yomu",
    "ikisaki",
    "narabi",
    "uketoru",
    "sanpo",
    "hitorigoto",
    "dekakeru",
    "iitai",
    "kaku",
    "kyou",
    "ie",
    "ichinichi",
)
for _karada_part in KARADA_PARTS:
    _karada_path = os.path.join(KARADA, _karada_part + ".py")
    with open(_karada_path, encoding="utf-8") as _karada_file:
        exec(compile(_karada_file.read(), _karada_path, "exec"), globals())
del _karada_part, _karada_path, _karada_file


if __name__ == "__main__":
    import sys

    # 「kaku」と添えて呼ばれた時は、決めた分まで待ったあと。日記だけを書く
    if sys.argv[1:] == ["kaku"]:
        write_at_its_minute()
    else:
        run_today()
