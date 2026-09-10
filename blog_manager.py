import datetime
import json
import os

ARTICLES_FILE = "articles.json"
BLOG_FOLDER = "blogs"

def load_articles():
    if os.path.exists(ARTICLES_FILE):
        with open(ARTICLES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_articles(articles):
    with open(ARTICLES_FILE, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

def generate_blog_html(date_str, content):
    filename = os.path.join(BLOG_FOLDER, f"blog_{date_str}.html")
    html_content = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8" />
<title>千遠生ブログ {date_str}</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<style>
body {{
    background-color: #fafaf7;
    font-family: 'Yu Mincho', '游明朝', 'MS Mincho', serif;
    color: #0029ae;
    margin: 20px auto;
    max-width: 700px;
    padding: 0 10px;
}}
header {{
    text-align: center;
    margin-bottom: 1rem;
}}
h1 {{
    margin: 0;
    font-size: 2rem;
    color: #0029ae;
}}
article {{
    padding: 1rem 0;
    margin-bottom: 1rem;
}}
</style>
</head>
<body>
<header>
  <h1>千遠生ブログ {date_str}</h1>
  <p><a href="../kakodogu.html">過去ログページへ戻る</a></p>
</header>
<article>
  <p>{content}</p>
</article>
</body>
</html>"""
    os.makedirs(BLOG_FOLDER, exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html_content)

def generate_index_html(articles):
    html = """<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <title>千遠生のブログ一覧</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    body {{
      background-color: #fafaf7;
      font-family: 'Yu Mincho', '游明朝', 'MS Mincho', serif;
      color: #0029ae;
      margin: 20px auto;
      max-width: 700px;
      padding: 0 10px;
    }}
    header {{
      text-align: center;
      margin-bottom: 1rem;
    }}
    h1 {{
      margin: 0;
      font-size: 2rem;
      color: #0029ae;
    }}
    article {{
      padding: 1rem 0;
      margin-bottom: 1rem;
    }}
    article h2 {{
      margin: 0 0 0.5rem;
      font-size: 1.2rem;
      color: #001d78;
    }}
    article .date {{
      font-size: 0.8rem;
      color: #0031a4;
      margin-bottom: 0.4rem;
    }}
    article p {{
      margin: 0;
      line-height: 1.4;
      max-height: 4.2em;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
  </style>
</head>
<body>
<header>
  <h1>千遠生のブログ一覧</h1>
</header>
"""
    for art in sorted(articles, key=lambda x: x["date"], reverse=True):
        html += f"""<article>
  <h2><a href="{BLOG_FOLDER}/blog_{art['date']}.html">{art['date']} 「{art['title']}」</a></h2>
  <div class="date">{art['date']}</div>
  <p>{art['content']}</p>
</article>
"""
    html += """
<nav>
  <a href="index.html">トップページへ</a>
</nav>
</body>
</html>"""
    with open("kakodogu.html", "w", encoding="utf-8") as f:
        f.write(html)

def add_new_article(title, content):
    today = datetime.date.today().strftime('%Y-%m-%d')
    articles = load_articles()
    new_article = {
        "date": today,
        "title": title,
        "content": content
    }
    articles.append(new_article)
    save_articles(articles)
    generate_blog_html(today, content)
    generate_index_html(articles)
    print(f"{today} のブログ記事を追加し、ファイル生成しました。")

if __name__ == "__main__":
    add_new_article("千遠生の日記", "これは自動生成された最新のブログ記事です。AIが少しずつ学習を進めています。")
