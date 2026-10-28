"""H026 (enum): tweet/news/market sentiment aggregate classification.

The reading, clause by clause:
  raw tweet = tweet count coefficient * signed tweet average polarity
  per-stage retention = 1 - u; final retention = (1 - u)^n with n the stated
      number of stages (the text writes "(1-u)^3" and "exactly three"; the
      exponent is read from "(1-u)^{N}").
  retained tweet = raw tweet * (1 - u)^n
  news = news coefficient * signed news polarity * influence factor
  aggregate = retained tweet + news + market signal (signed, added as is)
  Bullish when aggregate >= upper ("at least", inclusive);
  Bearish when aggregate <= -lower ("at most the negative of L", inclusive);
  Neutral otherwise.  The two arms cannot both hold since the upper threshold
  is positive and the lower one negative in the text; Bullish is tested first
  in the stated order.
Slot tweet_retention_factor_checkpoint ("signed-signal retention factor after
one stage") = 1 - u.
"""
from hlib import num, first_true, ipow

KEY = "H026"


def solve(b):
    t_n, t_pol = num(b, "The raw tweet signal is {N} times signed average polarity {N}.")
    u = num(b, "the same ratio u={N} of the surviving signed signal is removed")
    n = num(b, "the final retention factor is (1-u)^{N}.")
    if "exactly three sequential moderation stages" in b and n != 3:
        raise ValueError("stage count in words disagrees with the exponent")
    n_n, n_pol, infl = num(b, "The news contribution is {N} times signed average polarity {N} times influence factor {N}.")
    mkt = num(b, "separate signed dimensionless market signal {N}.")
    up, lo = num(b, "Bullish when it is at least {N}, Bearish when it is at most the negative of {N}, and Neutral otherwise")
    keep1 = 1 - u
    raw = t_n * t_pol
    retained = raw * ipow(keep1, n)
    news = n_n * n_pol * infl
    agg = retained + news + mkt
    label = first_true([(agg >= up, "Bullish"), (agg <= -lo, "Bearish")], otherwise="Neutral")
    return {"final": label,
            "slots": {"tweet_retention_factor_checkpoint": keep1},
            "info": {"raw_tweet": raw, "retained_tweet": retained, "news": news,
                     "market": mkt, "aggregate": agg, "bull_at_least": up,
                     "bear_at_most": -lo, "margin_to_bull": agg - up,
                     "margin_to_bear": agg + lo}}
