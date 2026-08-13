#!/usr/bin/env python3
"""
AlphaPai Research CLI
=====================
Alpha派投研 API 命令行工具（统一入口）。

基础能力（config / hello）与各功能模块（qa / recall / agent 等）分别位于
独立文件中，便于后续扩展新功能：

  alphapai_base.py   — 配置、HTTP 客户端、公共工具
  cmd_config.py      — API Key 配置
  cmd_hello.py       — 健康检查
  cmd_qa.py          — 投研知识问答
  cmd_recall.py      — 投研知识检索
  cmd_agent.py       — 投研 Agent
  cmd_report.py      — 股票公告列表
  cmd_watchlist.py   — 自选股列表
  cmd_image.py       — 搜图表
  cmd_bluebook.py    — 蓝宝书
  cmd_hot_topics.py  — 机构热议
  cmd_brokerage_commentary.py — 点评（brokerage commentary）
  cmd_meeting_booking.py — 预约会议
  cmd_meeting_minutes.py — 会议纪要
  cmd_announcement.py — 公告
  cmd_research_report.py — 研报

模块用法（供其他脚本导入）：
  from alphapai_base import AlphaPaiClient, load_config
  from cmd_qa import qa_text
  client = AlphaPaiClient(load_config())
  result = qa_text(client, "问题")
"""

import argparse
import sys

import cmd_agent
import cmd_announcement
import cmd_bluebook
import cmd_config
import cmd_hello
import cmd_hot_topics
import cmd_image
import cmd_meeting_booking
import cmd_meeting_minutes
import cmd_qa
import cmd_recall
import cmd_recording_summary
import cmd_report
import cmd_research_report
import cmd_brokerage_commentary
import cmd_social
import cmd_watchlist

COMMANDS = {
    "config": cmd_config,
    "hello": cmd_hello,
    "qa": cmd_qa,
    "recall": cmd_recall,
    "agent": cmd_agent,
    "report": cmd_report,
    "watchlist": cmd_watchlist,
    "image": cmd_image,
    "social": cmd_social,
    "recording": cmd_recording_summary,
    "bluebook": cmd_bluebook,
    "hot-topics": cmd_hot_topics,
    "brokerage-commentary": cmd_brokerage_commentary,
    "meeting-booking": cmd_meeting_booking,
    "meeting-minutes": cmd_meeting_minutes,
    "announcement": cmd_announcement,
    "research-report": cmd_research_report,
}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        prog="alphapai_client.py",
        description="AlphaPai Research CLI — Alpha派投研API命令行工具",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for mod in COMMANDS.values():
        mod.register_parser(sub)

    args = parser.parse_args()
    command = "brokerage-commentary" if args.command == "review" else args.command
    COMMANDS[command].run(args)


if __name__ == "__main__":
    main()
