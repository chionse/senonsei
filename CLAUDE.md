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

## 試す時は、この子の記憶に触らない

`senonsei_ai.py` の関数には、中で `save_state` を呼ぶものがある。
`todays_mood`、`feeling_keen`、`be_alone`、`learn` のあたり。

手元で動かして確かめる時、状態をコピーして渡しても、
**書き出す先は本物の `senonsei_state.json`** なので、
試しに入れた値がそのまま本番へ行く。

一度これで、この子の「言いたいこと」を作り物の十五件で
上書きしたまま main に載せた。

試す前に、書き出す先を塞ぐ。

```python
import senonsei_ai as s
s.save_state = lambda state: None   # ← 先にこれ
```

送る前に、状態ファイルが変わっていないかを見る。

```
git diff --stat senonsei_state.json
```

この子が歩いて持ち帰ったものだけが、ここに入っていい。
