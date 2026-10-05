# Local Voice Transcript Pipeline

在個人電腦上**完全離線**完成「錄音 → 逐字稿 → 結構化 Word 報告」的自動化流程。
語音辨識使用 [faster-whisper](https://github.com/SYSTRAN/faster-whisper)（Whisper large-v3），摘要整理使用透過 [LM Studio](https://lmstudio.ai/) 在本機運行的大型語言模型，錄音與文字內容不會上傳至任何雲端服務。

## 開發動機

課堂、會議與實驗室討論的錄音數量多，人工整理費時；而使用雲端轉錄服務則有資料外流的疑慮。
本專案的目標是在一般消費級顯示卡上，以本地模型完成轉錄與摘要，並將結果整理成可直接閱讀的 Word 文件。

## 流程

```
Recordings/          放入錄音檔 (.aac / .m4a / .mp3 / .wav)
   │
   ▼  移至 Temp_Processing/
[階段一] 載入 Whisper large-v3 (GPU, float16) → 產生含時間戳的逐字稿
   │                                             └─► Study_Notes/<檔名>.txt
   ▼
[階段二] 卸載 Whisper，釋放 VRAM（del model → gc.collect() → torch.cuda.empty_cache()）
   │
   ▼
[階段三] 呼叫本機 LLM（LM Studio，OpenAI 相容 API）整理逐字稿
   │                                             └─► Final_Reports/<檔名>.docx
   ▼
錄音檔移至 Audio_Archive/
```

### 設計重點

- **VRAM 分時使用**：Whisper 與 LLM 不同時常駐顯示卡記憶體。每個檔案轉錄完畢後先完整釋放 Whisper，再交給 LLM，讓單張顯示卡也能依序執行兩個模型。
- **檔案狀態以資料夾區分**：待處理、處理中、已歸檔分別放在不同資料夾，中途失敗時可直接看出卡在哪個階段。
- **Markdown → Word 轉換**：將 LLM 輸出的標題（`#`、`##`、`###`）與條列（`-`、`*`）轉為 Word 的對應樣式。
- **可替換模型**：`reprocess_single.py` 可針對同一份逐字稿切換不同 LLM 重新產生報告，輸出檔名會加上模型後綴，方便比較不同模型的整理品質。

## 檔案說明

| 檔案 | 用途 |
|---|---|
| `transcribe_pipeline.py` | 主流程：批次處理 `Recordings/` 內所有錄音 |
| `reprocess_single.py` | 針對單一逐字稿，用指定模型重新產生 Word 報告 |
| `path_config.py` | 路徑設定：首次執行時選擇資料夾並記錄於 `config.json` |
| `config.example.json` | 設定檔範本 |

## 環境需求

- Windows（其他系統未測試）
- Python 3.10 以上
- 支援 CUDA 的 NVIDIA 顯示卡（Whisper large-v3 約需 4 GB VRAM；LLM 需求依所選模型而定）
- [LM Studio](https://lmstudio.ai/)，並已下載要使用的模型（開發時使用 `deepseek-r1-0528-qwen3-8b`、`gpt-oss-20b`）

## 安裝

```bash
git clone https://github.com/<your-account>/local-voice-transcript-pipeline.git
cd local-voice-transcript-pipeline
pip install -r requirements.txt
```

> `torch` 請依照顯示卡的 CUDA 版本，至 [PyTorch 官網](https://pytorch.org/get-started/locally/) 取得對應的安裝指令。

## 使用方式

### 1. 啟動 LM Studio 本機伺服器

在 LM Studio 載入模型，並於 Developer 分頁啟動伺服器（預設為 `http://127.0.0.1:1234`）。

### 2. 第一次執行：選擇資料夾

```bash
python transcribe_pipeline.py
```

第一次執行時會跳出資料夾選擇視窗，選定的根資料夾底下會自動建立：

```
<根資料夾>/
├─ Recordings/        ← 把錄音檔放這裡
├─ Temp_Processing/
├─ Audio_Archive/
├─ Study_Notes/
└─ Final_Reports/
```

- 取消選擇時，會使用專案內的 `data/` 作為預設位置。
- 已存在的資料夾會略過，不會覆蓋。
- 選擇結果記錄在 `config.json`，之後執行不會再詢問；**刪除 `config.json` 即可重新選擇**。

### 3. 設定 API token（選用）

若 LM Studio 有啟用 API 驗證，請用記事本打開專案內的 `config.json`，把 token 貼在 `lm_api_token` 後面的雙引號中間，存檔即可。貼好後的樣子：

```json
{
  "data_root": "D:\\my_recordings",
  "lm_studio_url": "http://127.0.0.1:1234/v1/chat/completions",
  "lm_api_token": "sk-lm-xxxxxxxx"
}
```

- LM Studio 未啟用 API 驗證時，此欄位留空（`""`）即可正常執行。
- `config.json` 已列入 `.gitignore`，不會被上傳。

### 4. 批次轉錄

將錄音檔放入 `Recordings/` 後執行：

```bash
python transcribe_pipeline.py
```

### 5. 單一檔案重新整理（比較不同模型）

編輯 `reprocess_single.py` 開頭的參數後執行：

```python
TARGET_FILE_NAME = "標準錄音 108.txt"   # Study_Notes/ 中的逐字稿檔名
CURRENT_MODEL    = "gpt-oss-20b"        # LM Studio 中的模型 ID
MODEL_SUFFIX     = "gpt-oss-20b"        # 輸出檔名後綴
```

```bash
python reprocess_single.py
```

輸出為 `Final_Reports/<檔名>_<後綴>.docx`；檔案已存在時會先詢問是否覆蓋。

## 已知限制

- 目前僅支援 CUDA 顯示卡，未提供 CPU 模式。
- LLM 輸出轉換 Word 時僅處理標題與條列，表格等其他 Markdown 語法會以純文字呈現。
- 逐字稿全文一次送入 LLM，過長的錄音可能超出模型的 context 長度。
