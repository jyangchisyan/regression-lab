import argparse
import json
from pathlib import Path
from statistics import median

parser = argparse.ArgumentParser()
parser.add_argument("--batch-id", required=True)
parser.add_argument("--results-dir", type=Path, default=Path("results"))
args = parser.parse_args()

experiments = []

for path in args.results_dir.glob("*.json"):
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("batch_id") == args.batch_id:
        experiments.append(data)

if not experiments:
    raise SystemExit("找不到指定批次")

# 確認每個 seed 只出現一次，且完整包含 0～9。
seeds = [data["order_seed"] for data in experiments]
if len(seeds) != 10 or set(seeds) != set(range(10)):
    raise SystemExit("此批次必須恰有 10 份紀錄，seed 各為 0～9")

# 比較同一版本、同一缺陷及相同程式修改。
identity_fields = (
    "base_commit",
    "scenario_id",
    "known_defect_id",
    "tracked_diff",
    "python_version",
)
for field in identity_fields:
    if len({data[field] for data in experiments}) != 1:
        raise SystemExit(f"批次的 {field} 不一致")

timing_modes = {data.get("timing_mode", "terminal_report") for data in experiments}
if len(timing_modes) != 1:
    raise SystemExit("批次的 timing_mode 不一致")

scenario_expectations = {
    "temperature_boundary_gt70": ("DEFECT-001", [True, False, True]),
    "temperature_threshold_too_low": ("DEFECT-002", [True, True, True]),
    "temperature_equivalent_change": (None, [None, None, None]),
}
scenario_id = experiments[0]["scenario_id"]
if scenario_id not in scenario_expectations:
    raise SystemExit("此分析器不支援該情境")
defect_id, detections = scenario_expectations[scenario_id]
if experiments[0]["known_defect_id"] != defect_id:
    raise SystemExit("缺陷標籤不符合情境")
expected = dict(zip(
    ["A 全量", "B 直接選取", "C 擴大選取"],
    zip([3, 1, 2], detections),
))
times = {strategy: [] for strategy in expected}

for data in experiments:
    if data["changed_files"] != ["temperature.py"]:
        raise SystemExit("此比較只接受 temperature.py 單一變更")
    rows = data["results"]
    if (
        len(rows) != 3
        or {row["strategy"] for row in rows} != set(expected)
    ):
        raise SystemExit("策略缺漏或重複")

    for row in rows:
        strategy = row["strategy"]
        count, detected = expected[strategy]

        if (
            row["tests_run"] != count
            or row["detected_known_defect"] is not detected
            or row["error_tests"]
            or row["status"] != ("failed" if detected else "passed")
            or (detected is not True and row["failed_tests"])
        ):
            raise SystemExit(f"{strategy} 的功能結果不符合預期")

        times[strategy].append(
            row["selection_and_execution_seconds"] * 1000
        )

print(f"批次：{args.batch_id}，共 {len(experiments)} 次")
timing_mode = next(iter(timing_modes))
print(f"情境：{scenario_id}，量測方式：{timing_mode}")
report_scope = "報告文字生成" if timing_mode == "buffered_report" else "報告終端機輸出"
print(f"時間範圍：選取＋測試執行與{report_scope}\n")
print("| 策略 | 中位數 ms | 最小 ms | 最大 ms |")
print("|---|---:|---:|---:|")

for strategy, values in times.items():
    print(
        f"| {strategy} | {median(values):.4f} "
        f"| {min(values):.4f} | {max(values):.4f} |"
    )
