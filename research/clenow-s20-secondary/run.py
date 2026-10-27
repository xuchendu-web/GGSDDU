"""CLENOW-S20-SECONDARY design stub.

Knife #5 of the slope family. This file is not a backtest.
Composer replaces it on the execution branch and writes
``research/clenow-s20-secondary/out/``.

Frozen books (see DESIGN.md and SPEC.json):

- F0     mode=off             SHARPE20, no Clenow key
- CS90S  mode=clenow_sort     N=90, score = (exp(beta*252)-1) * R^2
- CS60S  mode=clenow_sort     N=60, same product
- CS90R  mode=slope_ann_sort  N=90, slope_ann only, R^2 not in the key

Band (same shape as AG40S, different key):

    slots = max_pos - held
    band_k = max(2 * slots, slots + 2)
    band = C_t[:band_k]          # already sharpe_key order
    take = rerank(band)[:slots]  # missing key sorts last; never drop

Do not replace SHARPE20 with Clenow. Do not apply a hard gate.
Do not force-exit a held name because its key worsened.
Do not sweep theta, N, or k. Third book is CS90R, not CS90K2
and not an accel tie-break.
Needle SHA 05f0f8a4f778fde886f3e7b2976646ff4b7d777b.
"""


def main() -> None:
    raise SystemExit(
        "CLENOW-S20-SECONDARY design stub: refuse to backtest. "
        "Implement the four-pack on the execution branch. See DESIGN.md."
    )


if __name__ == "__main__":
    main()
