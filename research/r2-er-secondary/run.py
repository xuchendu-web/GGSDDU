"""R2-ER-SECONDARY design stub.

Knife #4 of the slope family. This file is not a backtest.
Composer replaces it on the execution branch and writes
``research/r2-er-secondary/out/``.

Frozen books (see DESIGN.md and SPEC.json):

- F0      mode=off         SHARPE20, no path key
- R290S   mode=r2_sort     OLS R^2(N=90) descending inside the S20 band
- ER20S   mode=er_sort     Kaufman ER(N=20) descending inside the S20 band
- COMBOS  mode=combo_sort  0.5*z(R^2)+0.5*z(ER) inside the same band

Band (same shape as AG40S, different key):

    slots = max_pos - held
    band_k = max(2 * slots, slots + 2)
    band = C_t[:band_k]          # already sharpe_key order
    take = rerank(band)[:slots]  # missing key sorts last; never drop

Do not apply R^2 >= 0.50, ER >= 0.40, or accel > 0.
Do not replace SHARPE20 with Clenow, R^2, or ER.
Do not force-exit a held name because its key worsened.
Do not sweep theta or N. Third book is COMBOS, not an accel tie-break.
Needle SHA 05f0f8a4f778fde886f3e7b2976646ff4b7d777b.
"""


def main() -> None:
    raise SystemExit(
        "R2-ER-SECONDARY design stub: refuse to backtest. "
        "Implement the four-pack on the execution branch. See DESIGN.md."
    )


if __name__ == "__main__":
    main()
