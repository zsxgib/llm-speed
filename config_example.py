#!/usr/bin/env python3
"""
API 和模型配置示例

使用方法：
1. 复制此文件为 config.py
2. 填入你的实际 API Key
3. 根据需要修改其他参数

注意：config.py 包含敏感信息，请勿提交到版本控制！
"""

import os

# ==================== API 配置 ====================
# MiniMax API Key
# 可以从环境变量读取，或直接填写
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "your-api-key-here")

# API 基础地址
# 国内版: https://api.minimaxi.com/v1
# 国际版: https://api.minimax.io/v1
BASE_URL = "https://api.minimaxi.com/v1"

# ==================== 模型配置 ====================
# 可选模型:
# - MiniMax-M2.5-highspeed  (高速版，推荐)
# - abab6.5-chat            (平衡型)
# - abab6.5s-chat           (轻量快速)
# - abab6.5t-chat           (适合复杂任务)
MODEL = "MiniMax-M2.5-highspeed"

# ==================== 单请求测试参数 ====================
# 测试请求数
NUM_REQUESTS = 10

# 预热请求数（正式测试前的热身）
WARMUP_REQUESTS = 3

# ==================== 并发测试参数 ====================
# 测试模式: 'concurrent' 或 'load'
TEST_MODE = "concurrent"

# 并发数（单个测试）
CONCURRENCY = 3

# 每个并发度的请求数
REQUESTS_PER_LEVEL = 20

# 并发梯度测试的并发度列表
CONCURRENCY_LEVELS = [2, 3, 4, 5, 10]

# ==================== 负载测试参数 ====================
# 测试时长（秒）
DURATION_SEC = 60

# 目标 QPS（每秒请求数）
TARGET_QPS = 10.0
