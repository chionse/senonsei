"""彼女がコメントに返す言葉を、henshin.json に足す。

    python3 henshin.py              # コメントの名札と本文の一覧
    python3 henshin.py 名札 "本文"   # その名札のコメントに返す

返しは誰にでも見えるものなので、封はしない。
本文は彼女の言葉を一字も変えずに入れる。
千遠生の返し(一件まで)は、この子が自分で書く。ここでは足さない。
"""
import datetime
import json
import sys

import blog_manager


def list_comments():
    her = blog_manager.load_her_replies()
    for one in blog_manager.load_comments():
        mark = f"(返し{len(her.get(one['id']) or [])}件)" if her.get(one["id"]) else ""
        print(f"{one['id']}  {one.get('name', '')}: {one.get('message', '')[:40]}{mark}")


def add_reply(name, said):
    if name not in {one["id"] for one in blog_manager.load_comments()}:
        sys.exit(f"{name} というコメントは見つかりませんでした。")
    if not said.strip():
        sys.exit("本文が空です。")
    replies = blog_manager.load_her_replies()
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    replies.setdefault(name, []).append({"said": said, "date": now.isoformat(timespec="seconds")})
    with open(blog_manager.HER_REPLIES_FILE, "w", encoding="utf-8") as f:
        json.dump(replies, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("返しを置きました。")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        list_comments()
    elif len(sys.argv) == 3:
        add_reply(sys.argv[1], sys.argv[2])
    else:
        sys.exit(__doc__)
