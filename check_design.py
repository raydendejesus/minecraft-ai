"""Build the design table and prove the lessons are right."""

import random
import time

import design_data as D

t = time.time()
D.table()
print(f"table ready in {time.time() - t:.0f}s")
op = D.table()[0]
print("functions with a formula:", int((op != 255).sum()), "of 65536")
exam = sum(D.is_exam(f) for f in range(65536))
print(f"locked away for the exam: {exam} ({exam / 655.36:.1f}%)")
random.seed(1)
bad, sizes = 0, []
for _ in range(4000):
    f = random.randrange(65536)
    if op[f] == 255:
        continue
    a = D.answer(f)
    bad += not D.works(D.request(f), a)
    sizes.append(D.gates(a))
print(f"4000 random lessons: {bad} wrong; gates average {sum(sizes) / len(sizes):.1f}, largest {max(sizes)}, "
      f"longest text {max(len(D.answer(f)) for f in range(0, 65536, 97) if op[f] != 255)} chars")
for f in (0b0110100110010110, 0b0001011101111111, 0b1000000000000001):
    print(" ", D.request(f), ">", D.answer(f))
