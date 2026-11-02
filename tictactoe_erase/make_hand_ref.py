"""
学習データの各エピソードの開始時（アームはホーム位置）の手元カメラ画像から、
手元カメラの明るさの基準画像 hand_ref.png を作る。

学習データの手元カメラは自動露出がオンで、どの景色でも画面全体の平均の明るさがほぼ一定だったので、
rollout_erase.py / record_bright.py は毎フレーム、画面全体の平均の明るさ・色味をこの画像に合わせる
（自動露出をソフトで再現する）。hand_frames=N を指定すると、開始時の N フレームで補正量を固定する。

Hugging Face から学習データの動画を1ファイル分だけダウンロードして使う。

例:
  python make_hand_ref.py --repo_id DQwalk/so101_pick_place_2cam_100 --cam hand
"""

import argparse
import glob
import os

import av
import cv2
import numpy as np
import pandas as pd
from huggingface_hub import HfApi, hf_hub_download


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo_id", default="DQwalk/so101_pick_place_2cam_100", help="学習データの repo_id")
    p.add_argument("--cam", default="hand", help="カメラ名（observation.images.<cam>）")
    p.add_argument("--file_index", type=int, default=None,
                   help="使う動画ファイルの番号（省略時は一番小さいファイル）")
    p.add_argument("--start_frames", type=int, default=5, help="各エピソードの先頭何フレームを使うか")
    p.add_argument("--cache_dir", default="hf_dataset_cache", help="ダウンロード先")
    p.add_argument("--out", default="hand_ref.png")
    args = p.parse_args()

    key = f"observation.images.{args.cam}"
    files = HfApi().list_repo_files(args.repo_id, repo_type="dataset")
    for f in files:
        if f.startswith("meta/episodes/") and f.endswith(".parquet"):
            hf_hub_download(args.repo_id, f, repo_type="dataset", local_dir=args.cache_dir)
    eps = pd.concat(pd.read_parquet(f) for f in sorted(glob.glob(f"{args.cache_dir}/meta/episodes/*/*.parquet")))

    if args.file_index is None:
        info = HfApi().dataset_info(args.repo_id, files_metadata=True)
        sizes = {s.rfilename: s.size for s in info.siblings if s.rfilename.startswith(f"videos/{key}/")
                 and s.rfilename.endswith(".mp4")}
        if not sizes:
            raise SystemExit(f"カメラ '{args.cam}' の動画が見つかりません")
        smallest = min(sizes, key=sizes.get)
        args.file_index = int(os.path.basename(smallest).split("-")[1].split(".")[0])
    eps = eps[eps[f"videos/{key}/file_index"] == args.file_index]
    chunk = int(eps[f"videos/{key}/chunk_index"].iloc[0])
    video = f"videos/{key}/chunk-{chunk:03d}/file-{args.file_index:03d}.mp4"
    print(f"{video} を使います（{len(eps)} エピソード）")
    path = hf_hub_download(args.repo_id, video, repo_type="dataset", local_dir=args.cache_dir)

    # 各エピソードの先頭フレームの番号を求める
    c = av.open(path)
    st = c.streams.video[0]
    fps = float(st.average_rate)
    starts = sorted(int(round(t * fps)) for t in eps[f"videos/{key}/from_timestamp"])
    wanted = {s + k for s in starts for k in range(args.start_frames)}
    frames = {}
    for i, f in enumerate(c.decode(st)):
        if i in wanted:
            frames[i] = f.to_ndarray(format="rgb24")
        if i > max(wanted):
            break
    c.close()

    per_ep = [np.mean([frames[s + k] for k in range(args.start_frames) if s + k in frames], axis=0)
              for s in starts]
    per_ep = np.stack(per_ep).astype(np.float32)
    ref = np.median(per_ep, axis=0).astype(np.uint8)
    cv2.imwrite(args.out, cv2.cvtColor(ref, cv2.COLOR_RGB2BGR))

    # エピソードごとの開始時の明るさのばらつき（小さいほど基準として信頼できる）
    m = per_ep.mean(axis=(1, 2, 3))
    print(f"保存しました: {args.out}  大きさ={ref.shape[1]}x{ref.shape[0]}")
    print(f"開始時の明るさ: 平均 {m.mean():.1f}  ばらつき(標準偏差/平均) {m.std() / m.mean():.3f}")

    check = os.path.splitext(args.out)[0] + "_check.png"
    tiles = [cv2.resize(x.astype(np.uint8), (213, 160)) for x in per_ep[:15]]
    while len(tiles) % 5:
        tiles.append(np.zeros_like(tiles[0]))
    grid = np.vstack([np.hstack(tiles[i:i + 5]) for i in range(0, len(tiles), 5)])
    cv2.imwrite(check, cv2.cvtColor(grid, cv2.COLOR_RGB2BGR))
    print(f"各エピソードの開始時の画像: {check}")


if __name__ == "__main__":
    main()
