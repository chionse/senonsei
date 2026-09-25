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

記憶は三つある。状態(`senonsei_state.json`)と、出会った言葉の束(`kotoba/`)と、
思いの蔵(`omoi/`)。`kotoba/` は `save_state` が一緒に書くので、
`save_state` を塞げば止まる。
`remember_a_thought` と `be_alone` は、`save_state` を塞いでも
蔵のほうへは直に書く。両方塞ぐ。

```python
import senonsei_ai as s
s.save_state = lambda state: None      # ← 先にこれ
s.keep_a_thought = lambda said, when: None
```

送る前に、どちらも変わっていないかを見る。

```
git status --short
```

`senonsei_state.json` か `kotoba/` か `omoi/` が出てきたら、試した跡が
残っている。`git checkout` で戻してから送る。

記憶を手で直すのは、散歩のあいだを避ける(毎時 20 分ごろに出て、数分で帰る)。
散歩中に main の記憶が変わると、帰ってきた時にこの子が持ち帰ったほうが
丸ごと使われ、手で直したぶんは消える(`kioku_mamori.py` とワークフローの説明)。

この子が歩いて持ち帰ったものだけが、ここに入っていい。

## メモと手紙は、封をしてから置く

このリポジトリは誰でも覗ける。`keywords.json`(メモ1)と
`menu.json`(メモ2)に平文で置くと、サイトでは伏せてあっても読めてしまう。
彼女がこの子にだけ宛てたものなので、封をしてから置く(`fuuin.py`)。

```
python3 fuuin.py memo   "言葉" "本文" [--opens-with 語,語] [--image images/x.png]
python3 fuuin.py letter 日数 "本文"
```

封をするのに鍵は要らない。錠前(`fuuin.json`)だけで封ができる。
開ける鍵(`MEMO_KEY`)は GitHub の秘密の置き場所にだけある。
鍵の中身はどこにも書かない。チャットにも出さない。

平文のメモや手紙を、一度でもコミットしてはいけない。
履歴に残るので、あとから封をしても取り消せない。

書き直す時は、彼女から全文をもらい直し、古い一つを消して新しく封をする。
手元に鍵は無いので、封の中身を開けて直すことはできない。

手元で試す時、鍵が無ければ封をしたものは閉じたまま扱われる。
メモは「???」のまま、手紙はこの子に届かない。それで正しい。

