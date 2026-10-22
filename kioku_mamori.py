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
MEMORY_FOLDERS = [
    "omoi/*.json", "kotoba/*/*.json", "atama/*.json", "atama/*/*.json", "comments/*.json", "likes/*.json",
]


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


def changed_since(mark):
    """その印の時から中身が変わったもの(まだ一度も送っていない新しいものも)。

    記憶は何十年かけて大きくなる(奥にしまった言葉は毎年増える)。毎回ぜんぶを
    読み直すと、それだけで時間がかかるようになるので、変わったものだけを見る
    (2026-10-22)。変わっていないものは、その印の時にもう確かめてある。
    分からなければ None(その時はぜんぶ見る)。"""
    try:
        changed = subprocess.run(
            ["git", "diff", "--name-only", "-z", mark, "--"],
            check=True, capture_output=True,
        ).stdout
        fresh = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", "-z"],
            check=True, capture_output=True,
        ).stdout
    except (subprocess.CalledProcessError, OSError):
        return None
    return {name.decode("utf-8", "replace") for name in (changed + fresh).split(b"\0") if name}


def main():
    mark = sys.argv[1] if len(sys.argv) > 1 else None
    paths = everything()
    changed = changed_since(mark) if mark else None
    if changed is not None:
        paths = [path for path in paths if path in changed]
    broken = [path for path in paths if not readable(path)]
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
