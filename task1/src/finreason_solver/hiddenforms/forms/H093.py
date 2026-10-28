"""H093 (decimal, ratio): engagement ratio that reaches a target sentiment score.

The reading, clause by clause:
* news contribution = news weight * average news polarity * influence factor
  ("equals W multiplied by average news polarity p and influence factor f").
* tweet contribution = tweet weight * average tweet polarity * engagement ratio.
* total = news + tweet = target  =>  engagement = (target - news) /
  (tweet weight * tweet polarity).
Slot news_score_checkpoint: "the weighted news contribution" = W * p * f.
"""
from hlib import num

KEY = "H093"


def solve(b):
    target = num(b, "must reach a total score of {N}.")
    wn, pn, inf = num(b, "Its news contribution equals {N} multiplied by average news polarity {N} and influence factor {N}.")
    wt, pt = num(b, "Its tweet contribution equals {N} multiplied by average tweet polarity {N} and an unknown engagement ratio")

    news = wn * pn * inf
    eng = (target - news) / (wt * pt)
    return {"final": eng,
            "slots": {"news_score_checkpoint": news},
            "info": {"tweet_contribution": target - news}}
