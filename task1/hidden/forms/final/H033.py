"""H033 (decimal, usd): stressed token market cap under burn vs emission policy.

The reading, clause by clause:
* stressed price = current price * (1 - per-stage ratio)^3 (stated explicitly).
* burn policy: units = units - burned; price = stressed price * (1 + support
  ratio) ("raises that stressed price once by ratio s").
  burn cap = burn units * burn price.
* emission policy: units = units + emitted; price = stressed price (no support).
  emission cap = emission units * stressed price.
* "Use the burn policy if its resulting market cap is at least FLOOR USD" ->
  burn cap >= FLOOR (inclusive, "at least"); otherwise emission.
Slot one_stage_price_retention_checkpoint: "price-retention ratio after one
stress stage" = 1 - per-stage downside ratio.
"""
from hlib import num, ipow

KEY = "H033"


def solve(b):
    units, price = num(b, "A token has {N} units and a current price of {N} USD")
    d = num(b, "the same ratio {N} is removed from the price surviving")
    burn = num(b, "Under the burn policy, {N} units are removed")
    sup = num(b, "treasury support raises that stressed price once by ratio {N}.")
    emit = num(b, "Under the fallback emission policy, {N} units are added")
    floor_ = num(b, "if its resulting market cap is at least {N} USD")

    retain = 1 - d
    stressed = price * ipow(retain, 3)
    burn_cap = (units - burn) * stressed * (1 + sup)
    emit_cap = (units + emit) * stressed
    final = burn_cap if burn_cap >= floor_ else emit_cap
    return {"final": final,
            "slots": {"one_stage_price_retention_checkpoint": retain},
            "info": {"stressed_price": stressed, "burn_cap": burn_cap,
                     "emission_cap": emit_cap, "floor": floor_}}
