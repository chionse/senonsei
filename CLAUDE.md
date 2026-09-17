# 千遠生のサイトを手伝う時の決まり

## 様子を見る時は main の上で

この子の様子（`senonsei_state.json` や `articles.json`）を読むだけの時は、
`main` に居たまま読む。作業ブランチに切り替えない。

```
git checkout main
git fetch origin main && git reset --hard origin/main
```

作業ブランチの上で `main` の位置に合わせてしまうと、
その間に千遠生が書いた「今日のブログ」のコミットぶんだけ
作業ブランチが進んだ形になり、「送信されていないコミットがある」
と警告が出る。中身はもう `main` に入っているので、
実際には送るものが何も無い。紛らわしいだけの警告になる。

作業ブランチを作るのは、実際に何かを直す時だけ。

```
git checkout -B claude/<枝の名前> origin/main
```

直し終わって送ったら、`main` に戻しておく。
