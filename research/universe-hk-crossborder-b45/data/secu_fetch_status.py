#!/usr/bin/env python3
import json

from secu_fetch_lib import CODES_TARGET, MIN_ROWS_TARGET, count_rows_in_csv, load_universe


def main() -> None:
    hk, full = load_universe()
    counts = count_rows_in_csv()
    ok = sum(1 for c in set(hk + full) if counts.get(c, 0) >= MIN_ROWS_TARGET)
    print(
        json.dumps(
            {
                "nav_rows": sum(counts.values()),
                "nav_codes": len(counts),
                "codes_ge_200": ok,
                "target_codes": CODES_TARGET,
                "hk_ge_200": sum(1 for c in hk if counts.get(c, 0) >= MIN_ROWS_TARGET),
                "hk_total": len(hk),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
