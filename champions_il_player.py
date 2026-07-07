"""学習した Champions IL モデルを poke-env プレイヤーとしてラップする。

metamon の BCRNNBaseline を土台にしつつ、Champions 固有の差分を上書きする:
- 観測空間: TeamPreviewObservationSpace(学習時と同じ)
- 行動空間: DefaultActionSpace(13択、メガ枠を含む)
- ギミック行動(index 9-12): テラスではなくメガシンカとしてオーダー生成
"""

import torch
from poke_env.player import Player
from poke_env.player.battle_order import BattleOrder
from torch.distributions import Categorical

from metamon.interface import (
    DefaultActionSpace,
    TeamPreviewObservationSpace,
    TokenizedObservationSpace,
    UniversalAction,
    UniversalState,
    consistent_move_order,
    consistent_pokemon_order,
)
from metamon.il.model import MetamonILModel
from metamon.tokenizer import get_tokenizer


def champions_order(battle, action_idx):
    """action_idx(0-12)を Champions 用の BattleOrder に変換。9-12 はメガ+技。"""
    wants_mega = action_idx >= 9
    if wants_mega:
        action_idx -= 9

    move_options = consistent_move_order(list(battle.active_pokemon.moves.values()))
    valid_moves = {m.id for m in battle.available_moves}
    switch_options = consistent_pokemon_order(
        [p for p in battle.team.values() if not p.fainted and not p.active]
    )
    valid_switches = {p.name for p in battle.available_switches}

    if action_idx <= 3 and not battle.force_switch:
        if action_idx < len(move_options):
            move = move_options[action_idx]
            if move.id in valid_moves:
                can_mega = bool(getattr(battle, "can_mega_evolve", False))
                return BattleOrder(move, mega=wants_mega and can_mega)
    if 4 <= action_idx <= 8:
        s = action_idx - 4
        if s < len(switch_options) and switch_options[s].name in valid_switches:
            return BattleOrder(switch_options[s])
    return None  # 無効 → 呼び出し側でフォールバック


class ChampionsILPlayer(Player):
    def __init__(self, *args, model_path, tokenizer_name="championsv1",
                 device="cpu", mask_actions=True, greedy=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.device = torch.device(device)
        self.model = torch.load(model_path, map_location=self.device, weights_only=False)
        assert isinstance(self.model, MetamonILModel)
        self.model.eval()
        self.tokenizer = get_tokenizer(tokenizer_name)
        self.obs_space = TokenizedObservationSpace(
            base_obs_space=TeamPreviewObservationSpace(), tokenizer=self.tokenizer
        )
        self.action_space = DefaultActionSpace()
        self.mask_actions = mask_actions
        self.greedy = greedy  # True: argmax(最有力手) / False: 分布からサンプリング
        self.hidden_states = {}

    def _illegal_mask(self, battle):
        # Champions 用: champions_order で実際にオーダー化できる行動だけを合法とする
        # (metamon の definitely_valid_actions はテラス前提でメガ枠を弾くため使わない)
        mask = [champions_order(battle, a) is None for a in range(13)]
        return torch.tensor(mask, dtype=torch.bool)

    def choose_move(self, battle):
        state = UniversalState.from_Battle(battle)
        obs = self.obs_space.state_to_obs(state)
        numerical = torch.from_numpy(obs["numbers"]).view(1, 1, -1).to(self.device)
        tokens = torch.from_numpy(obs["text_tokens"]).view(1, 1, -1).to(self.device)

        hidden = self.hidden_states.get(battle.battle_tag)
        with torch.inference_mode():
            logits, new_hidden = self.model(
                token_inputs=tokens, numerical_inputs=numerical, hidden_state=hidden
            )
            if self.mask_actions:
                mask = self._illegal_mask(battle).view(1, 1, -1)
                logits = logits.masked_fill(mask, -float("inf"))
            if self.greedy:
                action_idx = logits.argmax(dim=-1).item()
            else:
                action_idx = Categorical(logits=logits).sample().item()
        self.hidden_states[battle.battle_tag] = new_hidden

        order = champions_order(battle, action_idx)
        return order if order is not None else self.choose_random_move(battle)
