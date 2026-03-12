#!/usr/bin/env python3
"""
MiniMax LLM 性能测试报告生成器
整合单请求测试和并发测试结果，生成综合报告
"""

import json
import glob
from datetime import datetime
from typing import List, Dict, Optional


class BenchmarkReport:
    def __init__(self):
        self.results = {
            "single": [],
            "concurrency": [],
            "load": []
        }

    def load_results(self, pattern: str = "benchmark_*.json"):
        """加载所有测试结果文件"""
        files = glob.glob(pattern)
        print(f"找到 {len(files)} 个结果文件")

        for file in files:
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                if 'single' in file:
                    self.results["single"].append(data)
                    print(f"  加载: {file} (单请求测试)")
                elif 'concurrency' in file:
                    test_type = data.get("test_type", "并发测试")
                    self.results["concurrency"].append(data)
                    print(f"  加载: {file} ({test_type})")
            except Exception as e:
                print(f"  跳过 {file}: {e}")

    def generate_markdown_report(self, output_file: str = "benchmark_report.md"):
        """生成 Markdown 格式报告"""
        lines = []
        lines.append("# MiniMax LLM 性能测试报告")
        lines.append(f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append("---\n")

        # 单请求测试结果
        if self.results["single"]:
            lines.append("## 一、单请求性能测试\n")
            for result in self.results["single"]:
                analysis = result.get("analysis", {})
                lines.append(f"### 测试时间: {result.get('timestamp', 'N/A')[:19]}\n")

                for metric, stats in analysis.items():
                    if metric == "output_tokens":
                        continue

                    lines.append(f"#### {self._metric_name(metric)}\n")
                    lines.append("| 指标 | 数值 |")
                    lines.append("|------|------|")
                    lines.append(f"| 平均值 | {stats.get('mean', 'N/A')} |")
                    lines.append(f"| 中位数 | {stats.get('median', 'N/A')} |")
                    lines.append(f"| 最小值 | {stats.get('min', 'N/A')} |")
                    lines.append(f"| 最大值 | {stats.get('max', 'N/A')} |")
                    if stats.get('p90'):
                        lines.append(f"| P90 | {stats['p90']} |")
                    lines.append(f"| 标准差 | {stats.get('stdev', 'N/A')} |")
                    lines.append("")

        # 并发测试结果
        if self.results["concurrency"]:
            lines.append("## 二、并发负载测试\n")
            for result in self.results["concurrency"]:
                metrics = result.get("metrics", {})
                test_type = result.get("test_type", "并发测试")
                lines.append(f"### {test_type} - {result.get('timestamp', 'N/A')[:19]}\n")

                lines.append("#### 基础指标\n")
                lines.append("| 指标 | 数值 |")
                lines.append("|------|------|")
                lines.append(f"| 总请求数 | {metrics.get('total_requests', 'N/A')} |")
                lines.append(f"| 成功 | {metrics.get('successful_requests', 'N/A')} |")
                lines.append(f"| 失败 | {metrics.get('failed_requests', 'N/A')} |")
                lines.append(f"| 总耗时 | {metrics.get('total_duration_sec', 'N/A')}s |")
                lines.append("")

                lines.append("#### 吞吐量指标\n")
                lines.append("| 指标 | 数值 |")
                lines.append("|------|------|")
                lines.append(f"| QPS | {metrics.get('qps', 'N/A')} |")
                lines.append(f"| Token Throughput | {metrics.get('token_throughput', 'N/A')} tokens/s |")
                lines.append(f"| Request Throughput | {metrics.get('request_throughput', 'N/A')} req/s |")
                lines.append("")

                lines.append("#### 延迟分布 (ms)\n")
                lines.append("| 分位 | 数值 |")
                lines.append("|------|------|")
                lines.append(f"| P50 | {metrics.get('latency_p50', 'N/A')} |")
                lines.append(f"| P90 | {metrics.get('latency_p90', 'N/A')} |")
                lines.append(f"| P99 | {metrics.get('latency_p99', 'N/A')} |")
                lines.append(f"| 平均 | {metrics.get('latency_mean', 'N/A')} |")
                lines.append(f"| 最小 | {metrics.get('latency_min', 'N/A')} |")
                lines.append(f"| 最大 | {metrics.get('latency_max', 'N/A')} |")
                lines.append("")

        # 性能指标说明
        lines.append("## 三、指标说明\n")
        lines.append("| 指标 | 说明 | 重要性 |")
        lines.append("|------|------|--------|")
        lines.append("| TTFT | Time to First Token，首Token延迟 | 高（影响首字体验） |")
        lines.append("| TPOT | Time Per Output Token，单Token生成时间 | 高（影响生成速度） |")
        lines.append("| Latency | 端到端延迟 | 高（总等待时间） |")
        lines.append("| TPS | Tokens Per Second，每秒Token数 | 高（吞吐量指标） |")
        lines.append("| QPS | Queries Per Second，每秒查询数 | 中（并发能力） |")
        lines.append("| Throughput | 吞吐量 | 中（系统处理能力） |")
        lines.append("")

        # 保存报告
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        print(f"\n报告已生成: {output_file}")
        return output_file

    def _metric_name(self, metric: str) -> str:
        """转换指标名称"""
        names = {
            "ttft_ms": "首Token延迟 (TTFT)",
            "tpot_ms": "单Token时间 (TPOT)",
            "latency_ms": "端到端延迟 (Latency)",
            "tps": "每秒Token数 (TPS)"
        }
        return names.get(metric, metric)

    def print_summary(self):
        """打印摘要"""
        print("\n" + "="*60)
        print("测试结果摘要")
        print("="*60)

        if self.results["single"]:
            print(f"\n单请求测试: {len(self.results['single'])} 次")
        if self.results["concurrency"]:
            print(f"并发测试: {len(self.results['concurrency'])} 次")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='生成测试报告')
    parser.add_argument('--input', '-i', default='benchmark_*.json', help='结果文件匹配模式')
    parser.add_argument('--output', '-o', default='benchmark_report.md', help='输出文件名')

    args = parser.parse_args()

    report = BenchmarkReport()
    report.load_results(args.input)
    report.print_summary()
    report.generate_markdown_report(args.output)


if __name__ == "__main__":
    main()
