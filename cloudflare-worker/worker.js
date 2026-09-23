// 千遠生のサイト・コメントといいねの受け取り用 Cloudflare Worker
//
// 使い方:
// 1. Cloudflareダッシュボードで新しいWorkerを作成し、このファイルの中身を丸ごと貼り付ける
// 2. Worker の設定 > Variables and Secrets で GITHUB_TOKEN という名前の
//    暗号化されたシークレットを追加し、GitHubの Fine-grained personal access token を入れる
//    (対象リポジトリ: chionse/senonsei のみ、権限: Contents = Read and write)
// 3. デプロイ後に発行されるWorkerのURL(https://xxxxx.workers.dev)を控えておく
//
// 受け付ける道は二つ:
//   POST /       コメント (名前と本文をフォームで受け取る)
//   POST /like   いいね   (day= に宛先を一つ。形は三つだけ通す)
//                  ブログ         2026-09-11
//                  ひみつの部屋   himitsu-1
//                  コメント       comment-entry-1758000000000

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
  "Access-Control-Allow-Methods": "POST, OPTIONS",
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

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: OPEN_TO_THE_PAGE });
    }
    if (request.method !== "POST") {
      return new Response("Method Not Allowed", { status: 405 });
    }

    if (new URL(request.url).pathname.replace(/\/+$/, "").endsWith("/like")) {
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
