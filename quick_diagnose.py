# quick_diagnose.py

import os
from dotenv import load_dotenv

load_dotenv()

print("🔍 快速診斷 Knowledge Base 設定")
print("="*60)

# 檢查環境變數
env_vars = {
    'AWS_REGION': os.getenv('AWS_REGION'),
    'AWS_ACCESS_KEY_ID': os.getenv('AWS_ACCESS_KEY_ID'),
    'AWS_SECRET_ACCESS_KEY': os.getenv('AWS_SECRET_ACCESS_KEY'),
    'BEDROCK_KB_ID': os.getenv('KNOWLEDGE_BASE_ID')
}

print("\n📋 環境變數檢查：")
all_present = True
for key, value in env_vars.items():
    if value:
        # 只顯示前幾個字符
        display = value[:15] + "..." if len(value) > 15 else value
        print(f"   ✅ {key}: {display}")
    else:
        print(f"   ❌ {key}: 未設定")
        all_present = False

if not all_present:
    print(f"\n❌ 有環境變數未設定！")
    print(f"\n請在 .env 中設定以下變數：")
    print(f"""
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
KNOWLEDGE_BASE_ID=...
""")
    exit(1)

print(f"\n✅ 所有環境變數已設定")

# 嘗試初始化 KB
print(f"\n{'='*60}")
print(f"🔧 嘗試初始化 Knowledge Base...")
print(f"{'='*60}\n")

try:
    from knowledge_base import kb_search
    
    if kb_search is None:
        print(f"❌ kb_search 是 None！")
        print(f"\n請檢查 knowledge_base.py 的初始化代碼")
    else:
        print(f"✅ Knowledge Base 初始化成功！")
        print(f"   類型: {type(kb_search)}")
        print(f"   KB ID: {kb_search.kb_id}")

except Exception as e:
    print(f"❌ 初始化失敗: {e}")
    import traceback
    traceback.print_exc()