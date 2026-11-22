
import json
import sys
from pathlib import Path

if len(sys.argv) < 3:
    raise SystemExit(
        "用法：python3 summarize_results.py 缺陷1.json 缺陷2.json ..."
    )

experiments = []
seen_defects = set()

for filename in sys.argv[1:]:
    data = json.loads(Path(filename).read_text(encoding="utf-8"))
    defect_id = data.get("known_defect_id")

    if defect_id is None:
        raise SystemExit(f"{filename}：不是已知缺陷情境")

    if defect_id in seen_defects:
        raise SystemExit(f"{defect_id} 重複，請每個缺陷只選一份紀錄")

    seen_defects.add(defect_id)
    experiments.append(data)

strategies = ["A 全量", "B 直接選取", "C 擴大選取"]
summary = {
    strategy: {"detected": 0, "reductions": []}
    for strategy in strategies
}

for data in experiments:
    rows = data["results"]

    if (
        len(rows) != len(strategies)
        or {row["strategy"] for row in rows} != set(strategies)
    ):
        raise SystemExit("每份紀錄必須各包含一次 A、B、C 策略")

    for row in rows:
        if (
            row.get("status") == "not_run"
            or row.get("error_tests")
            or type(row.get("detected_known_defect")) is not bool
        ):
            raise SystemExit("紀錄未執行、發生錯誤或缺少檢出判定，請先檢查")

    baseline = next(row for row in rows if row["strategy"] == "A 全量")
    if not baseline["detected_known_defect"]:
        raise SystemExit("全量測試未檢出已知缺陷，請先確認實驗情境")

    for row in rows:
        item = summary[row["strategy"]]
        item["detected"] += int(row["detected_known_defect"])
        item["reductions"].append(row["reduction_ratio"])

total = len(experiments)

print(f"不同已知缺陷數：{total}\n")
print("| 策略 | 檢出缺陷數 | 已知缺陷檢出率 | 平均案例縮減率 |")
print("|---|---:|---:|---:|")

for strategy, item in summary.items():
    average_reduction = sum(item["reductions"]) / total
    print(
        f"| {strategy} "
        f"| {item['detected']}/{total} "
        f"| {item['detected'] / total:.1%} "
        f"| {average_reduction:.1%} |"
    )