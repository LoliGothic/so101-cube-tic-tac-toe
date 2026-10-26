"""
BrightnessMatcher を LeRobot の観測プロセッサとして使うためのステップ。
rollout_erase.py と record_bright.py から使う。
"""

from __future__ import annotations

import logging

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
