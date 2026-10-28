"""Run one example of every Builder op on the lab server and report any command Bedrock rejects."""

import data
from lab import Lab

EXAMPLES = [
    "tower stone_bricks 4 6", "cylinder quartz_block 3 4", "pyramid sandstone 9", "bridge spruce_planks 8 x",
    "castle_wall cobblestone 9 4 z", "windows oak_planks 10 4 x", "fence_ring oak_fence 7 5", "farm 9 7",
    "lamp_post oak_fence 4", "house cobblestone oak_planks spruce_planks 7 4 7 south",
    "gable spruce_planks 9 9", "roof brick_block 7 7", "frame oak_log 7 4 7", "stairs stone 5",
]

with Lab() as lab:
    bad = 0
    for i, req in enumerate(EXAMPLES):
        ox = (i % 4) * 18
        oz = (i // 4) * 18
        lab.cmd(f"fill {ox} 101 {oz} {ox + 16} 112 {oz + 16} air", wait=0.1)
        errors = []
        for cmd in data.reference(req).splitlines():
            out = " ".join(lab.cmd(f"execute positioned {ox} 101 {oz} run {cmd}", wait=0.3))
            if "ERROR" in out or "Syntax" in out:
                errors.append(f"{cmd} -> {out[-80:]}")
        bad += bool(errors)
        print(f"{'OK ' if not errors else 'BAD'} {req}")
        for e in errors[:3]:
            print("     ", e)
    print(f"{len(EXAMPLES) - bad}/{len(EXAMPLES)} ops accepted by Bedrock")
