"""Ask the model for every machine and report how much of each it wrote correctly.

    python check_machines.py builder_machines.pt
"""

import os
import sys

import torch

import data
from data import decode, encode, fmt
from model import HERE, TinyGPT

path = sys.argv[1] if len(sys.argv) > 1 else "builder_machines.pt"
ck = torch.load(os.path.join(HERE, path), map_location="cuda")
m = TinyGPT(**ck["config"]).cuda().eval()
m.load_state_dict(ck["model"])
good = 0
for req in data.MACHINE_REQUESTS:
    want = data.reference(req)
    got = decode(m.generate(encode(fmt(req)), max_new=len(want) + 20)).strip()
    same = next((i for i, (a, b) in enumerate(zip(got, want)) if a != b), min(len(got), len(want)))
    ok = got == want.strip()
    good += ok
    print(f"  {req:22s} {len(want):5d} chars  {'EXACT' if ok else f'wrong from character {same}'}", flush=True)
print(f"{good}/{len(data.MACHINE_REQUESTS)} machines exact")
