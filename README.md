# OpenBMC 變更導向回歸測試實作教學

本專案是研究計畫「基於 OpenBMC 之變更導向回歸測試方法與效能評估」的 Python 入門實驗。目前尚未連接 OpenBMC 或 QEMU，先用小型案例理解測試選取、漏檢與安全回退。

## 研究問題與目前進度

- RQ1：選取相關測試能否減少案例數與執行時間？目前已能記錄案例比例與耗時。
- RQ2：縮減測試後是否漏檢？目前以一個刻意注入的門檻缺陷比較三種策略。
- RQ3：歷史資訊能否改善排序？尚未實作。

已完成：Git 差異讀取、人工對應表、去除重複測試、未知變更回退、無變更情境、JSON 紀錄與案例縮減率。後續才加入已知缺陷判定、跨情境分析與真實 OpenBMC 測試。

## 檔案與執行環境

需要 Python 3 與 Git；程式只使用標準函式庫。請在儲存庫根目錄操作。

| 檔案 | 用途 |
|---|---|
| `temperature.py` | 正常規格為達到 70°C 就觸發，即 `>= 70` |
| `test_fan.py` | 驗證 70°C 應觸發 |
| `unit_test.py` | 比較三種策略並寫入 JSON |
| `examples/results/` | 教學過程留下的代表性原始紀錄 |
| `results/` | 每次執行產生的本地結果，預設不提交 |

執行完整教學實驗請用：

```bash
python3 unit_test.py
```

`python3 -m unittest discover -v` 預設不會搜尋名稱為 `unit_test.py` 的檔案，因此不能代替上面的策略比較指令。

## 1. 理解三種策略

| 策略 | `temperature.py` 變更時選取 | 案例數 |
|---|---|---:|
| A 全量 | 溫度、風扇、功率 | 3 |
| B 直接選取 | 溫度 | 1 |
| C 擴大選取 | 溫度、風扇 | 2 |

溫度測試只檢查 69°C；風扇測試檢查 70°C；功率測試驗證 12 × 2 = 24。這是人工設計的教學關聯，尚未從真實程式依賴自動推導。

## 2. 無變更情境

確認 `temperature.py` 內容為：

```python
def at_threshold(celsius):
    return celsius >= 70
```

儲存後執行：

```bash
git diff --name-only HEAD --
python3 unit_test.py
```

差異指令應沒有輸出。A 應執行 3 個且全部通過；B、C 應各執行 0 個，JSON 狀態為 `not_run`。不同 Python 版本可能顯示 `OK` 或 `NO TESTS RAN`，零個測試都不代表功能已驗證。

程式的情境標籤目前寫死在 `experiment` 中。執行這個情境前，應將 `scenario_id` 設為 `no_change`、`known_defect_id` 設為 `None`。若修改已追蹤的 `unit_test.py`，它也會進入差異並觸發回退，因此先將這項情境設定獨立提交，再確認沒有差異。後續宜改用命令列參數，避免設定污染實驗差異。

## 3. 注入門檻缺陷

將 `temperature.py` 的 `>= 70` 改為 `> 70`，儲存但不要提交這個刻意注入的缺陷。確認情境標籤為 `temperature_boundary_gt70` 與 `DEFECT-001`；儲存庫提供的程式預設即為這組標籤。

```bash
git diff HEAD -- temperature.py
git diff --name-only HEAD --
python3 unit_test.py
```

變更清單應只有 `temperature.py`。如果同時包含其他已追蹤檔案，先處理那些變更，否則會回退全量。

| 策略 | 執行數 | 結果 | 案例縮減率 |
|---|---:|---|---:|
| A 全量 | 3 | 風扇測試失敗，檢出缺陷 | 0% |
| B 直接選取 | 1 | 通過，但漏檢 | 66.7% |
| C 擴大選取 | 2 | 風扇測試失敗，檢出缺陷 | 33.3% |

69°C 在兩種判斷中都回傳 `False`，所以 B 沒抓到問題。70°C 正好是此次修改影響的邊界，所以 A、C 能抓到問題。選中的測試全部通過，不等於沒有缺陷。

## 4. 未知變更回退

保持缺陷情境，建立一個未列於對應表的檔案：

```bash
printf '# Unknown path for the regression lab\n' > common.py
git add common.py
git diff --name-only HEAD --
python3 unit_test.py
```

建立前請確認沒有需要保留的同名檔案。若檔案已存在，直接使用現有檔案，不要覆寫。

預期差異包含 `common.py` 與 `temperature.py`。B、C 各印一次回退訊息，三種策略都跑 3 個測試且檢出風扇缺陷。這是在對應表不完整時保留全量測試範圍的保守策略。

完成後只取消暫存：

```bash
git restore --staged common.py
```

檔案仍保留在本地，但成為未追蹤檔案，不再出現在目前的差異指令中。不要提交這個未知路徑實驗檔案。

## 5. 選取函式的原理

`direct_map` 與 `expanded_map` 以程式檔名對應測試物件。`select_tests()` 依序：

1. 檢查變更檔案是否都在對應表中；有未知檔案就回傳全量。
2. 收集已知檔案對應的測試，用 `test.id()` 去重。
3. 沒有變更時回傳空清單。

目前讀取的是 `git diff --name-only HEAD --`：包含暫存與未暫存的已追蹤差異，也包含已暫存的新檔案，但不包含一般未追蹤檔案。「差異清單為空」不等於工作目錄乾淨。

提交會改變 `HEAD`。若將缺陷也提交，再對 `HEAD` 比較，缺陷就不會被當作變更；因此儲存庫保留正常基準，實驗時再修改。

## 6. JSON 紀錄與解讀

每次執行在 `results/` 新增以 UTC 時間命名的 JSON。

| 欄位 | 意義 |
|---|---|
| `recorded_at` | UTC 紀錄時間 |
| `changed_files` | Git 差異取得的路徑 |
| `scenario_id` / `known_defect_id` | 人工指定的情境與缺陷標籤，非自動辨識 |
| `status` | `passed`、`failed` 或 `not_run` |
| `tests_run` | 實際執行案例數 |
| `failed_tests` | 斷言失敗案例 |
| `error_tests` | 執行發生例外的案例 |
| `elapsed_seconds` | `perf_counter()` 量測的測試與報告輸出耗時 |
| `selection_ratio` | 策略執行數 / 全量案例數 |
| `reduction_ratio` | 1 − 選取比例 |

目前固定有三個測試，比例假設測試正常跑完、沒有提早中止。浮點數如 `0.33333333333333337` 是正常表示，展示時可四捨五入。

代表性紀錄：

- [無變更](examples/results/20261122T091314046528Z.json)：較早版本，尚無比例及情境欄位。
- [已知缺陷](examples/results/20261122T092105583992Z.json)：包含選取比例、縮減率及缺陷標籤。

這些是當時的原始紀錄，沒有補寫當時尚未產生的欄位。

## 7. 下一步：已知缺陷檢出欄位（尚未加入程式）

在 `records = []` 前加入：

```python
scenario_id = "temperature_boundary_gt70"
known_defect_id = "DEFECT-001"
defect_revealing_tests = {"test_fan.FanTests.test_fan_at_70"}
```

在迴圈中取得 `failed_tests` 後計算：

```python
detected_known_defect = (
    bool(set(failed_tests) & defect_revealing_tests)
    if known_defect_id is not None
    else None
)
```

將 `detected_known_defect` 加入每筆 `records`；`experiment` 的情境欄位改用上面的變數。缺陷情境預期 A/C 為 `true`、B 為 `false`；無缺陷時將 `known_defect_id` 設為 `None`，輸出為 `null`。

交集判斷只適用於目前受控缺陷；一般失敗還要確認根因，不能把任何失敗都算成這個缺陷。跨多個已知缺陷情境後，才以「檢出缺陷數 / 已知缺陷總數」計算檢出率。

## 研究限制與後續工作

- 單一缺陷不能證明選取方法對其他缺陷有效。
- 耗時極短且策略固定按 A/B/C 順序執行，不適合據此宣稱效能提升；需重複實驗並控制順序及環境。
- 尚未記錄選取方法本身的執行成本，也未建立程式版本與測試版本的完整追溯資訊。
- `unit_test.py` 尚無主程式保護，匯入也會執行實驗；腳本即使測試失敗仍可能回傳結束碼 0，尚不能直接當成 CI 品質閘門。
- 後續先加入情境參數、結果分析與可靠的執行入口，再建立多缺陷資料集、歷史排序及 OpenBMC/Linux 實驗環境，視需求加入 QEMU。
