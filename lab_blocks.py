"""Check which block names this Bedrock version accepts. Usage: python lab_blocks.py name1 name2 ..."""

import sys

from lab import Lab

with Lab() as lab:
    for i, name in enumerate(sys.argv[1:]):
        out = " ".join(lab.cmd(f"setblock {i % 30} 102 {2 + 2 * (i // 30)} {name}", wait=0.4))
        print(f"{'OK ' if 'Block placed' in out else 'BAD'} {name:28s} {'' if 'Block placed' in out else out[-90:]}")
