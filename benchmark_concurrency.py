#!/usr/bin/env python3
"""
MiniMax LLM 并发负载测试
测试指标：QPS、Throughput、并发延迟分布

配置来源：
- config.py: API密钥、模型、测试参数
- prompts.py: 测试提示词列表（20种）
"""

import os
import time
import json
import random
import asyncio
import statistics
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from openai import OpenAI
except ImportError:
    print("请先安装依赖: pip install openai")
    exit(1)

# 导入配置
from config import (
    MINIMAX_API_KEY, MODEL, BASE_URL,
    TEST_MODE, NUM_REQUESTS, CONCURRENCY,
    DURATION_SEC, TARGET_QPS
)
from prompts import PROMPTS


@dataclass
class ConcurrencyMetrics:
    """并发测试指标"""
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_duration_sec: float
    qps: float                    # Queries Per Second
    token_throughput: float       # Tokens per second
    request_throughput: float     # Requests per second
    latencies_ms: List[float] = field(default_factory=list)
    ttfts_ms: List[float] = field(default_factory=list)
    tpots_ms: List[float] = field(default_factory=list)
    token_counts: List[int] = field(default_factory=list)  # 每个请求的token数


class MiniMaxConcurrencyBenchmark:
    def __init__(self, api_key: str = MINIMAX_API_KEY, base_url: str = BASE_URL):
        self.api_key = api_key
        if not self.api_key or self.api_key == "your-api-key-here":
            raise ValueError("请设置全局变量 MINIMAX_API_KEY 或环境变量")

        self.base_url = base_url

    def get_random_prompt(self) -> str:
        """随机选择一个prompt"""
        return random.choice(PROMPTS)

    def create_client(self) -> OpenAI:
        """创建新的客户端实例（线程安全）"""
        return OpenAI(api_key=self.api_key, base_url=self.base_url)

    def single_request(self, model: str, request_id: int) -> Optional[Dict]:
        """
        执行单个请求并返回结果（每次使用随机prompt）
        """
        client = self.create_client()
        prompt = self.get_random_prompt()
        messages = [{"role": "user", "content": prompt}]

        start_time = time.perf_counter()
        first_token_time = None
        output_chunks = []
        total_output_tokens = 0

        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7,
                stream=True,
                stream_options={"include_usage": True}
            )

            for chunk in response:
                current_time = time.perf_counter()

                # 从usage中获取准确的token数
                if chunk.usage and chunk.usage.completion_tokens:
                    total_output_tokens = chunk.usage.completion_tokens

                if first_token_time is None and chunk.choices and chunk.choices[0].delta.content:
                    first_token_time = current_time

                if chunk.choices and chunk.choices[0].delta.content:
                    output_chunks.append(chunk.choices[0].delta.content)

            end_time = time.perf_counter()

            # 计算token数
            if total_output_tokens == 0:
                # 粗略估算
                import re
                output_text = "".join(output_chunks)
                chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', output_text))
                other_chars = len(output_text) - chinese_chars
                total_output_tokens = chinese_chars + other_chars // 4
                if total_output_tokens == 0:
                    total_output_tokens = len(output_chunks)

            latency_ms = (end_time - start_time) * 1000
            ttft_ms = (first_token_time - start_time) * 1000 if first_token_time else None

            # 计算 TPOT (排除首token)
            decoding_time_ms = latency_ms - ttft_ms if ttft_ms else latency_ms
            if total_output_tokens > 1:
                tpot_ms = decoding_time_ms / (total_output_tokens - 1)
            else:
                tpot_ms = 0

            tps = total_output_tokens / (latency_ms / 1000) if latency_ms > 0 else 0

            return {
                "request_id": request_id,
                "latency_ms": latency_ms,
                "ttft_ms": ttft_ms,
                "tpot_ms": round(tpot_ms, 1),
                "tokens": total_output_tokens,
                "tps": round(tps, 1),
                "success": True
            }

        except Exception as e:
            return {
                "request_id": request_id,
                "error": str(e),
                "success": False
            }

    def run_concurrent_test(
        self,
        model: str = MODEL,
        num_requests: int = NUM_REQUESTS,
        concurrency: int = CONCURRENCY
    ) -> ConcurrencyMetrics:
        """
        运行并发测试
        """
        print(f"\n{'='*60}")
        print(f"并发负载测试")
        print(f"{'='*60}")
        print(f"模型: {model}")
        print(f"总请求数: {num_requests}")
        print(f"并发数: {concurrency}")
        print(f"Prompt池: {len(PROMPTS)} 种")
        print(f"{'='*60}\n")

        results = []
        success_count = 0
        failed_count = 0

        start_time = time.perf_counter()

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            # 提交所有任务
            future_to_id = {
                executor.submit(self.single_request, model, i): i
                for i in range(num_requests)
            }

            # 处理完成的任务
            completed = 0
            for future in as_completed(future_to_id):
                request_id = future_to_id[future]
                try:
                    result = future.result()
                    results.append(result)
                    completed += 1

                    if result.get("success"):
                        success_count += 1
                        tokens = result.get('tokens', 0)
                        ttft = result.get('ttft_ms', 0)
                        tpot = result.get('tpot_ms', 0)
                        latency = result.get('latency_ms', 0)
                        tps = result.get('tps', 0)
                        from datetime import datetime
                        current_time = datetime.now().strftime('%H:%M:%S')
                        print(f"[{completed:3d}/{num_requests}] {current_time} 成功 - Tokens: {tokens:4d} | TTFT: {ttft:6.0f}ms | TPOT: {tpot:5.1f}ms | TPS: {tps:5.1f}", flush=True)
                    else:
                        failed_count += 1
                        print(f"[{completed:3d}/{num_requests}] 失败 - {result.get('error', '未知错误')[:50]}", flush=True)

                except Exception as e:
                    failed_count += 1
                    print(f"请求 {request_id} 异常: {e}")

        end_time = time.perf_counter()
        total_duration = end_time - start_time

        # 计算指标
        successful_results = [r for r in results if r.get("success")]
        latencies = [r["latency_ms"] for r in successful_results]
        ttfts = [r["ttft_ms"] for r in successful_results if r.get("ttft_ms")]
        tpots = [r["tpot_ms"] for r in successful_results if r.get("tpot_ms")]
        token_counts = [r["tokens"] for r in successful_results]
        total_tokens = sum(token_counts)

        metrics = ConcurrencyMetrics(
            total_requests=num_requests,
            successful_requests=success_count,
            failed_requests=failed_count,
            total_duration_sec=round(total_duration, 2),
            qps=round(success_count / total_duration, 2) if total_duration > 0 else 0,
            token_throughput=round(total_tokens / total_duration, 2) if total_duration > 0 else 0,
            request_throughput=round(success_count / total_duration, 2) if total_duration > 0 else 0,
            latencies_ms=latencies,
            ttfts_ms=ttfts,
            tpots_ms=tpots,
            token_counts=token_counts
        )

        return metrics

    def run_load_test(
        self,
        model: str = MODEL,
        duration_sec: int = DURATION_SEC,
        target_qps: float = TARGET_QPS
    ) -> ConcurrencyMetrics:
        """
        运行负载测试（固定速率发送请求）
        """
        print(f"\n{'='*60}")
        print(f"负载测试 (固定速率)")
        print(f"{'='*60}")
        print(f"模型: {model}")
        print(f"测试时长: {duration_sec}秒")
        print(f"目标QPS: {target_qps}")
        print(f"Prompt池: {len(PROMPTS)} 种")
        print(f"{'='*60}\n")

        results = []
        success_count = 0
        failed_count = 0

        start_time = time.perf_counter()
        interval = 1.0 / target_qps
        next_request_time = start_time

        while time.perf_counter() - start_time < duration_sec:
            current_time = time.perf_counter()

            if current_time >= next_request_time:
                # 发送请求
                result = self.single_request(model, len(results))
                results.append(result)

                if result.get("success"):
                    success_count += 1
                else:
                    failed_count += 1

                next_request_time = current_time + interval

            # 短暂休眠避免CPU占用过高
            time.sleep(0.001)

        end_time = time.perf_counter()
        total_duration = end_time - start_time

        # 计算指标
        successful_results = [r for r in results if r.get("success")]
        latencies = [r["latency_ms"] for r in successful_results]
        ttfts = [r["ttft_ms"] for r in successful_results if r.get("ttft_ms")]
        tpots = [r["tpot_ms"] for r in successful_results if r.get("tpot_ms")]
        token_counts = [r["tokens"] for r in successful_results]
        total_tokens = sum(token_counts)

        metrics = ConcurrencyMetrics(
            total_requests=len(results),
            successful_requests=success_count,
            failed_requests=failed_count,
            total_duration_sec=round(total_duration, 2),
            qps=round(success_count / total_duration, 2) if total_duration > 0 else 0,
            token_throughput=round(total_tokens / total_duration, 2) if total_duration > 0 else 0,
            request_throughput=round(success_count / total_duration, 2) if total_duration > 0 else 0,
            latencies_ms=latencies,
            ttfts_ms=ttfts,
            tpots_ms=tpots,
            token_counts=token_counts
        )

        return metrics

    def print_report(self, metrics: ConcurrencyMetrics, test_type: str = "并发测试"):
        """
        打印测试报告
        """
        print(f"\n{'='*60}")
        print(f"{test_type}报告")
        print(f"{'='*60}")
        print(f"\n总请求数: {metrics.total_requests}")
        print(f"成功: {metrics.successful_requests}")
        print(f"失败: {metrics.failed_requests}")
        print(f"成功率: {metrics.successful_requests/metrics.total_requests*100:.1f}%")
        print(f"\n总耗时: {metrics.total_duration_sec:.2f}秒")
        print(f"\n【吞吐量指标】")
        print(f"  QPS (Queries Per Second): {metrics.qps}")
        print(f"  Token Throughput: {metrics.token_throughput} tokens/s")
        print(f"  Request Throughput: {metrics.request_throughput} req/s")

        if metrics.latencies_ms:
            latencies = sorted(metrics.latencies_ms)
            print(f"\n【延迟分布 (ms)】")
            print(f"  P50 (中位数): {statistics.median(latencies):.1f}")
            print(f"  P90: {latencies[int(len(latencies)*0.9)]:.1f}" if len(latencies) >= 10 else "  P90: N/A")
            print(f"  P99: {latencies[int(len(latencies)*0.99)]:.1f}" if len(latencies) >= 100 else "  P99: N/A")
            print(f"  平均: {statistics.mean(latencies):.1f}")
            print(f"  最小: {min(latencies):.1f}")
            print(f"  最大: {max(latencies):.1f}")

        if metrics.ttfts_ms:
            print(f"\n【TTFT分布 (ms)】")
            print(f"  平均: {statistics.mean(metrics.ttfts_ms):.1f}")
            print(f"  中位数: {statistics.median(metrics.ttfts_ms):.1f}")

        if metrics.tpots_ms:
            print(f"\n【TPOT分布 (ms/token)】")
            print(f"  平均: {statistics.mean(metrics.tpots_ms):.1f}")
            print(f"  中位数: {statistics.median(metrics.tpots_ms):.1f}")
            print(f"  最小: {min(metrics.tpots_ms):.1f}")
            print(f"  最大: {max(metrics.tpots_ms):.1f}")

        # 计算每个请求的 TPS
        if metrics.token_counts and metrics.latencies_ms:
            tps_list = [tokens / (latency_ms / 1000) for tokens, latency_ms in zip(metrics.token_counts, metrics.latencies_ms) if latency_ms > 0]
            if tps_list:
                print(f"\n【TPS (Tokens Per Second)】")
                print(f"  平均: {statistics.mean(tps_list):.1f}")
                print(f"  中位数: {statistics.median(tps_list):.1f}")
                print(f"  最小: {min(tps_list):.1f}")
                print(f"  最大: {max(tps_list):.1f}")

        # 保存结果
        output_file = f"log/benchmark_concurrency_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "test_type": test_type,
                "metrics": {
                    "total_requests": metrics.total_requests,
                    "successful_requests": metrics.successful_requests,
                    "failed_requests": metrics.failed_requests,
                    "total_duration_sec": metrics.total_duration_sec,
                    "qps": metrics.qps,
                    "token_throughput": metrics.token_throughput,
                    "request_throughput": metrics.request_throughput,
                    "latency_p50": statistics.median(metrics.latencies_ms) if metrics.latencies_ms else None,
                    "latency_p90": sorted(metrics.latencies_ms)[int(len(metrics.latencies_ms)*0.9)] if len(metrics.latencies_ms) >= 10 else None,
                    "latency_p99": sorted(metrics.latencies_ms)[int(len(metrics.latencies_ms)*0.99)] if len(metrics.latencies_ms) >= 100 else None,
                    "latency_mean": statistics.mean(metrics.latencies_ms) if metrics.latencies_ms else None,
                    "latency_min": min(metrics.latencies_ms) if metrics.latencies_ms else None,
                    "latency_max": max(metrics.latencies_ms) if metrics.latencies_ms else None,
                    "ttft_mean": statistics.mean(metrics.ttfts_ms) if metrics.ttfts_ms else None,
                    "tpot_mean": statistics.mean(metrics.tpots_ms) if metrics.tpots_ms else None,
                    "tps_mean": statistics.mean(tps_list) if 'tps_list' in locals() and tps_list else None,
                    "tps_median": statistics.median(tps_list) if 'tps_list' in locals() and tps_list else None,
                    "avg_tokens_per_request": statistics.mean(metrics.token_counts) if metrics.token_counts else None
                },
                "raw_latencies": metrics.latencies_ms,
                "tpots_ms": metrics.tpots_ms,
                "token_counts": metrics.token_counts,
                "timestamp": datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)
        print(f"\n结果已保存到: {output_file}")


def main():
    benchmark = MiniMaxConcurrencyBenchmark()

    if TEST_MODE == "concurrent":
        metrics = benchmark.run_concurrent_test()
        benchmark.print_report(metrics, "并发测试")
    elif TEST_MODE == "load":
        metrics = benchmark.run_load_test()
        benchmark.print_report(metrics, "负载测试")
    else:
        print(f"错误的 TEST_MODE: {TEST_MODE}, 请使用 'concurrent' 或 'load'")


if __name__ == "__main__":
    main()
