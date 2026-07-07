# pokemon_battle_simulator

ポケモンチャンピオンズ(BSS Reg M-B)向けのバトルシミュレーション+AI開発プロジェクト。

**目的**: 構築したパーティの診断(AI対AIの大量対戦による勝率・傾向分析)と、
強化学習によるバトルAIの開発(将来的にはユーザー対AIの練習環境)。

## アーキテクチャ

```
[Pokémon Showdown ローカルサーバー (Node.js, port 8000)]
        ↕ WebSocket
[poke-env (Python)] ← battle_runner.py が bot 同士の対戦を実行
        ↓
[logs/*.jsonl] ← analyze.py が勝率・選出・先発・敗因を分析
```

- フォーマット: `gen9championsbssregmb`(Showdown の champions mod がチャンピオンズ環境を再現:
  技変更261件・アイテム制限・ロースター制限・ステータスポイント制(合計66/各32)・メガシンカあり・テラスなし)
- 開発拠点は2つ: **研究室GPUサーバー**(`ssh lab`、本番・学習用。LAN内のみ接続可)と
  **ローカルMac**(外出先用)。GitHub(このリポジトリ)経由で同期する。

## セットアップ

前提: Node.js 18+, Python 3.12+

```bash
# 1. Showdown 本体(このリポジトリの隣にクローン)
cd .. && git clone https://github.com/smogon/pokemon-showdown.git
cd pokemon-showdown && npm install

# 2. Python 環境(このリポジトリ直下)
cd ../pokemon_battle_simulator
python3 -m venv .venv
.venv/bin/pip install poke-env pandas matplotlib

# 3. Showdown サーバー起動(バックグラウンド)
cd ../pokemon-showdown
nohup node pokemon-showdown start --no-security > ~/showdown.log 2>&1 &
```

## 使い方

```bash
# パーティ同士を N 戦させる(結果は logs/*.jsonl)
.venv/bin/python battle_runner.py --team-a teams/my_party.txt --team-b teams/top_rain.txt -n 1000 --concurrency 20

# ログ分析(勝率・選出組み合わせ・先発別勝率・対面マトリクス・敗因)
.venv/bin/python analyze.py logs/battles_XXXX.jsonl --min-n 30

# チームの形式チェック
cd ../pokemon-showdown && ./pokemon-showdown validate-team gen9championsbssregmb < ../pokemon_battle_simulator/teams/my_party.txt

# 公式サーバーから Champions リプレイを収集(学習データ用)
.venv/bin/python collect_replays.py          # 差分収集
.venv/bin/python collect_replays.py --full   # 全ページ走査
```

### チームファイルの書式(`teams/*.txt`)

Showdown エクスポート形式。ただしチャンピオンズ仕様:
努力値の代わりにステータスポイント(`EVs: 2 HP / 32 Atk / 32 Spe`、合計66・各32まで)、
持ち物はチャンピオンズ実装済みのもののみ、テラスタイプ行は書かない。

## bot について

`battle_runner.py` の `ChampionsHeuristicsPlayer` は poke-env の SimpleHeuristicsPlayer を
チャンピオンズ仕様に調整したもの(テラス封印・メガシンカ有効化)。
**ルールベースの初心者レベル**であり、選出はランダム。診断結果は「bot の限界込み」で読むこと
(例: こだわりロックを考慮しない、交代読みをしない)。

## これまでの主な結果(2026-07-03)

- my_party vs 環境トップ4構築(GameWith SS帯、実ステ振り)の勝率:
  サザングロス 62.6% / リザXゲコ 65.8% / バシャガブ 63.2% / **雨(ラグラージ) 46.3%(負け越し)**
- 雨構築戦の分析: 相手先発ブリジュラス時の勝率17.4%、敗戦の40%でブリジュラスが生存。
  ただし bot はサザンドラでりゅうせいぐん連打しかしない(スカーフロック)ため、
  人間の実戦感覚(バシャ・スカーフマスカの方が重い)とはズレがある → 学習型AIの動機
- スループット: ローカルサーバーで**約55戦/秒**(concurrency 20)

## AI開発ロードマップ

- **Phase 1(完了)**: Showdown + poke-env の診断パイプライン
- **Phase 2(着手中)**: 学習型AI
  - データ: 公式 Showdown の Champions リプレイを毎日自動収集中
    (サーバーの cron、**2026-08-03 自動停止**。Reg M-B だけで1,600件+、約150件/日で増加)
  - 方針: 人間リプレイで模倣学習 → 相手プール方式の self-play RL でファインチューニング
    (弱いbot相手への過適応・ジャンケン循環を避けるため、固定相手でのRLはしない)
  - 参考: **PokéAgent Challenge**(NeurIPS 2025)= Metamon + PokéChamp チーム主催。
    プレイヤー視点再構成済みリプレイ軌跡400万件・self-play軌跡1800万件・チーム20万件を公開
    (Gen 9 OU なので直接は使えないが、観測空間設計とツールを流用予定)
- **Phase 3**: self-play RL 本格化(必要なら server を飛ばして sim 直結で高速化)
- **Phase 4**: ユーザー対AI環境の整備、動画等の外部データ取り込み

## Phase 2 の進捗(2026-07-05)

metamon をフォークして Champions 対応を実装し、**学習パイプラインの疎通まで完了**:

- **リプレイ再構成の Champions 対応**(ローカル `~/dev/metamon` の champions ブランチ):
  3v3 選出 / champions 図鑑(新メガ92種・見た目フォルム) / メガ進化イベント /
  持ち物なし許容 / 使用率統計のフォールバック / テラス任意化
- **メガ判断の行動エンコード**: テラス枠(行動9-12)をメガに転用、can_mega 遷移も記録。
  メガ温存(例: メガ前クリアボディで いかく を受けない)の判断が学習可能に
- **使用率統計**: Smogon 公式統計(月次公開)を metamon 形式に変換
  (`tools/build_champions_usage_stats.py`、毎月データ追加時は LATEST_USAGE_STATS_DATE も更新)
- **最終データセット: 18,911軌跡**(M-A 15,747 + M-B 3,164、102MB)。
  パース成功率: M-B 90.6% / M-A 93.9%(未完試合を除く実質 ~97%)
- **語彙 `championsv1`**: 2,022トークン(`tools/build_champions_vocab.py`)
- **学習 dry-run 成功**: 極小モデル(82k パラメータ)1エポックで検証精度22.8%
  (13択ランダム≒8%)。コマンド例:
  ```
  METAMON_CACHE_DIR=~/dev/metamon_cache python -m metamon.il.train \
    --run_name <name> --gpu 0 --formats gen9championsbssregmb gen9championsbssregma \
    --parsed_replay_dir ~/dev/metamon_cache/parsed_champions \
    --tokenizer championsv1 --base_obs_space TeamPreviewObservationSpace \
    --model_config <gin> --epochs <n>
  ```

## モデルの学習と対戦評価の運用手順(サーバー)

前提: metamon フォークは `~/sakurai/metamon`、学習venv は `~/sakurai/metamon_env`、
キャッシュ(統計・パース済み軌跡)は `~/sakurai/metamon_cache`。
共通の環境変数: `METAMON_CACHE_DIR=~/sakurai/metamon_cache`。
torch.compile はホストに `g++` と `python3.12-dev`(Python.h)が必要
(2026-07-07 に両方導入済み)。無い環境では eval_model.py が自動で eager 実行に
フォールバックする。学習コマンドの `TORCHDYNAMO_DISABLE=1` は toolchain が
揃っていれば外してよい(compile 有効で1.5〜2倍高速)。

### 学習(模倣学習)

```bash
cd ~/sakurai/metamon
METAMON_CACHE_DIR=~/sakurai/metamon_cache WANDB_MODE=disabled TORCHDYNAMO_DISABLE=1 \
nohup ~/sakurai/metamon_env/bin/python -m metamon.il.train \
  --run_name <実験名> --gpu 0 \
  --formats gen9championsbssregmb gen9championsbssregma \
  --parsed_replay_dir ~/sakurai/metamon_cache/parsed_champions \
  --tokenizer championsv1 --base_obs_space TeamPreviewObservationSpace \
  --model_config metamon/il/configs/transformer_embedding.gin \
  --epochs 500 --batch_size 64 --val_min_date 2026-07-04 > ~/sakurai/train.log 2>&1 &
```

- `--val_min_date`: 時間分割(この日以降が検証、前日までが訓練)。リプレイが増えたら進める
- 早期停止つき(検証精度が2エポック改善しなければ終了)。1エポック約3分(RTX 8000)
- ベストモデル: `logs_and_checkpoints/<実験名>_trial1/ckpts/<実験名>_trial1_BEST.pt`
- 新しいリプレイを取り込むには: パース(下記)→ 語彙再構築 → 学習、の順

```bash
# リプレイ再パース(データ更新時)と語彙再構築
cd ~/sakurai/pokemon_battle_simulator
METAMON_CACHE_DIR=~/sakurai/metamon_cache ~/sakurai/metamon_env/bin/python \
  tools/build_champions_usage_stats.py --cache-dir ~/sakurai/metamon_cache  # 月次統計
# パースは parse_parallel を使う(battle_runner とは別、実行例は git log 参照)
~/sakurai/metamon_env/bin/python tools/build_champions_vocab.py \
  --parsed-dir ~/sakurai/metamon_cache/parsed_champions \
  --out ~/sakurai/metamon/metamon/tokenizer/championsv1.json
```

### 対戦評価(学習済みモデル vs heuristic bot)

Showdown サーバー(port 8000)が起動していること。

```bash
cd ~/sakurai/pokemon_battle_simulator
MODEL=~/sakurai/metamon/logs_and_checkpoints/<実験名>_trial1/ckpts/<実験名>_trial1_BEST.pt
METAMON_CACHE_DIR=~/sakurai/metamon_cache ~/sakurai/metamon_env/bin/python eval_model.py \
  --model $MODEL --team-a teams/my_party.txt --team-b teams/top_rain.txt -n 100
```

- IL モデル側が team-a、heuristic bot が team-b。選出は両者ランダム
- モデルのラッパーは `champions_il_player.py`(13択・メガ対応・TeamPreview観測)
- 推論は CPU で十分(1.4Mパラメータ・1手1回の推論。`--device cuda:0` も可)
- 注意: eval_model.py はフォーク版 poke-env(metamon_env)で動く。
  battle_runner.py(bot同士の診断)は本家 poke-env(.venv)で動く — venv を混ぜないこと

## 次にやること

1. **本学習(サーバー)**: GitHub に metamon フォーク用リポジトリを作成 → champions
   ブランチを push → サーバーで本家サイズのモデルを学習(RTX 8000)
2. **学習前の確認**: train/val 分割が試合単位(同一試合の2視点が同じ側)になっているか
   検証・修正(リーク対策)
3. **評価**: 学習済みモデルを診断パイプラインの heuristic bot と対戦させ勝率測定
4. **型予測モデル**(v2): 制約推論(行動順→スカーフ検出、ダメージ逆算)+統計フォールバック段階化。
   FoulPlay の対戦中推論エンジンを参考調査
5. **観測空間 v2**: 期待ダメージ特徴、相手スタイル推定(深読みタイプ)特徴
6. (v3以降)ドメイン知識ベースの報酬 shaping、self-play リーグ、Bo3 対応

## インフラのメモ

- 研究室サーバー: Quadro RTX 8000 48GB / Ubuntu 24.04 / Showdown は `~/pokemon-showdown`、
  プロジェクトは `~/sakurai/pokemon_battle_simulator`
- リプレイ保存先: サーバーの `data/replays/<format>/<id>.json`(git 管理外)
- Showdown サーバーはマシン再起動後に手動で再起動が必要(上記セットアップ 3 のコマンド)
- 参考リンク: [PokéAgent Challenge](https://pokeagent.github.io/) /
  [poke-env docs](https://poke-env.readthedocs.io/) /
  [Showdown protocol](https://github.com/smogon/pokemon-showdown/blob/master/PROTOCOL.md)
