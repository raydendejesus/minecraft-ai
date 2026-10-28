"""Make sure every design survives compact -> parts exactly, and show lengths."""

import redstone_lib as R

for name in list(R.DESIGNS) + [f"ram{n}" for n in range(1, 9)]:
    parts = R.design_parts("ram", int(name[3:])) if name.startswith("ram") and name[3:].isdigit() \
        else R.design_parts(name)
    text = R.to_compact(parts)
    back = R.from_compact(text)
    same = sorted(set(back)) == sorted(set(parts))
    print(f"{name:11s} parts {len(parts):3d}  chars {len(text):5d}  round-trip {'ok' if same else 'BROKEN'}")
