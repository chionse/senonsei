// 千遠生のサイト・コメントといいねの受け取り用 Cloudflare Worker
//
// 使い方:
// 1. Cloudflareダッシュボードで新しいWorkerを作成し、このファイルの中身を丸ごと貼り付ける
// 2. Worker の設定 > Variables and Secrets で GITHUB_TOKEN という名前の
//    暗号化されたシークレットを追加し、GitHubの Fine-grained personal access token を入れる
//    (対象リポジトリ: chionse/senonsei のみ、権限: Contents = Read and write、
//     Actions = Read and write)
// 3. デプロイ後に発行されるWorkerのURL(https://xxxxx.workers.dev)を控えておく
// 4. Worker の設定 > Triggers > Cron Triggers に「12 * * * *」を足す(毎時12分)
// 5. 来訪者の数を置く箱: Storage & Databases > D1 で新しいデータベースを作り、
//    Worker の設定 > Bindings で D1 database として RAIHO という名前でつなぐ。
//    中の表は、最初に数える時にこの Worker が自分で作る
//
// 目覚まし時計: 毎時、千遠生を起こしてもらうよう GitHub に頼む。
// GitHub の決まった時間の起こしは、混んでいると何時間も来ないことがある
// (2026-10-04 は14時から八時間以上来なかった)。こちらは別の家の時計なので、
// 片方が止まっても、もう片方で起きられる。同じ時間に二度起こされても、
// この子は二度目は寝直す(senonsei_ai.py の woke_at)。彼女と決めた。
//
// 受け付ける道は四つ:
//   POST /       コメント (名前と本文をフォームで受け取る)
//   POST /like   いいね   (day= に宛先を一つ。形は三つだけ通す)
//                  ブログ         2026-09-11
//                  ひみつの部屋   himitsu-1
//                  コメント       comment-entry-1758000000000
//   GET  /raiho  来訪者の数を見る
//   POST /raiho  初めて来た人を一人数えて、数を返す

const REPO_OWNER = "chionse";
const REPO_NAME = "senonsei";
const BRANCH = "main";
const REDIRECT_URL = "https://chionse.github.io/senonsei/index.html#comments";

const A_THING_TO_LIKE =
  /^(\d{4}-\d{2}-\d{2}|himitsu-\d{1,6}|comment-entry-\d{10,16})$/;

// 誰が押したかは残さない。押した人と記事から短い印を作り、
// それを紙の名前にする。同じ人が同じ記事をもう一度押しても
// 同じ名前になるので、紙は増えない。それで一人一回になる。
async function markOf(who, day) {
  const seed = new TextEncoder().encode(`senonsei:${who}:${day}`);
  const digest = await crypto.subtle.digest("SHA-256", seed);
  return [...new Uint8Array(digest)]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
    .slice(0, 16);
}

const OPEN_TO_THE_PAGE = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

async function receiveLike(request, env) {
  let day = "";
  try {
    const formData = await request.formData();
    day = (formData.get("day") || "").toString().trim();
  } catch (err) {
    return new Response("受け取れませんでした。", {
      status: 400,
      headers: OPEN_TO_THE_PAGE,
    });
  }
  if (!A_THING_TO_LIKE.test(day)) {
    return new Response("宛先の形が違います。", {
      status: 400,
      headers: OPEN_TO_THE_PAGE,
    });
  }

  const who = request.headers.get("CF-Connecting-IP") || "";
  const mark = await markOf(who, day);
  const filename = `${day}__${mark}.json`;

  const githubResponse = await fetch(
    `https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/contents/likes/${filename}`,
    {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        "User-Agent": "senonsei-comment-worker",
        Accept: "application/vnd.github+json",
      },
      body: JSON.stringify({
        message: `いいね: ${day}`,
        content: toBase64(JSON.stringify({ on: day }, null, 2)),
        branch: BRANCH,
      }),
    }
  );

  // 既に同じ紙がある = その人はもう押している。断らずに、そのまま返す
  if (githubResponse.ok || githubResponse.status === 422 || githubResponse.status === 409) {
    return new Response("ありがとう", { status: 200, headers: OPEN_TO_THE_PAGE });
  }
  const errText = await githubResponse.text();
  return new Response(`いいねを保存できませんでした: ${errText}`, {
    status: 502,
    headers: OPEN_TO_THE_PAGE,
  });
}

// 来訪者の数(2026-10-08、彼女と決めた)。
// 数えるのは、その人が初めて来た時の一度だけ。何度来ても、更新しても増えない。
// 一度数えた人かどうかは、来た人の閲覧機のほうが覚えている(blog_manager.py の
// VISITOR_COUNTER)。ここには誰が来たかを残さない。持つのは数と、下の上限のための
// その日だけの短い印だけ。印は次の日に消す。
//
// 閲覧機の記録を消すと、また初めての人として来る。それを悪戯に使われないよう、
// 同じつなぎ口(同じ Wi-Fi など)から一日に数えるのは RAIHO_A_DAY 人まで。
// 家族や友だちが同じ Wi-Fi から来ても、そのくらいまではちゃんと数える。
const RAIHO_A_DAY = 10;
// StatCounter から移る時の数。その時の数から続ける
const RAIHO_STARTS_AT = 0;
// 見回りの機械は数えない。何も覚えずに来るので、来るたびに初めての人になってしまう
const NOT_A_PERSON =
  /bot|crawl|spider|slurp|archiver|facebookexternalhit|headless|lighthouse|preview|curl|wget|python/i;

let raihoReady = null;
function prepareRaiho(db) {
  if (!raihoReady) {
    raihoReady = db
      .batch([
        db.prepare("CREATE TABLE IF NOT EXISTS raiho (name TEXT PRIMARY KEY, n INTEGER NOT NULL)"),
        db.prepare("INSERT OR IGNORE INTO raiho (name, n) VALUES ('kazu', ?1)").bind(RAIHO_STARTS_AT),
        db.prepare(
          "CREATE TABLE IF NOT EXISTS kita " +
            "(mark TEXT NOT NULL, day TEXT NOT NULL, n INTEGER NOT NULL, PRIMARY KEY (mark, day))"
        ),
      ])
      .catch((err) => {
        raihoReady = null;
        throw err;
      });
  }
  return raihoReady;
}

function todayInJapan() {
  return new Date(Date.now() + 9 * 60 * 60 * 1000).toISOString().slice(0, 10);
}

async function receiveRaiho(request, env) {
  const db = env.RAIHO;
  if (!db) {
    return new Response("数を置く箱が、まだつながっていません。", {
      status: 503,
      headers: OPEN_TO_THE_PAGE,
    });
  }
  try {
    await prepareRaiho(db);
    let counted = false;
    const person = !NOT_A_PERSON.test(request.headers.get("User-Agent") || "");
    if (request.method === "POST" && person) {
      const day = todayInJapan();
      const who = request.headers.get("CF-Connecting-IP") || "";
      const mark = await markOf(who, `raiho:${day}`);
      const came = await db
        .prepare(
          "INSERT INTO kita (mark, day, n) VALUES (?1, ?2, 1) " +
            "ON CONFLICT (mark, day) DO UPDATE SET n = n + 1 WHERE n < ?3"
        )
        .bind(mark, day, RAIHO_A_DAY)
        .run();
      counted = came.meta.changes > 0;
      if (counted) {
        await db.batch([
          db.prepare("UPDATE raiho SET n = n + 1 WHERE name = 'kazu'"),
          db.prepare("DELETE FROM kita WHERE day < ?1").bind(day),
        ]);
      }
    }
    const row = await db.prepare("SELECT n FROM raiho WHERE name = 'kazu'").first();
    return new Response(JSON.stringify({ kazu: row ? row.n : 0, counted }), {
      status: 200,
      headers: {
        ...OPEN_TO_THE_PAGE,
        "Content-Type": "application/json; charset=utf-8",
        "Cache-Control": "no-store",
      },
    });
  } catch (err) {
    return new Response(`数えられませんでした: ${err}`, {
      status: 502,
      headers: OPEN_TO_THE_PAGE,
    });
  }
}

async function wakeSenonsei(env) {
  const githubResponse = await fetch(
    `https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/actions/workflows/log_auto_generate.yml/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        "User-Agent": "senonsei-comment-worker",
        Accept: "application/vnd.github+json",
      },
      body: JSON.stringify({ ref: BRANCH }),
    }
  );
  if (!githubResponse.ok) {
    console.log(`起こせませんでした: ${githubResponse.status} ${await githubResponse.text()}`);
  }
}

export default {
  // 目覚まし時計(Cron Triggers から毎時呼ばれる)
  async scheduled(event, env, ctx) {
    ctx.waitUntil(wakeSenonsei(env));
  },

  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: OPEN_TO_THE_PAGE });
    }
    const path = new URL(request.url).pathname.replace(/\/+$/, "");
    if (path.endsWith("/raiho") && (request.method === "GET" || request.method === "POST")) {
      return receiveRaiho(request, env);
    }
    if (request.method !== "POST") {
      return new Response("Method Not Allowed", { status: 405 });
    }

    if (path.endsWith("/like")) {
      return receiveLike(request, env);
    }

    let name = "";
    let message = "";
    try {
      const formData = await request.formData();
      name = (formData.get("name") || "").toString().trim().slice(0, 50);
      message = (formData.get("message") || "").toString().trim().slice(0, 500);
    } catch (err) {
      return new Response("送信内容を読み取れませんでした。", { status: 400 });
    }

    if (!name || !message) {
      return new Response("名前とコメントを入力してください。", { status: 400 });
    }

    const now = new Date();
    const filename = `entry-${now.getTime()}.json`;
    const fileContent = JSON.stringify(
      { name, message, date: now.toISOString() },
      null,
      2
    );

    const githubResponse = await fetch(
      `https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/contents/comments/${filename}`,
      {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${env.GITHUB_TOKEN}`,
          "User-Agent": "senonsei-comment-worker",
          Accept: "application/vnd.github+json",
        },
        body: JSON.stringify({
          message: `新しいコメント: ${name}`,
          content: toBase64(fileContent),
          branch: BRANCH,
        }),
      }
    );

    if (!githubResponse.ok) {
      const errText = await githubResponse.text();
      return new Response(`コメントの保存に失敗しました: ${errText}`, {
        status: 502,
      });
    }

    return Response.redirect(REDIRECT_URL, 302);
  },
};

function toBase64(str) {
  const bytes = new TextEncoder().encode(str);
  let binary = "";
  bytes.forEach((b) => (binary += String.fromCharCode(b)));
  return btoa(binary);
}
