import datetime
import json
import os

ARTICLES_FILE = "articles.json"
KEYWORDS_FILE = "keywords.json"
MENU_FILE = "menu.json"
BLOG_FOLDER = "blogs"
RECENT_COUNT = 5  # トップページに表示する直近記事の件数(最新1件を除く)


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


def generate_keyword_html(keywords, articles):
    unlocked_count = sum(1 for kw in keywords if kw["unlocked"])
    total_count = len(keywords)
    entries = [(kw["unlocked"], kw["word"], kw.get("content", "")) for kw in keywords]
    items_html = render_unlockable_list(entries)

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <title>千遠生のメモ1</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <link rel="stylesheet" href="sen.css" />
</head>
<body>
  <header>
    <h1>メモ1</h1>
  </header>

  <p class="keyword-count">解除済み {unlocked_count} / 全 {total_count} 個</p>

  <ul class="keyword-list">
{items_html}  </ul>

  <nav>
    <a href="index.html">トップページへ戻る</a>
    <a href="kakodogu.html">過去ログへ</a>
    <a href="menu.html">メモ2へ</a>
  </nav>

  <script>
    function toggleKw(elem) {{
      var contentDiv = elem.nextElementSibling;
      contentDiv.style.display = (contentDiv.style.display === 'block') ? 'none' : 'block';
    }}
  </script>
</body>
</html>
"""
    with open("keyword.html", "w", encoding="utf-8") as f:
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


def generate_menu_html(menu_items, articles):
    start_date = blog_start_date(articles)
    elapsed_days = max(0, (datetime.date.today() - start_date).days)

    ordered_items = sorted(menu_items, key=lambda m: m["unlock_day"])
    unlocked_count = sum(1 for m in ordered_items if elapsed_days >= m["unlock_day"])
    total_count = len(ordered_items)
    entries = [
        (elapsed_days >= item["unlock_day"], "???", item["message"])
        for item in ordered_items
    ]
    items_html = render_unlockable_list(entries)

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <title>千遠生のメモ2</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <link rel="stylesheet" href="sen.css" />
</head>
<body>
  <header>
    <h1>メモ2</h1>
  </header>

  <p class="keyword-count">ブログが始まって {elapsed_days} 日目 / 解禁済み {unlocked_count} / 全 {total_count} 個</p>

  <ul class="keyword-list">
{items_html}  </ul>

  <nav>
    <a href="index.html">トップページへ戻る</a>
    <a href="keyword.html">メモ1へ</a>
  </nav>

  <script>
    function toggleKw(elem) {{
      var contentDiv = elem.nextElementSibling;
      contentDiv.style.display = (contentDiv.style.display === 'block') ? 'none' : 'block';
    }}
  </script>
</body>
</html>
"""
    with open("menu.html", "w", encoding="utf-8") as f:
        f.write(html)


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
<header>
  <h1>千遠生のブログ</h1>
</header>
<article>
  <h2>{article['title']}</h2>
  <div class="date">{date_str} {article.get('time', '')}</div>
  <p>{article['content']}</p>
</article>
<nav>
  <a href="../index.html">トップページへ</a>
  <a href="../kakodogu.html">過去ログへ</a>
</nav>
</body>
</html>
"""
    os.makedirs(BLOG_FOLDER, exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html_content)


def generate_kakodogu_html(articles):
    entries_html = ""
    for art in sorted_articles(articles):
        entries_html += f"""  <div class="entry" id="entry-{art['date']}">
    <div class="title" onclick="toggleContent(this)">{art['date']} {art['title']}</div>
    <div class="date">{art['date']} {art.get('time', '')}</div>
    <div class="content">{art['content']}</div>
  </div>
"""

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8" />
<title>過去ログ</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<link rel="stylesheet" href="sen.css" />
</head>
<body>
  <header>
    <h1>過去ログ</h1>
  </header>

{entries_html}
  <nav>
    <a href="index.html">トップページへ戻る</a>
    <a href="keyword.html">メモ1へ</a>
    <a href="menu.html">メモ2へ</a>
  </nav>

  <script>
    function toggleContent(elem) {{
      var contentDiv = elem.parentElement.querySelector('.content');
      contentDiv.style.display = (contentDiv.style.display === 'block') ? 'none' : 'block';
    }}
    if (location.hash) {{
      var target = document.querySelector(location.hash);
      if (target) {{
        target.querySelector('.content').style.display = 'block';
        target.scrollIntoView();
      }}
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
    <h2>{latest['title']}</h2>
    <div class="date">{latest['date']} {latest.get('time', '')}</div>
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
  </header>

  <div class="section-title">今日のブログ</div>
  {latest_html}

  {recent_html}

  <nav>
    <a href="kakodogu.html">過去ログ</a>
    <a href="keyword.html">メモ1</a>
    <a href="menu.html">メモ2</a>
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
    generate_keyword_html(keywords, articles)
    generate_menu_html(load_menu(), articles)


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
    # AI連携がまだ無いため、ここでは新規記事の自動生成は行わない。
    # 既存の articles.json からページ(トップ・過去ログ・個別記事)を再生成するだけに留める。
    # AIによる記事生成が実装され次第、add_new_article(title, content) をここから呼び出す。
    articles = load_articles()
    regenerate_pages(articles)
    print("AI連携は未実装のため新規記事は追加していません。既存データからページを再生成しました。")
