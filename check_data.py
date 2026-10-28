"""Print sample training pairs for the new ops and check the longest example fits."""

import random

import data
from model import DEFAULT_CONFIG

random.seed(3)
for _ in range(4):
    r = f"logic {data.random_expr()} | a=1 b=0 c=1"
    print(r, "=>", data.reference(r))
for _ in range(3):
    r = f"truth {data.random_expr()}"
    print(r, "=>", data.reference(r))
print(data.validate_request("redstone ram_byte"), "|", data.validate_request("logic a xor b | a=1 b=1 c=0"))
print(data.reference("redstone not"))

longest = max(len(data.encode(data.fmt(*data.sample([])))) for _ in range(20000))
print("longest of 20000 samples:", longest, "chars; context is", DEFAULT_CONFIG["ctx"])
