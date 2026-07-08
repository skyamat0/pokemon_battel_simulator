"""生リプレイ(json)を metamon の学習用軌跡(.lz4)に一括パースする。

参照先(入力): data/replays/<format>/*.json      ← collect_replays.py が貯める生リプレイ
保存先(出力): $METAMON_CACHE_DIR/parsed_champions/<format>/*.lz4  ← 1リプレイ→2視点の軌跡

パーサを改良したら過去分も含めて全件やり直す必要があるため、既定は全件パース(上書き)。
実行には METAMON_CACHE_DIR(使用率統計・図鑑の場所)が必要。metamon venv で実行する。

使い方:
    METAMON_CACHE_DIR=~/sakurai/metamon_cache \\
      ~/sakurai/metamon_env/bin/python tools/parse_champions_replays.py \\
      --replay-dir ~/sakurai/pokemon_battle_simulator/data/replays \\
      --out ~/sakurai/metamon_cache/parsed_champions
"""

import argparse
import glob
import os
import warnings

FORMATS = ["gen9championsbssregmb", "gen9championsbssregma"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-dir", required=True, help="生リプレイ json のルート")
    parser.add_argument("--out", required=True, help="パース済み .lz4 の出力ルート")
    parser.add_argument("--formats", nargs="*", default=FORMATS)
    parser.add_argument("--pool-size", type=int, default=10, help="並列ワーカー数")
    args = parser.parse_args()

    warnings.filterwarnings("ignore")
    from metamon.backend.replay_parser.parse_replays import ReplayParser

    for fmt in args.formats:
        files = sorted(glob.glob(os.path.join(args.replay_dir, fmt, "*.json")))
        out_dir = os.path.join(args.out, fmt)
        rp = ReplayParser(replay_output_dir=out_dir, verbose=False)
        print(f"[{fmt}] {len(files)}件 パース開始", flush=True)
        rp.parse_parallel(files, pool_size=args.pool_size)
        n_out = len(glob.glob(os.path.join(out_dir, "*.lz4")))
        print(f"[{fmt}] 出力軌跡: {n_out}(リプレイ換算 {n_out // 2} / {len(files)})", flush=True)
    print("=== 全件パース完了 ===", flush=True)


if __name__ == "__main__":
    main()
