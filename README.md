# OpenBMC 變更導向回歸測試實作教學

本專案對應研究計畫「基於 OpenBMC 之變更導向回歸測試方法與效能評估」。目前用 Python 小型案例練習，尚未連接 OpenBMC 或 QEMU。

## 目前完成的流程

Git 變更 → 人工檔案與測試對應表 → 選取或回退全量 → 執行測試 → JSON 紀錄 → 單次、跨缺陷與批次分析。

已完成兩個已知缺陷、命令列情境、版本追溯、選取成本、可重現的隨機策略順序、批次識別與緩衝報告計時，並已將實驗流程移入 `main()`。歷史失敗資訊排序、真實 OpenBMC 測試與 CI 品質閘門尚未完成。

## 環境與檔案

需要 Python 3 與 Git，只使用標準函式庫。在儲存庫根目錄執行指令。

| 檔案 | 用途 |
|---|---|
| `temperature.py` | 基準規格：達到 70°C 即觸發，`celsius >= 70` |
| `test_fan.py` | 驗證 70°C 應觸發 |
| `unit_test.py` | 溫度／功率測試、三種策略、JSON 紀錄 |
| `analyze_result.py` | 分析單份紀錄 |
| `summarize_results.py` | 每個已知缺陷選一份紀錄，彙整檢出率 |
| `analyze_batch.py` | 檢查同批 10 次紀錄並彙整時間 |
| `examples/results/` | 已提交的教學原始數據 |
| `results/` | 本地產生的紀錄，已忽略 |

`unit_test.py` 不是預設 unittest discovery 的檔名，請直接執行本文件中的指令。

## 1. 三種測試策略

| 策略 | 已知溫度檔案變更時選取 | 案例數 |
|---|---|---:|
| A 全量 | 溫度、風扇、功率 | 3 |
| B 直接選取 | 溫度 | 1 |
| C 擴大選取 | 溫度、風扇 | 2 |

溫度測試只檢查 69°C，風扇測試檢查 70°C，功率測試檢查 12 × 2 = 24。這些是教學用人工對應，並非自動分析真實程式依賴。

`select_tests()` 遇到未知檔案回退全量；已知檔案依對應表選取，以 `test.id()` 去重；沒有變更則選取零個測試。

## 2. 情境參數與 Git 基準

`--scenario` 指定紀錄及判定規則，**不會自動修改程式**。請先手動修改 `temperature.py`，其他教學程式則先提交成為穩定基準。

| 情境 | 函式回傳式 | 缺陷標籤 | A/B/C 執行數 | A/B/C 檢出 |
|---|---|---|---|---|
| `no_change` | `celsius >= 70` | `null` | 3/0/0 | 全為 `null` |
| `temperature_boundary_gt70` | `celsius > 70` | DEFECT-001 | 3/1/2 | true/false/true |
| `temperature_threshold_too_low` | `celsius >= 69` | DEFECT-002 | 3/1/2 | true/true/true |
| `temperature_equivalent_change` | `70 <= celsius` | `null` | 3/1/2 | 全為 `null` |

等價修改只就目前整數輸入而言。`no_change` 中 A 全部通過，B/C 為 `not_run`；零個測試不代表功能已驗證。等價修改則三種策略全部通過。

確認變更：

```bash
git diff --name-only HEAD --
git diff HEAD -- temperature.py
```

除 `no_change` 應無差異外，其他情境應只有 `temperature.py`。差異指令包含已暫存及未暫存的已追蹤修改、已暫存新檔案，**不包含一般未追蹤檔案**。

若 `unit_test.py` 等未知檔案也變更，B/C 都會回退全量。只提交已完成的教學程式，保留刻意注入的溫度修改，例如：

```bash
git add unit_test.py
git diff --cached --name-only
git commit -m "Update experiment runner"
```

確認暫存區只有要提交的檔案。不要把缺陷一起提交，否則它會成為 `HEAD` 基準，不再列為變更。

## 3. 單次缺陷實驗與 JSON 分析

將回傳式改為 `celsius > 70`，執行：

```bash
python3 unit_test.py --scenario temperature_boundary_gt70 --seed 0 --batch-id defect001-single-01
python3 analyze_result.py results/實際產生的檔名.json
```

DEFECT-001 影響 70°C 邊界，溫度測試只檢查 69°C，因此 B 通過卻漏檢。A/C 執行風扇測試而檢出。

再將回傳式改為 `celsius >= 69`：

```bash
python3 unit_test.py --scenario temperature_threshold_too_low --seed 0 --batch-id defect002-single-01
python3 analyze_result.py results/實際產生的檔名.json
```

DEFECT-002 讓 69°C 提早觸發，溫度測試會失敗，因此三種策略都檢出。

檢出判定是 `failed_tests` 與該情境的 `revealing_tests` 是否有交集。這只適用於受控情境；一般失敗仍須確認根因。無已知缺陷時記為 `null`，不算漏檢。

## 4. 未知變更回退與無變更驗證

保持 DEFECT-001 修改。建立沒有重要內容的 `common.py`，再暫存：

```bash
git add common.py
python3 unit_test.py --scenario temperature_boundary_gt70 --seed 0 --batch-id fallback-01
git restore --staged common.py
```

差異應包含 `common.py` 與 `temperature.py`；B/C 各印一次回退訊息，三種策略都執行 3 個並檢出缺陷。取消暫存後檔案仍保留。這種回退紀錄不要混入 3/1/2 的策略比較。

再改回 `celsius >= 70`，確認差異清單為空：

```bash
python3 unit_test.py --scenario no_change --seed 0 --batch-id no-change-01
```

A 應 3 個全通過，B/C 應各 0 個。`--scenario` 本身不驗證你是否正確修改程式，須核對 Git 差異及結果。

## 5. 跨缺陷彙整

每個不同缺陷只選一份正確紀錄，且變更應只有 `temperature.py`：

```bash
python3 summarize_results.py results/缺陷1.json results/缺陷2.json
```

| 策略 | 檢出缺陷數 | 已知缺陷檢出率 | 平均案例縮減率 |
|---|---:|---:|---:|
| A 全量 | 2/2 | 100.0% | 0.0% |
| B 直接選取 | 1/2 | 50.0% | 66.7% |
| C 擴大選取 | 2/2 | 100.0% | 33.3% |

公式：選取比例＝執行數／全量案例數；案例縮減率＝1−選取比例；已知缺陷檢出率＝檢出缺陷數／不同已知缺陷總數。重跑同一缺陷不增加缺陷總數。

## 6. 版本追溯與量測範圍

JSON 包含 UTC `recorded_at`、`changed_files`、`scenario_id`、`known_defect_id`、`base_commit`、`tracked_diff`、`python_version`、`order_seed`、`strategy_order`、`batch_id`、`timing_mode`。

每個策略包含 `status`、`tests_run`、`failed_tests`、`error_tests`、`detected_known_defect`、案例比例與以下時間：

| 時間欄位 | 範圍 |
|---|---|
| `selection_seconds` | 選取函式；A 記 0 表示不執行選取函式 |
| `elapsed_seconds` | 測試框架執行與報告文字生成 |
| `selection_and_execution_seconds` | 上述兩項相加，不是完整程序總時間 |

目前用 `io.StringIO()` 緩衝報告，計時結束後才輸出，`timing_mode` 為 `buffered_report`。終端機報告輸出不在執行計時內；Git 查詢、對應表建立、JSON 寫入也不在上述加總內。回退分支的選取函式本身會印訊息，選取成本仍包含那項輸出。

舊版沒有 `timing_mode` 的批次以終端機輸出計時；新舊方式分開分析。失敗 traceback 的文字生成仍在計時內，故成功與失敗路徑的成本也不同。

## 7. 重複實驗與隨機順序

`random.Random(seed).shuffle()` 決定策略執行順序，同 seed 可重現。順序可能重複，並不保證平衡。測試選取仍先 B 後 C；JSON `results` 順序會變，分析須依策略名稱辨識。

保持 `celsius > 70`，建立一批新的 10 次紀錄：

```bash
for seed in {0..9}; do
  python3 unit_test.py --scenario temperature_boundary_gt70 --seed "$seed" --batch-id defect001-buffered-02
done
python3 analyze_batch.py --batch-id defect001-buffered-02
```

每次重收整批都改批次名稱。分析器要求 seed 0～9 各一份，同版本、同程式修改、同 Python 與計時方式，並核對情境預期及單一溫度檔案變更。

已收集的緩衝批次中位數為 A＝0.2671 ms、B＝0.1356 ms、C＝0.5156 ms。**案例減少不保證耗時下降**；微型實驗受框架、失敗報告與系統波動影響，不能據此宣稱真實系統加速。

## 8. 全通過的等價修改比較

將回傳式改成 `70 <= celsius`，其餘不動：

```bash
for seed in {0..9}; do
  python3 unit_test.py --scenario temperature_equivalent_change --seed "$seed" --batch-id equivalent-buffered-04
done
python3 analyze_batch.py --batch-id equivalent-buffered-04
```

預期三種策略都通過，案例數仍 3/1/2，檢出欄位全為 `null`。這是用來減少成功／失敗報告差異的正常情境，不能當成另一個缺陷加入檢出率分母。

## 9. 重現既有數據

`examples/results/` 保留舊版代表紀錄、兩個缺陷與四個完整批次，沒有補寫歷史欄位。

```bash
python3 summarize_results.py examples/results/20261122T125912262006Z.json examples/results/20261122T114003744543Z.json
python3 analyze_batch.py --results-dir examples/results --batch-id defect001-repeat-01
python3 analyze_batch.py --results-dir examples/results --batch-id defect001-buffered-01
python3 analyze_batch.py --results-dir examples/results --batch-id equivalent-buffered-03
# 此舊批次預期被拒絕：包含 unit_test.py 變更，已回退為 3/3/3
python3 analyze_batch.py --results-dir examples/results --batch-id equivalent-buffered-01
```

既有 `equivalent-buffered-01` 的差異包含 `temperature.py` 與 `unit_test.py`，實際為 3/3/3 全量回退。原始資料保留供稽核，但不納入等價情境的選取效能比較。後續的 `equivalent-buffered-03` 已正確收集 10 次且每次為 3/1/2，可用於正常情境的時間描述。

## 10. 執行入口重構

原本匯入 `unit_test.py` 就會讀取 Git、解析參數、執行測試並寫檔。現在測試類別與 `select_tests()` 留在模組層級，實驗流程放進：

```python
def main():
    # Git 差異、測試與對應表建立、參數解析、選取、執行、JSON 寫入
    ...

if __name__ == "__main__":
    main()
```

`select_tests(changed_files, mapping, all_tests)` 明確接收全量清單，不再依賴全域的實驗物件。重構保留 CLI 參數、紀錄格式、計時範圍及策略行為。

驗證匯入：

```bash
python3 -c "import unit_test; print('匯入完成，未執行實驗')"
```

匯入不應印變更、跑測試或新增 JSON。命令列執行仍依前述指令操作。重構前後已在隔離環境比較四種情境與未知變更回退，除時間與版本資訊外結果一致。

## 11. 批次重複問題排查

若分析出現「此批次必須恰有 10 份紀錄，seed 各為 0～9」，通常是資料缺漏或同批次名稱被重複使用。曾觀察到本地 `equivalent-buffered-01` 累積 20 份、`equivalent-buffered-02` 累積 40 份；這些混合批次不能直接分析。不要挑出較快的紀錄或覆寫舊數據來湊滿 10 份。

保留舊紀錄，以未用過的 `batch_id` 重新收集。每批只執行一次 seed 0～9 的迴圈；分析指令可以重複執行，不會新增紀錄。收集前先確認教學程式已提交、Git 差異只有 `temperature.py`。

## 12. 正常情境的新批次結果

`equivalent-buffered-03` 包含 seed 0～9 各一次，三種策略全部通過，檢出欄位全為 `null`。

| 策略 | 中位數 ms | 最小 ms | 最大 ms |
|---|---:|---:|---:|
| A 全量 | 0.1496 | 0.0918 | 0.2347 |
| B 直接選取 | 0.1373 | 0.0568 | 0.2200 |
| C 擴大選取 | 0.1324 | 0.0623 | 0.3594 |

以中位數描述，B 比 A 低約 8.2%，C 比 A 低約 11.5%。這不是統計顯著性結論；其他批次曾觀察到 C 高於 A，且本批次範圍也高度重疊，因此尚未證明穩定的耗時優勢。最大／最小值不是信賴區間。

## 13. 什麼是「微型功能示範」

目前僅有一個溫度比較函式、三個測試、兩個人工門檻缺陷，以及人工設定的檔案與測試關聯。這個刻意簡化的程式，是用來理解研究方法的小型示範。

它已證明流程能串接，並能展示選取如何漏檢、回退及記錄結果；它尚不能代表實際 OpenBMC 工作負載。一次比較或乘法極短，測試框架與報告成本可能占很大比例。

接下來應擴充感測器資料解析、風扇控制規則、事件紀錄等具有實際行為的模組與測試，再移到真正 OpenBMC 模組。不要單純加入 `sleep()` 製造加速。評估時須同時回答是否避開無關測試、是否漏檢，以及節省成本是否足以抵銷選取成本。

## 研究限制與後續工作

兩個人工缺陷不代表 OpenBMC 的整體檢出能力。後續需要更多獨立缺陷、穩定且較具代表性的工作負載、平衡執行順序與環境資訊，再評估統計差異。

目前 Git 差異不記錄未追蹤檔案，版本追溯尚非完整環境封存。執行入口已完成重構；測試失敗仍未轉成 CI 失敗結束碼，應先完善錯誤處理再接 CI。最後才延伸歷史測試排序、Linux/OpenBMC 模組與適合的 QEMU 驗證。
