"""
〇×ゲームの盤面と、ロボットの手を決める処理。

盤面は 3×3 の行列（リストのリスト）で、0 = 空、1 = ロボット、-1 = 人。
マスの名前は「行・列」の2桁（左上 = 1行1列 = "11"）。モデル名の cell11〜cell33 と同じ。

  11 12 13
  21 22 23
  31 32 33

中の処理（探索など）では、左上を 0 として行ごとに 0〜8 の位置で扱う。
人に見せる名前との変換は cell_name / parse_cell で行う。

〇×ゲームには、相手が最善を尽くしても必ず勝てる手順はない（お互い最善なら引き分け）。
best_move は全部の手を最後まで読んで（ミニマックス）、絶対に負けない手のうち、
相手がミスしやすい手を選ぶ。相手がミスしたら必ず勝ちに行く。
このファイルは LeRobot に依存しないので、単体でテストできる。
"""

from __future__ import annotations

from functools import lru_cache

ROBOT = 1
HUMAN = -1
EMPTY = 0

_LINES = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),   # 横
    (0, 3, 6), (1, 4, 7), (2, 5, 8),   # 縦
    (0, 4, 8), (2, 4, 6),              # 斜め
]
# 同じ評価の手が複数あるときの優先順: 中央 → 角 → 辺
_PREFERENCE = [4, 0, 2, 6, 8, 1, 3, 5, 7]


def new_board() -> list[list[int]]:
    return [[EMPTY] * 3 for _ in range(3)]


def cell_to_rc(cell: int) -> tuple[int, int]:
    """位置 0〜8 → 行列の添字 (行, 列)（どちらも 0 始まり）"""
    if not 0 <= cell <= 8:
        raise ValueError(f"位置は 0〜8 にしてください（今は {cell}）")
    return divmod(cell, 3)


def cell_name(cell: int) -> str:
    """位置 0〜8 → マスの名前（"11"〜"33"）"""
    r, c = cell_to_rc(cell)
    return f"{r + 1}{c + 1}"


def parse_cell(name) -> int:
    """マスの名前 "11"〜"33" → 位置 0〜8"""
    s = str(name).strip()
    if len(s) != 2 or s[0] not in "123" or s[1] not in "123":
        raise ValueError(f"マスは 行・列 の2桁（11〜33）で指定してください（今は {name}）")
    return (int(s[0]) - 1) * 3 + int(s[1]) - 1


def _flat(board) -> tuple[int, ...]:
    return tuple(v for row in board for v in row)


def _winner_flat(b: tuple[int, ...]) -> int:
    for i, j, k in _LINES:
        if b[i] != EMPTY and b[i] == b[j] == b[k]:
            return b[i]
    return 0


def winner(board) -> int:
    """揃っていれば ROBOT / HUMAN、揃っていなければ 0"""
    return _winner_flat(_flat(board))


def is_full(board) -> bool:
    return EMPTY not in _flat(board)


def is_over(board) -> bool:
    return winner(board) != 0 or is_full(board)


def legal_moves(board) -> list[int]:
    return [i for i, v in enumerate(_flat(board)) if v == EMPTY]


@lru_cache(maxsize=None)
def _score(b: tuple[int, ...], turn: int) -> int:
    """turn の番の局面を、ROBOT から見た点数で返す（勝ち: 正、負け: 負、引き分け: 0）。
    早く勝つほど・遅く負けるほど点数の絶対値が大きくなる。"""
    w = _winner_flat(b)
    empties = b.count(EMPTY)
    if w != 0:
        return w * (empties + 1)
    if empties == 0:
        return 0
    scores = []
    for i in range(9):
        if b[i] == EMPTY:
            nb = b[:i] + (turn,) + b[i + 1:]
            scores.append(_score(nb, -turn))
    return max(scores) if turn == ROBOT else min(scores)


@lru_cache(maxsize=None)
def _win_rate(b: tuple[int, ...], turn: int, me: int) -> float:
    """相手がでたらめに打ち、me は最善手（その中で勝率が一番高い手）を打つとしたときの me の勝率。
    負けない手が複数あるとき、相手がミスしやすい手を選ぶのに使う。"""
    w = _winner_flat(b)
    if w != 0 or EMPTY not in b:
        return 1.0 if w == me else 0.0
    moves = [i for i in range(9) if b[i] == EMPTY]
    nexts = [b[:i] + (turn,) + b[i + 1:] for i in moves]
    if turn != me:
        return sum(_win_rate(nb, -turn, me) for nb in nexts) / len(nexts)
    scores = [_score(nb, -turn) * me for nb in nexts]
    top = max(scores)
    return max(_win_rate(nb, -turn, me) for nb, s in zip(nexts, scores) if s == top)


def best_move(board, player: int = ROBOT) -> int:
    """player の最善手の位置（0〜8）を返す。
    1. 負けない手（ミニマックスの点数が一番よい手）
    2. その中で、相手がミスしやすい手（相手がでたらめに打ったときの勝率が高い手）
    3. それでも同じなら 中央 → 角 → 辺"""
    b = _flat(board)
    if _winner_flat(b) != 0 or EMPTY not in b:
        raise ValueError("もう決着しているので、置けるマスがありません")
    best, best_key = None, None
    for i in _PREFERENCE:
        if b[i] != EMPTY:
            continue
        nb = b[:i] + (player,) + b[i + 1:]
        s = _score(nb, -player) * player       # player から見た点数
        key = (s, round(_win_rate(nb, -player, player), 6))
        if best_key is None or key > best_key:
            best, best_key = i, key
    return best


def format_board(board, marks: dict[int, str] | None = None) -> str:
    """ターミナル表示用。空のマスにはマスの名前を出す。
    例:
        B | 12 | 13
      ----+----+----
       21 |  P | 23
      ..."""
    marks = marks or {ROBOT: "R", HUMAN: "H"}
    rows = []
    for r in range(3):
        cells = [f"{marks[v]:>2}" if v != EMPTY else cell_name(r * 3 + c) for c, v in enumerate(board[r])]
        rows.append(" " + " | ".join(cells))
    return "\n----+----+----\n".join(rows)
