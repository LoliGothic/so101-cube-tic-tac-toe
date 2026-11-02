"""
カメラの明るさを学習データに合わせるための確認ツール。

CameraController などで露出（Exposure）を変えながら、このツールで
「今のカメラ」と「学習データの基準画像」の明るさ・白飛びの割合を見比べる。
白飛びした部分はソフトの補正では戻らないので、まずカメラ側で合わせる。

画面: [今のカメラ | 基準画像]  下に 明るさ（平均）・白飛びの割合・基準との比 を表示

キー:
  w : 今の画面を check_XXX.png に保存
  q : 終了

例（手元カメラ。アームはホーム位置にしておく）:
  python check_brightness.py --index 0 --ref hand_ref.png
例（俯瞰カメラ）:
  python check_brightness.py --index 1 --ref empty_board.png
"""

import argparse

import cv2
import numpy as np

from cam_util import Camera, add_camera_args
from erase_core import load_rgb


def measure(rgb: np.ndarray) -> tuple[np.ndarray, float, float]:
    """チャンネルごとの平均、全体の平均、白飛び（どれかのチャンネルが 250 以上）の割合 [%]"""
    ch = rgb.reshape(-1, 3).mean(axis=0)
    white = (rgb.max(axis=2) >= 250).mean() * 100
    return ch, float(ch.mean()), float(white)


def main():
    p = argparse.ArgumentParser()
    add_camera_args(p)
    p.add_argument("--ref", default="hand_ref.png", help="学習データの基準画像（hand_ref.png / empty_board.png）")
    p.add_argument("--scale", type=float, default=0.8, help="表示倍率")
    args = p.parse_args()

    ref = load_rgb(args.ref)
    ref_ch, ref_mean, ref_white = measure(ref)
    cam = Camera(args)
    print("w: 保存 / q: 終了")
    print(f"基準 {args.ref}: 明るさ {ref_mean:.1f}  白飛び {ref_white:.2f}%")
    n_saved = 0
    try:
        while True:
            rgb = cam.read()
            ch, mean, white = measure(rgb)
            ratio = ch / (ref_ch + 1e-6)
            ok = np.abs(ratio - 1).max() < 0.1 and white < max(2.0, ref_white * 2)

            r = cv2.resize(ref, (rgb.shape[1], rgb.shape[0])) if ref.shape != rgb.shape else ref
            panel = cv2.cvtColor(np.hstack([rgb, r]), cv2.COLOR_RGB2BGR)
            lines = [
                f"camera: mean {mean:5.1f}  white {white:5.2f}%",
                f"ref   : mean {ref_mean:5.1f}  white {ref_white:5.2f}%",
                f"camera/ref (R,G,B) = {ratio.round(2).tolist()}  -> {'OK' if ok else 'adjust exposure'}",
            ]
            for i, t in enumerate(lines):
                cv2.putText(panel, t, (10, panel.shape[0] - 70 + 25 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                            (0, 255, 0) if ok else (0, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(panel, "camera", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)
            cv2.putText(panel, "reference", (rgb.shape[1] + 10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2,
                        cv2.LINE_AA)
            if args.scale != 1.0:
                panel = cv2.resize(panel, None, fx=args.scale, fy=args.scale)
            cv2.imshow("check_brightness", panel)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("w"):
                name = f"check_{n_saved:03d}.png"
                cv2.imwrite(name, panel)
                n_saved += 1
                print(f"保存: {name}")
    finally:
        cam.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
