"""
lerobot-record と同じ引数で動き、俯瞰カメラの画像の明るさを空盤面の画像（empty_board.png）に
合わせてから記録するスクリプト（LeRobot 0.6 系の record API を使用）。

rollout_erase.py も同じ基準画像に合わせるので、学習データと推論時の明るさが揃う。

  - --bright.* 以外の引数は、そのまま lerobot-record に渡される
  - 記録される画像・Rerun に表示される画像は、補正後の画像になる

独自の引数:
  --bright.cam=front                明るさを合わせるカメラ名（--robot.cameras で付けた名前）
  --bright.ref=empty_board.png      基準画像（この明るさに合わせる）
  --bright.roi=board_roi_mask.png   明るさの比較に使う盤面ROIマスク
  --bright.enable=true              false にすると補正なし（比較用）

例:
  python record_bright.py \
    --robot.type=so101_follower --robot.port=/dev/tty.usbmodemXXXX --robot.id=my_follower \
    --robot.cameras="{ front: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30}}" \
    --teleop.type=so101_leader --teleop.port=/dev/tty.usbmodemYYYY --teleop.id=my_leader \
    --dataset.repo_id=<ユーザー名>/<データセット名> --dataset.single_task="place at center" \
    --dataset.num_episodes=10 --display_data=true \
    --bright.cam=front
"""


import logging
import sys

from brightness import BrightnessMatcher
from erase_core import load_mask, load_rgb

logger = logging.getLogger("record_bright")

# ---------------------------------------------------------------------------
# 1. --bright.* の引数を取り出し、残りを LeRobot の CLI パーサーに渡す
# ---------------------------------------------------------------------------
BRIGHT_DEFAULTS = {
    "cam": "front",
    "ref": "empty_board.png",
    "roi": "board_roi_mask.png",
    "enable": "true",
}


def pop_bright_args(argv):
    opts = dict(BRIGHT_DEFAULTS)
    rest = [argv[0]]
    i = 1
    while i < len(argv):
        a = argv[i]
        if a.startswith("--bright."):
            body = a[len("--bright."):]
            if "=" in body:
                k, v = body.split("=", 1)
            else:
                k = body
                i += 1
                if i >= len(argv):
                    raise SystemExit(f"--bright.{k} の値がありません")
                v = argv[i]
            if k not in opts:
                raise SystemExit(f"不明な引数です: --bright.{k}（使えるもの: {', '.join(opts)}）")
            opts[k] = v
        else:
            rest.append(a)
        i += 1
    return opts, rest


BRIGHT_OPTS, sys.argv = pop_bright_args(sys.argv)

# ---------------------------------------------------------------------------
# 2. LeRobot の読み込み
# ---------------------------------------------------------------------------
import lerobot.scripts.lerobot_record as official_record  # noqa: E402
from lerobot.processor import RobotProcessorPipeline  # noqa: E402
from lerobot.processor.converters import (  # noqa: E402
    observation_to_transition,
    transition_to_observation,
)
from lerobot.utils.import_utils import register_third_party_plugins  # noqa: E402

from brightness_step import MatchBrightnessStep  # noqa: E402


def make_obs_processor():
    if BRIGHT_OPTS["enable"].lower() in ("false", "0", "no"):
        logger.info("--bright.enable=false なので明るさ補正なしで記録します")
        return None
    matcher = BrightnessMatcher(load_rgb(BRIGHT_OPTS["ref"]), load_mask(BRIGHT_OPTS["roi"]))
    return RobotProcessorPipeline(
        steps=[MatchBrightnessStep(cam_key=BRIGHT_OPTS["cam"], matcher=matcher)],
        to_transition=observation_to_transition,
        to_output=transition_to_observation,
    )


# ---------------------------------------------------------------------------
# 3. 公式の lerobot-record をそのまま実行し、観測プロセッサだけ差し込む
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    register_third_party_plugins()
    obs_processor = make_obs_processor()   # ファイルの読み込みミスはロボットの準備前に気づける
    official_record.record(robot_observation_processor=obs_processor)
