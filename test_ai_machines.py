"""The AI builds a big machine: only blocks from the model's own answer get placed and tested.

    python test_ai_machines.py adder 4
    python test_ai_machines.py alu 4
    python test_ai_machines.py counter 4
    python test_ai_machines.py decoder 4

The model's answer is saved in ai_machines/. The test scripts only supply which levers and lamps
to use. If the answer can't be turned into blocks, that counts as a failure.
"""

import os
import sys

import torch

import redstone_lib as R
from data import decode, encode, fmt
from model import HERE, TinyGPT

MODEL = "builder_machines.pt"


def ask_ai(request):
    ck = torch.load(os.path.join(HERE, MODEL), map_location="cuda")
    m = TinyGPT(**ck["config"]).cuda().eval()
    m.load_state_dict(ck["model"])
    ids = encode(fmt(request))
    text = decode(m.generate(ids, max_new=ck["config"]["ctx"] - len(ids) - 1)).strip()
    del m
    torch.cuda.empty_cache()
    return text


def main():
    kind, bits = sys.argv[1], int(sys.argv[2])
    request = f"redstone {kind} {bits}"
    text = ask_ai(request)
    os.makedirs(os.path.join(HERE, "ai_machines"), exist_ok=True)
    with open(os.path.join(HERE, "ai_machines", f"{kind}_{bits}.txt"), "w", encoding="utf-8") as f:
        f.write(text)
    try:
        ai_parts = R.from_runs(text)
    except (ValueError, IndexError, KeyError) as e:
        print(f"AI BUILD {request}: unbuildable answer ({e})", flush=True)
        sys.exit(2)
    designed = getattr(R, kind)(bits)
    print(f"AI wrote {len(ai_parts)} parts ({len(designed[0])} in the lesson)", flush=True)

    def ai_version(*_a, **_k):                 # hand back the AI's blocks, keep only the ports
        return (ai_parts, *designed[1:])

    setattr(R, kind, ai_version)
    sys.argv = [sys.argv[0], str(bits)]
    if kind == "alu":
        import test_alu as t
    elif kind == "adder":
        import test_adder as t
    elif kind == "counter":
        import test_counter as t
    else:
        import test_decoder as t
    t.main()


if __name__ == "__main__":
    main()
