"""
空盤面の基準画像を撮る。

  1. 盤面のキューブをすべて取り除く（ストック置き場のキューブはそのままでOK）
  2. アームを rollout 開始時と同じホーム位置に置く
  3. このスクリプトを実行し、プレビューを見ながら SPACE で保存（q で終了）

ノイズを減らすため、SPACE を押した後の数フレームを平均して保存する。

例:
  python capture_empty.py --index 0 --width 640 --height 480 --fps 30 --out empty_board.png
"""

import argparse

import cv2
import numpy as np

from cam_util import Camera, add_camera_args


def main():
    p = argparse.ArgumentParser()
    add_camera_args(p)
    p.add_argument("--out", default="empty_board.png")
    p.add_argument("--avg", type=int, default=15, help="平均するフレーム数")
    args = p.parse_args()

    cam = Camera(args)
    print("SPACE: 保存 / q: 終了")
    try:
        while True:
            rgb = cam.read()
            view = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            cv2.putText(view, "SPACE: save  q: quit", (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA)
            cv2.imshow("capture_empty", view)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord(" "):
                acc = np.zeros(rgb.shape, np.float32)
                for _ in range(args.avg):
                    acc += cam.read().astype(np.float32)
                avg = np.clip(acc / args.avg, 0, 255).astype(np.uint8)
                cv2.imwrite(args.out, cv2.cvtColor(avg, cv2.COLOR_RGB2BGR))
                print(f"保存しました: {args.out}  大きさ={avg.shape[1]}x{avg.shape[0]}")
                break
    finally:
        cam.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
