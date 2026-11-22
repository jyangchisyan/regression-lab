import json
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("用法：python3 analyze_result.py results/檔名.json")

path = Path(sys.argv[1])
experiment = json.loads(path.read_text(encoding="utf-8"))

print("情境：", experiment.get("scenario_id", "未標記"))
print("缺陷：", experiment.get("known_defect_id"))
print("變更：", experiment["changed_files"])
print()
print("| 策略 | 執行數 | 案例縮減率 | 已知缺陷檢出 |")
print("|---|---:|---:|---|")

for result in experiment["results"]:
    detected = result.get("detected_known_defect")
    detection_text = {
        True: "檢出",
        False: "未檢出",
        None: "未記錄或不適用",
    }[detected]

    reduction = result.get("reduction_ratio")
    reduction_text = (
        f"{reduction:.1%}" if reduction is not None else "未記錄"
    )

    print(
        f"| {result['strategy']} "
        f"| {result['tests_run']} "
        f"| {reduction_text} "
        f"| {detection_text} |"
    )
