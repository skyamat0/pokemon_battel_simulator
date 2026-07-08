# 実験記録

すべての学習・評価実験をここに記録する(2026-07-07 運用開始)。

## 学習

| ID | 日付 | 手法 | モデル | データ | val精度(ベスト) | Top-2 | 備考 |
|---|---|---|---|---|---|---|---|
| il_dryrun_mac | 07-05 | BC | 82k (tiny) | M-B 3,136(ランダム分割) | 22.8%(1ep) | 41.3% | Mac CPU疎通確認 |
| gpu_dryrun2 | 07-07 | BC | 82k (tiny) | M-A+M-B, 時間分割 | 22.8%(1ep) | 43.0% | サーバーGPU疎通・時間分割確認 |
| **champions_il_v1** | 07-07 | BC | 1.4M | 全レート 42,018軌跡 / val=7/4以降454 | **38.1%**(11ep, 早期停止13ep) | 59.5% | eager実行(compile無効時代) |
| champions_il_v15 | 07-07 | BC | 7.3M | **レート1300+** 15,076試合 / val=7/4以降∩1300+ **96試合** | 23.9%(4ep) | — | **失敗(教訓あり)**: val 96試合では accuracy がノイズで暴れ、loss が単調改善中(1.90→1.69)なのに acc 基準の早期停止(patience2)が誤発動。※ v1 の38.1%とは val セットが違うため精度の直接比較は不可 |
| champions_il_v15b | 07-07 | BC | 7.3M | train 14,957 / **val 215(7/1以降∩1300+)** | 26.2%(9ep) | — | loss基準早期停止(patience4)。val loss 1.94→1.72で頭打ち。v1(38%)より低いが val セット別物で比較不可。対戦評価で決着させる宿題 |
| champions_rl_v2a | 07-07 | オフラインRL(exp_rl) | small_agent | champions_human.yaml (replay100%) | **失敗** | | 起動時の環境初期化でクラッシュ。当初 gymnasium 不整合と誤診 → 真因は下記2バグ |
| **champions_rl_v2**(疎通) | 07-08 | オフラインRL(exp_rl) | 14.1M(Tformer+Vanilla) | champions_human.yaml 42,472軌跡(replay100%) | — | **疎通成功**。本家と同一アーキ(TformerTrajEncoder + 価値関数NCritics×4)。1エポックで30MBの重み保存を確認 |
| champions_rl_v2(本走行) | 07-08 | オフラインRL(exp_rl) | 14.1M | champions_human.yaml 42,472軌跡(パース済み・7/8以前のデータで凍結) | (実行中・20ep) | | 本番学習。1エポック=25,000勾配ステップ≒24分、20エポックで**約8時間**。開始 06:49 UTC。ckpt: `~/sakurai/rl_checkpoints/champions_rl_v2/ckpts/`。完了後は eval_model.py で対bot戦績を測る |

### v2a→v2 で判明した2つの根本原因(昨日の gymnasium 誤診の訂正)

1. **amago 3.4.0 の型バグ**: `Experiment.traj_save_len` デフォルトが `1e10`(float)。
   `AMAGOEnv.random_traj_length()` の `random.randint(*save_every)` が float を受け付けず
   環境初期化でクラッシュ。非同期ワーカー内で起きたため `'Timestep' object is not subscriptable`
   という別のエラーに化けて表面化していた(sync実行で真因が露出)。
   → `create_offline_rl_trainer` で `traj_save_len` に整数を明示して解決
2. **GPU世代の非対応**: amago の TformerTrajEncoder は FlashAttention2 必須だが、
   FA2 は Ampere 以降専用で **Quadro RTX 8000(Turing, sm_75)では原理的に動かない**。
   → flash-attn は入れず、数学的に等価な `VanillaAttention` を gin 登録(`gin.external_configurable`)。
   本家と同一の Transformer 系列エンコーダのまま flash 依存だけ除去(`champions_small_vanilla.gin`)

## 対戦評価(100戦、選出ランダム、bot=ChampionsHeuristics)

| ID | 日付 | モデル | 手選択 | 自チーム vs 相手チーム | モデル勝率 | 参考 |
|---|---|---|---|---|---|---|
| eval_v1 | 07-07 | v1 | サンプリング | my_party vs top_rain | **21%** | bot同士だと my_party側 40.7% |
| eval_greedy | 07-07 | v1 | **greedy** | my_party vs top_rain | **29%** | greedy化で+8pt |
| eval_mirror | 07-07 | v1 | greedy | my_party ミラー | **15%** | 相性を消すと悪化。原因未解明(次回からturn_log付きで分析可能) |

## 既知の運用ノート

- 評価は greedy を標準とする
- eval_model.py は logs/eval_*.jsonl に全対戦ログを記録(analyze.py 互換)
- 対botはあくまで代理指標。真の評価は対人(ユーザー)とラダー
- **データ更新パイプラインは半自動**: 収集(collect_replays.py)は cron で自動(毎日3/15時、
  ~8/3で自動停止)だが、パース(json→lz4)・語彙再構築・学習は手動。学習前に
  `tools/parse_champions_replays.py` で全件パース → `tools/build_champions_vocab.py` の順で更新する
- 学習データは「最後にパースした時点」で凍結される。`--val_min_date`(IL専用)は凍結プール内で
  train/val の境界を引くだけで、データ総量は変えない

## バックログ

- **学習データ更新パイプラインの統合スクリプト**: collect→parse→vocab を1コマンド化(現状は手動3ステップ)
- 局面タイプ別の精度分解(交代読み等の難所で当てられているかの診断)
- 観測空間 v2: 相手型の期待埋め込み・期待ダメージ特徴(本人主筆)
- cron 停止期限(2026-08-03)の延長要否は運用しながら判断
