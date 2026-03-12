#!/usr/bin/env python3
"""
MiniMax LLM 单请求性能测试
测试指标：TTFT、TPOT、Latency、TPS

配置来源：
- config.py: API密钥、模型、测试参数、API风格
- prompts.py: 测试提示词列表（20种）
"""

import os
import time
import json
import random
import statistics
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

# 导入配置和客户端
from config import MINIMAX_API_KEY, MODEL, BASE_URL, API_STYLE, NUM_REQUESTS, WARMUP_REQUESTS
from prompts import PROMPTS
from api_client import APIClient


@dataclass
class RequestMetrics:
    """单次请求的性能指标"""
    ttft_ms: float          # Time to First Token (ms)
    tpot_ms: float          # Time Per Output Token (ms)
    latency_ms: float       # 端到端延迟 (ms)
    tps: float              # Tokens Per Second
    input_tokens: int
    output_tokens: int
    total_tokens: int
    timestamp: str


class MiniMaxBenchmark:
    def __init__(self, api_key: str = MINIMAX_API_KEY, base_url: str = BASE_URL, style: str = API_STYLE):
        self.api_key = api_key
        if not self.api_key or self.api_key == "your-api-key-here":
            raise ValueError("请设置全局变量 MINIMAX_API_KEY 或环境变量")

        self.client = APIClient(
            api_key=api_key,
            base_url=base_url,
            style=style,
            model=MODEL
        )
        self.style = style

    def measure_request(
        self,
        model: str,
        prompt: str,
        temperature: float = 0.7
    ) -> RequestMetrics:
        """
        测量单次请求的各项性能指标
        """
        # 记录各个时间点
        start_time = time.perf_counter()
        first_token_time = None
        token_times = []
        output_chunks = []

        try:
            # 流式请求以精确测量 TTFT
            for chunk in self.client.chat_stream(prompt):
                current_time = time.perf_counter()

                # 记录首token时间
                if first_token_time is None and chunk.is_first and chunk.content:
                    first_token_time = current_time

                # 记录每个chunk的时间和内容
                if chunk.content:
                    token_times.append(current_time)
                    output_chunks.append(chunk.content)

            end_time = time.perf_counter()

            # 计算指标
            latency_ms = (end_time - start_time) * 1000
            ttft_ms = (first_token_time - start_time) * 1000 if first_token_time else latency_ms

            output_text = "".join(output_chunks)

            # 计算输出token数：按字符估算（API不统一返回usage）
            # 中文字符约1-2个token，英文约4字符/token
            import re
            chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', output_text))
            other_chars = len(output_text) - chinese_chars
            output_tokens = chinese_chars + other_chars // 4
            if output_tokens == 0:
                output_tokens = len(output_chunks)

            input_tokens = len(prompt.split())  # 粗略估算

            # 计算 TPOT (排除首token)
            if len(token_times) > 1:
                tpot_ms = (token_times[-1] - token_times[0]) * 1000 / (len(token_times) - 1)
            else:
                tpot_ms = 0

            # 计算 TPS = 总token数 / 总时间
            total_time_sec = end_time - start_time
            tps = output_tokens / total_time_sec if total_time_sec > 0 else 0

            return RequestMetrics(
                ttft_ms=round(ttft_ms, 2),
                tpot_ms=round(tpot_ms, 2),
                latency_ms=round(latency_ms, 2),
                tps=round(tps, 2),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            print(f"请求失败: {e}")
            raise

    def get_random_prompt(self) -> str:
        """随机选择一个prompt"""
        return random.choice(PROMPTS)

    def run_benchmark(
        self,
        model: str = MODEL,
        num_requests: int = NUM_REQUESTS,
        warmup: int = WARMUP_REQUESTS
    ) -> List[RequestMetrics]:
        """
        运行基准测试（每次使用随机prompt）
        """
        print(f"\n{'='*60}")
        print(f"模型: {model}")
        print(f"API风格: {self.style}")
        print(f"测试次数: {num_requests} (预热: {warmup})")
        print(f"Prompt池: {len(PROMPTS)} 种")
        print(f"{'='*60}\n")

        # 预热
        if warmup > 0:
            print("预热中...")
            for i in range(warmup):
                try:
                    prompt = self.get_random_prompt()
                    self.measure_request(model, prompt)
                    print(f"  预热 {i+1}/{warmup} 完成")
                except Exception as e:
                    print(f"  预热 {i+1}/{warmup} 失败: {e}")
            print()

        # 正式测试
        results = []
        for i in range(num_requests):
            try:
                prompt = self.get_random_prompt()
                metric = self.measure_request(model, prompt)
                results.append(metric)
                print(f"请求 {i+1}/{num_requests}: "
                      f"TTFT={metric.ttft_ms:.0f}ms, "
                      f"TPOT={metric.tpot_ms:.2f}ms, "
                      f"Latency={metric.latency_ms:.0f}ms, "
                      f"Tokens={metric.output_tokens}, "
                      f"TPS={metric.tps:.1f}")
            except Exception as e:
                print(f"请求 {i+1}/{num_requests} 失败: {e}")

        return results

    def analyze_results(self, results: List[RequestMetrics]) -> dict:
        """
        统计分析结果
        """
        if not results:
            return {}

        def stats(values: List[float]) -> dict:
            return {
                "mean": round(statistics.mean(values), 2),
                "median": round(statistics.median(values), 2),
                "min": round(min(values), 2),
                "max": round(max(values), 2),
                "p90": round(sorted(values)[int(len(values)*0.9)], 2) if len(values) >= 10 else None,
                "stdev": round(statistics.stdev(values), 2) if len(values) > 1 else 0
            }

        return {
            "ttft_ms": stats([r.ttft_ms for r in results]),
            "tpot_ms": stats([r.tpot_ms for r in results]),
            "latency_ms": stats([r.latency_ms for r in results]),
            "tps": stats([r.tps for r in results]),
            "output_tokens": stats([r.output_tokens for r in results])
        }

    def print_report(self, results: List[RequestMetrics]):
        """
        打印测试报告
        """
        if not results:
            print("\n没有有效的测试结果")
            return

        analysis = self.analyze_results(results)

        print(f"\n{'='*60}")
        print("性能测试报告")
        print(f"{'='*60}")
        print(f"\n总请求数: {len(results)}")

        for metric_name, stats in analysis.items():
            if metric_name == "output_tokens":
                continue
            print(f"\n【{metric_name}】")
            print(f"  平均值: {stats['mean']}")
            print(f"  中位数: {stats['median']}")
            print(f"  最小值: {stats['min']}")
            print(f"  最大值: {stats['max']}")
            if stats['p90']:
                print(f"  P90:    {stats['p90']}")
            print(f"  标准差: {stats['stdev']}")

        # 保存结果
        output_file = f"log/benchmark_single_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "metrics": [vars(r) for r in results],
                "analysis": analysis,
                "timestamp": datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)
        print(f"\n结果已保存到: {output_file}")


def main():
    # 创建测试实例
    benchmark = MiniMaxBenchmark()

    # 运行测试（使用全局变量配置）
    results = benchmark.run_benchmark()

    # 打印报告
    benchmark.print_report(results)


if __name__ == "__main__":
    main()
