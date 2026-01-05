#!/usr/bin/env bash
set -euo pipefail

# 默认用 stress 模式，方便快速触发告警阈值；想要正常流量可传 normal。
MODE="${1:-stress}"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "${SCRIPT_DIR}/mock_llm_metrics_server.py" --mode "${MODE}"

