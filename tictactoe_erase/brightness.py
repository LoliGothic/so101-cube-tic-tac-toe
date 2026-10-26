"""
カメラ画像の明るさ・色味を、基準画像（empty_board.png）に合わせる処理。

考え方
  - 盤面ROIの画素で「今のフレーム / 基準画像」の比を R/G/B ごとに求める
  - アームや手、キューブが写っても影響を受けないよう、比の中央値を使う
  - 自動露出による急な変化でちらつかないよう、フレーム間でなめらかにする
  - 今のフレームをその比で割って、基準画像と同じ明るさにする

画像はすべて RGB の uint8（LeRobot のカメラ出力と同じ）として扱う。
このファイルは LeRobot に依存しないので、単体でテストできる。
"""

from __future__ import annotations

import numpy as np


class BrightnessMatcher:
    """毎フレーム、基準画像と同じ明るさになるように補正する。"""

    def __init__(
        self,
        ref_rgb: np.ndarray,
        roi_mask: np.ndarray,
        smooth: float = 0.3,       # 1 に近いほど今のフレームの値をすぐ使う（小さいほどなめらか）
        min_gain: float = 0.6,     # これより大きく補正しない（カメラが真っ暗/真っ白なときの暴走防止）
        max_gain: float = 1.6,
        dark_level: int = 40,      # 基準画像でこれより暗い画素（盤面の黒線など）は比が不安定なので使わない
    ):
        if roi_mask.shape[:2] != ref_rgb.shape[:2]:
            raise ValueError(
                f"ROIマスクの大きさ {roi_mask.shape[:2]} と基準画像の大きさ {ref_rgb.shape[:2]} が違います"
            )
        self.ref = ref_rgb
        self.smooth = smooth
        self.min_gain = min_gain
        self.max_gain = max_gain

        # 比を計算する画素（盤面のうち暗すぎない所。計算を軽くするため間引く）
        use = (roi_mask > 0) & (ref_rgb.max(axis=2) > dark_level)
        ys, xs = np.nonzero(use)
        if len(ys) < 500:
            raise ValueError("明るさの比較に使える盤面の画素が少なすぎます。ROIマスクを確認してください")
        step = max(1, len(ys) // 4000)
        self._idx = (ys[::step], xs[::step])
        self._ref_px = ref_rgb[self._idx].astype(np.float32) + 1.0
        self.reset()

    def reset(self) -> None:
        self.gain = None   # 今の補正量（R/G/B ごとの「今のフレーム / 基準画像」）

    def estimate(self, frame_rgb: np.ndarray) -> np.ndarray:
        """基準画像と比べて今のフレームがどれだけ明るい/暗いか（チャンネルごと）"""
        f = frame_rgb[self._idx].astype(np.float32) + 1.0
        g = np.median(f / self._ref_px, axis=0)
        return np.clip(g, self.min_gain, self.max_gain).astype(np.float32)

    def apply(self, frame_rgb: np.ndarray) -> np.ndarray:
        """基準画像と同じ明るさにした画像（RGB, uint8）を返す"""
        if frame_rgb.shape != self.ref.shape:
            raise ValueError(
                f"カメラ画像の大きさ {frame_rgb.shape} と基準画像の大きさ {self.ref.shape} が違います。"
                " capture_empty.py を同じ width/height で撮り直してください。"
            )
        g = self.estimate(frame_rgb)
        self.gain = g if self.gain is None else (1 - self.smooth) * self.gain + self.smooth * g
        if np.abs(self.gain - 1).max() < 0.01:
            return frame_rgb
        return np.clip(frame_rgb.astype(np.float32) / self.gain, 0, 255).astype(np.uint8)
