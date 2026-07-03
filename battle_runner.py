"""固定パーティ同士で N バトル実行し、結果を JSONL に記録する。

使い方:
    python battle_runner.py --team-a teams/sample_top.txt --team-b teams/my_team.txt -n 100
"""

import argparse
import asyncio
import datetime
import json
import pathlib

from poke_env.player import SimpleHeuristicsPlayer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team-a", required=True, help="A側パーティファイル")
    parser.add_argument("--team-b", required=True, help="B側パーティファイル")
    parser.add_argument("-n", "--n-battles", type=int, default=100)
    parser.add_argument("--format", default="gen9bssregi", help="バトルフォーマット")
    parser.add_argument("--concurrency", type=int, default=10, help="同時実行バトル数")
    parser.add_argument("--out-dir", default="logs", help="ログ出力先")
    return parser


def battle_record(tag, battle) -> dict:
    # opponent_team は「観測できた」相手ポケモンのみなので、
    # b_remaining は選出3匹すべてが見えた場合のみ正確
    return {
        "battle_tag": tag,
        "winner": "A" if battle.won else ("B" if battle.won is False else "tie"),
        "turns": battle.turn,
        "a_selection": [m.species for m in battle.team.values()],
        "a_remaining": sum(not m.fainted for m in battle.team.values()),
        "b_selection_seen": [m.species for m in battle.opponent_team.values()],
        "b_remaining_seen": sum(not m.fainted for m in battle.opponent_team.values()),
    }


async def run(args) -> None:
    team_a = pathlib.Path(args.team_a).read_text()
    team_b = pathlib.Path(args.team_b).read_text()

    player_a = SimpleHeuristicsPlayer(
        battle_format=args.format, team=team_a,
        max_concurrent_battles=args.concurrency,
    )
    player_b = SimpleHeuristicsPlayer(
        battle_format=args.format, team=team_b,
        max_concurrent_battles=args.concurrency,
    )

    await player_a.battle_against(player_b, n_battles=args.n_battles)

    records = [battle_record(tag, b) for tag, b in player_a.battles.items()]

    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"battles_{timestamp}.jsonl"
    with out_path.open("w") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    n = len(records)
    a_wins = sum(r["winner"] == "A" for r in records)
    b_wins = sum(r["winner"] == "B" for r in records)
    avg_turns = sum(r["turns"] for r in records) / n if n else 0
    print(f"総バトル数: {n}")
    print(f"A ({args.team_a}) 勝率: {a_wins / n:.1%} ({a_wins}勝)")
    print(f"B ({args.team_b}) 勝率: {b_wins / n:.1%} ({b_wins}勝)")
    print(f"平均ターン数: {avg_turns:.1f}")
    print(f"ログ: {out_path}")


if __name__ == "__main__":
    asyncio.run(run(build_parser().parse_args()))
