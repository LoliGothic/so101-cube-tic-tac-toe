"""
カメラを開く共通処理。

rollout のときと同じ見た目（解像度・回転・色）になるように、LeRobot の OpenCVCamera を使う。
LeRobot が import できない環境では、素の cv2.VideoCapture にフォールバックする。
返す画像は常に RGB の uint8。
"""

from __future__ import annotations

import argparse

import cv2
import numpy as np


def add_camera_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--index", default="0",
                   help="カメラ番号 or デバイスパス（rollout の index_or_path と同じ値）")
    p.add_argument("--width", type=int, default=640)
    p.add_argument("--height", type=int, default=480)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--fourcc", default=None, help="rollout で fourcc を指定しているなら同じ値（例: MJPG）")
    p.add_argument("--rotation", type=int, default=0, choices=[0, 90, 180, -90],
                   help="rollout で rotation を指定しているなら同じ値")


def _parse_index(s: str):
    return int(s) if s.isdigit() else s


class Camera:
    def __init__(self, args: argparse.Namespace):
        self._lerobot = None
        self._cap = None
        idx = _parse_index(args.index)
        try:
            from lerobot.cameras.opencv import OpenCVCamera, OpenCVCameraConfig

            kwargs = dict(index_or_path=idx, fps=args.fps, width=args.width, height=args.height)
            if args.fourcc:
                kwargs["fourcc"] = args.fourcc
            if args.rotation:
                kwargs["rotation"] = args.rotation
            cfg = OpenCVCameraConfig(**kwargs)
            self._lerobot = OpenCVCamera(cfg)
            self._lerobot.connect()
            print("[camera] LeRobot の OpenCVCamera で接続しました")
        except ImportError:
            print("[camera] LeRobot が見つからないので cv2.VideoCapture を使います")
            self._cap = cv2.VideoCapture(idx)
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
            self._cap.set(cv2.CAP_PROP_FPS, args.fps)
            if args.fourcc:
                self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*args.fourcc))
            if not self._cap.isOpened():
                raise RuntimeError(f"カメラ {args.index} を開けません")
            self._rotation = args.rotation

    def read(self) -> np.ndarray:
        """RGB の uint8 画像を返す"""
        if self._lerobot is not None:
            return np.ascontiguousarray(self._lerobot.read())
        ok, bgr = self._cap.read()
        if not ok:
            raise RuntimeError("フレームを取得できません")
        rot = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, -90: cv2.ROTATE_90_COUNTERCLOCKWISE}
        if self._rotation in rot:
            bgr = cv2.rotate(bgr, rot[self._rotation])
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    def close(self) -> None:
        if self._lerobot is not None:
            self._lerobot.disconnect()
        if self._cap is not None:
            self._cap.release()
