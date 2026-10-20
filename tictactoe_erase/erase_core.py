"""
俯瞰カメラ画像から、盤面に置いてあるキューブだけを消す処理。

考え方
  - bg  : 空盤面の画像（アームはホーム位置）。事前に1枚撮っておく。
  - S   : ターン開始時（rollout 開始直後の最初のフレーム）の画像。アームはホーム位置、キューブは置いてある。
  - static = |S - bg| が大きい画素 ∩ 盤面ROI   … 消す候補（置いてあるキューブとその影）
  - arm    = |現在フレーム - S| が大きい画素    … 残す部分（アームと掴んでいるキューブ）
  - 消す範囲 = static かつ arm ではない画素 → bg の画素で置き換える

画像はすべて RGB の uint8（LeRobot のカメラ出力と同じ）として扱う。
このファイルは LeRobot に依存しないので、単体でテストできる。
"""

from __future__ import annotations

import cv2
import numpy as np


def _k(n: int) -> np.ndarray:
    """円形のカーネル（モルフォロジー処理用）"""
    n = max(1, int(n))
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (n, n))


def load_rgb(path: str) -> np.ndarray:
    """PNG などを読み込んで RGB で返す（cv2.imread は BGR なので変換する）"""
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"画像を読み込めません: {path}")
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def load_mask(path: str) -> np.ndarray:
    m = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if m is None:
        raise FileNotFoundError(f"マスクを読み込めません: {path}")
    return np.where(m > 127, 255, 0).astype(np.uint8)


class CubeEraser:
    """盤面上のキューブを消す。1回の rollout（＝1手）ごとに reset() する想定。"""

    def __init__(
        self,
        bg_rgb: np.ndarray,
        roi_mask: np.ndarray,
        static_thresh: int = 30,   # S と bg の差がこれより大きい画素を「置いてあるキューブ」とみなす
        arm_thresh: int = 35,      # 現在フレームと S の差がこれより大きい画素を「アーム」とみなす
        static_dilate: int = 7,    # キューブの縁のにじみを含めるための膨張
        arm_hole_fill: int = 31,   # アームのマスクの穴埋め（同色キューブの上を通るとき用）
        arm_dilate: int = 3,
        feather: int = 11,         # 差し替えの境目をぼかす幅（奇数）
        use_gain: bool = True,     # 照明の変化に合わせて bg の明るさを補正する
        per_frame_gain: bool = True,  # 毎フレーム明るさの変化を補正する（自動露出を切れないカメラ用）
    ):
        if bg_rgb.ndim != 3 or bg_rgb.shape[2] != 3:
            raise ValueError("bg は H×W×3 の画像にしてください")
        if roi_mask.shape[:2] != bg_rgb.shape[:2]:
            raise ValueError(
                f"ROIマスクの大きさ {roi_mask.shape[:2]} と空盤面画像の大きさ {bg_rgb.shape[:2]} が違います"
            )
        self.bg = bg_rgb
        self.roi = roi_mask
        self.static_thresh = static_thresh
        self.arm_thresh = arm_thresh
        self.static_dilate = static_dilate
        self.arm_hole_fill = arm_hole_fill
        self.arm_dilate = arm_dilate
        self.feather = feather if feather % 2 == 1 else feather + 1
        self.use_gain = use_gain
        self.per_frame_gain = per_frame_gain
        self.reset()

    # ------------------------------------------------------------------
    def reset(self) -> None:
        self.S = None
        self.static = None
        self.bg_adj = None
        self.gain = np.ones(3, np.float32)
        self.frame_gain = np.ones(3, np.float32)
        self._ref_idx = None
        # デバッグ用に最後のマスクを保持
        self.last_arm = None
        self.last_mask = None

    @property
    def started(self) -> bool:
        return self.S is not None

    # ------------------------------------------------------------------
    def begin_turn(self, frame_rgb: np.ndarray) -> None:
        """ターン開始時（アームがホーム位置）のフレームを渡す。"""
        self._check_shape(frame_rgb)
        S = frame_rgb.copy()

        d = cv2.absdiff(S, self.bg).max(axis=2)
        static = np.where(d > self.static_thresh, 255, 0).astype(np.uint8)
        static &= self.roi
        static = cv2.morphologyEx(static, cv2.MORPH_OPEN, _k(5))      # 小さなノイズを除去
        static = cv2.dilate(static, _k(self.static_dilate))
        static &= self.roi                                             # 膨張しても ROI の外には出さない

        # 明るさ補正：盤面のうちキューブがない画素で S と bg の明るさを比べる
        gain = np.ones(3, np.float32)
        if self.use_gain:
            ref = (self.roi > 0) & (static == 0)
            if ref.sum() > 1000:
                gain = S[ref].astype(np.float32).mean(0) / (self.bg[ref].astype(np.float32).mean(0) + 1e-6)
                gain = np.clip(gain, 0.8, 1.25).astype(np.float32)
        self.gain = gain
        self.bg_adj = np.clip(self.bg.astype(np.float32) * gain, 0, 255)

        self.S = S
        self.static = static

        # 毎フレームの明るさ補正に使う参照画素（盤面のうちキューブがない所。計算を軽くするため間引く）
        ref = (self.roi > 0) & (static == 0)
        ys, xs = np.nonzero(ref)
        step = max(1, len(ys) // 4000)
        self._ref_idx = (ys[::step], xs[::step]) if len(ys) > 500 else None

    def _estimate_frame_gain(self, frame_rgb: np.ndarray) -> np.ndarray:
        """S と比べて今のフレームがどれだけ明るく/暗くなったか（チャンネルごと）。
        アームが写っている画素の影響を受けないよう、比の中央値を使う。"""
        if not self.per_frame_gain or self._ref_idx is None:
            return np.ones(3, np.float32)
        f = frame_rgb[self._ref_idx].astype(np.float32) + 1.0
        s = self.S[self._ref_idx].astype(np.float32) + 1.0
        g = np.median(f / s, axis=0)
        return np.clip(g, 0.6, 1.6).astype(np.float32)

    # ------------------------------------------------------------------
    def erase(self, frame_rgb: np.ndarray) -> np.ndarray:
        """キューブを消した画像（RGB, uint8）を返す。最初の呼び出しで自動的に begin_turn する。"""
        if self.S is None:
            self.begin_turn(frame_rgb)
        self._check_shape(frame_rgb)

        if not self.static.any():           # 盤面にキューブがなければ何もしない
            self.last_arm = np.zeros(frame_rgb.shape[:2], np.uint8)
            self.last_mask = self.last_arm
            return frame_rgb

        # カメラの自動露出で明るさが変わっても、アームの判定がずれないように補正する
        g = self._estimate_frame_gain(frame_rgb)
        self.frame_gain = g
        if np.abs(g - 1).max() > 0.02:
            frame_cmp = np.clip(frame_rgb.astype(np.float32) / g, 0, 255).astype(np.uint8)
            bg_now = np.clip(self.bg_adj * g, 0, 255)
        else:
            frame_cmp = frame_rgb
            bg_now = self.bg_adj

        # アーム（と掴んでいるキューブ）＝ターン開始時から変化した画素
        d = cv2.absdiff(frame_cmp, self.S).max(axis=2)
        arm = np.where(d > self.arm_thresh, 255, 0).astype(np.uint8)
        arm = cv2.morphologyEx(arm, cv2.MORPH_OPEN, _k(3))
        if self.arm_hole_fill > 1:
            arm = cv2.morphologyEx(arm, cv2.MORPH_CLOSE, _k(self.arm_hole_fill))
        if self.arm_dilate > 1:
            arm = cv2.dilate(arm, _k(self.arm_dilate))

        mask = self.static & cv2.bitwise_not(arm)

        alpha = cv2.GaussianBlur(mask, (self.feather, self.feather), 0).astype(np.float32) / 255.0
        alpha *= (self.roi > 0)             # ぼかしても ROI の外（ストック置き場）には絶対に触らない
        alpha = alpha[..., None]

        out = frame_rgb.astype(np.float32) * (1 - alpha) + bg_now * alpha

        self.last_arm = arm
        self.last_mask = mask
        return np.clip(out, 0, 255).astype(np.uint8)

    # ------------------------------------------------------------------
    def debug_panel(self, frame_rgb: np.ndarray, erased_rgb: np.ndarray) -> np.ndarray:
        """[元画像 | 消去後 | マスク重ね合わせ] を横に並べた BGR 画像（cv2.imwrite / imshow 用）"""
        over = frame_rgb.copy()
        if self.static is not None:
            over[self.static > 0] = (0.5 * over[self.static > 0] + [127, 0, 0]).astype(np.uint8)  # 赤: 消す候補
        if self.last_arm is not None:
            a = self.last_arm > 0
            over[a] = (0.5 * over[a] + [0, 127, 0]).astype(np.uint8)                              # 緑: アーム
        contours, _ = cv2.findContours(self.roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(over, contours, -1, (255, 255, 0), 2)                                     # 黄: ROI
        panel = np.hstack([frame_rgb, erased_rgb, over])
        panel = cv2.cvtColor(panel, cv2.COLOR_RGB2BGR)
        h = panel.shape[0]
        for i, label in enumerate(["original", "erased", "red=erase green=arm yellow=ROI"]):
            cv2.putText(panel, label, (i * frame_rgb.shape[1] + 10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
        return panel

    def _check_shape(self, frame_rgb: np.ndarray) -> None:
        if frame_rgb.shape != self.bg.shape:
            raise ValueError(
                f"カメラ画像の大きさ {frame_rgb.shape} と空盤面画像の大きさ {self.bg.shape} が違います。"
                " capture_empty.py を rollout と同じ width/height で撮り直してください。"
            )
