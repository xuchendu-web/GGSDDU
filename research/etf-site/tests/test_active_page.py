#!/usr/bin/env python3
"""主动ETF 栏目：渲染契约，禁止假规模/假代码。"""
import json
import os
import re
import unittest

from jinja2 import Environment, FileSystemLoader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_active():
    with open(os.path.join(ROOT, "data", "active-etf.json"), encoding="utf-8") as fh:
        return json.load(fh)


def render(name, **kw):
    env = Environment(loader=FileSystemLoader(os.path.join(ROOT, "templates")), autoescape=False)
    return env.get_template(name).render(
        base="../" if name != "index.html" else "",
        built="2026-10-26",
        bench="测试基准",
        **kw,
    )


class ActivePageTests(unittest.TestCase):
    def test_eighteen_funds_no_fake_aum(self):
        data = load_active()
        self.assertEqual(len(data["funds"]), 18)
        self.assertEqual(data["kpis"][0]["value"], "18")
        for fund in data["funds"]:
            self.assertNotIn("aum", fund)
            self.assertNotIn("nav", fund)
            self.assertNotIn("listed", fund)
            if fund["trade"] != "待核":
                self.assertRegex(fund["trade"], r"^\d{6}$")
            if fund["sub"] != "待核":
                self.assertRegex(fund["sub"], r"^\d{6}$")

    def test_nav_order_and_sections(self):
        html = render("active.html", active=load_active(), nav_active=True)
        nav = re.search(r'<nav class="primary".*?</nav>', html, re.S).group(0)
        self.assertLess(nav.index("编制"), nav.index("主动ETF"))
        self.assertLess(nav.index("主动ETF"), nav.index("市场"))
        self.assertIn('aria-current="page"', nav)
        for heading in ("制度三卡", "国内 18 只", "四象 + 海外迷你对照", "跟踪", "资料"):
            self.assertIn(heading, html)
        self.assertIn("上市前不做跟踪填数", html)
        self.assertNotIn("TBD", html)
        self.assertNotIn("000000", html)
        self.assertIn("待核", html)
        self.assertEqual(html.count("<tbody>"), 2)
        self.assertGreaterEqual(html.count("<tr>"), 18)

    def test_build_emits_active(self):
        with open(os.path.join(ROOT, "build.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn('page("active.html","active/index.html"', src)
        self.assertIn("data/active-etf.json", src)
        self.assertNotIn("rtun", src.lower())
        self.assertNotIn("13389", src)


if __name__ == "__main__":
    unittest.main()
