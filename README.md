# MiniMax LLM 性能测试套件

基于 MiniMax API 的 LLM 核心性能指标测试脚本。

## 脚本说明

| 脚本 | 功能 | 测试指标 |
|------|------|----------|
| `benchmark_single.py` | 单请求性能测试 | TTFT、TPOT、Latency、TPS |
| `benchmark_concurrency.py` | 并发负载测试 | QPS、Throughput、并发延迟分布 |
| `benchmark_report.py` | 报告生成器 | 汇总分析、Markdown报告 |

## 安装依赖

```bash
pip install -r requirements.txt
```

## 配置方式

所有参数都通过修改脚本顶部的 **全局变量** 来配置。

### 配置文件说明

| 文件 | 内容 |
|------|------|
| `config.py` | API密钥、模型、测试参数 |
| `prompts.py` | 20种测试提示词 |

#### config.py 示例

```python
MINIMAX_API_KEY = "your-api-key"
MODEL = "MiniMax-M2.5-highspeed"
BASE_URL = "https://api.minimaxi.com/v1"
NUM_REQUESTS = 10
CONCURRENCY = 3
```

#### prompts.py 示例

```python
PROMPTS = [
    "请解释深度学习的基本原理...",
    "请写快速排序算法...",
    # ... 共20种
]
```

## 使用示例

### 1. 单请求性能测试

编辑 `benchmark_single.py` 顶部的全局变量，然后运行：

```bash
python benchmark_single.py
```

### 2. 并发负载测试

编辑 `benchmark_concurrency.py` 顶部的全局变量，然后运行：

```bash
# 并发测试模式
TEST_MODE = "concurrent"  # 设置后再运行
python benchmark_concurrency.py

# 负载测试模式
TEST_MODE = "load"  # 设置后再运行
python benchmark_concurrency.py
```

使用代理：

```bash
proxychains4 python benchmark_single.py
proxychains4 python benchmark_concurrency.py
```

### 3. 生成测试报告

```bash
python benchmark_report.py
```

## 支持的模型

MiniMax 平台可用模型：

| 模型 | 描述 |
|------|------|
| `abab6.5s-chat` | 轻量快速，适合简单任务 |
| `abab6.5-chat` | 平衡型 |
| `abab6.5t-chat` | 适合复杂任务 |
| `MiniMax-Text-01` | 最新大模型 |

## 测试指标说明

| 指标 | 全称 | 说明 | 测试脚本 |
|------|------|------|----------|
| **TTFT** | Time to First Token | 首Token延迟，从请求到收到第一个token的时间 | single |
| **TPOT** | Time Per Output Token | 单Token平均生成时间（不含首token） | single |
| **Latency** | End-to-End Latency | 完整请求响应时间 | single |
| **TPS** | Tokens Per Second | 每秒生成token数 | single/concurrency |
| **QPS** | Queries Per Second | 每秒处理的请求数 | concurrency |
| **Throughput** | 吞吐量 | 单位时间处理的token/请求数 | concurrency |

## 测试设计原则

1. **预热**：正式测试前执行3次warmup，消除冷启动影响
2. **流式测量**：使用 `stream=True` 精确捕获 TTFT
3. **多次采样**：每个配置至少10次请求取统计值
4. **百分位统计**：记录 P50/P90/P99，关注尾部延迟

## 输出文件

所有测试结果保存在 `log/` 目录：

- `log/benchmark_single_YYYYMMDD_HHMMSS.json` - 单请求测试原始数据
- `log/benchmark_concurrency_YYYYMMDD_HHMMSS.json` - 并发测试原始数据
- `log/concurrency_gradient_YYYYMMDD_HHMMSS.json` - 并发梯度测试原始数据
- `benchmark_report.md` - 综合报告（当前目录）

## 完整测试流程

```bash
# 1. 修改 benchmark_single.py 中的 MINIMAX_API_KEY
# 2. 单模型性能基线测试
python benchmark_single.py

# 3. 不同并发度测试
# 修改 benchmark_concurrency.py 中的 CONCURRENCY 变量
for c in 1 5 10 20; do
    # 编辑脚本设置 CONCURRENCY = $c
    python benchmark_concurrency.py
done

# 4. 负载测试（找到饱和点）
# 修改 benchmark_concurrency.py:
# TEST_MODE = "load"
# TARGET_QPS = 想要的值
for qps in 1 2 5 10; do
    # 编辑脚本设置 TARGET_QPS = $qps
    python benchmark_concurrency.py
done

# 5. 生成报告
python benchmark_report.py
```
