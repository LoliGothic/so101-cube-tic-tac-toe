# 01. セットアップ：環境構築からエピソード収集まで

Mac 2台・2人で、SO-101（Leader / Follower）を使って「赤と青のキューブを同じ色の箱に入れる」お手本データ（エピソード）を録り終えるまでの手順です。
セットアップの詳細コマンドは [README.md](../README.md) を参照してください。

> LeRobot は更新が速いため、コマンドや引数が変わっていた場合は[公式ドキュメント](https://huggingface.co/docs/lerobot/il_robots)を優先してください。

---

## 全体像

| 段階 | 内容 | 担当 | 目安時間 | 完了の条件 |
|---|---|---|---|---|
| 1 | Mac に環境を入れる | 2人とも各自 | 半日 | `lerobot-find-port` が実行できる |
| 2 | モーター ID 設定・組み立て・キャリブレーション | 2人で | 1〜2日（組み立て済みなら半日） | 両アームのキャリブレーションが終わる |
| 3 | テレオペで動作確認 | 2人で | 1時間 | Leader に Follower が追従する |
| 4 | 作業スペース・カメラ・Hugging Face の準備 | 2人で | 半日〜1日 | カメラ付きテレオペで映像が正しく見える |
| 5 | 試しに10エピソード録る | 2人で | 半日 | Hub 上でデータが確認できる |
| 6 | 本番の2色仕分けを50エピソード録る | 2人で | 1〜2時間（慣れないうちは倍） | 50エピソードが Hub にある |

**2人での進め方の原則**
- 実機を使う段階（2〜6）は、**アームをつなぐ Mac を1台に決める**
- 実機を使わない作業（環境構築、コードの準備、順番表づくり）は並行して進める

---

## 段階 1：Mac に環境を入れる

**担当：** 2人とも、それぞれの Mac で行う
**目的：** 2人が同じバージョンの LeRobot を使える状態にする

### 手順

1. **Miniforge（conda）を入れる**（未導入の場合のみ）
   ```bash
   curl -L -O "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
   bash Miniforge3-$(uname)-$(uname -m).sh
   ```
   終わったらターミナルを開き直す。

2. **仮想環境を作る**
   ```bash
   conda create -y -n lerobot python=3.12
   conda activate lerobot
   ```

3. **ffmpeg を入れる**（動画の保存に必要）
   ```bash
   conda install ffmpeg -c conda-forge
   ffmpeg -version
   ```
   8系になっていたら 7系に下げる。
   ```bash
   conda install ffmpeg=7.1.1 -c conda-forge
   ```

4. **LeRobot をインストールする**
   ```bash
   git clone https://github.com/huggingface/lerobot.git
   cd lerobot
   pip install -e ".[feetech]"
   ```

5. **バージョンを2人で揃える**
   - 先にインストールした人がコミットハッシュを確認して共有する
     ```bash
     git log -1 --format=%H
     ```
   - もう1人は同じコミットに合わせてから、もう一度インストールする
     ```bash
     git checkout <共有されたハッシュ>
     pip install -e ".[feetech]"
     ```
   - ハッシュは README の「チーム開発のルール」に記入する

6. **動作確認**
   ```bash
   lerobot-find-port
   ```
   コマンドが起動すれば OK（アームがなくてもよい）。

### チェックリスト
- [ ] 2人とも `conda activate lerobot` できる
- [ ] ffmpeg が 7系
- [ ] 2人の LeRobot のコミットハッシュが同じ
- [ ] `lerobot-find-port` が起動する

### つまずきやすい点
- 新しいターミナルを開くたびに `conda activate lerobot` が必要
- `pip install` が失敗したら、仮想環境が有効になっているか（プロンプトに `(lerobot)` が出ているか）を確認

---

## 段階 2：モーター ID 設定・組み立て・キャリブレーション

**担当：** 2人で。1人が Mac を操作、1人がモーターのつなぎ替え・組み立て
**目的：** Leader / Follower を正しく動く状態にする
**使う Mac：** ここで決めた1台を、以降の実機作業でも使う

> 組み立て済みキットの場合は、**2-1（ポート確認）と 2-4（キャリブレーション）だけ**で済むことが多いです。

### 2-1. ポート確認

1. 両方のモーターバスに電源を入れ、USB で Mac につなぐ
2. 実行して、指示が出たら**調べたい方の USB を抜いて Enter**
   ```bash
   lerobot-find-port
   ```
3. 表示されたポート名を記録し、USB を差し直す。もう一方も同様に確認
4. `.env` を作って書く（Git にはコミットしない）
   ```bash
   export LEADER_PORT=/dev/tty.usbmodemXXXXXXXXXXX
   export FOLLOWER_PORT=/dev/tty.usbmodemYYYYYYYYYYY
   ```

> ポート名は抜き差しや再起動で変わることがあります。動かないときはまずここを再確認。

### 2-2. モーター ID 設定（組み立て前に行う）

Follower のモーターは全部同じギア比（1/345）ですが、**Leader は関節ごとに違う**ので、本体ラベルと照合します。

| Leader の関節 | ID | ギア比 |
|---|---|---|
| shoulder_pan | 1 | 1/191 |
| shoulder_lift | 2 | 1/345 |
| elbow_flex | 3 | 1/191 |
| wrist_flex | 4 | 1/147 |
| wrist_roll | 5 | 1/147 |
| gripper | 6 | 1/147 |

**Leader**
```bash
source .env
lerobot-setup-motors \
  --teleop.type=so101_leader \
  --teleop.port=$LEADER_PORT
```

**Follower**
```bash
lerobot-setup-motors \
  --robot.type=so101_follower \
  --robot.port=$FOLLOWER_PORT
```

**進め方（1個ずつ）**
1. 画面に表示された関節名を読み上げる（操作担当）
2. 対応するモーター **1個だけ** をモーターバスにつなぐ（組み立て担当）
3. Enter を押す → `motor id set to <ID>` と出たら成功
4. ラベルに「L-1」「F-3」のように Leader / Follower と ID を書いて貼る

### 2-3. 組み立て

- [公式の組み立て手順](https://huggingface.co/docs/lerobot/so101)の動画を見ながら進める
- **ネジ**：外装パーツをサーボホーンに固定するのは大きいネジ、モーターをフレームに固定するのは小さいネジ
- **サーボホーン**：突起側ではなく**平らな面を外側**に
- **手首カメラのマウント**：Follower の手首にこのタイミングで付ける
- ラベルどおりの関節に付けているか、1つ付けるごとに確認

### 2-4. キャリブレーション

`id` はアームを識別する名前です。**2人で決めた名前に統一**してください（ここでは `team_follower` / `team_leader`）。

**Follower**
```bash
lerobot-calibrate \
  --robot.type=so101_follower \
  --robot.port=$FOLLOWER_PORT \
  --robot.id=team_follower
```

**Leader**
```bash
lerobot-calibrate \
  --teleop.type=so101_leader \
  --teleop.port=$LEADER_PORT \
  --teleop.id=team_leader
```

- 画面の指示に従い、中間の姿勢にしてから各関節を可動範囲いっぱいまで**ゆっくり**動かす
- 無理に押し込むと基準位置がずれるので注意
- 結果は `~/.cache/huggingface/lerobot/calibration/` 以下に保存される

### チェックリスト
- [ ] `.env` に両方のポートが書いてある
- [ ] 12個すべてのモーターに ID とラベルがある
- [ ] 組み立てが終わり、手首カメラが付いている
- [ ] Follower・Leader 両方のキャリブレーションが終わった

---

## 段階 3：テレオペで動作確認

**担当：** 2人で
**目的：** アーム側の準備が終わったことを確認し、操作に慣れる

```bash
source .env
lerobot-teleoperate \
  --robot.type=so101_follower \
  --robot.port=$FOLLOWER_PORT \
  --robot.id=team_follower \
  --teleop.type=so101_leader \
  --teleop.port=$LEADER_PORT \
  --teleop.id=team_leader
```

- 最初は**小さくゆっくり**動かし、Follower の周りに物や手がないことを確認
- 2人とも一度 Leader を操作して、つかむ・運ぶ・離すを練習する

### 動きがおかしいとき

| 症状 | 疑うこと |
|---|---|
| 特定の関節が別の関節の動きをする | モーター ID の取り違え（特に gripper と wrist_roll） |
| 角度がずれる・可動域が狭い | キャリブレーションのやり直し |
| ガタつく・引っかかる | サーボホーンの向き、ネジの締め忘れ |

### チェックリスト
- [ ] Leader の全関節の動きに Follower が正しく追従する
- [ ] 2人とも操作を試した

---

## 段階 4：作業スペース・カメラ・Hugging Face の準備

**担当：** 2人で
**目的：** 録り始めた後に一切変えなくて済む環境を作る

> **ここで決めた配置は、本番の記録と、学習後の自律動作まで変えません。**
> 途中で変えると、それまでに録ったデータが使えなくなります。

### 4-1. 作業スペース

- [ ] アームを板にクランプで固定する
- [ ] 俯瞰カメラ（C920n）のスタンドを**同じ板**にクランプで固定する
- [ ] 左右の箱の位置を決め、輪郭をテープで貼る（例：左＝赤、右＝青）
- [ ] キューブを置く範囲（約20cm四方）をテープで囲み、3×3の9か所に番号付きの印を付ける
  ```
  ┌───┬───┬───┐
  │ 1 │ 2 │ 3 │   ← 奥
  ├───┼───┼───┤
  │ 4 │ 5 │ 6 │
  ├───┼───┼───┤
  │ 7 │ 8 │ 9 │   ← 手前
  └───┴───┴───┘
  ```
- [ ] アームを最大まで伸ばし、9か所すべてと両方の箱に届くことを確認する
- [ ] 囲いと LED ライトで照明を固定し、カーテンを閉める
- [ ] 机の上には、キューブと箱以外を置かない

### 4-2. カメラ番号の確認

1. Mac のカメラ許可を出す：システム設定 → プライバシーとセキュリティ → カメラ で、ターミナル（または VS Code）を許可
2. iPhone の連係カメラをオフにしておく（番号が増えて混乱するため）
3. 実行する
   ```bash
   lerobot-find-cameras opencv
   ```
4. 保存された画像を開き、**どの番号が俯瞰で、どの番号が手首か**を確認する（保存先はコマンドの出力に表示されます）
5. `.env` に追記する
   ```bash
   export TOP_CAM=0
   export WRIST_CAM=1
   ```

> カメラ番号も抜き差しや再起動で変わります。**録る日は毎回最初に確認**してください。

### 4-3. カメラ付きテレオペで映り方を確認

```bash
source .env
lerobot-teleoperate \
  --robot.type=so101_follower \
  --robot.port=$FOLLOWER_PORT \
  --robot.id=team_follower \
  --robot.cameras="{ top: {type: opencv, index_or_path: $TOP_CAM, width: 640, height: 480, fps: 30}, wrist: {type: opencv, index_or_path: $WRIST_CAM, width: 640, height: 480, fps: 30}}" \
  --teleop.type=so101_leader \
  --teleop.port=$LEADER_PORT \
  --teleop.id=team_leader \
  --display_data=true
```

**確認ポイント**
- [ ] 俯瞰：9か所の枠と両方の箱が画面に収まっている
- [ ] 俯瞰：アームを伸ばしても画面からはみ出さない
- [ ] 手首：キューブに近づいたとき、キューブとグリッパーの先端が映る
- [ ] 色：赤と青がはっきり見分けられる（白飛び・暗すぎがない）
- [ ] 俯瞰カメラのピントが、アームの映り込みで大きく変わらない

> カメラ名 `top` と `wrist` は、**記録・学習・自律動作のすべてで同じ名前**を使います。

### 4-4. Hugging Face の準備

1. 2人ともアカウントを作る
2. チーム用の Organization を作り、2人ともメンバーにする
3. 設定画面で **Write 権限のアクセストークン**を作る
4. アームをつなぐ Mac でログインする
   ```bash
   hf auth login
   ```
   （古いバージョンでは `huggingface-cli login`）
5. `.env` に追記する
   ```bash
   export HF_USER=<チームのOrganization名>
   ```

### 完成した `.env` の例

```bash
export LEADER_PORT=/dev/tty.usbmodemXXXXXXXXXXX
export FOLLOWER_PORT=/dev/tty.usbmodemYYYYYYYYYYY
export TOP_CAM=0
export WRIST_CAM=1
export HF_USER=your-team-name
```

---

## 段階 5：試しに10エピソード録る

**担当：** 2人で（操作係・配置係）
**目的：** 記録 → アップロード → 確認の流れを一度通し、本番で詰まらないようにする

### 5-1. 記録する

「赤いキューブを1個つかむ」だけの簡単なタスクで録ります。

```bash
source .env
lerobot-record \
  --robot.type=so101_follower \
  --robot.port=$FOLLOWER_PORT \
  --robot.id=team_follower \
  --robot.cameras="{ top: {type: opencv, index_or_path: $TOP_CAM, width: 640, height: 480, fps: 30}, wrist: {type: opencv, index_or_path: $WRIST_CAM, width: 640, height: 480, fps: 30}}" \
  --teleop.type=so101_leader \
  --teleop.port=$LEADER_PORT \
  --teleop.id=team_leader \
  --display_data=true \
  --dataset.repo_id=${HF_USER}/test_grab_cube \
  --dataset.single_task="Grab the red cube" \
  --dataset.num_episodes=10 \
  --dataset.episode_time_s=20 \
  --dataset.reset_time_s=10
```

### 5-2. 記録中の流れ

「**20秒の記録 → 10秒のリセット**」が10回繰り返されます。

| タイミング | 操作係 | 配置係 |
|---|---|---|
| 記録中（20秒） | Leader でキューブをつかむ | 失敗したら声をかける |
| リセット中（10秒） | アームを待機姿勢に戻す | キューブを次の印の位置に置き直す |

### 5-3. キーボード操作

| キー | 動作 |
|---|---|
| → | 今のエピソードを早めに終えて次へ |
| ← | 今のエピソードをやり直す（失敗したとき） |
| Esc | 記録を終了してアップロード |

> Mac でキーが反応しない場合は、システム設定 → プライバシーとセキュリティ の「アクセシビリティ」「入力監視」でターミナルを許可してください。

### 5-4. 確認する

- [ ] Hugging Face のチームのページに `test_grab_cube` ができている
- [ ] データセットのビューアで、俯瞰・手首の両方の映像が再生できる
- [ ] 関節角度の値が時間とともに変化している
- [ ] エピソード数が10ある

### 困ったとき

- **途中で止まった**：同じコマンドに `--resume=true` を付けて再実行すると続きから録れる
- **映像が真っ黒**：カメラ許可、カメラ番号を再確認
- **映像が止まる・コマ落ちする**：カメラを USB ハブから外し、Mac 本体の別ポートにつなぐ

---

## 段階 6：本番の2色仕分けを録る

**担当：** 2人で（操作係・配置係、10エピソードごとに交代）
**目的：** 学習に使う質の揃ったお手本を50エピソード集める

### 6-1. 録る前に決めること

#### (1) 録る順番表

赤25・青25を、9か所の印にほぼ均等に割り振り、**ランダムな順**に並べた表を作ります。
下のスクリプトで作れます（実機を使わないので、もう1人が先に作っておく）。

```python
# scripts/make_order.py
import csv
import random

random.seed(0)  # 同じ表を再現できるように固定
positions = list(range(1, 10))

rows = []
for color in ["red", "blue"]:
    # 25回を9か所に均等に近く割り振る
    pos_list = (positions * 3)[:25]
    rows += [(color, p) for p in pos_list]

random.shuffle(rows)

with open("order.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["episode", "color", "position", "result", "memo"])
    for i, (c, p) in enumerate(rows):
        w.writerow([i, c, p, "", ""])

print("order.csv を作成しました")
```

```bash
python scripts/make_order.py
```

`order.csv` を印刷するか画面に出し、録りながら `result` 欄に成否、`memo` 欄に気づいたことを書きます。

#### (2) 動かし方のルール

- [ ] **開始と終了**：毎回同じ待機姿勢から始め、箱に入れたら待機姿勢に戻して終える
- [ ] **つかみ方**：キューブの真上からまっすぐ下ろしてつかむ
- [ ] **運び方**：持ち上げてから箱の真上へ移動し、下ろしてから離す
- [ ] **速さ**：急がない。毎回同じくらいのペースで動かす
- [ ] **失敗の扱い**：落とした・箱を外した・迷って止まった場合は ← でやり直す（失敗は混ぜない）

#### (3) 役割

| 役割 | やること |
|---|---|
| 操作係 | Leader を操作する。上のルールを守る |
| 配置係 | 順番表を読み上げ、リセット中にキューブを指定の色・位置に置く。失敗を判定して ← を押す。表に記録する |

10エピソードごとに役割を交代し、休憩を入れます。疲れると動きが雑になり、データの質が落ちます。

### 6-2. 記録する

段階5のコマンドから、データセット名・タスク文・エピソード数を変えます。
仕分けは運ぶ距離があるので、記録時間を少し長めにしています。

```bash
source .env
lerobot-record \
  --robot.type=so101_follower \
  --robot.port=$FOLLOWER_PORT \
  --robot.id=team_follower \
  --robot.cameras="{ top: {type: opencv, index_or_path: $TOP_CAM, width: 640, height: 480, fps: 30}, wrist: {type: opencv, index_or_path: $WRIST_CAM, width: 640, height: 480, fps: 30}}" \
  --teleop.type=so101_leader \
  --teleop.port=$LEADER_PORT \
  --teleop.id=team_leader \
  --display_data=true \
  --dataset.repo_id=${HF_USER}/cube_sort_red_blue_v1 \
  --dataset.single_task="Put the cube in the box of the same color." \
  --dataset.num_episodes=50 \
  --dataset.episode_time_s=30 \
  --dataset.reset_time_s=15
```

- 動作が早く終わったら → で次へ進めてよい
- 途中で止めた場合は `--resume=true` を付けて再開

### 6-3. 記録後の確認

- [ ] エピソード数が50ある
- [ ] 順番表で、赤と青がそれぞれ25回ずつ成功として記録されている
- [ ] ビューアで数エピソードを見て、映像・関節角度が正常
- [ ] 失敗エピソードが混ざっていない（混ざっていたら番号をメモしておく）

### 目安時間

- 1エピソード：記録30秒＋リセット15秒 ≒ 45秒
- 50エピソード：約40分〜1時間（慣れないうちは倍を見込む）

---

## 次にやること

1. `cube_sort_red_blue_v1` を使って ACT を学習させる（研究室の GPU マシンまたは Google Colab）
2. 学習済みモデルで自律動作させ、赤・青それぞれ10回ずつ成功率を測る
3. 成功率が低ければ、デモの追加（例：各色+25回）や、動かし方のルールを見直して撮り直す

---

## 付録：毎回の記録日の開始チェック

- [ ] `conda activate lerobot`
- [ ] 両アームの電源・USB を接続
- [ ] `lerobot-find-port` でポートが `.env` と一致しているか確認
- [ ] `lerobot-find-cameras opencv` でカメラ番号が `.env` と一致しているか確認
- [ ] 照明をつけ、カーテンを閉めた
- [ ] 箱・カメラ・アームの位置がテープの印からずれていない
- [ ] `source .env`
