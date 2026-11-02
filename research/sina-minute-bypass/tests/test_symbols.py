import unittest

from sina_bypass.symbols import market_prefix, sina_symbol, tencent_symbol, to_code


class SymbolTests(unittest.TestCase):
    def test_sh_etf(self):
        self.assertEqual(to_code("510300"), "510300")
        self.assertEqual(sina_symbol("510300"), "sh510300")
        self.assertEqual(tencent_symbol("SH510300"), "sh510300")
        self.assertEqual(market_prefix("511260"), "sh")

    def test_sz_etf(self):
        self.assertEqual(sina_symbol("159915"), "sz159915")
        self.assertEqual(sina_symbol("sz159915"), "sz159915")

    def test_bad(self):
        with self.assertRaises(ValueError):
            to_code("abc")


if __name__ == "__main__":
    unittest.main()
