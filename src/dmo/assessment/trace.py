"""Observable execution data, never an LLM's private reasoning."""

from time import perf_counter


class ExecutionTrace:
    def __init__(self):
        self.started = self.previous = perf_counter()
        self.steps = []

    def record(self, key: str, title: str, summary: str, details=None):
        now = perf_counter()
        self.steps.append({
            "index": len(self.steps) + 1, "key": key, "title": title,
            "status": "completed", "summary": summary,
            "duration_ms": round((now - self.previous) * 1000, 3),
            "elapsed_ms": round((now - self.started) * 1000, 3),
            "details": details or {},
        })
        self.previous = now

    def export(self):
        return {"kind": "execution_record", "presentation": "replay",
                "notice": "记录已执行的程序步骤；播放速度不代表实际计算耗时。规则评估不是机器学习预测。",
                "steps": self.steps}
