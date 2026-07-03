"""バトルログ(JSONL)を集計して診断レポートを表示する。

使い方:
    python analyze.py logs/battles_XXXX.jsonl
"""

import argparse
import json
import pathlib
from collections import defaultdict


def load(path):
    return [json.loads(line) for line in pathlib.Path(path).read_text().splitlines()]


def rate(wins, total):
    return f"{wins / total:.1%} ({wins}/{total})" if total else "-"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log")
    parser.add_argument("--min-n", type=int, default=10, help="表示する最小サンプル数")
    args = parser.parse_args()

    records = load(args.log)
    n = len(records)
    a_wins = sum(r["winner"] == "A" for r in records)
    print(f"総バトル数: {n} / A側勝率: {rate(a_wins, n)}")

    # 自分(A)の選出3匹の組み合わせ別勝率
    combo = defaultdict(lambda: [0, 0])  # {組み合わせ: [勝ち, 総数]}
    for r in records:
        key = " / ".join(sorted(r["a_selection"]))
        combo[key][1] += 1
        combo[key][0] += r["winner"] == "A"
    print("\n■ A側: 選出組み合わせ別勝率(上位/下位)")
    ranked = sorted(
        ((w / t, w, t, k) for k, (w, t) in combo.items() if t >= args.min_n),
        reverse=True,
    )
    shown = ranked[:5] + (ranked[-5:] if len(ranked) > 10 else ranked[5:])
    for wr, w, t, k in shown:
        print(f"  {wr:6.1%} ({w}/{t})  {k}")

    # 先発別勝率(選出は実質 6C1×5C2: 先発の対面が試合を作るという観点)
    if records and records[0].get("a_lead"):
        for side, label in (("a_lead", "A側: 自分の先発別勝率"), ("b_lead", "相手の先発別: A側勝率")):
            lead = defaultdict(lambda: [0, 0])
            for r in records:
                lead[r[side]][1] += 1
                lead[r[side]][0] += r["winner"] == "A"
            print(f"\n■ {label}")
            for k, (w, t) in sorted(lead.items(), key=lambda x: -x[1][0] / x[1][1]):
                print(f"  {k:<16} {w / t:>7.1%} ({w}/{t})")

        # 先発対面マトリクス
        matchup = defaultdict(lambda: [0, 0])
        for r in records:
            matchup[(r["a_lead"], r["b_lead"])][1] += 1
            matchup[(r["a_lead"], r["b_lead"])][0] += r["winner"] == "A"
        print("\n■ 先発対面別 A側勝率(有利上位・不利上位)")
        cells = sorted(
            ((w / t, w, t, a, b) for (a, b), (w, t) in matchup.items() if t >= args.min_n),
            reverse=True,
        )
        shown_cells = cells[:8] + (cells[-8:] if len(cells) > 16 else cells[8:])
        for wr, w, t, a, b in shown_cells:
            print(f"  {wr:6.1%} ({w:>3}/{t:<3})  自分:{a:<14} vs 相手:{b}")

    # 自分の各ポケモン: 選出率・選出時勝率・被倒率
    mon = defaultdict(lambda: [0, 0, 0])  # {種: [選出数, 勝ち, 倒された]}
    for r in records:
        for s in r["a_selection"]:
            mon[s][0] += 1
            mon[s][1] += r["winner"] == "A"
            mon[s][2] += s in r.get("a_fainted", [])
    print("\n■ A側: ポケモン別成績")
    print(f"  {'ポケモン':<16} {'選出率':>8} {'選出時勝率':>10} {'被倒率':>8}")
    for s, (sel, w, ko) in sorted(mon.items(), key=lambda x: -x[1][0]):
        print(f"  {s:<16} {sel / n:>7.1%} {w / sel:>9.1%} {ko / sel:>7.1%}")

    # 相手の各ポケモン: 出現時の自分の勝率(=そのポケモンがどれだけ刺さっているか)
    opp = defaultdict(lambda: [0, 0, 0])
    for r in records:
        for s in r["b_selection_seen"]:
            opp[s][0] += 1
            opp[s][1] += r["winner"] == "A"
            opp[s][2] += s in r.get("b_fainted_seen", [])
    print("\n■ 相手(B): 出現ポケモン別(A側から見た勝率が低い=刺さられている)")
    print(f"  {'ポケモン':<16} {'出現数':>6} {'A側勝率':>8} {'撃破率':>8}")
    for s, (seen, w, ko) in sorted(opp.items(), key=lambda x: x[1][1] / x[1][0]):
        print(f"  {s:<16} {seen:>6} {w / seen:>7.1%} {ko / seen:>7.1%}")

    # 敗戦時に生き残っている相手(=詰み筋になっている相手)
    survivor = defaultdict(int)
    losses = [r for r in records if r["winner"] == "B"]
    for r in losses:
        for s in r["b_selection_seen"]:
            if s not in r.get("b_fainted_seen", []):
                survivor[s] += 1
    print(f"\n■ 敗戦時({len(losses)}戦)に生き残っていた相手ポケモン")
    for s, c in sorted(survivor.items(), key=lambda x: -x[1]):
        print(f"  {s:<16} {c:>4}回 ({c / len(losses):.1%})")


if __name__ == "__main__":
    main()
