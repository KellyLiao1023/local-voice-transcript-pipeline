import os
import json

# --- 路徑記憶：第一次執行時選資料夾，之後從 config.json 讀取 ---
REPO_DIR     = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH  = os.path.join(REPO_DIR, "config.json")
DEFAULT_ROOT = os.path.join(REPO_DIR, "data")   # 沒選資料夾時的預設位置

# 根資料夾底下會自動建立的子資料夾
SUBDIRS = {
    "incoming":   "Recordings",       # 放入待處理的錄音檔
    "processing": "Temp_Processing",  # 處理中暫存
    "archive":    "Audio_Archive",    # 處理完成的錄音檔
    "notes":      "Study_Notes",      # Whisper 逐字稿 (.txt)
    "reports":    "Final_Reports",    # LLM 整理後的 Word 報告
}

DEFAULT_CONFIG = {
    "data_root":     "",
    "lm_studio_url": "http://127.0.0.1:1234/v1/chat/completions",
    "lm_api_token":  "",
}


def _ask_data_root():
    """跳出資料夾選擇視窗；無法開視窗時改用終端機輸入。取消則使用預設位置。"""
    print("📁 尚未設定資料夾，請選擇存放錄音與報告的根資料夾...")
    try:
        import tkinter as tk
        from tkinter import filedialog
        win = tk.Tk()
        win.withdraw()
        win.attributes("-topmost", True)
        chosen = filedialog.askdirectory(title="選擇資料根資料夾（取消則使用預設 data/）",
                                         initialdir=REPO_DIR)
        win.destroy()
    except Exception:
        chosen = input(f"請輸入資料夾路徑（直接 Enter 使用預設 {DEFAULT_ROOT}）：").strip()
    return os.path.abspath(chosen) if chosen else DEFAULT_ROOT


def load_config():
    """讀取 config.json；沒有路徑就詢問一次並寫回。子資料夾已存在則略過，不存在則建立。"""
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))

    if not cfg["data_root"]:
        cfg["data_root"] = _ask_data_root()
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        print(f"💾 已將路徑記錄於：{CONFIG_PATH}（刪除此檔即可重新選擇）")

    cfg["dirs"] = {key: os.path.join(cfg["data_root"], name) for key, name in SUBDIRS.items()}
    for path in cfg["dirs"].values():
        os.makedirs(path, exist_ok=True)

    print(f"📂 資料根目錄：{cfg['data_root']}")
    return cfg
