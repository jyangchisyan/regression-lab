import subprocess
import sys
import unittest

import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from temperature import at_threshold
from test_fan import FanTests


class TemperatureTests(unittest.TestCase):
    def test_temperature(self):
        self.assertFalse(at_threshold(69))


class PowerTests(unittest.TestCase):
    def test_power_watts(self):
        voltage = 12
        current = 2
        self.assertEqual(voltage * current, 24)

result = subprocess.run(
    ["git", "diff", "--name-only", "HEAD", "--"],
    check=True,
    capture_output=True,
    text=True,
)
changed_files = result.stdout.splitlines()
print("變更檔案", changed_files, flush=True)


temperature_test = TemperatureTests("test_temperature")
fan_test = FanTests("test_fan_at_70")
power_test = PowerTests("test_power_watts")

all_tests = [temperature_test, fan_test, power_test]

# 每個程式檔案直接對應的測試
direct_map = {
    "temperature.py": [temperature_test],
}

# 每個程式檔案可能影響的相關測試
expanded_map = {
    "temperature.py": [temperature_test, fan_test],
}


def select_tests(changed_files, mapping):
    unknown_files = set(changed_files) - set(mapping)

    if unknown_files:
        print("未知變更，回退全量", sorted(unknown_files), flush=True)
        return list(all_tests)

    selected = []
    seen = set()

    for filename in changed_files:
        for test in mapping[filename]:
            if test.id() not in seen:
                selected.append(test)
                seen.add(test.id())

    return selected


direct_tests = select_tests(changed_files, direct_map)
expanded_tests = select_tests(changed_files, expanded_map)

scenario_id = "temperature_boundary_gt70"
known_defect_id = "DEFECT-001"

# 這個已知缺陷預期會造成哪些測試斷言失敗
defect_revealing_tests = {
    "test_fan.FanTests.test_fan_at_70",
}

records = []

for label, tests in [
    ("A 全量", all_tests),
    ("B 直接選取", direct_tests),
    ("C 擴大選取", expanded_tests),
]:
    print(f"\n{label}", flush=True)

    suite = unittest.TestSuite(tests)

    started = perf_counter()
    result = unittest.TextTestRunner(
        stream=sys.stdout,
        verbosity=2,
    ).run(suite)
    elapsed = perf_counter() - started

    failed_tests = [test.id() for test, _ in result.failures]
    error_tests = [test.id() for test, _ in result.errors]

    if result.testsRun == 0:
        status = "not_run"
    elif result.wasSuccessful():
        status = "passed"
    else:
        status = "failed"

    detected_known_defect = (
        bool(set(failed_tests) & defect_revealing_tests)
        if known_defect_id is not None
        else None
    )
    
    records.append({
        "strategy": label,
        "status": status,
        "tests_run": result.testsRun,
        "failed_tests": failed_tests,
        "error_tests": error_tests,
        "elapsed_seconds": elapsed,
        "selection_ratio": result.testsRun / len(all_tests),
        "reduction_ratio": 1 - result.testsRun / len(all_tests),
        "detected_known_defect": detected_known_defect,

    })

    print(
        f"摘要 {label}｜執行 {result.testsRun} 個"
        f"｜狀態 {status}"
        f"｜斷言失敗 {failed_tests}"
        f"｜執行錯誤 {error_tests}"
    )

experiment = {
    "recorded_at": datetime.now(timezone.utc).isoformat(),
    "changed_files": changed_files,
    "results": records,
    "scenario_id": "temperature_boundary_gt70",
    "known_defect_id": "DEFECT-001",
    "scenario_id": scenario_id,
    "known_defect_id": known_defect_id,
}

output_dir = Path("results")
output_dir.mkdir(exist_ok=True)

output_path = output_dir / (
    datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    + ".json"
)
output_path.write_text(
    json.dumps(experiment, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print(f"\n實驗紀錄已儲存：{output_path}")