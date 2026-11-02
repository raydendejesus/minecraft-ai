"""How long would the AI's answer be for each machine, with straight runs written once?"""

import redstone_lib as R

MACHINES = {"adder 4": lambda: R.adder(4)[0], "alu 4": lambda: R.alu(4)[0], "counter 4": lambda: R.counter(4)[0],
            "decoder 4": lambda: R.decoder(4)[0], "ram 4 8 (16 bytes)": lambda: R.ram(4, 8)[0],
            "ram 7 8 (128 bytes)": lambda: R.ram(7, 8)[0]}

for name, build in MACHINES.items():
    parts = build()
    text = R.to_runs(parts)
    print(f"{name:22s} {len(parts):6d} parts  {len(R.to_compact(parts)):7d} chars plain  {len(text):7d} chars with runs  "
          f"{text.count(chr(10)) + 1:6d} lines", flush=True)
    back = sorted(set(R.from_runs(text)))
    assert back == sorted(set(parts)), name
print("all round-trip exactly")
