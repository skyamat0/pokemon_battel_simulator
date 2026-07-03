"""固定パーティ同士で N バトル実行し、結果を JSONL に記録する。

使い方:
    python battle_runner.py --team-a teams/sample_top.txt --team-b teams/my_team.txt -n 100
"""

import argparse
import asyncio
import datetime
import json
import pathlib

from poke_env import AccountConfiguration
from poke_env.battle.move import Move
from poke_env.player import SimpleHeuristicsPlayer
from poke_env.player.battle_order import SingleBattleOrder


class ChampionsHeuristicsPlayer(SimpleHeuristicsPlayer):
    """チャンピオンズ実機仕様に合わせた bot: テラスタル封印・メガシンカ解禁。

    SimpleHeuristicsPlayer は mega フラグを立てないため、
    メガシンカ可能なターンは常に技オーダーに mega を付与する。
    """

    @staticmethod
    def _should_terastallize(battle, move):
        return False

    def choose_move(self, battle):
        order = super().choose_move(battle)
        if (
            getattr(battle, "can_mega_evolve", False)
            and isinstance(order, SingleBattleOrder)
            and isinstance(order.order, Move)
        ):
            order.mega = True
        return order


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team-a", required=True, help="A側パーティファイル")
    parser.add_argument("--team-b", required=True, help="B側パーティファイル")
    parser.add_argument("-n", "--n-battles", type=int, default=100)
    parser.add_argument("--format", default="gen9championsbssregmb", help="バトルフォーマット")
    parser.add_argument("--concurrency", type=int, default=10, help="同時実行バトル数")
    parser.add_argument("--out-dir", default="logs", help="ログ出力先")
    return parser


# 行動ログとして JSONL に残すイベント種別
KEEP_EVENTS = {
    "turn", "move", "switch", "drag", "faint", "cant", "win", "tie",
    "-boost", "-unboost", "-status", "-weather", "-mega",
    "-fieldstart", "-sidestart", "-sideend", "-heal", "-damage",
    "-crit", "-supereffective", "-resisted", "-immune", "-miss",
}


def battle_record(tag, battle) -> dict:
    # battle.team はロスター6匹を含むため、実際に場に出た個体(revealed)だけを選出とみなす。
    # 種名は base_species で正規化(ばけのかわ剥がれ・メガ進化後のフォルム名を吸収)。
    # opponent 側は「観測できた」ポケモンのみなので、選出3匹すべてが見えた場合のみ正確。
    a_sent = [m for m in battle.team.values() if m.revealed]
    b_seen = list(battle.opponent_team.values())

    # 生プロトコルログから先発・メガ使用・行動ログを抽出する。
    # player_role で p1/p2 を A/B に対応付ける
    a_role = battle.player_role or "p1"
    leads, megas, turn_log = {}, set(), []
    before_turn1 = True
    for ev in battle._replay_data:
        if len(ev) < 2:
            continue
        kind = ev[1]
        if kind == "turn":
            before_turn1 = False
        if before_turn1 and kind == "switch":
            role = ev[2][:2]
            leads.setdefault(role, ev[3].split(",")[0])
        if kind == "-mega":
            megas.add(ev[2][:2])
        if kind in KEEP_EVENTS:
            turn_log.append("|".join(ev[1:]))

    b_role = "p2" if a_role == "p1" else "p1"
    return {
        "battle_tag": tag,
        "winner": "A" if battle.won else ("B" if battle.won is False else "tie"),
        "turns": battle.turn,
        "a_lead": leads.get(a_role),
        "b_lead": leads.get(b_role),
        "a_selection": sorted(m.base_species for m in a_sent),
        "a_fainted": sorted(m.base_species for m in a_sent if m.fainted),
        "a_remaining": sum(not m.fainted for m in a_sent),
        "a_mega_used": a_role in megas,
        "b_selection_seen": sorted(m.base_species for m in b_seen),
        "b_fainted_seen": sorted(m.base_species for m in b_seen if m.fainted),
        "b_remaining_seen": sum(not m.fainted for m in b_seen),
        "b_mega_used": b_role in megas,
        "a_role": a_role,
        "turn_log": turn_log,
    }


async def run(args) -> None:
    team_a = pathlib.Path(args.team_a).read_text()
    team_b = pathlib.Path(args.team_b).read_text()

    # Showdown はログイン名を接続単位で占有するため、実行ごとに一意な名前にする
    run_id = datetime.datetime.now().strftime("%H%M%S")
    player_a = ChampionsHeuristicsPlayer(
        account_configuration=AccountConfiguration(f"botA-{run_id}", None),
        battle_format=args.format, team=team_a,
        max_concurrent_battles=args.concurrency,
    )
    player_b = ChampionsHeuristicsPlayer(
        account_configuration=AccountConfiguration(f"botB-{run_id}", None),
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
