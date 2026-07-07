"""学習した Champions IL モデルを heuristic bot と対戦させて戦績を測る。

使い方:
    python eval_model.py --model <BEST.pt> --team-a teams/my_party.txt \
        --team-b teams/top_rain.txt -n 100
"""

import argparse
import asyncio
import datetime
import os

# サーバーに C コンパイラが無く torch.compile が例外を吐いて対戦がハングするため、
# torch を import する前に eager 実行へ固定する
os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")

from poke_env import AccountConfiguration
from poke_env.environment.move import Move
from poke_env.player import SimpleHeuristicsPlayer

from champions_il_player import ChampionsILPlayer


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
        max_concurrent_battles=args.concurrency,
    )
    bot = ChampionsHeuristicsPlayer(
        account_configuration=AccountConfiguration(f"botB-{run_id}", None),
        battle_format=args.format, team=team_b,
        max_concurrent_battles=args.concurrency,
    )

    await model.battle_against(bot, n_battles=args.n_battles)

    n = model.n_finished_battles
    wins = model.n_won_battles
    print(f"総バトル数: {n}")
    print(f"ILモデル 勝率: {wins / n:.1%} ({wins}勝)")
    print(f"heuristic bot 勝率: {(n - wins) / n:.1%}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", required=True)
    p.add_argument("--team-a", required=True, help="ILモデルが使うパーティ")
    p.add_argument("--team-b", required=True, help="bot が使うパーティ")
    p.add_argument("-n", "--n-battles", type=int, default=100)
    p.add_argument("--format", default="gen9championsbssregmb")
    p.add_argument("--tokenizer", default="championsv1")
    p.add_argument("--device", default="cpu")
    p.add_argument("--concurrency", type=int, default=5)
    asyncio.run(run(p.parse_args()))
