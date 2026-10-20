"""
ロボットを動かさずに、カメラだけで消去処理を確認する。

  1. 盤面にキューブをいくつか置き、アームをホーム位置にする（手やアームは盤面にかけない）
  2. このスクリプトを実行して s を押す → その瞬間が「ターン開始時の画像 S」になる
  3. アームを手で動かしたり（ロボット未接続ならトルクがないので手で動かせる）、
     キューブを持った手を盤面の上にかざしたりして、
     「置いてあるキューブだけが消え、アーム・掴んでいるキューブ・ストック置き場は残るか」を確認する

画面: [元画像 | 消去後 | 赤=消す範囲 緑=アーム判定 黄=ROI]

キー:
  s : S を撮り直す（キューブの配置を変えたら押す）
  w : 今の画面を debug_live_XXX.png に保存
  q : 終了

例:
  python test_erase_live.py --index 0 --width 640 --height 480 --fps 30
"""

import argparse
import time

import cv2

from cam_util import Camera, add_camera_args
from erase_core import CubeEraser, load_mask, load_rgb


def main():
    p = argparse.ArgumentParser()
    add_camera_args(p)
    p.add_argument("--bg", default="empty_board.png")
    p.add_argument("--roi", default="board_roi_mask.png")
    p.add_argument("--static_thresh", type=int, default=30)
    p.add_argument("--arm_thresh", type=int, default=35)
    p.add_argument("--arm_hole_fill", type=int, default=31)
    p.add_argument("--scale", type=float, default=0.7, help="表示倍率（画面に収まらないとき小さく）")
    args = p.parse_args()

    eraser = CubeEraser(
        load_rgb(args.bg), load_mask(args.roi),
        static_thresh=args.static_thresh, arm_thresh=args.arm_thresh, arm_hole_fill=args.arm_hole_fill,
    )
    cam = Camera(args)
    print("s: ターン開始画像を撮る / w: 保存 / q: 終了")
    n_saved = 0
    try:
        while True:
            frame = cam.read()
            t0 = time.perf_counter()
            if eraser.started:
                erased = eraser.erase(frame)
            else:
                erased = frame
            ms = (time.perf_counter() - t0) * 1e3

            panel = eraser.debug_panel(frame, erased)
            msg = (f"S captured  frame_gain={eraser.frame_gain.round(2).tolist()}  {ms:.1f}ms"
                   if eraser.started else "press 's' to capture turn-start image S")
            cv2.putText(panel, msg, (10, panel.shape[0] - 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2, cv2.LINE_AA)
            if args.scale != 1.0:
                panel_show = cv2.resize(panel, None, fx=args.scale, fy=args.scale)
            else:
                panel_show = panel
            cv2.imshow("test_erase_live", panel_show)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("s"):
                eraser.reset()
                eraser.begin_turn(frame)
                print(f"S を撮りました。明るさ補正 gain={eraser.gain}")
            if key == ord("w"):
                name = f"debug_live_{n_saved:03d}.png"
                cv2.imwrite(name, panel)
                n_saved += 1
                print(f"保存: {name}")
    finally:
        cam.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
