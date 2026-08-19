# -*- coding: utf-8 -*-
"""industry-quadrant-monitor · 第三期验收校验台 (_validate_phase3)

分层校验第三期交付物，分两类：

  · 无网络单元校验（--self）：T4b 渲染层静态检查、T5 覆盖率门槛 fail-fast
  · 产物校验（给定报告基名）：T3 三格式产物 + Excel sheet + T4a N3 字符串 symptom
  · 缓存解析（给定报告基名）：T1 从 run.log 提取命中次数与耗时，供两次运行间对比

用法：
  python _validate_phase3.py --self
  python _validate_phase3.py <report_base>          # 例：industry_quadrant_phase3
  python _validate_phase3.py <report_base> --self    # 全部
"""

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

EXPECTED_SHEETS = ["四象限汇总", "行业得分", "改善行业", "PE分位明细", "数据血统"]


def _section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def _ok(name, cond, detail=""):
    mark = "PASS" if cond else "FAIL"
    print("  [{}] {} {}".format(mark, name, ("— " + detail) if detail else ""))
    return cond


# ─────────────────────────────────────────────────────────────
# T3 产物校验
# ─────────────────────────────────────────────────────────────
def check_artifacts(base):
    _section("T3 · 三格式产物（HTML/Excel/PDF）")
    ok = True
    html = Path(base + ".html")
    xlsx = Path(base + ".xlsx")
    pdf = Path(base + ".pdf")
    ok &= _ok("HTML 存在", html.exists(), str(html))
    ok &= _ok("Excel 存在", xlsx.exists(), str(xlsx))
    ok &= _ok("PDF 存在", pdf.exists(), str(pdf))
    if not (html.exists() and xlsx.exists() and pdf.exists()):
        return False

    # PDF 不能只是头部（reportlab 失败会写成空/极小）
    ok &= _ok("PDF 非平凡 (>1KB)", pdf.stat().st_size > 1024,
              "{} bytes".format(pdf.stat().st_size))

    # Excel sheet 完整性
    try:
        import openpyxl
        wb = openpyxl.load_workbook(str(xlsx), read_only=True)
        sheets = wb.sheetnames
        missing = [s for s in EXPECTED_SHEETS if s not in sheets]
        ok &= _ok("Excel 含全部底稿 sheet", not missing,
                  "期望 {} / 实际 {}".format(EXPECTED_SHEETS, sheets))
        wb.close()
    except Exception as e:
        ok &= _ok("Excel 可打开", False, str(e))

    # T4a：N3 修复——hover 不应再出现 "N/A%"
    txt = html.read_text(encoding="utf-8", errors="ignore")
    bad = "N/A%" in txt
    ok &= _ok("N3 · HTML 无 'N/A%' 字符串 symptom", not bad)
    return ok


# ─────────────────────────────────────────────────────────────
# T4b 渲染层静态检查（C3 象限标注）
# ─────────────────────────────────────────────────────────────
def check_render_static():
    _section("T4b · 渲染层静态检查（C3 象限标注）")
    ok = True
    src = (HERE / "render.py").read_text(encoding="utf-8", errors="ignore")
    n_add = src.count("add_annotation")
    ok &= _ok("C3 · 使用逐次 add_annotation（>=4）", n_add >= 4,
              "add_annotation 出现 {} 次".format(n_add))
    # 仅匹配真正的「方法调用」形式（带前导点），避开注释/文档里对旧写法的描述
    bad_call = re.search(r"\.update_layout\(annotations=", src) is not None
    ok &= _ok("C3 · 未使用 fig.update_layout(annotations= ...) 覆盖式合并",
              not bad_call)
    # N-3 标题级别：不应再写死「申万二级」
    ok &= _ok("N-3 · 标题未写死『申万二级』", "申万二级" not in src)
    return ok


# ─────────────────────────────────────────────────────────────
# T5 覆盖率门槛 fail-fast（无网络）
# ─────────────────────────────────────────────────────────────
def check_coverage_gate():
    _section("T5 · 覆盖率门槛 fail-fast（回归：--min-coverage 1.0 → 退出码 4）")
    ok = True
    try:
        import industry_monitor as m
        meta = {"cov_industry": 0.5, "cov_financial": 0.99, "cov_technical": 0.99}
        raised = False
        try:
            m.coverage_gate(meta, 1.0, False)
        except Exception as e:
            raised = True
            ok &= _ok("T5 · cov=0.5 < 1.0 且未 allow-partial → 抛错",
                      "DataError" in type(e).__name__ or "Data" in type(e).__name__,
                      type(e).__name__)
        ok &= _ok("T5 · 不达标时确实拒绝产出", raised)

        # allow-partial 应放行
        meta2 = {"cov_industry": 0.5, "cov_financial": 0.99, "cov_technical": 0.99}
        try:
            m.coverage_gate(meta2, 1.0, True)
            ok &= _ok("T5 · allow-partial 时放行不抛错", True)
        except Exception as e:
            ok &= _ok("T5 · allow-partial 时放行不抛错", False, str(e))
    except Exception as e:
        ok &= _ok("T5 · 导入/执行", False, str(e))
    return ok


# ─────────────────────────────────────────────────────────────
# T1 缓存解析（从 run.log）
# ─────────────────────────────────────────────────────────────
def parse_cache_log(base):
    _section("T1 · 缓存与耗时（来自 {}.run.log）".format(base))
    log = Path(base + ".run.log")
    if not log.exists():
        print("  [SKIP] 找不到日志 {}".format(log))
        return None
    txt = log.read_text(encoding="utf-8", errors="ignore")
    fin_hit = txt.count("财务表缓存命中")
    pettm_hit = txt.count("PETTM 缓存命中")
    m_el = re.search(r"总耗时\s*([\d.]+)\s*秒", txt)
    elapsed = float(m_el.group(1)) if m_el else None
    print("  财务表缓存命中 : {} 次".format(fin_hit))
    print("  PETTM 缓存命中 : {} 次".format(pettm_hit))
    print("  总耗时         : {} 秒".format(elapsed))
    return {"fin_hit": fin_hit, "pettm_hit": pettm_hit, "elapsed": elapsed}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base", nargs="?", default=None, help="报告基名（不含扩展名）")
    ap.add_argument("--self", action="store_true", help="仅跑无网络单元校验")
    args = ap.parse_args()

    overall = True
    if args.self or args.base is None:
        overall &= check_render_static()
        overall &= check_coverage_gate()
    if args.base:
        overall &= check_artifacts(args.base)
        parse_cache_log(args.base)

    _section("结论")
    print("  {}".format("全部通过 ✅" if overall else "存在失败项 ❌"))
    sys.exit(0 if overall else 1)


if __name__ == "__main__":
    main()
