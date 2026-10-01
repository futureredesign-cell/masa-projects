#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校正ログ（01_校正ログ/校正_*.md）の修正を、手元の OCR テキストに適用する。

使い方:
    python3 apply_corrections.py --source ocr.txt --out ocr_corrected.txt [--confidence 高|中|低]
                                 [--log-dir DIR] [--no-global]

- 校正ログの表 `| 行 | 誤 | 正 | 種別 | 確度 | 備考 |` を読み、行番号で位置を特定し、
  その行に「誤」の文字列が存在する場合だけ「正」に置換する。
- 「見出しを独立行に」「削除」のような操作指示になっている行（改行ずれ・ノイズの一部）は
  自動適用しない。ただし「正」が「（削除）」の場合は「誤」の文字列を削除する。
- 見つからなかった修正、適用しなかった修正は `<out>.report.md` に一覧で出力する。
- 既定ではさらに、原注部分（「原注はじめに」で始まる行以降）の英文に混入した全角記号を
  半角に統一する一括ルールを適用する（--no-global で無効化）。

校正済みのテキストは底本（翻訳書）の複製にあたるため、リポジトリには置かずローカルで扱うこと。
"""
import argparse
import glob
import os
import re
import sys

CONF_RANK = {"高": 3, "中": 2, "低": 1}

# 「正」がこれらを含む行は操作指示なので自動適用しない
SKIP_WORDS = (
    "改行", "独立行", "分離", "再配置", "復元", "移動", "連結", "入れ替", "順序",
    "並べ", "統一", "参照", "／", "〜のように", "として", "削除／", "区切り",
    "見出し", "＋", "→", "項目", "段落", "を削除", "に分け", "から本文", "キャプション",
)

# 全文に適用してよい、文脈に依存しない語の置換（OCR の字形混同）
SAFE_WORD_RULES = (
    ("日標", "目標"), ("研先", "研究"), ("倍じ", "信じ"), ("倍仰", "信仰"), ("言仰", "信仰"),
    ("官仰", "信仰"), ("真面日", "真面目"), ("日的", "目的"), ("日を向け", "目を向け"),
    ("配供者", "配偶者"), ("配得者", "配偶者"),
    ("新共同記", "新共同訳"), ("中命記", "申命記"), ("ウォレス者、", "ウォレス著、"),
    ("Signiticant", "Significant"), ("Difterence", "Difference"), ("Ditterence", "Difference"),
    ("Houghton Miflin", "Houghton Mifflin"), ("Protessors", "Professors"), ("Mindtuness", "Mindfulness"),
)
DELETE_MARKERS = ("（削除）", "(削除)", "削除", "—", "―", "（削除／ロゴ）", "(なし)", "（なし）")


def strip_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] in "「『" and s[-1] in "」』":
        return s[1:-1]
    return s


def unescape_cell(s: str) -> str:
    s = s.strip()
    s = s.replace("\\|", "|")
    # `code` で囲まれたセル
    if len(s) >= 2 and s[0] == "`" and s[-1] == "`":
        s = s[1:-1]
    return s


def parse_logs(log_dir: str):
    rows = []
    for path in sorted(glob.glob(os.path.join(log_dir, "校正_*.md"))):
        with open(path, encoding="utf-8") as f:
            for raw in f:
                line = raw.rstrip("\n")
                if not line.startswith("|") or re.match(r"^\|\s*-", line) or line.startswith("| 行"):
                    continue
                cells = [unescape_cell(c) for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
                if len(cells) < 5:
                    continue
                m = re.fullmatch(r"\s*(\d{1,4})\s*", cells[0])
                if not m:
                    continue
                conf = cells[4].strip()[:1]
                if conf not in CONF_RANK:
                    continue
                rows.append({
                    "file": os.path.basename(path),
                    "line": int(m.group(1)),
                    "wrong": cells[1],
                    "right": cells[2],
                    "kind": cells[3].strip(),
                    "conf": conf,
                    "note": cells[5] if len(cells) > 5 else "",
                })
    return rows


def is_instruction(row) -> bool:
    r = row["right"]
    if r.startswith("（削除") or r in DELETE_MARKERS:
        return False
    if any(w in r for w in SKIP_WORDS):
        return True
    if any(w in row["wrong"] for w in ("1 行に", "1行に", "行が分割", "全体")):
        return True
    # 「正」が「誤」の 3 倍超に膨らんでいるものは説明文とみなす
    if len(r) > 3 * max(len(row["wrong"]), 8):
        return True
    return False


def strip_annotation(s: str) -> str:
    """「研先者（2箇所）」「人生後半戦略書（1回目）」のような注記を取り除く。"""
    return re.sub(r"\s*[（(]\s*(\d+\s*(箇所|か所|カ所|回目|件)|[12]\s*つ目)\s*[）)]\s*$", "", s)


def apply_safe_word_rules(lines):
    n = 0
    for i, s in enumerate(lines):
        for a, b in SAFE_WORD_RULES:
            if a in s:
                n += s.count(a)
                s = s.replace(a, b)
        lines[i] = s
    return n


def apply_global_rules(lines, start_idx):
    """原注部分の英文に混入した全角記号を半角化する。"""
    n = 0
    ascii_ = r"[A-Za-z0-9.)\]\"”’'/_-]"
    rules = [
        (re.compile(rf"(?<={ascii_})，\s*"), ", "),
        (re.compile(rf"(?<={ascii_})：\s*"), ": "),
        (re.compile(rf"(?<={ascii_})；\s*"), "; "),
        (re.compile(rf"(?<={ascii_})？"), "?"),
        (re.compile(rf"(?<={ascii_})！"), "!"),
        (re.compile(r"（(?=[A-Za-z0-9])"), "("),
        (re.compile(r"(?<=[A-Za-z0-9.])）"), ")"),
        (re.compile(r"\bIst (ed|American ed|U\.S\. ed)\."), r"1st \1."),
    ]
    for i in range(start_idx, len(lines)):
        s = lines[i]
        for pat, rep in rules:
            s, k = pat.subn(rep, s)
            n += k
        lines[i] = s
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--source", required=True, help="OCR テキスト（底本）")
    ap.add_argument("--out", required=True, help="出力先")
    ap.add_argument("--log-dir", default=os.path.join(here, "..", "01_校正ログ"))
    ap.add_argument("--confidence", default="高", choices=list(CONF_RANK))
    ap.add_argument("--no-global", action="store_true", help="原注部分の全角記号半角化を行わない")
    args = ap.parse_args()

    with open(args.source, encoding="utf-8") as f:
        lines = f.read().split("\n")

    # 原注の開始行は修正前のテキストで特定しておく
    notes_start = next((i for i, s in enumerate(lines) if s.startswith("原注") and "1." in s[:12]), None)

    rows = parse_logs(args.log_dir)
    threshold = CONF_RANK[args.confidence]
    applied, unmatched, skipped, already, below = [], [], [], 0, 0
    seen = set()
    for row in sorted(rows, key=lambda r: (r["line"], -len(r["wrong"]))):
        key = (row["line"], row["wrong"], row["right"])
        if key in seen:
            continue
        seen.add(key)
        if CONF_RANK[row["conf"]] < threshold:
            below += 1
            continue
        if is_instruction(row):
            skipped.append(row)
            continue
        idx = row["line"] - 1
        if idx < 0 or idx >= len(lines):
            unmatched.append(row)
            continue
        wrong = strip_annotation(row["wrong"])
        is_delete = row["right"].startswith("（削除") or row["right"] in DELETE_MARKERS
        right = "" if is_delete else strip_annotation(row["right"])
        if wrong not in lines[idx]:
            w2, r2 = strip_quotes(wrong), (strip_quotes(right) if right else "")
            if w2 and w2 in lines[idx]:
                wrong, right = w2, r2
            elif right and right in lines[idx]:
                already += 1  # 別のログの修正で既に直っている
                continue
            else:
                unmatched.append(row)
                continue
        lines[idx] = lines[idx].replace(wrong, right)
        applied.append(row)

    g = w = 0
    if not args.no_global:
        w = apply_safe_word_rules(lines)
        if notes_start is not None:
            g = apply_global_rules(lines, notes_start)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    rep = args.out + ".report.md"
    with open(rep, "w", encoding="utf-8") as f:
        f.write(f"# 適用レポート\n\n- 校正ログの行数: {len(rows)}\n- 適用: {len(applied)}\n"
                f"- 確度不足で未適用（--confidence {args.confidence}）: {below}\n"
                f"- 操作指示のため未適用（人手で対応）: {len(skipped)}\n"
                f"- 他のログの修正で既に直っていたもの: {already}\n"
                f"- 行内に「誤」が見つからず未適用: {len(unmatched)}\n"
                f"- 全文の安全な語置換（日標→目標 など）: {w} 箇所\n"
                f"- 原注部分の全角記号半角化: {g} 箇所\n\n")
        f.write("## 行内に「誤」が見つからなかった修正\n\n| ログ | 行 | 誤 | 正 | 確度 |\n|---|---|---|---|---|\n")
        for r in unmatched:
            f.write(f"| {r['file']} | {r['line']} | {r['wrong']} | {r['right']} | {r['conf']} |\n")
        f.write("\n## 操作指示のため未適用（人手で対応）\n\n| ログ | 行 | 誤 | 正 | 種別 |\n|---|---|---|---|---|\n")
        for r in skipped:
            f.write(f"| {r['file']} | {r['line']} | {r['wrong']} | {r['right']} | {r['kind']} |\n")

    print(f"applied={len(applied)} already={already} unmatched={len(unmatched)} skipped={len(skipped)} "
          f"below_conf={below} safe_words={w} notes_punct={g}")
    print(f"report: {rep}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
