#!/usr/bin/env python3
"""
并发梯度测试脚本
自动测试 2, 3, 4, 5, 10 并发度，汇总结果

配置来源：
- config.py: API密钥、模型、测试参数
"""

import os
import sys
import json
import time
from datetime import datetime

# 导入 benchmark_concurrency 的类
from benchmark_concurrency import MiniMaxConcurrencyBenchmark

# 导入配置
from config import MODEL, BASE_URL, MINIMAX_API_KEY, API_STYLE, CONCURRENCY_LEVELS, REQUESTS_PER_LEVEL


STYLE = API_STYLE  # 使用全局变量


def run_concurrency_test(concurrency: int, requests: int, current: int = 1, total: int = 6) -> dict:
    """运行单个并发度的测试"""
    print(f"\n{'='*60}")
    print(f"[{current}/{total}] 开始测试: 并发度 = {concurrency}")
    print(f"{'='*60}")

    benchmark = MiniMaxConcurrencyBenchmark(
        api_key=MINIMAX_API_KEY,
        base_url=BASE_URL,
        style=API_STYLE
    )

    try:
        metrics = benchmark.run_concurrent_test(
            model=MODEL,
            num_requests=requests,
            concurrency=concurrency
        )

        return {
            "concurrency": concurrency,
            "num_requests": requests,
            "successful_requests": metrics.successful_requests,
            "failed_requests": metrics.failed_requests,
            "success_rate": round(metrics.successful_requests / metrics.total_requests * 100, 1),
            "total_duration_sec": metrics.total_duration_sec,
            "qps": metrics.qps,
            "token_throughput": metrics.token_throughput,
            "request_throughput": metrics.request_throughput,
            "latency_p50": sorted(metrics.latencies_ms)[len(metrics.latencies_ms)//2] if metrics.latencies_ms else None,
            "latency_p90": sorted(metrics.latencies_ms)[int(len(metrics.latencies_ms)*0.9)] if len(metrics.latencies_ms) >= 10 else None,
            "latency_mean": sum(metrics.latencies_ms) / len(metrics.latencies_ms) if metrics.latencies_ms else None,
            "latency_min": min(metrics.latencies_ms) if metrics.latencies_ms else None,
            "latency_max": max(metrics.latencies_ms) if metrics.latencies_ms else None,
            "avg_tokens_per_request": sum(metrics.token_counts) / len(metrics.token_counts) if metrics.token_counts else None,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"测试失败: {e}")
        return {
            "concurrency": concurrency,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


def print_summary(results: list):
    """打印汇总结果"""
    print(f"\n{'='*95}")
    print("并发梯度测试汇总")
    print(f"{'='*95}")
    print(f"\n{'并发度':<8} {'成功率':<10} {'QPS':<10} {'Token吞吐':<12} {'平均Token数':<12} {'P50延迟(ms)':<12} {'P90延迟(ms)':<12}")
    print("-" * 95)

    for r in results:
        if "error" in r:
            print(f"{r['concurrency']:<8} {'失败':<10} {'-':<10} {'-':<12} {'-':<12} {'-':<12} {'-':<12}")
        else:
            p50 = f"{r['latency_p50']:.0f}" if r['latency_p50'] else "-"
            p90 = f"{r['latency_p90']:.0f}" if r['latency_p90'] else "-"
            avg_tokens = f"{r['avg_tokens_per_request']:.0f}" if r.get('avg_tokens_per_request') else "-"
            print(f"{r['concurrency']:<8} {r['success_rate']:<10.1f} {r['qps']:<10.2f} {r['token_throughput']:<12.2f} {avg_tokens:<12} {p50:<12} {p90:<12}")

    print(f"{'='*95}\n")

    # 分析趋势
    valid_results = [r for r in results if "error" not in r]
    if len(valid_results) >= 2:
        print("【趋势分析】")
        # 找QPS峰值
        max_qps_result = max(valid_results, key=lambda x: x['qps'])
        print(f"  QPS峰值: {max_qps_result['qps']:.2f} (并发度={max_qps_result['concurrency']})")

        # 找延迟突增点
        for i in range(1, len(valid_results)):
            prev_p90 = valid_results[i-1].get('latency_p90')
            curr_p90 = valid_results[i].get('latency_p90')
            if prev_p90 and curr_p90 and curr_p90 > prev_p90 * 1.5:
                print(f"  延迟突增: 并发度从 {valid_results[i-1]['concurrency']} 到 {valid_results[i]['concurrency']}, P90延迟从 {prev_p90:.0f}ms 增至 {curr_p90:.0f}ms")
                break

    print()


def main():
    total_tests = len(CONCURRENCY_LEVELS)
    total_requests = total_tests * REQUESTS_PER_LEVEL

    print(f"=" * 60)
    print(f"并发梯度测试")
    print(f"=" * 60)
    print(f"模型: {MODEL}")
    print(f"API风格: {API_STYLE}")
    print(f"API地址: {BASE_URL}")
    print(f"测试并发度: {CONCURRENCY_LEVELS}")
    print(f"每轮请求数: {REQUESTS_PER_LEVEL}")
    print(f"总请求数: {total_requests}")
    print(f"=" * 60)

    all_results = []
    completed_requests = 0

    for idx, concurrency in enumerate(CONCURRENCY_LEVELS, 1):
        print(f"\n[\u603b体进度 {completed_requests}/{total_requests}] 开始测试并发度 {concurrency}")

        result = run_concurrency_test(concurrency, REQUESTS_PER_LEVEL, idx, len(CONCURRENCY_LEVELS))
        all_results.append(result)

        completed_requests += REQUESTS_PER_LEVEL

        # 短暂休息，避免对API造成过大压力
        if concurrency != CONCURRENCY_LEVELS[-1]:
            print(f"\n[休息 3 秒...]")
            time.sleep(3)

    # 打印汇总
    print_summary(all_results)

    # 保存完整结果
    output_file = f"log/concurrency_gradient_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "model": MODEL,
            "concurrency_levels": CONCURRENCY_LEVELS,
            "requests_per_level": REQUESTS_PER_LEVEL,
            "results": all_results,
            "timestamp": datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)

    print(f"完整结果已保存: {output_file}")


if __name__ == "__main__":
    main()
