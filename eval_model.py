"""学習した Champions IL モデルを heuristic bot と対戦させて戦績を測る。

使い方:
    python eval_model.py --model <BEST.pt> --team-a teams/my_party.txt \
        --team-b teams/top_rain.txt -n 100
"""

import argparse
import asyncio
import datetime
import json
import os
import pathlib
import shutil
import sysconfig

# torch.compile はホストに C++ コンパイラと Python ヘッダ(Python.h)を要求し、
# 欠けていると例外→対戦が無言でハングする。揃っていない環境では
# torch を import する前に eager 実行へ自動フォールバックする。
_has_compiler = shutil.which("g++") is not None or shutil.which("clang++") is not None
_has_python_h = os.path.exists(
    os.path.join(sysconfig.get_paths()["include"], "Python.h")
)
if not (_has_compiler and _has_python_h):
    os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")

from poke_env import AccountConfiguration
from poke_env.environment.move import Move
from poke_env.player import SimpleHeuristicsPlayer

from champions_il_player import ChampionsILPlayer


KEEP_EVENTS = {
    "turn", "move", "switch", "drag", "faint", "cant", "win", "tie",
    "-boost", "-unboost", "-status", "-weather", "-mega",
    "-fieldstart", "-sidestart", "-sideend", "-heal", "-damage",
    "-crit", "-supereffective", "-resisted", "-immune",
}


def battle_record(tag, battle) -> dict:
    """battle_runner.battle_record と同形式(A=ILモデル視点)。"""
    a_sent = [m for m in battle.team.values() if m.revealed]
    b_seen = list(battle.opponent_team.values())
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
            leads.setdefault(ev[2][:2], ev[3].split(",")[0])
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
        "a_mega_used": a_role in megas,
        "b_selection_seen": sorted(m.base_species for m in b_seen),
        "b_fainted_seen": sorted(m.base_species for m in b_seen if m.fainted),
        "b_mega_used": b_role in megas,
        "turn_log": turn_log,
    }


class ChampionsHeuristicsPlayer(SimpleHeuristicsPlayer):
    """フォーク poke-env 版の Champions 対応 heuristic: テラス封印・メガ有効化。"""

    @staticmethod
    def _should_terastallize(*args, **kwargs):
        return False

    def choose_move(self, battle):
        order = super().choose_move(battle)
        if (
            getattr(battle, "can_mega_evolve", False)
            and getattr(order, "order", None) is not None
            and isinstance(order.order, Move)
        ):
            order.mega = True
        return order


async def run(args):
    team_a = open(args.team_a).read()
    team_b = open(args.team_b).read()
    run_id = datetime.datetime.now().strftime("%H%M%S")

    model = ChampionsILPlayer(
        account_configuration=AccountConfiguration(f"ilA-{run_id}", None),
        battle_format=args.format, team=team_a,
        model_path=args.model, tokenizer_name=args.tokenizer, device=args.device,
        greedy=args.greedy,
        max_concurrent_battles=args.concurrency,
    )
    bot = ChampionsHeuristicsPlayer(
        account_configuration=AccountConfiguration(f"botB-{run_id}", None),
        battle_format=args.format, team=team_b,
        max_concurrent_battles=args.concurrency,
    )

    await model.battle_against(bot, n_battles=args.n_battles)

    # battle_runner と同形式のログを記録(analyze.py がそのまま使える)
    records = [battle_record(tag, b) for tag, b in model.battles.items()]
    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"eval_{ts}.jsonl"
    with out_path.open("w") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    n = model.n_finished_battles
    wins = model.n_won_battles
    print(f"総バトル数: {n}")
    print(f"ILモデル 勝率: {wins / n:.1%} ({wins}勝)")
    print(f"heuristic bot 勝率: {(n - wins) / n:.1%}")
    print(f"ログ: {out_path}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", required=True)
    p.add_argument("--team-a", required=True, help="ILモデルが使うパーティ")
    p.add_argument("--team-b", required=True, help="bot が使うパーティ")
    p.add_argument("-n", "--n-battles", type=int, default=100)
    p.add_argument("--format", default="gen9championsbssregmb")
    p.add_argument("--tokenizer", default="championsv1")
    p.add_argument("--device", default="cpu")
    p.add_argument("--greedy", action="store_true", help="argmaxで手を選ぶ(既定はサンプリング)")
    p.add_argument("--out-dir", default="logs", help="対戦ログ(jsonl)の出力先")
    p.add_argument("--concurrency", type=int, default=5)
    asyncio.run(run(p.parse_args()))
