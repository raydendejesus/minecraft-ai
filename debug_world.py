import world_sim as W

w = W.World(seed=523453)
a = W.Agent(w)
x, y, z = a.pos
print("feet", a.pos, "below:", W.NAMES[w.get(x, y - 1, z)])
gy = y - 12
for limit in (2000, 10000, 40000):
    path, cost = a.path_to(lambda p: p[1] <= gy, lambda p: 1.5 * abs(p[1] - gy), limit=limit)
    print(limit, "->", None if path is None else (len(path), round(cost, 1), path[-1]))
