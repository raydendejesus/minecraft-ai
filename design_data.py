"""Circuit design lessons: given what a circuit must do, work out the logic for it.

    design 0110100110010110   > (a xor b) xor (c xor d)

The request is a truth table over inputs a, b, c, d (16 outputs, abcd = 0000 first). The answer can
be any expression that produces that table, so it's scored by evaluating it, not by comparing text.

There are 65,536 possible tables. Every tenth one is locked away and never used in training
(is_exam), so the exam can only be passed by actually working out new designs.

The lessons come from a search for the shortest expression for every table (fewest two-input gates,
with NOT free), cached in design_table.bin after the first run.
"""

import os
import random
import struct

import numpy as np

import data

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "design_table.bin")
VARS = {"a": 0x00FF, "b": 0x0F0F, "c": 0x3333, "d": 0x5555}      # output bit 15 - row number
MASK = 0xFFFF
OPS = ("and", "or", "xor")
_table = None


def is_exam(f):
    """Locked-away goals: never trained on, used only by the exam. A scrambled pick, so that they
    aren't a pattern like 'every table ending in 0'."""
    return (f * 2654435761 >> 8) % 10 == 0


def build_table():
    """Shortest formula for every function, found level by level. Stored as a back-pointer per
    function: op (0 literal, 1-3 and/or/xor, 4 not), left, right."""
    op = np.full(65536, 255, dtype=np.uint8)
    left = np.zeros(65536, dtype=np.uint16)
    right = np.zeros(65536, dtype=np.uint16)
    levels = []
    first = []
    for i, name in enumerate(VARS):
        f = VARS[name]
        op[f], left[f] = 0, i
        first.append(f)
        g = (~f) & MASK
        op[g], left[g] = 4, f
        first.append(g)
    levels.append(np.array(first, dtype=np.int64))
    k = 0
    while (op == 255).any() and k < 12:
        k += 1
        found = []
        for i in range((k + 1) // 2):
            j = k - 1 - i
            A, B = levels[i], levels[j]
            for code, name in enumerate(OPS, 1):
                for start in range(0, len(A), 256):
                    a = A[start:start + 256]
                    aa = np.repeat(a, len(B))
                    bb = np.tile(B, len(a))
                    out = aa & bb if name == "and" else aa | bb if name == "or" else aa ^ bb
                    uniq, idx = np.unique(out, return_index=True)
                    new = op[uniq] == 255
                    uniq, idx = uniq[new], idx[new]
                    op[uniq] = code
                    left[uniq] = aa[idx]
                    right[uniq] = bb[idx]
                    found.append(uniq)
                    comp = (~uniq) & MASK
                    free = op[comp] == 255
                    comp, src = comp[free], uniq[free]
                    op[comp] = 4
                    left[comp] = src
                    found.append(comp)
        levels.append(np.unique(np.concatenate(found)) if found else np.array([], dtype=np.int64))
        print(f"  {k} gates: {len(levels[-1])} new, {(op != 255).sum()} of 65536 found", flush=True)
    return op, left, right


def table():
    global _table
    if _table is None:
        if os.path.exists(CACHE):
            raw = np.fromfile(CACHE, dtype=np.uint16).reshape(3, 65536)
            _table = (raw[0].astype(np.uint8), raw[1], raw[2])
        else:
            op, left, right = build_table()
            np.stack([op.astype(np.uint16), left, right]).tofile(CACHE)
            _table = (op, left, right)
    return _table


def formula(f):
    """Text for the shortest expression of function f."""
    op, left, right = table()
    code = int(op[f])
    if code == 0:
        return "abcd"[int(left[f])]
    if code == 4:
        inner = formula(int(left[f]))
        return f"not {inner}"
    return f"({formula(int(left[f]))} {OPS[code - 1]} {formula(int(right[f]))})"


def clean(text):
    return text[1:-1] if text.startswith("(") and text.endswith(")") and _balanced(text[1:-1]) else text


def _balanced(t):
    depth = 0
    for ch in t:
        depth += ch == "("
        depth -= ch == ")"
        if depth < 0:
            return False
    return depth == 0


def to_bits(f):
    return format(f, "016b")


def request(f):
    return f"design {to_bits(f)}"


def answer(f):
    return "# " + clean(formula(f))


def works(req, text):
    """Does this expression really produce the requested table? Any valid design counts."""
    want = req.split()[1]
    expr = text.strip().lstrip("#").strip()
    try:
        got = ""
        for row in range(16):
            env = {"a": bool(row & 8), "b": bool(row & 4), "c": bool(row & 2), "d": bool(row & 1)}
            got += str(int(data.eval_logic(expr, env)))
    except (KeyError, IndexError, TypeError, ValueError):
        return False
    return got == want


def gates(text):
    return sum(text.split().count(op) for op in OPS)


def random_function(exam=False):
    while True:
        f = random.randrange(65536)
        if is_exam(f) == exam:
            return f
