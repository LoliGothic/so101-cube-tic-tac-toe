"""
BrightnessMatcher を LeRobot の観測プロセッサとして使うためのステップ。
rollout_erase.py と record_bright.py から使う。
"""

from __future__ import annotations

import logging
import os

import cv2
import numpy as np
from lerobot.processor import ObservationProcessorStep

from brightness import BrightnessMatcher

logger = logging.getLogger("brightness")


class MatchBrightnessStep(ObservationProcessorStep):
    """robot.get_observation() の結果のうち、指定カメラの画像の明るさを基準画像に合わせる。"""

    def __init__(self, cam_key: str, matcher: BrightnessMatcher, log_every: int = 150):
        self.cam_key = cam_key
        self.matcher = matcher
        self.log_every = max(1, log_every)
        self._n = 0

    def observation(self, observation: dict) -> dict:
        if self.cam_key not in observation:
            img_keys = [k for k, v in observation.items() if isinstance(v, np.ndarray) and v.ndim == 3]
            raise KeyError(
                f"カメラ '{self.cam_key}' が観測にありません。見つかったカメラ: {img_keys}。"
                " カメラ名を --robot.cameras の名前に合わせてください。"
            )
        observation[self.cam_key] = self.matcher.apply(observation[self.cam_key])
        if self._n % self.log_every == 0:
            logger.info("明るさ補正: 基準画像との比 (R,G,B) = %s", np.round(self.matcher.gain, 3).tolist())
        self._n += 1
        return observation

    def reset(self) -> None:
        self.matcher.reset()
        self._n = 0

    def transform_features(self, features):
        return features   # 画像の大きさ・型は変えない


def make_hand_step(cam_key: str, ref_path: str, freeze_after: int = 0) -> MatchBrightnessStep | None:
    """手元カメラ用のステップ。画面全体の平均の明るさ・色味を hand_ref.png（学習データ）と同じにする。
    学習データの手元カメラは自動露出がオンで、どの景色でも平均の明るさがほぼ一定だったので、
    毎フレーム合わせる（＝自動露出をソフトで再現する）のが既定。freeze_after>0 なら開始時の数フレームで固定する。"""
    if not cam_key:
        return None
    if not os.path.exists(ref_path):
        logger.warning("%s がないので手元カメラ '%s' の明るさ補正はしません（make_hand_ref.py で作れます）",
                       ref_path, cam_key)
        return None
    img = cv2.imread(ref_path, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"画像を読み込めません: {ref_path}")
    ref = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    # ホーム位置で写る景色が学習時と違うこともあるので、画素ごとではなく画面全体の平均の明るさで合わせる
    whole = np.full(ref.shape[:2], 255, np.uint8)
    matcher = BrightnessMatcher(ref, whole, freeze_after=max(0, freeze_after), match_mean=True,
                                dark_level=-1, bright_level=256, min_gain=0.3, max_gain=3.0)
    return MatchBrightnessStep(cam_key=cam_key, matcher=matcher)
