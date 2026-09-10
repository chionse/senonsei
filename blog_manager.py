import datetime
import json
import os

ARTICLES_FILE = "articles.json"
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
        entries_html += f"""  <div class="entry">
    <div class="title" onclick="toggleContent(this)">{art['date']} {art['title']}</div>
    <div class="date">{art['date']} {art.get('time', '')}</div>
    <div class="content">{art['content']}</div>
  </div>
"""

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8" />
<title>千遠生の過去ログ</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<link rel="stylesheet" href="sen.css" />
</head>
<body>
  <header>
    <h1>千遠生の過去ログ</h1>
  </header>

{entries_html}
  <nav>
    <a href="index.html">トップページへ戻る</a>
    <a href="keyword.html">キーワードメモへ</a>
  </nav>

  <script>
    function toggleContent(elem) {{
      var contentDiv = elem.parentElement.querySelector('.content');
      contentDiv.style.display = (contentDiv.style.display === 'block') ? 'none' : 'block';
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
  <title>千遠生のブログ</title>
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
    <a href="keyword.html">キーワードメモ</a>
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
