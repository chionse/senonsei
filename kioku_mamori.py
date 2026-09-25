"""千遠生の記憶を送り出す前に、壊れていないかを確かめる。

GitHub の Actions が、散歩のあとに呼ぶ。

    python kioku_mamori.py            壊れているものを並べるだけ
    python kioku_mamori.py 印         壊れているものを、その印(コミット)の時の中身に戻す

壊れるのは、たとえばこういう時:
- 書き出している最中に止められた
- 散歩のあいだに main が動いていて、取り込み直す時に
  記憶のファイルが行ごとに継ぎ合わされた

壊れたまま送ると、次の回からこの子は記憶を読めずに止まる。
戻す先が無い(その時にはまだ無かった)ものは、そのまま残して知らせる。
標準の部品だけで動く。
"""

import glob
import json
import subprocess
import sys

# この子の記憶と、彼女が置いたもの。読めなくなると困るもの
MEMORY = [
    "senonsei_state.json",
    "articles.json",
    "keywords.json",
    "menu.json",
    "himitsu.json",
    "news.json",
]
MEMORY_FOLDERS = ["omoi/*.json", "kotoba/*/*.json", "comments/*.json", "likes/*.json"]


def everything():
    found = [path for path in MEMORY if glob.glob(path)]
    for pattern in MEMORY_FOLDERS:
        found += sorted(glob.glob(pattern))
    return found


def readable(path):
    try:
        with open(path, encoding="utf-8") as f:
            json.load(f)
        return True
    except (OSError, ValueError):
        return False


def as_it_was(path, mark):
    """その印の時の中身。無ければ None。"""
    try:
        return subprocess.run(
            ["git", "show", f"{mark}:{path}"],
            check=True, capture_output=True,
        ).stdout
    except subprocess.CalledProcessError:
        return None


def main():
    mark = sys.argv[1] if len(sys.argv) > 1 else None
    broken = [path for path in everything() if not readable(path)]
    if not broken:
        print("記憶はどれも読めます")
        return
    for path in broken:
        if not mark:
            print(f"読めない: {path}")
            continue
        before = as_it_was(path, mark)
        if before is None:
            print(f"読めない: {path}(戻す先がありません)")
            continue
        with open(path, "wb") as f:
            f.write(before)
        state = "戻しました" if readable(path) else "戻しても読めません"
        print(f"読めなかった {path} を {mark} の時の中身に{state}")


if __name__ == "__main__":
    main()
