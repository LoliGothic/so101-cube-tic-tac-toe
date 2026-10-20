"""
盤面の範囲（ROI）マスクを作る。消去処理はこの範囲の内側だけで行われる。

操作:
  左クリック : 盤面の角を順にクリック（4点以上。盤面がゆがんでいれば多めに）
  Backspace  : 最後の点を取り消す
  r          : やり直し
  Enter      : 確定して保存
  q / Esc    : 保存せず終了

保存されるもの:
  board_roi_mask.png : 盤面の内側が白、外側が黒のマスク
  roi_check.png      : 空盤面画像に ROI の輪郭を重ねた確認用画像

例:
  python make_roi.py --bg empty_board.png
  python make_roi.py --bg empty_board.png --y_limit 400   # y=400 より下（ストック置き場）は必ず対象外
"""

import argparse

import cv2
import numpy as np


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bg", default="empty_board.png")
    p.add_argument("--out", default="board_roi_mask.png")
    p.add_argument("--check", default="roi_check.png")
    p.add_argument("--dilate", type=int, default=15, help="縁の影を含めるために広げる量(px)。0で広げない")
    p.add_argument("--y_limit", type=int, default=None,
                   help="この y 座標より下は必ず対象外にする（ストック置き場を守る）")
    args = p.parse_args()

    bg = cv2.imread(args.bg)
    if bg is None:
        raise SystemExit(f"{args.bg} が読み込めません。先に capture_empty.py を実行してください。")

    pts = []

    def on_click(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            pts.append((x, y))

    win = "make_roi (click corners, Enter=save)"
    cv2.namedWindow(win)
    cv2.setMouseCallback(win, on_click)

    while True:
        view = bg.copy()
        if args.y_limit is not None:
            cv2.line(view, (0, args.y_limit), (view.shape[1], args.y_limit), (0, 0, 255), 1)
        for i, q in enumerate(pts):
            cv2.circle(view, q, 5, (0, 255, 0), -1)
            cv2.putText(view, str(i + 1), (q[0] + 6, q[1] - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)
        if len(pts) >= 2:
            cv2.polylines(view, [np.array(pts)], len(pts) >= 3, (0, 255, 0), 1)
        cv2.putText(view, f"points={len(pts)}  Enter=save r=reset BS=undo q=quit", (10, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1, cv2.LINE_AA)
        cv2.imshow(win, view)
        key = cv2.waitKey(20) & 0xFF
        if key in (ord("q"), 27):
            print("保存せず終了しました")
            break
        if key == ord("r"):
            pts.clear()
        if key in (8, 127) and pts:   # Backspace（Linux=8, macOS=127）
            pts.pop()
        if key in (13, 10):           # Enter
            if len(pts) < 3:
                print("3点以上クリックしてください")
                continue
            mask = np.zeros(bg.shape[:2], np.uint8)
            cv2.fillPoly(mask, [np.array(pts, np.int32)], 255)
            if args.dilate > 0:
                mask = cv2.dilate(mask, np.ones((args.dilate, args.dilate), np.uint8))
            if args.y_limit is not None:
                mask[args.y_limit:, :] = 0
            cv2.imwrite(args.out, mask)

            check = bg.copy()
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(check, contours, -1, (0, 255, 0), 2)
            cv2.imwrite(args.check, check)
            print(f"保存しました: {args.out}, {args.check}")
            print(f"クリックした点: {pts}")
            cv2.imshow(win, check)
            cv2.waitKey(1500)
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
