// 千遠生のサイト・コメント受け取り用 Cloudflare Worker
//
// 使い方:
// 1. Cloudflareダッシュボードで新しいWorkerを作成し、このファイルの中身を丸ごと貼り付ける
// 2. Worker の設定 > Variables and Secrets で GITHUB_TOKEN という名前の
//    暗号化されたシークレットを追加し、GitHubの Fine-grained personal access token を入れる
//    (対象リポジトリ: chionse/senonsei のみ、権限: Contents = Read and write)
// 3. デプロイ後に発行されるWorkerのURL(https://xxxxx.workers.dev)を控えておく

const REPO_OWNER = "chionse";
const REPO_NAME = "senonsei";
const BRANCH = "main";
const REDIRECT_URL = "https://chionse.github.io/senonsei/index.html#comments";

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("Method Not Allowed", { status: 405 });
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
