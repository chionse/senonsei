import datetime
import os

def generate_blog_html():
    today = datetime.date.today()
    date_str = today.strftime('%Y-%m-%d')

    txt_filename = f"blog_{date_str}.txt"
    html_filename = f"blog_{date_str}.html"

    # テキストファイル読み込み
    if not os.path.exists(txt_filename):
        print(f"{txt_filename} が見つかりません。")
        return

    with open(txt_filename, 'r', encoding='utf-8') as f:
        content = f.read()

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
  <p><a href="index.html">トップページに戻る</a></p>
</header>
<article>
  <p>{content}</p>
</article>
</body>
</html>"""

    with open(html_filename, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"{html_filename} を作成しました。")

if __name__ == "__main__":
    generate_blog_html()
