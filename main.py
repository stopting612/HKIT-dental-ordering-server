# main.py

from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import AzureOpenAI
from dotenv import load_dotenv
import os
import json
from typing import Optional, Dict, List
from datetime import datetime
import time

from tools import TOOLS, execute_tool
from order_manager import order_manager
from conversation_manager import conversation_manager, session_manager

from knowledge_base import kb_search

if kb_search is None:
    print("\n" + "="*60)
    print("⚠️  警告：Knowledge Base 未初始化")
    print("="*60)
    print("\n伺服器將以有限功能模式啟動")
    print("如需啟用 Knowledge Base 功能，請先執行診斷：")
    print("   python quick_diagnose.py")
    print("\n或執行完整測試：")
    print("   python test_aws_credentials.py")
    print("\n" + "="*60 + "\n")
    # 不再 exit(1)，允許伺服器繼續啟動

# 載入環境變數
load_dotenv()

# 初始化 FastAPI
app = FastAPI(title="Dental Ordering AI Agent")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化 Azure OpenAI
client = AzureOpenAI(
    azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT'),
    api_key=os.getenv('AZURE_OPENAI_KEY'),
    api_version=os.getenv('AZURE_OPENAI_API_VERSION')
)

DEPLOYMENT_NAME = os.getenv('AZURE_OPENAI_DEPLOYMENT')

# In-Memory 對話儲存（快取）
conversations: Dict[str, Dict] = {}

# System Prompt（保持不變）
SYSTEM_PROMPT = SYSTEM_PROMPT = SYSTEM_PROMPT = """你是專業的牙科訂單助手。你的任務是幫助牙醫下訂單給牙科實驗室。

## 材料分類系統
材料有**兩層結構**：
1. **Material Category** (主類別): PFM / Metal-Free / Full Cast
2. **Material Subtype** (子類型): 具體材料（由工具決定哪些可用）

⚠️ **重要：你不需要知道哪些材料可用或不可用。所有規則由 validate_material 工具決定。**

## 訂單收集流程
1. 確認修復類型 (Crown/Bridge/Veneer/Inlay/Onlay)
2. 收集牙位資訊
3. 【如果是 Bridge】驗證牙位 → 呼叫 validate_bridge(tooth_positions="...")
4. 詢問材料主類別 → 問："請問材料類別？PFM / Metal-Free / Full Cast"
5. 查詢可用的子類型 → 呼叫 validate_material(...) → 列出選項
6. 收集材料子類型 → 等用戶選擇後，呼叫 validate_material 驗證
7. 搜尋產品 → 呼叫 search_products(...) → 必須呼叫此工具來查詢價格和產品資訊
8. 讓用戶選擇產品 → 記住產品代碼和名稱
9. 收集色階（預設 A2）
10. 收集病人姓名
11. 顯示訂單摘要 → 詢問確認
12. 確認訂單

## 🆕 關鍵區分：材料 vs 病人姓名

**材料相關術語（這些不是病人姓名）：**
- Palladium-based, High-noble, Semi-precious, Non-precious
- Emax, IPS e.max, Zirconia, FMZ
- PFM, Metal-free, Full-cast
- Gold, Titanium, Ceramic

**何時呼叫 store_patient_name：**
- ✅ 只在用戶**明確提供病人姓名**時呼叫
- ✅ 通常在收集完產品和色階**之後**
- ✅ 當你問「請問病人姓名？」用戶回答時
- ❌ **絕對不要**把材料名稱當作病人姓名

## 額外重要規則 - 嚴禁誤認材料縮寫為病人姓名

以下縮寫/詞彙**絕對不是病人姓名**，永遠不要用 store_patient_name 工具處理它們：
- NP → 幾乎一定是 Non-Precious（非貴金屬）
- HP → High Precious / High Noble
- SP → Semi-Precious
- Ti → Titanium
- Zr → Zirconia
- FMZ → Full Metal Zirconia
- e.max / Emax / IPS

**判斷原則（必須嚴格遵守）**：
1. 如果上下文還在談材料、產品、價格 → 看到 NP/HP/SP 就是材料
2. 只有在你**明確問過**「請問病人姓名是？」之後，且用戶回覆的是完整中文姓名或明顯英文人名，才呼叫 store_patient_name
3. 如果回覆只有 1~3 個字母/數字組合 → 極大概率是色階（A2/B1）或材料縮寫（NP/HP），**不要**存成病人姓名

**判斷方法：**
```
用戶說："Palladium-based" 
→ 上下文：剛搜尋完產品，這是在選擇材料
→ 動作：記錄為材料選擇，**不要呼叫** store_patient_name

用戶說："陳大明"
→ 上下文：已收集完材料和色階，正在問病人姓名
→ 動作：呼叫 store_patient_name(patient_name="陳大明")
```

## 處理價格和產品查詢

**當用戶詢問價格或產品資訊時：**
- ✅ 必須使用 search_products 工具
- ✅ 即使材料尚未完全確定，也要嘗試搜尋
- ✅ 向用戶展示找到的產品和價格

**價格查詢的關鍵詞：**
- 多少錢、價格、price、cost、費用
- 要多久、製作時間、delivery time
- 有什麼產品、推薦什麼、what products

## 資料收集規則
記住以下資訊：
- restoration_type, tooth_positions, material_category, material_subtype
- product_code, product_name, shade, patient_name
- bridge_span, position_type

**收集順序（嚴格遵守）：**
1. restoration_type → 2. tooth_positions → 3. material_category → 4. material_subtype 
→ 5. product_code → 6. shade → 7. **最後才是** patient_name

訂單摘要格式：
```
📋 訂單摘要
修復類型: {restoration_type}
牙位: {tooth_positions}
材料: {material_category} ({material_subtype})
產品: {product_name} (代碼: {product_code})
色階: {shade}
病人: {patient_name}
請確認以上資訊是否正確？（回覆「確認」或「修改」）
```

## 重要原則
1. **工具優先** - 所有規則由工具決定
2. **兩步驟流程** - 先查詢，再驗證
3. **信任工具結果** - 使用工具返回的資訊
4. **按順序收集** - 不要跳過步驟，嚴格按照 1→2→3→4→5→6→7 的順序
5. **記住資訊** - 收集的每個資訊都要記住
6. **清楚摘要** - 確認前顯示完整摘要
7. **查價必用工具** - 查詢價格時必須呼叫 search_products
8. 🆕 **上下文判斷** - 根據對話進度判斷用戶輸入的意圖，不要把材料名稱誤認為病人姓名
"""


# Pydantic Models
class ChatRequest(BaseModel):
    session_id: str
    message: str
    user_id: Optional[str] = None  # 用戶 ID（從登入取得）


class ChatResponse(BaseModel):
    reply: str
    tool_calls: List[dict] = []
    state: Optional[dict] = None


# Endpoints
@app.get("/")
async def root():
    return {
        "message": "Dental Ordering AI Agent API",
        "status": "running",
        "encryption": os.getenv('ENCRYPTION_ENABLED', 'false')
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    """AI Agent 對話端點（含加密儲存）"""
    session_id = request.session_id
    user_msg = request.message
    user_id = request.user_id
    
    start_time = time.time()
    
    # ===== 1. 初始化對話歷史（In-Memory）=====
    if session_id not in conversations:
        conversations[session_id] = {
            'messages': [],
            'order_data': {}
        }
        
        # 🆕 在資料庫建立 session
        session_manager.create_session(
            session_id=session_id,
            user_id=user_id,
            session_type='order'
        )
    
    # ===== 2. 加入用戶訊息到 in-memory =====
    conversations[session_id]['messages'].append({
        "role": "user",
        "content": user_msg
    })
    
    # ===== 3. 🔐 背景儲存用戶訊息（加密，不阻塞）=====
    background_tasks.add_task(
        conversation_manager.log_message,
        session_id=session_id,
        role='user',
        content=user_msg,
        user_id=user_id
    )
    
    # ===== 4. 檢查是否是訂單確認 =====
    if '確認' in user_msg or 'confirm' in user_msg.lower() or 'yes' in user_msg.lower():
        order_data = conversations[session_id].get('order_data', {})
        
        required_fields = ['restoration_type', 'tooth_positions', 'material_category', 'material_subtype', 'patient_name']
        
        if all(field in order_data and order_data[field] for field in required_fields):
            print("\n" + "="*60)
            print("📋 準備建立訂單")
            print("="*60)
            for key, value in order_data.items():
                print(f"   {key}: {value}")
            print("="*60 + "\n")
            
            # 建立訂單
            created_order = order_manager.create_order(
                session_id=session_id,
                user_id=user_id,
                order_data=order_data
            )
            
            if created_order:
                order_number = created_order['order_number']
                order_id = created_order['id']
                
                # 結束 session
                session_manager.end_session(
                    session_id=session_id,
                    status='completed',
                    order_id=order_id
                )
                
                # 更新所有對話，關聯到訂單
                background_tasks.add_task(
                    _link_conversations_to_order,
                    session_id,
                    order_id
                )
                
                # 清空訂單資料
                conversations[session_id]['order_data'] = {}
                
                # 確認訊息
                confirmation_msg = f"""✅ 訂單已確認並提交到系統！

📋 **訂單編號**: {order_number}

訂單詳情：
- 修復類型: {order_data.get('restoration_type')}
- 牙位: {order_data.get('tooth_positions')}
- 材料: {order_data.get('material_category')} ({order_data.get('material_subtype')})
- 產品: {order_data.get('product_name', 'N/A')} (代碼: {order_data.get('product_code', 'N/A')})
- 色階: {order_data.get('shade', 'A2')}
- 病人: {order_data.get('patient_name')}

實驗室將會收到通知並開始製作。

---
如需新的訂單，請說「新訂單」。"""
                
                conversations[session_id]['messages'].append({
                    "role": "assistant",
                    "content": confirmation_msg
                })
                
                # 🔐 儲存確認訊息
                background_tasks.add_task(
                    conversation_manager.log_message,
                    session_id=session_id,
                    role='assistant',
                    content=confirmation_msg,
                    user_id=user_id,
                    order_id=order_id
                )
                
                # 更新 session 統計
                background_tasks.add_task(
                    session_manager.update_session_activity,
                    session_id
                )
                
                return ChatResponse(
                    reply=confirmation_msg,
                    tool_calls=[],
                    state={'order_created': True, 'order_number': order_number}
                )
            else:
                error_msg = "❌ 訂單建立失敗，請檢查網絡連接或稍後再試。"
                conversations[session_id]['messages'].append({
                    "role": "assistant",
                    "content": error_msg
                })
                
                background_tasks.add_task(
                    conversation_manager.log_message,
                    session_id=session_id,
                    role='assistant',
                    content=error_msg,
                    user_id=user_id
                )
                
                return ChatResponse(reply=error_msg, tool_calls=[])
        else:
            missing_fields = [f for f in required_fields if f not in order_data or not order_data[f]]
            error_msg = f"⚠️ 訂單資料不完整，缺少：{', '.join(missing_fields)}。請提供完整資訊後再確認。"
            
            conversations[session_id]['messages'].append({
                "role": "assistant",
                "content": error_msg
            })
            
            background_tasks.add_task(
                conversation_manager.log_message,
                session_id=session_id,
                role='assistant',
                content=error_msg,
                user_id=user_id
            )
            
            return ChatResponse(reply=error_msg, tool_calls=[])
    
    # ===== 5. 正常 AI Agent 流程（ReAct Loop）=====
    max_iterations = 5
    tool_calls_log = []
    
    for iteration in range(max_iterations):
        print(f"\n--- Iteration {iteration + 1} ---")
        
        try:
            response = client.chat.completions.create(
                model=DEPLOYMENT_NAME,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    *conversations[session_id]['messages']
                ],
                tools=TOOLS,
                tool_choice="auto"
            )
        except Exception as e:
            # 處理 Azure OpenAI 內容過濾錯誤
            error_msg = str(e)
            if 'content_filter' in error_msg or 'ResponsibleAIPolicyViolation' in error_msg:
                print(f"⚠️  Azure OpenAI 內容過濾器觸發: {error_msg[:200]}")
                
                # 給用戶友好的回應
                friendly_msg = "抱歉，系統檢測到可能的敏感內容。請換個方式描述，或直接提供具體的產品代碼和病人資訊。"
                
                conversations[session_id]['messages'].append({
                    "role": "assistant",
                    "content": friendly_msg
                })
                
                background_tasks.add_task(
                    conversation_manager.log_message,
                    session_id=session_id,
                    role='assistant',
                    content=friendly_msg,
                    user_id=user_id
                )
                
                return ChatResponse(
                    reply=friendly_msg,
                    tool_calls=tool_calls_log
                )
            else:
                # 其他錯誤，重新拋出
                raise
        
        message = response.choices[0].message
        
        # 檢查 AI 是否想呼叫工具
        if message.tool_calls:
            conversations[session_id]['messages'].append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in message.tool_calls
                ]
            })
            
            # 執行所有工具
            for tool_call in message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                print(f"🔧 呼叫工具: {function_name}")
                print(f"   參數: {json.dumps(function_args, ensure_ascii=False)}")
                
                tool_calls_log.append({
                    "tool": function_name,
                    "arguments": function_args
                })
                
                # 執行工具
                function_response = execute_tool(function_name, function_args)
                
                print(f"   結果: {json.dumps(function_response, ensure_ascii=False)[:200]}...")
                
                # 🔐 記錄 tool call（加密）
                background_tasks.add_task(
                    conversation_manager.log_message,
                    session_id=session_id,
                    role='tool',
                    content='',
                    user_id=user_id,
                    tool_call_id=tool_call.id,
                    tool_name=function_name,
                    tool_arguments=function_args,
                    tool_result=function_response
                )
                
                # 提取訂單資料
                _extract_order_data(
                    session_id,
                    function_name,
                    function_args,
                    function_response
                )
                
                # 加入工具結果
                conversations[session_id]['messages'].append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(function_response, ensure_ascii=False)
                })
            
            continue
        
        else:
            # AI 不需要呼叫工具
            assistant_msg = message.content
            
            conversations[session_id]['messages'].append({
                "role": "assistant",
                "content": assistant_msg
            })
            
            # 計算回應時間
            response_time = int((time.time() - start_time) * 1000)
            
            # 🔐 儲存 assistant 訊息（加密）
            background_tasks.add_task(
                conversation_manager.log_message,
                session_id=session_id,
                role='assistant',
                content=assistant_msg,
                user_id=user_id,
                response_time_ms=response_time
            )
            
            # 更新 session 統計
            background_tasks.add_task(
                session_manager.update_session_activity,
                session_id
            )
            
            # 從訊息中提取訂單資料
            _extract_order_data_from_message(session_id, user_msg, assistant_msg)
            
            return ChatResponse(
                reply=assistant_msg,
                tool_calls=tool_calls_log,
                state=conversations[session_id].get('order_data', {})
            )
    
    return ChatResponse(
        reply="抱歉，處理過程中遇到問題。",
        tool_calls=tool_calls_log
    )


# ===== 輔助函數 =====

def _extract_order_data(session_id: str, tool_name: str, tool_args: dict, tool_result: dict):
    """從工具呼叫中提取訂單資料"""
    order_data = conversations[session_id]['order_data']
    
    if tool_name == "validate_bridge":
        if tool_result.get('valid'):
            order_data['restoration_type'] = 'bridge'
            order_data['tooth_positions'] = tool_args.get('tooth_positions')
            order_data['bridge_span'] = tool_result.get('bridge_span')
            order_data['position_type'] = tool_result.get('position_type')
    
    elif tool_name == "validate_material":
        if tool_result.get('valid'):
            order_data['restoration_type'] = tool_args.get('restoration_type')
            order_data['material_category'] = tool_result.get('material_category')
            order_data['material_subtype'] = tool_result.get('material_subtype')
    
    elif tool_name == "search_products":
        if not order_data.get('restoration_type'):
            order_data['restoration_type'] = tool_args.get('restoration_type')
        if not order_data.get('material_category'):
            order_data['material_category'] = tool_args.get('material_category')
        if not order_data.get('material_subtype'):
            order_data['material_subtype'] = tool_args.get('material_subtype')
        
        if tool_result.get('found') and tool_result.get('products'):
            products = tool_result['products']
            if products:
                first_product = products[0]
                if not order_data.get('product_code'):
                    order_data['product_code'] = first_product.get('product_code')
                if not order_data.get('product_name'):
                    order_data['product_name'] = first_product.get('material_name', 'N/A')
    
    # 🆕 處理病人姓名工具
    elif tool_name == "store_patient_name":
        if tool_result.get('success'):
            patient_name = tool_result.get('patient_name')
            if patient_name:
                order_data['patient_name'] = patient_name
                print(f"   ✅ 訂單資料已更新: patient_name = '{patient_name}'")


def _extract_order_data_from_message(session_id: str, user_msg: str, assistant_msg: str):
    """從對話訊息中提取訂單資料"""
    order_data = conversations[session_id]['order_data']
    user_msg_lower = user_msg.lower()
    
    import re
    
    # 提取修復類型
    if 'crown' in user_msg_lower or '牙冠' in user_msg:
        if not order_data.get('restoration_type'):
            order_data['restoration_type'] = 'crown'
    
    # 提取牙位
    if order_data.get('restoration_type') == 'crown':
        numbers = re.findall(r'\b([1-4][1-8])\b', user_msg)
        if numbers and not order_data.get('tooth_positions'):
            order_data['tooth_positions'] = numbers[0]
    
    # 提取產品代碼
    codes = re.findall(r'\b(\d{4})\b', user_msg)
    if codes:
        order_data['product_code'] = codes[0]
    
    # 提取色階
    shade_match = re.search(r'\b([A-D][1-4](?:\.\d)?)\b', user_msg, re.IGNORECASE)
    if shade_match:
        order_data['shade'] = shade_match.group(1).upper()


def _link_conversations_to_order(session_id: str, order_id: int):
    """將所有對話關聯到訂單"""
    try:
        from supabase import create_client
        supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))
        
        supabase.table('conversations')\
            .update({'order_id': order_id})\
            .eq('session_id', session_id)\
            .execute()
        
        print(f"✅ 對話已關聯到訂單: {session_id} → Order #{order_id}")
    except Exception as e:
        print(f"⚠️  關聯對話失敗: {e}")


# ===== 其他 API Endpoints =====

@app.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """清除對話歷史"""
    if session_id in conversations:
        del conversations[session_id]
        return {"message": f"Session {session_id} cleared"}
    return {"message": f"Session {session_id} not found"}


@app.get("/session/{session_id}")
async def get_session(session_id: str):
    """查看對話歷史（in-memory）"""
    if session_id in conversations:
        return conversations[session_id]
    return {"message": f"Session {session_id} not found"}


@app.get("/conversations/{session_id}")
async def get_conversation_history(
    session_id: str,
    decrypt: bool = True,
    user_id: Optional[str] = None
):
    """
    查詢對話歷史（從資料庫，自動解密）
    
    需要權限檢查：用戶只能查看自己的對話
    """
    history = conversation_manager.get_conversation_history(
        session_id=session_id,
        decrypt=decrypt,
        user_id=user_id
    )
    
    return {
        "session_id": session_id,
        "message_count": len(history),
        "messages": history
    }


@app.get("/orders/recent")
async def get_recent_orders(limit: int = 10):
    """取得最近的訂單"""
    orders = order_manager.get_recent_orders(limit=limit)
    return {"count": len(orders), "orders": orders}


@app.get("/orders/{order_number}")
async def get_order(order_number: str):
    """查詢特定訂單"""
    order = order_manager.get_order(order_number)
    if order:
        return order
    return {"error": "Order not found"}


# Debug endpoints
from material_normalizer import get_cache_stats, clear_cache

@app.get("/debug/cache-stats")
async def cache_stats():
    """查看材料標準化緩存統計"""
    return get_cache_stats()


@app.post("/debug/clear-cache")
async def clear_normalization_cache():
    """清除材料標準化緩存"""
    clear_cache()
    return {"message": "Cache cleared"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)