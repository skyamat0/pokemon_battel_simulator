"""Smogon の Champions 使用率統計を metamon の usage-stats キャッシュ形式に変換する。

metamon 標準の create_usage_jsons.py はティアが gen1-9 の ubers/ou/uu/ru/nu/pu に
ハードコードされているため、Champions フォーマット用に同じ出力規約で別途ビルドする。

使い方(metamon が入った venv で実行):
    python tools/build_champions_usage_stats.py --cache-dir ~/dev/metamon_cache

出力:
    {cache}/usage-stats/movesets_data/gen9/<championsティア>/<rank>/<YYYY-MM>.json
    {cache}/usage-stats/checks_data/gen9/<championsティア>/<rank>/<YYYY-MM>.json
"""

import argparse
import json
import os
import pathlib
import urllib.request

FORMATS = ["gen9championsbssregmb", "gen9championsbssregma"]
DATES = ["2026-04", "2026-05", "2026-06"]
RANKS = [0, 1500, 1630, 1760]
HEADERS = {"User-Agent": "pokemon-battle-simulator stats builder (research use)"}


def download_raw(raw_dir: pathlib.Path) -> int:
    """Smogon から moveset テキストを取得(存在しない月×formatはスキップ)"""
    n = 0
    for date in DATES:
        out = raw_dir / date / "moveset"
        out.mkdir(parents=True, exist_ok=True)
        for fmt in FORMATS:
            for rank in RANKS:
                path = out / f"{fmt}-{rank}.txt"
                if path.exists():
                    continue
                url = f"https://www.smogon.com/stats/{date}/moveset/{fmt}-{rank}.txt"
                req = urllib.request.Request(url, headers=HEADERS)
                try:
                    with urllib.request.urlopen(req, timeout=30) as r:
                        path.write_bytes(r.read())
                    n += 1
                except Exception:
                    pass  # その月に存在しないフォーマットは無視
    return n


def build(raw_dir: pathlib.Path, save_dir: pathlib.Path) -> None:
    from metamon.backend.team_prediction.usage_stats.stat_reader import SmogonStat

    for fmt in FORMATS:
        tier = fmt[4:]  # gen9 を除いたティア名(metamon の {gen}/{tier} 規約に合わせる)
        for date in DATES:
            if not (raw_dir / date / "moveset" / f"{fmt}-1500.txt").exists():
                continue
            ranks = SmogonStat.available_ranks(fmt, raw_stats_dir=str(raw_dir), date=date)
            for rank in ranks:
                stat = SmogonStat(
                    fmt, raw_stats_dir=str(raw_dir), date=date, rank=rank, verbose=False
                )
                if not stat.movesets:
                    continue
                moveset_path = save_dir / "movesets_data" / "gen9" / tier / str(rank) / f"{date}.json"
                moveset_path.parent.mkdir(parents=True, exist_ok=True)
                moveset_path.write_text(json.dumps(stat.movesets))

                checks = {mon: stat.movesets[mon]["checks"] for mon in stat.movesets}
                checks_path = save_dir / "checks_data" / "gen9" / tier / str(rank) / f"{date}.json"
                checks_path.parent.mkdir(parents=True, exist_ok=True)
                checks_path.write_text(json.dumps(checks))
                print(f"{fmt} {date} rank={rank}: {len(stat.movesets)} 匹分を書き出し")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", required=True, help="METAMON_CACHE_DIR 相当のパス")
    args = parser.parse_args()

    cache = pathlib.Path(os.path.expanduser(args.cache_dir))
    raw_dir = cache / "smogon_raw"
    n = download_raw(raw_dir)
    print(f"生ファイル新規ダウンロード: {n} 件")
    build(raw_dir, cache / "usage-stats")


if __name__ == "__main__":
    main()
