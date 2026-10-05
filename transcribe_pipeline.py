import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import shutil
import time
import requests
import json
import gc      # 垃圾回收
import torch   # 強制清理 GPU 緩存
from faster_whisper import WhisperModel
from docx import Document
from path_config import load_config

# --- 1. 路徑與金鑰設定（由 config.json 提供，見 path_config.py） ---
CFG = load_config()
INCOMING_DIR   = CFG["dirs"]["incoming"]
PROCESSING_DIR = CFG["dirs"]["processing"]
ARCHIVE_DIR    = CFG["dirs"]["archive"]
NOTE_DIR       = CFG["dirs"]["notes"]
WORD_DIR       = CFG["dirs"]["reports"]
LM_API_TOKEN   = CFG["lm_api_token"]
LM_STUDIO_URL  = CFG["lm_studio_url"]

# --- 2. 核心功能：AI 摘要與 Word 生成 ---
def call_ai_and_make_word(txt_path, file_base_name):
    """此時 Whisper 已被卸載，顯存全數留給 GPT-OSS 20B"""
    with open(txt_path, "r", encoding="utf-8") as f:
        content = f.read()

    prompt = f"請將以下逐字稿整理成結構化的 Word 檔案：\n其內容盡量避免表格，重點可用條列方式...\n\n逐字稿內容：\n{content}"
    payload = {
        "model": "deepseek-r1-0528-qwen3-8b", # 或者是 deepseek-r1-0528-qwen3-8b
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5
    }
    headers = {"Authorization": f"Bearer {LM_API_TOKEN}", "Content-Type": "application/json"}
    
    print(f"🧠 AI 正在進行轉譯 (VRAM 已釋放，運行空間充足)...")
    try:
        response = requests.post(LM_STUDIO_URL, json=payload, headers=headers, timeout=1200)
        res_data = response.json()
        if 'choices' not in res_data:
            print(f"❌ AI 回傳異常：{res_data}")
            return

        ai_reply = res_data['choices'][0]['message']['content']
        doc = Document()
        doc.add_heading(f'對話紀錄：{file_base_name}', 0)
        # (此處省略你之前的 Markdown 解析邏輯，代碼中已包含)
        for line in ai_reply.split('\n'):
            line = line.strip()
            if not line: continue
            if line.startswith('### '): doc.add_heading(line[2:], level=3)
            elif line.startswith('## '): doc.add_heading(line[3:], level=2)
            elif line.startswith('# '): doc.add_heading(line[2:], level=1)
            elif line.startswith('- ') or line.startswith('* '):
                doc.add_paragraph(line[2:], style='List Bullet')
            else:
                doc.add_paragraph(line.replace('**', ''))
        
        doc.save(os.path.join(WORD_DIR, f"{file_base_name}.docx"))
        print(f"✅ Word 報告已存至：{WORD_DIR}")
    except Exception as e:
        print(f"❌ AI 摘要失敗：{e}")

# --- 3. 核心管線：動態載入/卸載邏輯 ---
def run_optimized_pipeline():
    os.makedirs(PROCESSING_DIR, exist_ok=True)
    files = [f for f in os.listdir(INCOMING_DIR) if f.lower().endswith(('.aac', '.m4a', '.mp3', '.wav'))]
    if not files: return

    for file_name in files:
        file_base = os.path.splitext(file_name)[0]
        src_path  = os.path.join(INCOMING_DIR, file_name)
        proc_path = os.path.join(PROCESSING_DIR, file_name)
        output_txt = os.path.join(NOTE_DIR, f"{file_base}.txt")

        try:
            shutil.move(src_path, proc_path)
            
            # 🚀 階段一：啟動 Whisper 酵素
            print(f"🧬 正在加載 Whisper 定序儀 (佔用約 4GB VRAM)...")
            model = WhisperModel("large-v3", device="cuda", compute_type="float16")
            
            print(f"🎙️ 正在轉錄：{file_name}")
            segments, _ = model.transcribe(proc_path, beam_size=5)
            with open(output_txt, "w", encoding="utf-8") as f:
                for s in segments:
                    f.write(f"[{s.start:.2f}s -> {s.end:.2f}s] {s.text}\n")
            
            # 🧹 階段二：強制降解 Whisper，騰出空間給 LLM
            print("🧹 轉錄完成，正在回收 VRAM 資源...")
            del model
            gc.collect()
            torch.cuda.empty_cache() # 關鍵：確保顯存完全清空
            time.sleep(10) # 稍微等待顯卡反應
            
            # 🧠 階段三：啟動 LLM 摘要
            call_ai_and_make_word(output_txt, file_base)

            shutil.move(proc_path, os.path.join(ARCHIVE_DIR, file_name))
            print(f"✅ {file_base} 處理完成，VRAM 負載已歸零。")

        except Exception as e:
            print(f"❌ 處理失敗：{e}")

if __name__ == "__main__":
    print("🚀 啟動：顯存優化批次處理模式...")
    run_optimized_pipeline()