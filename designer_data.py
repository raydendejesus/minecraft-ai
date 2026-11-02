"""Lessons for the bigger model: everything the Builder knows, plus designing circuits.

The training log scores it on locked-away design goals only, and a design counts when it works,
so that number shows real problem solving rather than memory.
"""

import os
import random

os.environ["MCAI_RAM"] = "1"          # RAM sticks are part of its lessons

import data
import design_data as D

EVAL_LIMIT = 160                      # characters allowed for an answer during the training log
DESIGN_SHARE = 0.6
machine_sample = data.machine_sample


def sample(corrections, correction_rate=0.0):
    if random.random() < DESIGN_SHARE:
        f = D.random_function()
        return D.request(f), D.answer(f)
    return data.sample([])


def random_request():
    return D.request(D.random_function(exam=True))


def correct(req, got):
    return D.works(req, got)


def reference(req):
    return D.answer(int(req.split()[1], 2))


def load_corrections():
    return []
