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

## 次にやること

1. **metamon コード調査** — 観測空間・軌跡形式・リプレイのプレイヤー視点再構成ツールが
   チャンピオンズに流用できるか判断(https://github.com/UT-Austin-RPL/metamon)
2. **FoulPlay 調査** — 探索ベースの強bot。champions mod で動けば診断用botの質が即改善
3. PokéAgent 論文 Appendix D/E(ベースライン改良・優勝解法)の精読
4. 特徴量エンコーダの実装(metamon 調査の結論を踏まえて)
5. リプレイ→(状態, 行動)ペアへの変換パイプライン(模倣学習の前処理)

## インフラのメモ

- 研究室サーバー: Quadro RTX 8000 48GB / Ubuntu 24.04 / Showdown は `~/pokemon-showdown`、
  プロジェクトは `~/sakurai/pokemon_battle_simulator`
- リプレイ保存先: サーバーの `data/replays/<format>/<id>.json`(git 管理外)
- Showdown サーバーはマシン再起動後に手動で再起動が必要(上記セットアップ 3 のコマンド)
- 参考リンク: [PokéAgent Challenge](https://pokeagent.github.io/) /
  [poke-env docs](https://poke-env.readthedocs.io/) /
  [Showdown protocol](https://github.com/smogon/pokemon-showdown/blob/master/PROTOCOL.md)
