"""
〇×ゲームの進行役。置いたマスを記録し、ロボットの手は自動で決める。
置く作業はどちらの手もロボットがやる（そのマス用のモデルで rollout_erase.py を実行する）。

コマンド:
  python game.py new --first robot     新しい対戦を始める（--first human で人が先手）
  python game.py human 22              人の手。人の色のキューブをマス22（真ん中）にロボットが置く
  python game.py robot                 ロボットの手。最善のマスを決めて、ロボットの色のキューブを置く
  python game.py show                  今の盤面と手の履歴を表示
  python game.py undo                  最後の1手を取り消す（記録だけ。盤面のキューブは手でどける）

human / robot に付けられるもの:
  --no_run    rollout せず記録だけする（手で置いたとき・失敗して手で直したとき）
  --dry_run   実行する rollout のコマンドを表示するだけ（記録もしない）

マスの名前（行・列の2桁。左上が 11。モデル名の cell11〜cell33 と同じ）:
  11 12 13
  21 22 23
  31 32 33

記録:
  game_state.json : 今の対戦の盤面（3×3 の行列。1=ロボット -1=人 0=空）と手の履歴
  game_log.csv    : 全対戦の表（1手1行。row / col は 1 始まり）。決着した手の result に win / lose / draw（ロボットから見て）

マスごとのモデルとタスク文、rollout の共通の引数は game_config.json に書く。
"""

import argparse
import csv
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime

from tictactoe_core import (
    HUMAN, ROBOT, best_move, cell_name, cell_to_rc, format_board, is_full, is_over, new_board, parse_cell, winner,
)

HERE = os.path.dirname(os.path.abspath(__file__))
PLAYERS = {"robot": ROBOT, "human": HUMAN}
NAMES = {ROBOT: "robot", HUMAN: "human"}
LOG_FIELDS = ["game_id", "move_no", "player", "cell", "row", "col", "time", "result"]


# ---------------------------------------------------------------------------
# 記録の読み書き
# ---------------------------------------------------------------------------
def load_state(path):
    if not os.path.exists(path):
        raise SystemExit("対戦が始まっていません。先に python game.py new --first robot（または human）を実行してください。")
    with open(path) as f:
        return json.load(f)


def save_state(path, state):
    with open(path, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def append_log(path, row):
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)


def remove_log(path, game_id, move_no):
    if not os.path.exists(path):
        return
    with open(path, newline="") as f:
        rows = [r for r in csv.DictReader(f) if not (r["game_id"] == game_id and r["move_no"] == str(move_no))]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        w.writeheader()
        w.writerows(rows)


def next_player(state) -> int:
    first = PLAYERS[state["first"]]
    return first if len(state["moves"]) % 2 == 0 else -first


def result_text(board):
    w = winner(board)
    if w == ROBOT:
        return "win"
    if w == HUMAN:
        return "lose"
    return "draw" if is_full(board) else ""


def show(state, cfg):
    marks = {ROBOT: cfg["marks"]["robot"], HUMAN: cfg["marks"]["human"]}
    print(format_board(state["board"], marks))
    res = result_text(state["board"])
    if res:
        print({"win": "ロボットの勝ち", "lose": "人の勝ち", "draw": "引き分け"}[res])
    else:
        print(f"次は {'ロボット' if next_player(state) == ROBOT else '人'} の番")


# ---------------------------------------------------------------------------
# ロボットに置かせる
# ---------------------------------------------------------------------------
def rollout_command(cfg, cell):
    c = cfg["cells"].get(cell_name(cell))
    if c is None:
        return None
    return [sys.executable, "rollout_erase.py", *cfg["rollout_args"],
            f"--policy.path={c['policy']}", f"--task={c['task']}"]


def place(args, state, cfg, player, cell):
    board = state["board"]
    if is_over(board):
        raise SystemExit("この対戦はもう決着しています。python game.py new で新しい対戦を始めてください。")
    if next_player(state) != player:
        raise SystemExit(f"今は {'ロボット' if next_player(state) == ROBOT else '人'} の番です。")
    r, c = cell_to_rc(cell)
    name = cell_name(cell)
    if board[r][c] != 0:
        raise SystemExit(f"マス {name} はもう埋まっています。")

    color = cfg["colors"][NAMES[player]]
    if not args.no_run:
        cmd = rollout_command(cfg, cell)
        if cmd is None:
            raise SystemExit(
                f"マス {name} のモデルが game_config.json にありません。"
                f"手で{color}のキューブをマス {name} に置いてから、--no_run を付けて同じコマンドを実行してください。"
            )
        if args.dry_run:
            print(shlex.join(cmd))
            return
        input(f"ストック置き場に{color}のキューブを置き、アームをホーム位置にして Enter（やめるなら Ctrl+C）")
        ret = subprocess.run(cmd, cwd=HERE).returncode
        if ret != 0:
            print(f"rollout が終了コード {ret} で終わりました。")
        if input(f"マス {name} に置けましたか？ [Y/n] ").strip().lower() in ("n", "no"):
            print("記録していません。もう一度同じコマンドを実行するか、手で直してから --no_run を付けて実行してください。")
            return
    elif args.dry_run:
        print("--no_run なので rollout は実行しません")
        return

    board[r][c] = player
    move_no = len(state["moves"]) + 1
    now = datetime.now().isoformat(timespec="seconds")
    state["moves"].append({"move_no": move_no, "player": NAMES[player], "cell": name, "time": now})
    save_state(args.state, state)
    append_log(args.log, {
        "game_id": state["game_id"], "move_no": move_no, "player": NAMES[player],
        "cell": name, "row": r + 1, "col": c + 1, "time": now, "result": result_text(board),
    })
    print(f"記録しました: {move_no}手目 {NAMES[player]} → マス {name}")
    show(state, cfg)


# ---------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description="〇×ゲームの進行役")
    p.add_argument("--config", default=os.path.join(HERE, "game_config.json"))
    p.add_argument("--state", default=os.path.join(HERE, "game_state.json"))
    p.add_argument("--log", default=os.path.join(HERE, "game_log.csv"))
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("new", help="新しい対戦を始める")
    s.add_argument("--first", choices=PLAYERS, required=True, help="先手（robot / human）")

    for name, help_ in (("human", "人の手を置く"), ("robot", "ロボットの手を決めて置く")):
        s = sub.add_parser(name, help=help_)
        if name == "human":
            s.add_argument("cell", help="置くマス（行・列の2桁。11〜33）")
        s.add_argument("--no_run", action="store_true", help="rollout せず記録だけする")
        s.add_argument("--dry_run", action="store_true", help="実行するコマンドを表示するだけ")

    sub.add_parser("show", help="今の盤面を表示")
    sub.add_parser("undo", help="最後の1手を取り消す")
    args = p.parse_args()

    with open(args.config) as f:
        cfg = json.load(f)

    if args.cmd == "new":
        state = {"game_id": datetime.now().strftime("%Y%m%d_%H%M%S"), "first": args.first,
                 "board": new_board(), "moves": []}
        save_state(args.state, state)
        print(f"新しい対戦を始めました（game_id={state['game_id']}, 先手={args.first}）")
        show(state, cfg)
        return

    state = load_state(args.state)
    if args.cmd == "show":
        for m in state["moves"]:
            print(f"{m['move_no']}手目 {m['player']:5s} → マス {m['cell']}")
        show(state, cfg)
    elif args.cmd == "undo":
        if not state["moves"]:
            raise SystemExit("取り消す手がありません。")
        m = state["moves"].pop()
        r, c = cell_to_rc(parse_cell(m["cell"]))
        state["board"][r][c] = 0
        save_state(args.state, state)
        remove_log(args.log, state["game_id"], m["move_no"])
        print(f"取り消しました: {m['move_no']}手目 {m['player']} → マス {m['cell']}（キューブは手でどけてください）")
        show(state, cfg)
    elif args.cmd == "human":
        try:
            cell = parse_cell(args.cell)
        except ValueError as e:
            raise SystemExit(str(e))
        place(args, state, cfg, HUMAN, cell)
    elif args.cmd == "robot":
        if is_over(state["board"]):
            raise SystemExit("この対戦はもう決着しています。python game.py new で新しい対戦を始めてください。")
        if next_player(state) != ROBOT:
            raise SystemExit("今は人の番です。")
        cell = best_move(state["board"], ROBOT)
        print(f"ロボットの手: マス {cell_name(cell)}")
        place(args, state, cfg, ROBOT, cell)


if __name__ == "__main__":
    main()
