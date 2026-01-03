# test_db_connection.py

from supabase import create_client, Client
from dotenv import load_dotenv
import os

# 載入環境變數
load_dotenv()

# Supabase 連接資訊
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

print(f"📡 嘗試連接到 Supabase...")
print(f"   URL: {SUPABASE_URL}")
print(f"   Key: {SUPABASE_KEY[:20]}..." if SUPABASE_KEY else "   Key: 未設定")

try:
    # 建立連接
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print(f"✅ Supabase 連接成功！")
    
    # ===== 測試 1: 查詢 Users =====
    print(f"\n📋 測試 1: 查詢 Users Table")
    response = supabase.table('users').select('*').execute()
    
    print(f"   找到 {len(response.data)} 個用戶")
    for user in response.data:
        print(f"   - {user['full_name']} ({user['email']}) - {user['role']}")
    
    # ===== 測試 2: 查詢 Orders =====
    print(f"\n📋 測試 2: 查詢 Orders Table")
    response = supabase.table('orders').select('*').execute()
    
    print(f"   找到 {len(response.data)} 個訂單")
    for order in response.data:
        print(f"   - {order['order_number']}: {order['restoration_type']} ({order['patient_name']}) - {order['status']}")
    
    # ===== 測試 3: 查詢 Sessions =====
    print(f"\n📋 測試 3: 查詢 Sessions Table")
    response = supabase.table('sessions').select('*').execute()
    
    print(f"   找到 {len(response.data)} 個 sessions")
    for session in response.data:
        print(f"   - {session['session_id']}: {session['status']} ({session['message_count']} 訊息)")
    
    # ===== 測試 4: 查詢 Conversations =====
    print(f"\n📋 測試 4: 查詢 Conversations Table")
    response = supabase.table('conversations').select('*').execute()
    
    print(f"   找到 {len(response.data)} 條對話")
    for conv in response.data:
        content_preview = conv['content'][:30] if conv['content'] else "[加密]"
        print(f"   - [{conv['role']}] {content_preview}...")
    
    # ===== 測試 5: 插入新訂單 =====
    print(f"\n📋 測試 5: 插入新訂單")
    
    from datetime import datetime
    
    # 先取得一個用戶 ID
    user_response = supabase.table('users').select('id').limit(1).execute()
    if user_response.data:
        user_id = user_response.data[0]['id']
        
        new_order = {
            'order_number': f'ORD-TEST-{datetime.now().strftime("%Y%m%d%H%M%S")}',
            'user_id': user_id,
            'session_id': 'test-connection-session',
            'restoration_type': 'crown',
            'tooth_positions': '21',
            'material_category': 'metal-free',
            'material_subtype': 'emax',
            'material': 'metal-free (emax)',
            'patient_name': '測試病人',
            'shade': 'A3',
            'status': 'pending'
        }
        
        response = supabase.table('orders').insert(new_order).execute()
        
        if response.data:
            print(f"   ✅ 訂單建立成功: {response.data[0]['order_number']}")
        else:
            print(f"   ❌ 訂單建立失敗")
    
    # ===== 測試 6: 統計查詢 =====
    print(f"\n📋 測試 6: 統計查詢")
    
    # 總用戶數
    user_count = supabase.table('users').select('id', count='exact').execute()
    print(f"   總用戶數: {user_count.count}")
    
    # 總訂單數
    order_count = supabase.table('orders').select('id', count='exact').execute()
    print(f"   總訂單數: {order_count.count}")
    
    # 已完成訂單數
    completed_count = supabase.table('orders')\
        .select('id', count='exact')\
        .eq('status', 'completed')\
        .execute()
    print(f"   已完成訂單: {completed_count.count}")
    
    # 今日訂單數
    today_count = supabase.table('orders')\
        .select('id', count='exact')\
        .gte('created_at', datetime.now().strftime('%Y-%m-%d'))\
        .execute()
    print(f"   今日訂單: {today_count.count}")
    
    print(f"\n🎉 所有測試通過！")

except Exception as e:
    print(f"\n❌ 連接失敗: {e}")
    print(f"\n請檢查：")
    print(f"   1. .env 檔案中的 SUPABASE_URL 和 SUPABASE_KEY 是否正確")
    print(f"   2. Supabase 專案是否啟動")
    print(f"   3. 網絡連接是否正常")