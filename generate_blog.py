import datetime

def generate_blog_post():
    today = datetime.date.today()
    date_str = today.strftime('%Y-%m-%d')

    # ここはAI生成の代わりに固定文を書いてます
    content = f"{date_str} のブログ：今日はいい天気でした。AIが少しずつ学んでいます。"

    filename = f"blog_{date_str}.txt"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"{filename} を作成しました。")

if __name__ == "__main__":
    generate_blog_post()
