import datetime
import json
import os

ARTICLES_FILE = "articles.json"
KEYWORDS_FILE = "keywords.json"
MENU_FILE = "menu.json"
BLOG_FOLDER = "blogs"
COMMENTS_FOLDER = "comments"
COMMENT_WORKER_ENDPOINT = "https://senonsei-comments.chitomatsu.workers.dev/"
RECENT_COUNT = 5  # トップページに表示する直近記事の件数(最新1件を除く)


def load_comments():
    """Cloudflare Workerがcomments/に自動コミットしたJSONファイルを全部読み込む。"""
    comments = []
    if os.path.isdir(COMMENTS_FOLDER):
        for filename in os.listdir(COMMENTS_FOLDER):
            if filename.endswith(".json"):
                with open(os.path.join(COMMENTS_FOLDER, filename), "r", encoding="utf-8") as f:
                    comments.append(json.load(f))
    comments.sort(key=lambda c: c.get("date", ""), reverse=True)
    return comments


def format_comment_date(iso_string):
    """コメントに記録されたUTC時刻を、日本時間の秒までの表示にする。"""
    if not iso_string:
        return ""
    try:
        dt = datetime.datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
    except ValueError:
        return ""
    jst = dt.astimezone(datetime.timezone(datetime.timedelta(hours=9)))
    return jst.strftime("%Y-%m-%d %H:%M:%S")


def load_articles():
    if os.path.exists(ARTICLES_FILE):
        with open(ARTICLES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_articles(articles):
    with open(ARTICLES_FILE, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)


def sorted_articles(articles):
    return sorted(articles, key=lambda a: (a["date"], a.get("time", "")), reverse=True)


def load_keywords():
    if os.path.exists(KEYWORDS_FILE):
        with open(KEYWORDS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_keywords(keywords):
    with open(KEYWORDS_FILE, "w", encoding="utf-8") as f:
        json.dump(keywords, f, ensure_ascii=False, indent=2)


def update_keywords(articles):
    """ブログ本文にキーワードが登場したらロックを解除する。"""
    keywords = load_keywords()
    ordered = sorted(articles, key=lambda a: (a["date"], a.get("time", "")))  # 古い順
    changed = False

    for kw in keywords:
        if kw["unlocked"]:
            continue
        for art in ordered:
            if kw["word"] in art["content"] or kw["word"] in art["title"]:
                kw["unlocked"] = True
                kw["unlocked_date"] = art["date"]
                changed = True
                break

    if changed:
        save_keywords(keywords)
    return keywords


def render_unlockable_list(entries):
    """entries: [(unlocked: bool, label: str, content: str), ...] から
    ロック中は「???」、解除済みはクリックで本文が開くリストのHTMLを作る。"""
    items_html = ""
    for unlocked, label, content in entries:
        if unlocked:
            items_html += f"""    <li>
      <div class="kw-word" onclick="toggleKw(this)">{label}</div>
      <div class="kw-content">{content}</div>
    </li>
"""
        else:
            items_html += '    <li class="locked">???</li>\n'
    return items_html


def generate_memo_html(keywords, menu_items, articles):
    """メモ1とメモ2を1つのページに入れ、上のタブで切り替えられるようにする。"""
    keyword_entries = [(kw["unlocked"], kw["word"], kw.get("content", "")) for kw in keywords]
    keyword_items = render_unlockable_list(keyword_entries)
    keyword_unlocked = sum(1 for kw in keywords if kw["unlocked"])

    start_date = blog_start_date(articles)
    elapsed = max(0, (datetime.date.today() - start_date).days)
    ordered_menu = sorted(menu_items, key=lambda m: m["unlock_day"])
    menu_entries = [
        (elapsed >= item["unlock_day"], "???", item["message"]) for item in ordered_menu
    ]
    menu_items_html = render_unlockable_list(menu_entries)
    menu_unlocked = sum(1 for m in ordered_menu if elapsed >= m["unlock_day"])

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <title>メモ</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <link rel="stylesheet" href="sen.css" />
</head>
<body>
  <div class="top-nav">
    <a href="index.html">←トップ</a>
  </div>

  <header>
    <h1>メモ</h1>
    <div class="memo-switch">
      <span class="here" id="tab1" onclick="showMemo(1)">メモ1</span>
      <span id="tab2" onclick="showMemo(2)">メモ2</span>
    </div>
  </header>

  <div id="memo1">
    <p class="keyword-count">解除済み 全{keyword_unlocked} / {len(keywords)} 個</p>
    <ul class="keyword-list">
{keyword_items}    </ul>
  </div>

  <div id="memo2" hidden>
    <p class="keyword-count">解禁済み 全{menu_unlocked} / {len(ordered_menu)} 個</p>
    <ul class="keyword-list">
{menu_items_html}    </ul>
  </div>

  <script>
    function toggleKw(elem) {{
      var contentDiv = elem.nextElementSibling;
      contentDiv.style.display = (contentDiv.style.display === 'block') ? 'none' : 'block';
    }}
    function showMemo(which) {{
      document.getElementById('memo1').hidden = (which !== 1);
      document.getElementById('memo2').hidden = (which !== 2);
      document.getElementById('tab1').className = (which === 1) ? 'here' : '';
      document.getElementById('tab2').className = (which === 2) ? 'here' : '';
    }}
  </script>
</body>
</html>
"""
    with open("memo.html", "w", encoding="utf-8") as f:
        f.write(html)


def load_menu():
    if os.path.exists(MENU_FILE):
        with open(MENU_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def blog_start_date(articles):
    """ブログが始まった日(=一番古い記事の日付)を返す。記事が無ければ今日にする。"""
    if not articles:
        return datetime.date.today()
    earliest = min(a["date"] for a in articles)
    return datetime.date.fromisoformat(earliest)


def generate_blog_html(article):
    date_str = article["date"]
    filename = os.path.join(BLOG_FOLDER, f"blog_{date_str}.html")
    html_content = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8" />
<title>千遠生ブログ {date_str}「{article['title']}」</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<link rel="stylesheet" href="../sen.css" />
</head>
<body>
<div class="top-nav"><a href="../index.html">←トップ</a></div>
<header>
  <h1>千遠生のブログ</h1>
</header>
<article>
  <div class="date">{date_str} {article.get('time', '')}<span class="article-title">{article['title']}</span></div>
  <p>{article['content']}</p>
</article>
</body>
</html>
"""
    os.makedirs(BLOG_FOLDER, exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html_content)


def generate_kakodogu_html(articles):
    """月ごとに1行、ログが溜まると下に積み重なっていく。"""
    ordered = sorted_articles(articles)

    grouped = {}
    for art in ordered:
        year, month, _ = art["date"].split("-")
        grouped.setdefault((year, month), []).append(art)

    log_html = ""
    for (year, month) in sorted(grouped, reverse=True):
        days = "".join(
            f'<span class="log-day" onclick="showEntry(\'{art["date"]}\')">'
            f'{int(art["date"].split("-")[2])}日</span>'
            for art in grouped[(year, month)]
        )
        log_html += (
            f'      <div class="log-row">'
            f'<span class="log-ym">{year}年 {int(month)}月</span>'
            f'<span class="log-days">{days}</span>'
            f"</div>\n"
        )

    entries_html = ""
    for index, art in enumerate(ordered):
        hidden = "" if index == 0 else " hidden"
        entries_html += f"""    <div class="entry" id="entry-{art['date']}"{hidden}>
      <div class="entry-title">{art['title']}</div>
      <div class="date">{art['date']} {art.get('time', '')}</div>
      <p>{art['content']}</p>
    </div>
"""
    if not ordered:
        entries_html = "    <p>まだ何も書かれていません。</p>\n"

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8" />
<title>過去ログ</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<link rel="stylesheet" href="sen.css" />
</head>
<body>
  <div class="top-nav"><a href="index.html">←トップ</a></div>

  <header>
    <h1>過去ログ</h1>
  </header>

  <div class="log-layout">
    <div class="log-list">
{log_html}    </div>
    <div class="log-view">
{entries_html}    </div>
  </div>

  <script>
    function showEntry(date) {{
      var entries = document.querySelectorAll('.log-view .entry');
      for (var i = 0; i < entries.length; i++) {{
        entries[i].hidden = (entries[i].id !== 'entry-' + date);
      }}
    }}
    if (location.hash) {{
      showEntry(location.hash.replace('#entry-', ''));
    }}
  </script>
</body>
</html>
"""
    with open("kakodogu.html", "w", encoding="utf-8") as f:
        f.write(html)


def generate_index_html(articles):
    ordered = sorted_articles(articles)

    if not ordered:
        latest_html = "<p>まだブログ記事がありません。</p>"
        recent_html = ""
    else:
        latest = ordered[0]
        latest_html = f"""<article>
    <div class="date">{latest['date']} {latest.get('time', '')}<span class="article-title">{latest['title']}</span></div>
    <p>{latest['content']}</p>
  </article>"""

        recent = ordered[1:1 + RECENT_COUNT]
        if recent:
            items = "\n".join(
                f'    <li><span class="date">{a["date"]}</span>'
                f'<a href="{BLOG_FOLDER}/blog_{a["date"]}.html">{a["title"]}</a></li>'
                for a in recent
            )
            recent_html = f"""<div class="section-title">直近のブログ</div>
  <ul class="recent-list">
{items}
  </ul>
  <div class="more-link"><a href="kakodogu.html">More...</a></div>"""
        else:
            recent_html = ""

    comments = load_comments()
    if comments:
        comments_html = "\n".join(
            f"""  <div class="comment-entry">
    <div class="comment-name">{c.get('name', '名無しさん')}<span class="comment-date">{format_comment_date(c.get('date', ''))}</span></div>
    <div class="comment-message">{c.get('message', '')}</div>
  </div>"""
            for c in comments
        )
    else:
        comments_html = "  <p>まだコメントはありません。</p>"

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <title>千遠生のサイト</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <link rel="stylesheet" href="sen.css" />
</head>
<body>
  <header>
    <h1>千遠生のサイト</h1>
    <div class="visitor-counter">
      あなたは
      <!-- Default Statcounter code for senonsei
      https://chionse.github.io/senonsei/index.html -->
      <script type="text/javascript">
      var sc_project=13354593;
      var sc_invisible=0;
      var sc_security="4b65a54b";
      var scJsHost = "https://";
      document.write("<sc"+"ript type='text/javascript' src='" + scJsHost+
      "statcounter.com/counter/counter.js'></"+"script>");
      </script>
      <noscript><div class="statcounter"><a title="web stats"
      href="https://statcounter.com/" target="_blank"><img class="statcounter"
      src="https://c.statcounter.com/13354593/0/4b65a54b/0/" alt="web stats"
      referrerPolicy="no-referrer-when-downgrade"></a></div></noscript>
      <!-- End of Statcounter Code -->
      人目の来訪者です
    </div>
  </header>

  <div class="section-title">今日のブログ</div>
  {latest_html}

  {recent_html}

  <div class="section-title" id="comments">コメント</div>
  <div class="comment-list">
{comments_html}
  </div>

  <form class="comment-form" method="POST" action="{COMMENT_WORKER_ENDPOINT}">
    <input type="text" name="name" placeholder="名前" required />
    <textarea name="message" placeholder="コメント" required></textarea>
    <button type="submit">送信</button>
  </form>

  <nav>
    <a href="kakodogu.html">過去ログ</a>
    <a href="memo.html">メモ</a>
    <a href="profile.html">プロフィール</a>
  </nav>
</body>
</html>
"""
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)


def regenerate_pages(articles):
    for art in articles:
        generate_blog_html(art)
    generate_kakodogu_html(articles)
    generate_index_html(articles)
    keywords = update_keywords(articles)
    generate_memo_html(keywords, load_menu(), articles)


def add_new_article(title, content, date_str=None):
    """記事を1件追加してページを再生成する。同じ日付の記事が既にある場合は追加しない(重複投稿の防止)。"""
    now = datetime.datetime.now()
    date_str = date_str or now.strftime('%Y-%m-%d')

    articles = load_articles()
    if any(a["date"] == date_str for a in articles):
        print(f"{date_str} の記事は既に存在するため追加しません。ページのみ再生成します。")
        regenerate_pages(articles)
        return

    new_article = {
        "date": date_str,
        "time": now.strftime('%H:%M'),
        "title": title,
        "content": content,
    }
    articles.append(new_article)
    save_articles(articles)
    regenerate_pages(articles)
    print(f"{date_str} のブログ記事を追加し、ページを再生成しました。")


if __name__ == "__main__":
    # 新しい記事を書くのは senonsei_ai.py の役目。
    # ここは既存データから全ページを組み直すだけ(コメント反映などで使う)。
    articles = load_articles()
    regenerate_pages(articles)
    print("既存データからページを再生成しました。")
