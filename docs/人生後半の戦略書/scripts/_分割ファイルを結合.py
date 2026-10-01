#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人生後半の戦略書（ブルックス）の納本ファイルを結合する（2026-10-01）。
クラウドの Claude からドライブへは一度に約4万バイトしか送れなかったので、校正版と原注を分割して置いた。
この .py を典拠フォルダで一度走らせると、
 1. 認知＿人生後半の戦略書＿ブルックス校正版.partNN.txt を結合して 校正版.txt を作り、バイト数と md5 を検算する
 2. 認知＿人生後半の戦略書＿ブルックス_原注と典拠索引.partNN.md を結合して同名の .md を作る
 3. _INDEX追記_人生後半の戦略書_20261001.md の1行を 00_INDEX.md（行動経済学の行の次）に入れる
 4. 検算が通ったら分割ファイルと追記ファイルと、この .py 自身を消す
使い方: cd 共有基盤/典拠 && python3 _分割ファイルを結合.py
"""
import glob, hashlib, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
TARGETS = [
    ("認知＿人生後半の戦略書＿ブルックス校正版", ".txt", 510437, "73ccff1d0cc141952bacd38886165c48"),
    ("認知＿人生後半の戦略書＿ブルックス_原注と典拠索引", ".md", 161127, "62d2b90e7d1a08a9635b23d46610adbc"),
]
ok = True
made = []
for base, ext, size, md5 in TARGETS:
    parts = sorted(glob.glob(f"{base}.part*{ext}"))
    if not parts:
        print("分割ファイルが見つからない:", base); ok = False; continue
    data = b"".join(open(p, "rb").read() for p in parts)
    got = hashlib.md5(data).hexdigest()
    if len(data) != size or got != md5:
        print(f"検算が合わない: {base} バイト {len(data)}（期待 {size}） md5 {got}（期待 {md5}）。分割ファイルは残す"); ok = False; continue
    out = base + ext
    open(out, "wb").write(data)
    print(f"結合: {out} {len(data)} バイト md5 一致")
    made.append((out, parts))
# INDEX 追記
add = "_INDEX追記_人生後半の戦略書_20261001.md"
if os.path.exists(add) and os.path.exists("00_INDEX.md"):
    line = [l for l in open(add, encoding="utf-8").read().split("\n") if l.startswith("- ○ 認知＿人生後半の戦略書")]
    idx = open("00_INDEX.md", encoding="utf-8").read().split("\n")
    if line and not any(l.startswith("- ○ 認知＿人生後半の戦略書") for l in idx):
        k = next((i for i, l in enumerate(idx) if l.startswith("- ◎ 認知＿行動経済学")), None)
        if k is None:
            k = next((i for i, l in enumerate(idx) if l.startswith("- ") and "認知＿" in l[:12]), len(idx) - 1)
        idx.insert(k + 1, line[0])
        open("00_INDEX.md", "w", encoding="utf-8").write("\n".join(idx))
        print("00_INDEX.md に1行入れた（行", k + 2, "）")
    else:
        print("00_INDEX.md は追記済みか、行が見つからない")
    if ok: os.remove(add)
if ok:
    for out, parts in made:
        for p in parts: os.remove(p)
    print("分割ファイルを消した。この .py も消す")
    os.remove(os.path.abspath(__file__))
else:
    print("検算に失敗したものがある。なりちゃんか Claude に知らせる"); sys.exit(1)
