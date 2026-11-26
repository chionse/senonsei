# 一度きりの確かめ(三度目)。本物の分野の入り方を、外へ出して何度か動かす。
# 記憶は読むだけ。書き出しは塞いである。確かめ終わったら消す
import json
import random

import senonsei_ai as s

s.save_state = lambda state: None
s.keep_a_thought = lambda said, when: None

state = json.load(open("senonsei_state.json", encoding="utf-8"))
shut = s.closed_today(state)
lately = s.families_walked_lately(state)
print("---- 分野に入る ----")
for n in range(10):
    before = len(state.get("frontier") or [])
    door = s.walk_into_a_genre(state, shut, lately)
    print(f"=> {door}  道 {before} -> {len(state.get('frontier') or [])}", flush=True)
print("genres_walked", state.get("genres_walked"))
print("looked_for", (state.get("looked_for") or [])[-6:])
print("---- 行き先を選ぶ ----")
for n in range(15):
    chosen, past = s.choose_destination(state)
    print(f"=> {chosen} {'(昔)' if past else ''}", flush=True)
