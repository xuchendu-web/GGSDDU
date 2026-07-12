"""
宽基 ETF 对话层 L0 路由原型：实体抽取 + 规则预筛 + 上下文继承。
L1（LLM 意图分类）在生产中仅处理 L0 未命中的输入，本原型输出其组装后的提示词。
设计文档：docs/对话层-宽基意图路由与提示词设计.md
"""

from __future__ import annotations

import dataclasses
import json
import re

INDEX_ALIASES = {
    "沪深300": "000300", "沪深三百": "000300", "hs300": "000300",
    "中证a500": "000510", "a500": "000510",
    "中证500": "000905", "中证1000": "000852",
    "上证50": "000016", "科创50": "000688",
    "创业板指": "399006", "创业板": "399006", "深证100": "399330",
}
# 裸数字仅在指数语境下映射
BARE_NUM_ALIASES = {"300": "000300", "500": "000905", "1000": "000852", "50": "000016"}

INDEX_CONTEXT_WORDS = ("指数", "宽基", "跟踪", "estimate", "估值", "和", "比", "哪个")

PRONOUNS = ("那", "它", "这只", "这个", "呢")


@dataclasses.dataclass
class SessionState:
    current_index: str | None = None
    current_etf: str | None = None
    current_amount: float | None = None
    current_scenario: str = "配置型"
    last_intent: str | None = None
    last_tool_call: dict | None = None


# ---------------- 实体抽取 ----------------

def extract_entities(text: str) -> dict:
    t = text.lower()
    ents: dict = {}

    # 指数别名（长词优先，避免"沪深300"被"300"截胡）
    for alias in sorted(INDEX_ALIASES, key=len, reverse=True):
        if alias in t:
            ents.setdefault("index_codes", []).append(INDEX_ALIASES[alias])
            t = t.replace(alias, " ")
    # 裸数字指数（需指数语境）
    if any(w in text for w in INDEX_CONTEXT_WORDS):
        for num, code in BARE_NUM_ALIASES.items():
            if re.search(rf"(?<![\d.]){num}(?![\d.%])", t):
                if code not in ents.get("index_codes", []):
                    ents.setdefault("index_codes", []).append(code)

    # ETF 代码：6 位，5/1 开头
    for m in re.findall(r"(?<!\d)([15]\d{5})(?!\d)", text):
        ents.setdefault("etf_codes", []).append(m)

    # 金额归一化（元）
    m = re.search(r"(\d+(?:\.\d+)?)\s*(亿|千万|百万|万)", text)
    if m:
        mult = {"亿": 1e8, "千万": 1e7, "百万": 1e6, "万": 1e4}[m.group(2)]
        ents["amount"] = float(m.group(1)) * mult
    else:
        m2 = re.search(r"(\d+)\s*个亿", text)
        if m2:
            ents["amount"] = float(m2.group(1)) * 1e8

    # 阈值表达式（监控）
    m = re.search(r"(pe|pb|分位|折溢价|跟踪误差)[^\d]{0,6}(跌破|低于|超过|高于|突破)\s*(\d+(?:\.\d+)?)\s*%?",
                  t)
    if m:
        direction = "below" if m.group(2) in ("跌破", "低于") else "above"
        ents["threshold"] = {"indicator": m.group(1), "direction": direction,
                             "value": float(m.group(3))}

    # 历史时点
    m = re.search(r"(20\d{2})\s*年\s*(\d{1,2})\s*月", text)
    if m:
        ents["time_point"] = f"{m.group(1)}-{int(m.group(2)):02d}"

    # 比例（组合增配）
    m = re.search(r"加\s*(\d+(?:\.\d+)?)\s*%", text)
    if m:
        ents["add_pct"] = float(m.group(1))

    return ents


# ---------------- 规则预筛 ----------------

PREFILTER_RULES: list[tuple[str, str]] = [
    (r"为什么|怎么算|依据是|凭什么|规则是", "drilldown"),
    (r"提醒|监控|告警|订阅|通知我", "monitor_setup"),
    (r"改成|换成.{0,8}再算|重新算", "param_update"),
    (r"生成.{0,6}报告|导出|pdf|投委会材料", "report_generate"),
    (r"消息|新闻|动态|公告|最近有什么|政策", "news_query"),
    (r"20\d{2}\s*年.{0,6}(比|对比|那波|行情)", "history_compare"),
    (r"选哪|哪只|哪个产品|费率最低|推荐一只|比选", "product_select"),
    (r"组合|持仓|重叠", "portfolio_impact"),
    (r"分批|建仓|冲击成本|买\s*\d|买.{0,4}亿", "execution_calc"),
    (r"会不会涨|会涨吗|跌到|涨到|目标位|预测|下周|下个月.{0,4}(涨|跌)", "out_of_scope"),
    (r"贵不贵|什么位置|估值|分位|时机|性价比", "timing_query"),
    (r"(和|跟|与).{1,12}(比|对比|哪个)", "index_compare"),
    (r"看看|分析|怎么样|如何", "index_analysis"),
]

NON_KUANJI_HINTS = ("半导体", "芯片", "医药", "白酒", "红利", "债券", "黄金", "纳指", "恒生科技")


def route(text: str, session: SessionState) -> dict:
    """L0 路由：返回 {intent, confidence, slots, context_used, next} 。
    next = "execute"（直接执行）| "llm_router"（转 L1）| "clarify"。"""
    ents = extract_entities(text)
    slots: dict = {}
    context_used = False

    # 品类边界：非宽基品种 → out_of_scope（提示转对应模块）
    if any(h in text for h in NON_KUANJI_HINTS):
        return {"intent": "out_of_scope", "confidence": 0.95, "slots": {},
                "context_used": False, "next": "execute",
                "note": "非宽基品种，提示切换至对应品类模块"}

    # 意图预筛
    intent = None
    for pattern, name in PREFILTER_RULES:
        if re.search(pattern, text.lower()):
            intent = name
            break

    # 槽位装配
    idx = ents.get("index_codes", [])
    if idx:
        slots["index_code"] = idx[0]
        if len(idx) > 1:
            slots["compare_target"] = idx[1]
    if ents.get("etf_codes"):
        slots["etf_code"] = ents["etf_codes"][0]
    for k in ("amount", "threshold", "time_point", "add_pct"):
        if k in ents:
            slots[k] = ents[k]

    # 上下文继承：短句/指代/无实体
    is_short_ref = (len(text) <= 12 and any(p in text for p in PRONOUNS))
    if intent is None and is_short_ref and session.last_intent:
        intent = session.last_intent
        context_used = True
    if intent == "index_compare" and "compare_target" not in slots and \
            session.current_index and slots.get("index_code") \
            and slots["index_code"] != session.current_index:
        slots["compare_target"] = slots["index_code"]
        slots["index_code"] = session.current_index
        context_used = True
    if "index_code" not in slots and session.current_index and \
            intent not in ("out_of_scope", None):
        slots["index_code"] = session.current_index
        context_used = True
    if intent == "execution_calc" and "etf_code" not in slots and session.current_etf:
        slots["etf_code"] = session.current_etf
        context_used = True

    if intent is None:
        return {"intent": "unknown", "confidence": 0.0, "slots": slots,
                "context_used": context_used, "next": "llm_router"}

    # 必要槽位检查
    required = {"index_analysis": ["index_code"], "timing_query": ["index_code"],
                "index_compare": ["index_code", "compare_target"],
                "product_select": ["index_code"], "execution_calc": ["amount"],
                "monitor_setup": ["index_code"], "history_compare": ["index_code", "time_point"],
                }.get(intent, [])
    missing = [r for r in required if r not in slots]
    if missing:
        return {"intent": intent, "confidence": 0.85, "slots": slots,
                "context_used": context_used, "next": "clarify",
                "clarify_question": f"请补充：{missing[0]}"}

    return {"intent": intent, "confidence": 0.9, "slots": slots,
            "context_used": context_used, "next": "execute"}


def update_session(session: SessionState, decision: dict) -> None:
    slots = decision["slots"]
    if slots.get("index_code"):
        session.current_index = slots["index_code"]
    if slots.get("etf_code"):
        session.current_etf = slots["etf_code"]
    if slots.get("amount"):
        session.current_amount = slots["amount"]
    if decision["intent"] not in ("unknown", "clarify", "out_of_scope", "drilldown"):
        session.last_intent = decision["intent"]


if __name__ == "__main__":
    session = SessionState()
    dialogue = [
        "帮我看看沪深300",
        "现在贵不贵",
        "和A500比呢",
        "跟踪300的ETF哪只费率最低",
        "买5个亿需要分批吗",
        "改成20亿再算",
        "我们组合加5%的510300会怎样",
        "为什么说流动性好",
        "沪深300最近有什么调样消息",
        "和2024年9月那波比怎么样",
        "PE分位跌破25%时提醒我",
        "生成完整报告",
        "下周会涨吗",
        "那科创50呢",
        "半导体ETF怎么样",
    ]
    for text in dialogue:
        d = route(text, session)
        update_session(session, d)
        slots_str = json.dumps(d["slots"], ensure_ascii=False)
        ctx = "↩ctx" if d["context_used"] else "    "
        print(f"{d['intent']:<18} {d['next']:<10} {ctx} {slots_str:<80} ← {text}")
