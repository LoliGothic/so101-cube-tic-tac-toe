# 〇×ゲーム用 キューブ消去 + lerobot-rollout

俯瞰カメラの画像から **盤面に置いてあるキューブだけ** を消して、空盤面で学習したポリシーに渡します。
アーム・掴んでいるキューブ・盤面の外（ストック置き場）は元の映像のまま残ります。

動作確認した LeRobot のバージョン: **0.6.1 / 0.6.2**（`lerobot-rollout` があるバージョン）

`rollout_erase.py` は公式の `lerobot-rollout` をそのまま呼び出し、ポリシーに渡す画像だけを差し替えます。
アームの制御（速度・終了時に初期位置へ戻る動きなど）は公式のコマンドと同じです。

## ファイル一覧

| ファイル | 役割 |
|---|---|
| `erase_core.py` | 消去処理の本体（LeRobot に依存しない） |
| `cam_util.py` | カメラを開く共通処理（LeRobot の OpenCVCamera を使用） |
| `capture_empty.py` | 空盤面の基準画像 `empty_board.png` を撮る |
| `make_roi.py` | 盤面の範囲マスク `board_roi_mask.png` を作る |
| `test_erase_live.py` | ロボットを動かさず、カメラだけで消去の様子を確認する |
| `rollout_erase.py` | `lerobot-rollout` と同じ引数で、消去処理つきで推論を実行する |

全部を同じフォルダに置き、**そのフォルダで** 以下のコマンドを実行してください。

---

## 手順

以下の `<...>` は自分の環境に置き換えてください。
特にカメラの設定（番号・width・height・fps）は、**学習データを撮ったときと同じ値** にします。

Mac の場合、初回はターミナルにカメラの使用許可を求めるダイアログが出ます。許可してください
（出なければ「システム設定 → プライバシーとセキュリティ → カメラ」でターミナルをオン）。

```bash
conda activate lerobot          # いつも使っている LeRobot の環境
cd tictactoe_erase
pip show lerobot | grep Version # 0.6 系であることを確認
```

### 0. カメラの自動調整を止める（できれば）

自動露出・オートホワイトバランスがオンだと、アームが写るだけで画面全体の明るさが変わります。
`erase_core.py` は毎フレーム明るさの変化を補正するので、**止められなくても動きます** が、止めたほうが安定します。

**Mac の場合**：無料の「CameraController」（GitHub: Itaybre/CameraController）を使います。

```bash
brew install --cask cameracontroller
```

1. CameraController を起動し、俯瞰カメラを選ぶ
2. Exposure の Auto をオフにし、明るさを学習データの画像と同じくらいに合わせる
3. White Balance の Auto をオフにする（オートフォーカスがあるカメラは Focus の Auto もオフ）

設定はカメラを抜き差しすると戻ることがあるので、毎回 `capture_empty.py` の前に確認してください。
空盤面の撮影と rollout は **同じ設定のまま** 行います。

**Linux の場合**：`v4l2-ctl -d /dev/video<番号> -l` で設定名を確認し、
`v4l2-ctl -d /dev/video<番号> -c auto_exposure=1 -c white_balance_automatic=0` のように切ります。

### 1. 空盤面の画像を撮る

盤面のキューブを全部どけて、**アームをホーム位置**（rollout を始めるときの姿勢）にしてから:

```bash
python capture_empty.py --index <カメラ番号> --width 640 --height 480 --fps 30 --out empty_board.png
```

プレビューが出たら **SPACE** で保存されます。
（rollout で `fourcc` や `rotation` を指定しているなら `--fourcc MJPG` `--rotation 180` のように同じ値を付ける）

### 2. 盤面の範囲（ROI）マスクを作る

```bash
python make_roi.py --bg empty_board.png
```

盤面の4隅を順にクリック → **Enter** で `board_roi_mask.png` と `roi_check.png` が保存されます。
`roi_check.png` の緑の線の内側が消去の対象です。**ストック置き場が線の外にあること** を確認してください。

ストック置き場が近くて線にかかる場合は、その上端の y 座標を指定して作り直します:

```bash
python make_roi.py --bg empty_board.png --y_limit <ストック置き場の上端のy>
```

### 3. カメラだけで消去を確認する（ロボットは動かさない）

```bash
python test_erase_live.py --index <カメラ番号> --width 640 --height 480 --fps 30
```

1. 盤面にキューブをいくつか置き、アームはホーム位置のまま **s** を押す（＝ターン開始時の画像）
2. 手やキューブを持った手を盤面にかざす、アームを手で動かす（rollout していなければトルクは入っていない）
3. 画面の見方: `[元画像 | 消去後 | 赤=消す範囲 緑=アーム判定 黄=ROI]`
4. **w** で画面を保存、**q** で終了

確認ポイント:
- 置いてあるキューブと影が消えて、空盤面と同じに見えるか
- アーム・手・掴んでいるキューブは残っているか
- ストック置き場のキューブは残っているか

※ rollout 実行中は同じカメラを開けないので、このテストは rollout とは別に行ってください。

### 4. 消去つきで rollout を実行する

**今使っている `lerobot-rollout` のコマンドの `lerobot-rollout` を `python rollout_erase.py` に置き換えて、`--erase.*` を足すだけ** です。

```bash
python rollout_erase.py \
  --strategy.type=base \
  --robot.type=so101_follower \
  --robot.port=<いつもの値（Mac なら /dev/tty.usbmodemXXXX）> \
  --robot.id=<キャリブレーションのID> \
  --robot.cameras="{ <カメラ名>: {type: opencv, index_or_path: <カメラ番号>, width: 640, height: 480, fps: 30}}" \
  --policy.path=<学習済みモデルのパス> \
  --task="<学習時と同じタスク文>" \
  --duration=30 \
  --display_data=true \
  --erase.cam=<カメラ名> \
  --erase.debug_dir=debug_frames
```

- `<カメラ名>` は学習データと同じ名前（例: `front`）。`--erase.cam` も同じ名前にする
- 起動する前に **アームをホーム位置** に置き、盤面にはキューブを置いた状態にしておく
  （起動直後の1フレーム目が「ターン開始時の画像」になる）
- 1回の実行 = 1手。終わるとアームは初期位置に戻る
- `--display_data=true` にすると、Rerun に **消去後の画像** が表示される（ポリシーが見ている画像そのもの）

比較のために消去なしで動かしたいときは `--erase.enable=false` を付けます。

### 5. 結果を確認する

`debug_frames/` に次の画像が保存されます。

- `S_turn_start.png` : ターン開始時の画像
- `frame_00000.jpg` … : 15フレームごとの `[元画像 | 消去後 | マスク]`

---

## うまくいかないとき

| 症状 | 対処 |
|---|---|
| `カメラ画像の大きさ ... が違います` | `capture_empty.py` を rollout と同じ width/height/rotation で撮り直す |
| `カメラ 'front' が観測にありません` | `--erase.cam` を `--robot.cameras` の名前に合わせる |
| `消去をかけていないカメラがあります` という警告 | 手首カメラなど別のカメラにはキューブが写ったまま。そのカメラを使わずに学習したモデルにするか、追加データで学習する |
| キューブの縁や影が残る | `--erase.static_thresh=20` のように下げる。照明を拡散光にする |
| 何もない盤面の一部まで差し替わる | 空盤面を撮ったときと照明・露出が違う。手順0を確認して `capture_empty.py` を撮り直す。`--erase.static_thresh=40` のように上げる |
| キューブがあった所だけ明るさが違う四角に見える | 露出が大きく変わっている。`test_erase_live.py` の `frame_gain` が 1 から大きく外れていないか確認し、手順0で自動露出を止める |
| アームの一部が消える | `--erase.arm_thresh=25` のように下げる（アームとキューブの色が近いと起きやすい） |
| アームの縁にキューブの色が細く残る | 多少なら問題なし。気になれば `--erase.arm_thresh` を上げる |
| 掴んだキューブが、同じ色の置いてあるキューブの真上で一瞬消える | 見た目がほぼ同じなので差分で区別できない（既知の制約）。目標マスの上では起きない |
| 消去は綺麗なのにまだ止まる | 学習時とタスク文・カメラ名・解像度が同じか確認。それでもだめならキューブを置いた状態のデモを追加して学習 |

## 仕組み（メモ）

- `bg` : 空盤面（アームはホーム位置）
- `S` : 実行開始時の1フレーム目（アームはホーム位置、キューブあり）
- 消す候補 = `|S - bg|` が大きい画素 ∩ ROI（置いてあるキューブと影）
- アーム = `|現在 - S|` が大きい画素（アームと掴んでいるキューブ）
- 消す範囲 = 消す候補 かつ アームではない → `bg`（明るさ補正済み）で置き換え
