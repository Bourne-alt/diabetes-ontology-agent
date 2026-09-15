import argparse
import asyncio
import json
import os

from .logs import setup_logging
from .runtime import AgentHarness, build_agent
from .settings import AgentSettings


def main():
    parser = argparse.ArgumentParser(description="糖尿病本体证据 Agent")
    parser.add_argument("message", nargs="?")
    parser.add_argument("--serve", action="store_true", help="启动本地网页及 SSE API")
    parser.add_argument("--port", type=int, default=8200)
    parser.add_argument("--json", action="store_true", help="输出完整 NDJSON 事件")
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别（默认 INFO，或 .env 的 AGENT_LOG_LEVEL）。排查问题用 DEBUG。",
    )
    parser.add_argument("--log-file", help="同时写入该文件，10MB×5 轮转。")
    parser.add_argument(
        "--log-payload",
        action="store_true",
        help="日志中记录工具参数与返回内容。⚠️ 含患者数据，仅限本地排查。",
    )
    args = parser.parse_args()
    # 命令行优先于 .env。日志走 stderr，不干扰 stdout 上的事件流（--json 可直接管道给 jq）。
    if args.log_level:
        os.environ["AGENT_LOG_LEVEL"] = args.log_level
    if args.log_file:
        os.environ["AGENT_LOG_FILE"] = args.log_file
    if args.log_payload:
        os.environ["AGENT_LOG_PAYLOAD"] = "1"
    setup_logging(force=True)
    if args.serve:
        import uvicorn

        uvicorn.run("agent.api:app", host="127.0.0.1", port=args.port)
        return
    if not args.message:
        parser.error("提供查询内容，或使用 --serve")

    async def run():
        settings = AgentSettings.load()
        harness = AgentHarness(build_agent(settings), settings)
        failed = False
        async for event in harness.stream(args.message):
            if args.json:
                print(json.dumps(event, ensure_ascii=False, default=str), flush=True)
            elif event["type"] == "text_delta":
                print(event["text"], end="", flush=True)
            elif event["type"] in ("tool_start", "tool_end", "todo_update", "error", "model_start"):
                print("\n" + json.dumps(event, ensure_ascii=False, default=str), flush=True)
            elif event["type"] == "answer":
                print("\n\n" + event["text"], flush=True)
            if event["type"] == "done":
                failed = event["status"] == "failed"
        return 1 if failed else 0

    try:
        raise SystemExit(asyncio.run(run()))
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
