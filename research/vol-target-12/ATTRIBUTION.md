## 归因（VT12 − FACE）

- **选股 selection**：持仓路径冻结，残差计入 `attribution_yearly.selection`（应≈0）。
- **择时 timing**：未杠杆组合日收益 × (L_VT12 − L_FACE) 按年汇总。
- **成本 cost**：换手差异导致的额外 0.2%RT（`cst_vt12 − cst_face`）。
- **按标的/年**：`attribution_by_name_year.csv` 为各次持仓段毛收益（未分 L）。
