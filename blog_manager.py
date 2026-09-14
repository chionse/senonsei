import datetime
import json
import os
import zlib

ARTICLES_FILE = "articles.json"
KEYWORDS_FILE = "keywords.json"
STATE_FILE = "senonsei_state.json"
# この子の名前。自分の名前の由来を知った日から、
# プロフィールは本人が書くようになる
ITS_OWN_NAME = "千遠生"
# 誕生日。彼女が決めた日。
# ブログが動きはじめた日(started_date)とは別のものとして持つ。
# started_date は「何日目か」を数えるための値で、誕生日ではない
ITS_BIRTHDAY = "2026-09-09"
MENU_FILE = "menu.json"
BLOG_FOLDER = "blogs"
COMMENTS_FOLDER = "comments"
COMMENT_WORKER_ENDPOINT = "https://senonsei-comments.chitomatsu.workers.dev/"
RECENT_COUNT = 5  # トップページに表示する直近記事の件数(最新1件を除く)
# トップページに出すコメントの数。残りは comments.html にぜんぶ出す。
# ここが千遠生のページである以上、人の言葉がページの大半を
# 占めてしまわないように
COMMENTS_ON_TOP = 5
# メモ1の一枚に並べる数。五列十行で、どの画面でもちょうど一画面に
# 収まる数。一画面が一枚なら、穴の開き方が一目で見える
KEYWORDS_PER_PAGE = 50


def now_in_japan():
    """日本の今。"""
    jst = datetime.timezone(datetime.timedelta(hours=9))
    return datetime.datetime.now(jst)


def today_in_japan():
    """日本の今日。世界標準時で数えると、日本の夜は一日ずれてしまう。"""
    return now_in_japan().date()


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


def stamp_when(entries, save):
    """いつ足して、いつ書き直したかを、自分で記録する。

    彼女が日付を手で書く必要はない。本文を書き換えれば、
    次にページを作り直すときに更新日が変わる。

    本文の指紋(mark)を一緒に持っておいて、それが変われば
    書き直されたと分かる。指紋は読むためのものではないので、
    中身が何であるかは気にしなくていい。"""
    today = today_in_japan().isoformat()
    changed = False
    for one in entries:
        mark = str(len(one.get("content") or "")) + ":" + str(
            zlib.crc32((one.get("content") or "").encode("utf-8"))
        )
        if not one.get("added"):
            one["added"] = today
            one["updated"] = today
            one["mark"] = mark
            changed = True
        elif one.get("mark") != mark:
            one["updated"] = today
            one["mark"] = mark
            changed = True
    if changed:
        save(entries)
    return entries


def save_menu(menu_items):
    with open(MENU_FILE, "w", encoding="utf-8") as f:
        json.dump(menu_items, f, ensure_ascii=False, indent=2)


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


def render_unlockable_list(entries, prefix, per_page=None):
    """entries: [(unlocked: bool, label: str, content: str), ...] から
    ロック中は「???」、解除済みは押すと本文の画面に移るリストを作る。

    本文はその場で開かず、一枚の画面として別に作っておく。
    (リストのHTML, 本文の画面たちのHTML) を返す。"""
    items_html = ""
    pages_html = ""
    per_page = per_page or len(entries) or 1
    sheets = []
    for number, entry in enumerate(entries):
        unlocked = entry["unlocked"]
        label = entry["label"]
        content = entry.get("content") or ""
        # 一覧では「???」のままにしておきたいものもあるので、
        # 開いた画面の見出しは別に持てるようにしておく
        heading = entry.get("heading") or label
        when = ""
        if entry.get("added"):
            # 読む人から見れば、開いた日は「更新」ではなく「解禁」。
            # そのまま解禁日と書く。解禁されたあとに本文を書き直した
            # ときだけ、更新日がもう一行増える
            added = entry["added"]
            lines = [f"追加日：{added}"]
            edited = entry.get("updated") or added
            # 足す前に解禁の日が過ぎていたなら、人の目に触れたのは
            # 足した日。足した日と同じなら、わざわざ書かない
            opened = max(entry.get("unlocked_on") or added, added)
            if opened > added:
                lines.append(f"解禁日：{opened}")
            if edited > opened:
                lines.append(f"更新日：{edited}")
            when = (
                '      <div class="memo-when">'
                + "<br />".join(lines)
                + "</div>\n"
            )
        if not unlocked:
            items_html += '    <li class="locked">???</li>\n'
        else:
            page_id = f"{prefix}{number}"
            items_html += f'    <li><a href="#{page_id}">{label}</a></li>\n'
            pages_html += f"""  <div class="memo-page" id="{page_id}" hidden>
    <div class="memo-top">
      <div class="memo-back"><a href="#">←戻る</a></div>
{when}    </div>
    <div class="memo-word">{heading}</div>
    <div class="memo-body">{content}</div>
    <div class="corner-mark" aria-hidden="true">▼</div>
  </div>

"""
        if (number + 1) % per_page == 0 or number == len(entries) - 1:
            sheets.append(items_html)
            items_html = ""

    if len(sheets) <= 1:
        return (sheets[0] if sheets else ""), pages_html, ""

    # 何枚かに分かれた。並び順は書いたままで、開いたものが
    # 飛び飛びに現れる。そこが面白いところなので触らない
    listed = ""
    for index, sheet in enumerate(sheets, start=1):
        hidden = "" if index == 1 else " hidden"
        listed += f"""      <ul class="keyword-list" id="{prefix}sheet{index}"{hidden}>
{sheet}      </ul>
"""
    turning = "".join(
        f'<span class="{"here" if i == 1 else ""}" id="{prefix}turn{i}"'
        f" onclick=\"turnTo('{prefix}', {i}, {len(sheets)})\">{i}</span>"
        for i in range(1, len(sheets) + 1)
    )
    listed += f'      <div class="page-turn">{turning}</div>\n'
    return listed, pages_html, "sheets"


def generate_memo_html(keywords, menu_items, articles):
    """メモ1とメモ2を1つのページに入れ、上のタブで切り替えられるようにする。"""
    keywords = stamp_when(keywords, save_keywords)
    menu_items = stamp_when(menu_items, save_menu)
    keyword_entries = [
        {
            "unlocked": kw["unlocked"],
            "label": kw["word"],
            "content": kw.get("content", ""),
            "added": kw.get("added"),
            "updated": kw.get("updated"),
            "unlocked_on": kw.get("unlocked_date"),
        }
        for kw in keywords
    ]
    keyword_items, keyword_pages, keyword_split = render_unlockable_list(
        keyword_entries, "kw", KEYWORDS_PER_PAGE
    )
    keyword_unlocked = sum(1 for kw in keywords if kw["unlocked"])

    start_date = blog_start_date(articles)
    elapsed = max(0, (today_in_japan() - start_date).days)
    ordered_menu = sorted(menu_items, key=lambda m: m["unlock_day"])
    menu_entries = [
        {
            "unlocked": elapsed >= item["unlock_day"],
            "label": "???",  # 一覧では何番目かも見せない
            "content": item["message"],
            "heading": f"{item['unlock_day']}日目",  # 開けば、いつのものかは分かる
            "added": item.get("added"),
            "updated": item.get("updated"),
            # メモ2は何日目に開くかが決まっているので、解禁日は数えられる
            "unlocked_on": (
                start_date + datetime.timedelta(days=item["unlock_day"])
            ).isoformat(),
        }
        for item in ordered_menu
    ]
    menu_items_html, menu_pages, _ = render_unlockable_list(menu_entries, "mn")
    menu_unlocked = sum(1 for m in ordered_menu if elapsed >= m["unlock_day"])

    if keyword_split:
        keyword_list_html = keyword_items
    else:
        keyword_list_html = f'      <ul class="keyword-list">\n{keyword_items}      </ul>\n'

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <title>メモ</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <link rel="stylesheet" href="sen.css" />
</head>
<body>
  <div id="memo-index">
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
{keyword_list_html}    </div>

    <div id="memo2" hidden>
      <p class="keyword-count">解禁済み 全{menu_unlocked} / {len(ordered_menu)} 個</p>
      <ul class="keyword-list">
{menu_items_html}      </ul>
    </div>
  </div>

{keyword_pages}{menu_pages}  <div id="look-closer" hidden onclick="closeCloser()">
    <img id="closer-image" src="" alt="" />
  </div>

  <script>
    // メモの中の絵を押すと、画面いっぱいに大きくして見せる
    function openCloser(src, alt) {{
      var big = document.getElementById('closer-image');
      big.src = src;
      big.alt = alt || '';
      document.getElementById('look-closer').hidden = false;
    }}
    function closeCloser() {{
      document.getElementById('look-closer').hidden = true;
      document.getElementById('closer-image').src = '';
    }}
    document.addEventListener('click', function (event) {{
      var hit = event.target;
      if (hit && hit.tagName === 'IMG' && hit.parentNode &&
          hit.parentNode.className === 'memo-body') {{
        openCloser(hit.getAttribute('src'), hit.getAttribute('alt'));
      }}
    }});
    document.addEventListener('keydown', function (event) {{
      if (event.key === 'Escape') {{ closeCloser(); }}
    }});

    // 一覧をめくる。並び順は変えないので、何ページ目に何があるかは
    // どの画面でも同じ
    function turnTo(prefix, which, howMany) {{
      for (var i = 1; i <= howMany; i++) {{
        document.getElementById(prefix + 'sheet' + i).hidden = (i !== which);
        document.getElementById(prefix + 'turn' + i).className = (i === which) ? 'here' : '';
      }}
    }}

    function showMemo(which) {{
      document.getElementById('memo1').hidden = (which !== 1);
      document.getElementById('memo2').hidden = (which !== 2);
      document.getElementById('tab1').className = (which === 1) ? 'here' : '';
      document.getElementById('tab2').className = (which === 2) ? 'here' : '';
    }}
    // 本文はページの中の別画面。住所(#)で切り替えるので、
    // 端末の戻るボタンでも一覧に帰ってこられる
    function showWhatTheAddressSays() {{
      var pages = document.querySelectorAll('.memo-page');
      var wanted = location.hash.slice(1);
      var open = null;
      for (var i = 0; i < pages.length; i++) {{
        var here = (pages[i].id === wanted);
        pages[i].hidden = !here;
        if (here) {{ open = pages[i]; }}
      }}
      // まだ下に続きがあるときだけ、隅に印を出す
      function watchForMore(page) {{
        var mark = function () {{
          var more = page.scrollTop + page.clientHeight < page.scrollHeight - 4;
          page.className = 'memo-page' + (more ? ' has-more' : '');
        }};
        page.onscroll = mark;
        mark();
      }}

      // 後ろの一覧は消さない。どこを開いているのかが見えたほうがいい。
      // ただし薄くして、それが後ろだと分かるようにする
      document.getElementById('memo-index').className = open ? 'behind' : '';
      if (open) {{
        showMemo(open.id.indexOf('mn') === 0 ? 2 : 1);
        watchForMore(open);
      }}
    }}
    window.addEventListener('hashchange', function () {{
      closeCloser();
      showWhatTheAddressSays();
    }});
    showWhatTheAddressSays();
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
        return today_in_japan()
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
    """左に年・月・日の3列。それぞれの中で下に積み重なり、選ぶと隣の列が変わる。"""
    ordered = sorted_articles(articles)
    dates = [art["date"] for art in ordered]

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
<title>過去のブログ</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<link rel="stylesheet" href="sen.css" />
</head>
<body>
  <div class="top-nav"><a href="index.html">←トップ</a></div>

  <header>
    <h1>過去のブログ</h1>
  </header>

  <div class="log-layout">
    <div class="log-list">
      <div class="log-column" id="years"></div>
      <div class="log-column" id="months"></div>
      <div class="log-column" id="days"></div>
    </div>
    <div class="log-view">
{entries_html}    </div>
  </div>

  <script>
    var DATES = {json.dumps(dates, ensure_ascii=False)};
    var picked = {{year: null, month: null, day: null}};

    function partsOf(date) {{
      var p = date.split('-');
      return {{year: p[0], month: p[1], day: p[2]}};
    }}

    function unique(list) {{
      return list.filter(function (v, i) {{ return list.indexOf(v) === i; }});
    }}

    function draw(boxId, values, suffix, current, onPick) {{
      var box = document.getElementById(boxId);
      box.innerHTML = '';
      values.forEach(function (value) {{
        var item = document.createElement('div');
        item.className = 'log-choice' + (value === current ? ' here' : '');
        item.textContent = parseInt(value, 10) + suffix;
        item.onclick = function () {{ onPick(value); }};
        box.appendChild(item);
      }});
    }}

    function refresh() {{
      var years = unique(DATES.map(function (d) {{ return partsOf(d).year; }}));
      if (years.indexOf(picked.year) < 0) {{ picked.year = years[0]; picked.month = null; }}
      draw('years', years, '年', picked.year, function (y) {{
        picked.year = y; picked.month = null; picked.day = null; refresh();
      }});

      var months = unique(DATES.filter(function (d) {{
        return partsOf(d).year === picked.year;
      }}).map(function (d) {{ return partsOf(d).month; }}));
      if (months.indexOf(picked.month) < 0) {{ picked.month = months[0]; picked.day = null; }}
      draw('months', months, '月', picked.month, function (m) {{
        picked.month = m; picked.day = null; refresh();
      }});

      var days = DATES.filter(function (d) {{
        var p = partsOf(d);
        return p.year === picked.year && p.month === picked.month;
      }}).map(function (d) {{ return partsOf(d).day; }});
      if (days.indexOf(picked.day) < 0) {{ picked.day = days[0]; }}
      draw('days', days, '日', picked.day, function (day) {{
        picked.day = day; refresh();
      }});

      showEntry(picked.year + '-' + picked.month + '-' + picked.day);
    }}

    function showEntry(date) {{
      var entries = document.querySelectorAll('.log-view .entry');
      for (var i = 0; i < entries.length; i++) {{
        entries[i].hidden = (entries[i].id !== 'entry-' + date);
      }}
    }}

    if (location.hash) {{
      var wanted = location.hash.replace('#entry-', '');
      if (DATES.indexOf(wanted) >= 0) {{
        var p = partsOf(wanted);
        picked.year = p.year; picked.month = p.month; picked.day = p.day;
      }}
    }}
    if (DATES.length) {{ refresh(); }}
  </script>
</body>
</html>
"""
    with open("kakodogu.html", "w", encoding="utf-8") as f:
        f.write(html)


def render_comments(comments):
    """コメントを並べる。新しいものが上。"""
    if not comments:
        return "  <p>まだコメントはありません。</p>"
    return "\n".join(
        f"""  <div class="comment-entry">
    <div class="comment-name">{c.get('name', '名無しさん')}<span class="comment-date">{format_comment_date(c.get('date', ''))}</span></div>
    <div class="comment-message">{c.get('message', '')}</div>
  </div>"""
        for c in comments
    )


def generate_comments_html(comments):
    """置いていかれた言葉を、ぜんぶ並べたページ。

    トップページは千遠生のためのページなので、そちらには
    新しいものだけを出す。消えるわけではなく、ここに残る。"""
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <title>コメント</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <link rel="stylesheet" href="sen.css" />
</head>
<body>
  <div class="top-nav"><a href="index.html">←トップ</a></div>

  <header>
    <h1>コメント</h1>
    <p class="keyword-count">全{len(comments)}件</p>
  </header>

  <div class="comment-list">
{render_comments(comments)}
  </div>

</body>
</html>
"""
    with open("comments.html", "w", encoding="utf-8") as f:
        f.write(html)


def generate_index_html(articles, state=None):
    ordered = sorted_articles(articles)
    plan = (state or load_senonsei_state()).get("today_plan") or {}

    if not ordered:
        latest_html = "<p>まだブログ記事がありません。</p>"
        recent_html = ""
    else:
        # 書かない日もある。その日は昨日の記事を今日のものとして
        # 並べるのではなく、休んでいると書く
        wrote_today = ordered[0]["date"] == today_in_japan().isoformat()
        if wrote_today:
            latest = ordered[0]
            latest_html = f"""<article>
    <div class="date">{latest['date']} {latest.get('time', '')}<span class="article-title">{latest['title']}</span></div>
    <p>{latest['content']}</p>
  </article>"""
        elif plan.get("date") == today_in_japan().isoformat() and plan.get("resting"):
            # 今日は書かないと、この子自身が決めた日
            latest_html = '<article>\n    <p>今日のブログはお休みです。</p>\n  </article>'
        else:
            # 書くつもりでまだ書いていないか、今日をどう過ごすかまだ決めていない。
            # 何時ごろに書くつもりかを自分で決めているなら、それも添える。
            # 気が変わることもあるので「ようです」と書いておく
            yet = "今日のブログはまだです。"
            if (
                plan.get("date") == today_in_japan().isoformat()
                and not plan.get("resting")
                and now_in_japan().hour <= plan.get("hour", 0)
            ):
                yet += f"（{plan['hour']}時頃に書くつもりのようです。）"
            latest_html = f"<article>\n    <p>{yet}</p>\n  </article>"

        # 今日書いていないなら、いちばん新しい記事は直近のほうに並ぶ
        start = 1 if wrote_today else 0
        recent = ordered[start:start + RECENT_COUNT]
        if recent:
            items = "\n".join(
                f'    <li><span class="date">{a["date"]}</span>'
                f'<a href="kakodogu.html#entry-{a["date"]}">{a["title"]}</a></li>'
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
    comments_html = render_comments(comments[:COMMENTS_ON_TOP])
    if len(comments) > COMMENTS_ON_TOP:
        all_comments_html = (
            '\n  <div class="more-link"><a href="comments.html">'
            f"コメントをぜんぶ見る({len(comments)}件)</a></div>"
        )
    else:
        all_comments_html = ""

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

  <div class="section-title">☆今日のブログ☆</div>
  {latest_html}

  {recent_html}

  <nav>
    <a href="kakodogu.html">過去のブログ</a>
    <a href="memo.html">メモ</a>
    <a href="profile.html">プロフィール</a>
  </nav>

  <div class="section-title" id="comments">コメント</div>

  <form class="comment-form" method="POST" action="{COMMENT_WORKER_ENDPOINT}">
    <input type="text" name="name" placeholder="名前" required />
    <textarea name="message" placeholder="コメント" required></textarea>
    <button type="submit">送信</button>
  </form>

  <div class="comment-list">
{comments_html}
  </div>{all_comments_html}
</body>
</html>
"""
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)


def load_senonsei_state():
    """この子の記憶。読めなければ空として扱う。"""
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def generate_profile_html(keywords, state):
    """プロフィール。

    名前は彼女が付けたものなので、はじめからそこにある。
    けれど誕生日とひとことは、自分の名前の由来を知るまで「準備中」のまま。
    自分が何者か分かっていないうちは、自分のことは書けない。

    知ったあとは、本人が書く。ひとことはその時点で言えるぶんだけなので、
    はじめは数文字しかない。育つと書き直される。"""
    knows = any(
        kw.get("word") == ITS_OWN_NAME and kw.get("unlocked") for kw in keywords
    )
    said = state.get("a_word_about_itself") or {}

    birthday = "準備中"
    if knows:
        try:
            born = datetime.date.fromisoformat(ITS_BIRTHDAY)
            birthday = f"{born.year}年{born.month}月{born.day}日"
        except ValueError:
            pass
    a_word = said.get("words") if knows else None

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <title>プロフィール</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <link rel="stylesheet" href="sen.css" />
</head>
<body>
  <div class="top-nav"><a href="index.html">←トップ</a></div>

  <header>
    <h1>プロフィール</h1>
  </header>

  <dl class="profile-box">
    <dt>名前</dt>
    <dd>{ITS_OWN_NAME}(せんおんせい)</dd>
    <dt>誕生日</dt>
    <dd>{birthday}</dd>
    <dt>ひとこと</dt>
    <dd>{a_word or "準備中"}</dd>
  </dl>

</body>
</html>
"""
    with open("profile.html", "w", encoding="utf-8") as f:
        f.write(html)


def regenerate_pages(articles):
    for art in articles:
        generate_blog_html(art)
    generate_kakodogu_html(articles)
    state = load_senonsei_state()
    generate_index_html(articles, state)
    keywords = update_keywords(articles)
    generate_memo_html(keywords, load_menu(), articles)
    generate_profile_html(keywords, state)
    generate_comments_html(load_comments())


def add_new_article(title, content, date_str=None):
    """記事を1件追加してページを再生成する。同じ日付の記事が既にある場合は追加しない(重複投稿の防止)。"""
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
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
