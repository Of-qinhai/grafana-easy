#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import random
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple


Labels = Tuple[Tuple[str, str], ...]


def _now() -> float:
    return time.time()


def _normalize_labels(labels: Mapping[str, str] | None) -> Labels:
    if not labels:
        return ()
    return tuple(sorted((str(k), str(v)) for k, v in labels.items()))


def _format_labels(labels: Labels) -> str:
    if not labels:
        return ""
    inner = ",".join(f'{k}="{_escape_label_value(v)}"' for k, v in labels)
    return "{" + inner + "}"


def _escape_label_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _poisson(lam: float) -> int:
    if lam <= 0:
        return 0
    # Knuth algorithm; fine for small lam (our default).
    L = math.exp(-lam)
    k = 0
    p = 1.0
    while p > L:
        k += 1
        p *= random.random()
    return k - 1


class Registry:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._help: Dict[str, str] = {}
        self._type: Dict[str, str] = {}

        self._counters: Dict[Tuple[str, Labels], float] = {}
        self._gauges: Dict[Tuple[str, Labels], float] = {}
        self._histograms: Dict[Tuple[str, Labels], "_HistogramState"] = {}
        self._histogram_buckets: Dict[str, List[float]] = {}

    def set_help(self, name: str, text: str) -> None:
        with self._lock:
            self._help[name] = text

    def set_type(self, name: str, metric_type: str) -> None:
        with self._lock:
            self._type[name] = metric_type

    def define_histogram(self, name: str, buckets: Sequence[float], help_text: str) -> None:
        with self._lock:
            self._histogram_buckets[name] = list(buckets)
            self._help[name] = help_text
            self._type[name] = "histogram"

    def inc_counter(self, name: str, value: float = 1.0, labels: Mapping[str, str] | None = None) -> None:
        key = (name, _normalize_labels(labels))
        with self._lock:
            self._help.setdefault(name, name)
            self._type.setdefault(name, "counter")
            self._counters[key] = self._counters.get(key, 0.0) + float(value)

    def set_gauge(self, name: str, value: float, labels: Mapping[str, str] | None = None) -> None:
        key = (name, _normalize_labels(labels))
        with self._lock:
            self._help.setdefault(name, name)
            self._type.setdefault(name, "gauge")
            self._gauges[key] = float(value)

    def observe_histogram(
        self,
        name: str,
        value: float,
        labels: Mapping[str, str] | None = None,
    ) -> None:
        key = (name, _normalize_labels(labels))
        with self._lock:
            buckets = self._histogram_buckets.get(name)
            if buckets is None:
                raise KeyError(f"Histogram '{name}' not defined")
            state = self._histograms.get(key)
            if state is None:
                state = _HistogramState.from_buckets(buckets)
                self._histograms[key] = state
            state.observe(value)

    def render(self) -> str:
        with self._lock:
            lines: List[str] = []

            # HELP/TYPE (stable-ish order).
            all_names = sorted(set(self._help) | set(self._type))
            for name in all_names:
                help_text = self._help.get(name)
                if help_text:
                    lines.append(f"# HELP {name} {help_text}")
                metric_type = self._type.get(name)
                if metric_type:
                    lines.append(f"# TYPE {name} {metric_type}")

            # Counters.
            for (name, labels), value in sorted(self._counters.items()):
                lines.append(f"{name}{_format_labels(labels)} {value}")

            # Gauges.
            for (name, labels), value in sorted(self._gauges.items()):
                lines.append(f"{name}{_format_labels(labels)} {value}")

            # Histograms.
            for (name, labels), state in sorted(self._histograms.items()):
                buckets = self._histogram_buckets[name]
                cumulative = 0
                for idx, le in enumerate(buckets):
                    cumulative += state.raw_bucket_counts[idx]
                    lines.append(
                        f'{name}_bucket{_format_labels((("le", f"{le}"),) + labels)} {cumulative}'
                    )
                cumulative += state.raw_bucket_counts[len(buckets)]
                lines.append(f'{name}_bucket{_format_labels((("le", "+Inf"),) + labels)} {cumulative}')
                lines.append(f"{name}_sum{_format_labels(labels)} {state.sum}")
                lines.append(f"{name}_count{_format_labels(labels)} {state.count}")

            return "\n".join(lines) + "\n"


@dataclass
class _HistogramState:
    buckets: List[float]
    raw_bucket_counts: List[int]
    sum: float = 0.0
    count: int = 0

    @classmethod
    def from_buckets(cls, buckets: Sequence[float]) -> "_HistogramState":
        return cls(buckets=list(buckets), raw_bucket_counts=[0] * (len(buckets) + 1))

    def observe(self, value: float) -> None:
        v = float(value)
        idx = len(self.buckets)
        for i, le in enumerate(self.buckets):
            if v <= le:
                idx = i
                break
        self.raw_bucket_counts[idx] += 1
        self.sum += v
        self.count += 1


class Simulator:
    def __init__(
        self,
        registry: Registry,
        *,
        services: Sequence[str],
        channels: Sequence[str],
        base_qps: float,
        mode: str,
    ) -> None:
        self._r = registry
        self._services = list(services)
        self._channels = list(channels)
        self._base_qps = float(base_qps)
        self._mode = mode

        self._lock = threading.RLock()
        self._inflight_by_service: Dict[str, List[float]] = {s: [] for s in self._services}
        self._mq_waiting = 0.0

        # Histogram definitions (buckets can be adjusted to your实际分布).
        self._r.define_histogram(
            "llm_record_mq_write_duration_seconds",
            buckets=[0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2],
            help_text="Gateway MQ write duration (seconds).",
        )
        self._r.define_histogram(
            "llm_request_duration",
            buckets=[0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 30, 60, 120],
            help_text="End-to-end request duration (seconds).",
        )
        self._r.define_histogram(
            "llm_ttft",
            buckets=[0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10],
            help_text="Time to first token (seconds).",
        )
        self._r.define_histogram(
            "llm_otps",
            buckets=[5, 10, 20, 30, 50, 80, 120, 200, 400, 800],
            help_text="Output tokens per second (tokens/s).",
        )
        self._r.define_histogram(
            "llm_tpot",
            buckets=[0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1],
            help_text="Time per output token (seconds/token).",
        )

        # Help/type for other metrics.
        self._r.set_help("llm_request_count", "Total requests.")
        self._r.set_type("llm_request_count", "counter")
        self._r.set_help("channel_llm_request_count", "Total requests by channel.")
        self._r.set_type("channel_llm_request_count", "counter")

        self._r.set_help("llm_request_count_by_token_bucket", "Requests bucketed by token length.")
        self._r.set_type("llm_request_count_by_token_bucket", "counter")
        self._r.set_help(
            "channel_llm_request_count_by_token_bucket", "Requests bucketed by token length (channel)."
        )
        self._r.set_type("channel_llm_request_count_by_token_bucket", "counter")

        self._r.set_help("llm_total_tokens", "Total tokens consumed.")
        self._r.set_type("llm_total_tokens", "counter")
        self._r.set_help("llm_input_tokens", "Input tokens consumed.")
        self._r.set_type("llm_input_tokens", "counter")
        self._r.set_help("llm_output_tokens", "Output tokens produced.")
        self._r.set_type("llm_output_tokens", "counter")
        self._r.set_help("llm_total_tokens_by_token_bucket", "Total tokens bucketed by token length.")
        self._r.set_type("llm_total_tokens_by_token_bucket", "counter")

        self._r.set_help("llm_chat_handler_active_count", "In-flight request count.")
        self._r.set_type("llm_chat_handler_active_count", "gauge")

        self._r.set_help("llm_record_mq_write_waiting", "Waiting MQ write backlog.")
        self._r.set_type("llm_record_mq_write_waiting", "gauge")
        self._r.set_help("llm_record_mq_write_error_count", "MQ write errors (counter).")
        self._r.set_type("llm_record_mq_write_error_count", "counter")
        self._r.set_help("llm_record_temp_store_write_error_count", "Temp store write errors (counter).")
        self._r.set_type("llm_record_temp_store_write_error_count", "counter")
        self._r.set_help("llm_record_mq_write_retry_count", "MQ write retries (counter).")
        self._r.set_type("llm_record_mq_write_retry_count", "counter")

    def step(self, dt_seconds: float) -> None:
        now = _now()

        # Mode knobs: use --mode stress to快速触发告警阈值。
        if self._mode == "stress":
            error_prob = 0.10
            client_cancel_prob = 0.08  # 客户端取消请求概率（499）
            mq_error_prob = 0.05
            temp_store_error_prob = 0.30
            retry_prob = 0.30
            avg_ttft = 1.2
            avg_otps = 12.0
            mq_capacity_per_sec = 2.0
            mq_write_scale = 0.8
        else:
            error_prob = 0.01
            client_cancel_prob = 0.03  # 客户端取消请求概率（499）
            mq_error_prob = 0.002
            temp_store_error_prob = 0.05
            retry_prob = 0.05
            avg_ttft = 0.15
            avg_otps = 60.0
            mq_capacity_per_sec = 200.0
            mq_write_scale = 0.02

        produced_total = 0

        for service in self._services:
            for channel in self._channels:
                req_n = _poisson(self._base_qps * dt_seconds)
                produced_total += req_n
                for _ in range(req_n):
                    self._emit_one_request(
                        now=now,
                        service=service,
                        channel=channel,
                        error_prob=error_prob,
                        client_cancel_prob=client_cancel_prob,
                        avg_ttft=avg_ttft,
                        avg_otps=avg_otps,
                        mq_error_prob=mq_error_prob,
                        temp_store_error_prob=temp_store_error_prob,
                        retry_prob=retry_prob,
                        mq_write_scale=mq_write_scale,
                    )

        # MQ backlog gauge (simple queue model).
        with self._lock:
            self._mq_waiting += produced_total
            consumed = min(self._mq_waiting, mq_capacity_per_sec * dt_seconds)
            self._mq_waiting -= consumed
            self._r.set_gauge("llm_record_mq_write_waiting", self._mq_waiting)

        # Active in-flight gauge by service.
        with self._lock:
            for service, end_times in self._inflight_by_service.items():
                # prune
                i = 0
                while i < len(end_times):
                    if end_times[i] <= now:
                        end_times.pop(i)
                    else:
                        i += 1
                self._r.set_gauge("llm_chat_handler_active_count", len(end_times), labels={"service": service})

    def _emit_one_request(
        self,
        *,
        now: float,
        service: str,
        channel: str,
        error_prob: float,
        client_cancel_prob: float,
        avg_ttft: float,
        avg_otps: float,
        mq_error_prob: float,
        temp_store_error_prob: float,
        retry_prob: float,
        mq_write_scale: float,
    ) -> None:
        # 状态码生成逻辑：先判断客户端取消，再判断服务器错误
        r = random.random()
        if r < client_cancel_prob:
            status_code = "499"  # 客户端取消请求
        elif r < client_cancel_prob + error_prob:
            status_code = "500"  # 服务器错误
        else:
            status_code = "200"  # 正常响应

        input_tokens, output_tokens = self._sample_tokens()
        total_tokens = input_tokens + output_tokens
        token_bucket = self._token_bucket(total_tokens)

        # QPS counters.
        self._r.inc_counter("llm_request_count", 1, labels={"service": service, "status_code": status_code})
        self._r.inc_counter(
            "channel_llm_request_count",
            1,
            labels={"service": service, "channel": channel, "status_code": status_code},
        )

        self._r.inc_counter(
            "llm_request_count_by_token_bucket",
            1,
            labels={"service": service, "token_bucket": token_bucket},
        )
        self._r.inc_counter(
            "channel_llm_request_count_by_token_bucket",
            1,
            labels={"service": service, "channel": channel, "token_bucket": token_bucket},
        )

        # Token counters.
        self._r.inc_counter("llm_input_tokens", input_tokens, labels={"service": service, "channel": channel})
        self._r.inc_counter("llm_output_tokens", output_tokens, labels={"service": service, "channel": channel})
        self._r.inc_counter("llm_total_tokens", total_tokens, labels={"service": service, "channel": channel})
        self._r.inc_counter(
            "llm_total_tokens_by_token_bucket",
            total_tokens,
            labels={"service": service, "channel": channel, "token_bucket": token_bucket},
        )

        # Latency / UX histograms.
        ttft = max(0.01, random.expovariate(1.0 / avg_ttft))
        otps = max(1.0, random.lognormvariate(math.log(avg_otps), 0.35))
        tpot = 1.0 / otps
        gen_time = output_tokens * tpot
        overhead = random.uniform(0.01, 0.08)
        total_duration = ttft + gen_time + overhead

        self._r.observe_histogram("llm_ttft", ttft, labels={"service": service, "channel": channel})
        self._r.observe_histogram("llm_otps", otps, labels={"service": service, "channel": channel})
        self._r.observe_histogram("llm_tpot", tpot, labels={"service": service, "channel": channel})
        self._r.observe_histogram("llm_request_duration", total_duration, labels={"service": service, "channel": channel})

        # In-flight (very rough): keep an end_time record.
        with self._lock:
            self._inflight_by_service[service].append(now + total_duration)

        # Gateway MQ write side.
        mq_write_duration = max(0.0005, random.lognormvariate(math.log(mq_write_scale), 0.6))
        self._r.observe_histogram("llm_record_mq_write_duration_seconds", mq_write_duration)

        # Retries/errors.
        if random.random() < retry_prob:
            retries = random.choice([1, 1, 2, 3])
            self._r.inc_counter("llm_record_mq_write_retry_count", retries)

        if random.random() < mq_error_prob:
            self._r.inc_counter("llm_record_mq_write_error_count", 1)
            # Fallback temp-store may still fail.
            if random.random() < temp_store_error_prob:
                self._r.inc_counter("llm_record_temp_store_write_error_count", 1)

    def _sample_tokens(self) -> Tuple[int, int]:
        # A simple distribution: mostly small, sometimes large.
        r = random.random()
        if self._mode == "stress":
            # More long-context requests.
            weights = [
                (0.30, (20, 400)),
                (0.40, (400, 1500)),
                (0.25, (1500, 4000)),
                (0.05, (4000, 8000)),
            ]
        else:
            weights = [
                (0.55, (20, 400)),
                (0.35, (400, 1500)),
                (0.09, (1500, 4000)),
                (0.01, (4000, 8000)),
            ]

        acc = 0.0
        low, high = 20, 400
        for p, (a, b) in weights:
            acc += p
            if r <= acc:
                low, high = a, b
                break
        input_tokens = random.randint(low, high)
        output_tokens = max(1, int(random.lognormvariate(math.log(120), 0.7)))
        return input_tokens, output_tokens

    @staticmethod
    def _token_bucket(total_tokens: int) -> str:
        if total_tokens <= 512:
            return "0-512"
        if total_tokens <= 1024:
            return "512-1k"
        if total_tokens <= 2048:
            return "1k-2k"
        if total_tokens <= 4096:
            return "2k-4k"
        if total_tokens <= 8192:
            return "4k-8k"
        return "8k+"


class MetricsHandler(BaseHTTPRequestHandler):
    registry: Registry

    def do_GET(self) -> None:  # noqa: N802
        if self.path not in ("/metrics", "/metrics/"):
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"not found\n")
            return

        payload = self.registry.render().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt: str, *args: object) -> None:
        # Reduce noise.
        return


def _parse_csv(value: str) -> List[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Expose mock LLM business metrics in Prometheus /metrics format.",
    )
    parser.add_argument("--listen", default="0.0.0.0", help="Listen address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=18080, help="Listen port (default: 18080)")
    parser.add_argument("--interval", type=float, default=1.0, help="Simulation tick interval seconds (default: 1)")
    parser.add_argument("--base-qps", type=float, default=2.0, help="Base QPS per (service,channel) (default: 2)")
    parser.add_argument(
        "--services",
        default="llm-api",
        help='Comma-separated services label values (default: "llm-api")',
    )
    parser.add_argument(
        "--channels",
        default="default,openai,azure",
        help='Comma-separated channels label values (default: "default,openai,azure")',
    )
    parser.add_argument(
        "--mode",
        choices=["normal", "stress"],
        default="normal",
        help='normal=低错误/低延迟；stress=更容易触发告警阈值 (default: normal)',
    )
    parser.add_argument("--seed", type=int, default=None, help="Random seed (optional)")
    parser.add_argument("--dump", action="store_true", help="Print one /metrics snapshot and exit")
    args = parser.parse_args(argv)

    if args.seed is not None:
        random.seed(args.seed)

    services = _parse_csv(args.services) or ["llm-api"]
    channels = _parse_csv(args.channels) or ["default"]

    registry = Registry()
    sim = Simulator(registry, services=services, channels=channels, base_qps=args.base_qps, mode=args.mode)

    # Warm up a bit so Grafana/Prometheus immediately has non-zero data.
    for _ in range(3):
        sim.step(args.interval)
        time.sleep(0.05)

    if args.dump:
        print(registry.render(), end="")
        return 0

    MetricsHandler.registry = registry
    server = ThreadingHTTPServer((args.listen, args.port), MetricsHandler)

    def loop() -> None:
        last = _now()
        while True:
            time.sleep(args.interval)
            now = _now()
            dt = max(0.05, now - last)
            sim.step(dt)
            last = now

    t = threading.Thread(target=loop, name="sim-loop", daemon=True)
    t.start()

    print(f"[mock-metrics] serving http://{args.listen}:{args.port}/metrics (mode={args.mode})")
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

