"""Keep only circuit lessons in the standard layout (gaps 6 and 4).

    python standard_layout_only.py

The teacher used to spread a circuit out when its router got stuck, and nothing in the formula
says when that happens, so the AI saw two layouts for big circuits with no way to tell which
(1 in 7 of the 6- and 7-gate lessons). Those lessons move to *_with_wide.jsonl copies; nothing
is deleted. Run once; circuit.lesson() only writes the standard layout from now on.
"""

import json
import os
import shutil

import circuit as C

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = ("circuit_lessons.jsonl", "circuit_corrections.jsonl")


def standard_heads(expr):
    """The gate and lamp headers of the standard layout, without routing a single wire."""
    real = C.NetRouter.route_net
    C.NetRouter.route_net = lambda self, net, goal: []
    try:
        C.circuit(expr)
    finally:
        C.NetRouter.route_net = real
    return [h for h, _, _ in C.PIECES if not h.startswith("# wire")]


def is_standard(req, out):
    heads = [line for line in out.splitlines() if line.startswith("#") and not line.startswith("# wire")]
    return heads == standard_heads(req.split(" ", 2)[2])


def main():
    for name in FILES:
        path = os.path.join(HERE, name)
        if not os.path.exists(path):
            continue
        rows = [json.loads(line) for line in open(path, encoding="utf-8")]
        keep = [r for r in rows if is_standard(*r)]
        backup = path.replace(".jsonl", "_with_wide.jsonl")
        if not os.path.exists(backup):
            shutil.copy(path, backup)
        with open(path + ".tmp", "w", encoding="utf-8") as f:
            for r in keep:
                f.write(json.dumps(r) + "\n")
        os.replace(path + ".tmp", path)
        print(f"{name}: kept {len(keep)}/{len(rows)} (all of them in {os.path.basename(backup)})")


if __name__ == "__main__":
    main()
