#!/usr/bin/env bash
set -euo pipefail

# 默认用 stress 模式，方便快速触发告警阈值；想要正常流量可传 normal。
MODE="${1:-stress}"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# 增加多个 channels 和 services，以便产生多个告警实例
exec python3 "${SCRIPT_DIR}/mock_llm_metrics_server.py" \
  --mode "${MODE}" \
  --channels "openai,anthropic,azure,cohere" \
  --services "llm-api,llm-gateway" \
  --base-qps 5.0

