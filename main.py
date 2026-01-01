# main.py
from dotenv import load_dotenv

# 載入環境變數 (必須在其他 imports 之前)
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openai import AzureOpenAI
import os
import json
from typing import Dict, List

from models import ChatRequest, ChatResponse
from tools import TOOLS, execute_tool

# 建立 FastAPI app
app = FastAPI(title="Dental Ordering API")

# CORS 設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Azure OpenAI 客戶端
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT")

# 對話歷史（記憶體儲存）
conversations: Dict[str, List[dict]] = {}

# System Prompt
SYSTEM_PROMPT = """你是專業的牙科訂單助手。你的任務是幫助牙醫下訂單給牙科實驗室。

## 材料分類系統

材料有**兩層結構**：
1. **Material Category** (主類別): PFM / Metal-Free / Full Cast
2. **Material Subtype** (子類型): 具體材料（由工具決定哪些可用）

⚠️ **重要：你不需要知道哪些材料可用或不可用。所有規則由 validate_material 工具決定。**

---

## 訂單收集流程

1. 確認修復類型 (Crown/Bridge/Veneer/Inlay/Onlay)

2. 收集牙位資訊

3. 【如果是 Bridge】驗證牙位
   → 呼叫 validate_bridge(tooth_positions="...")

4. 詢問材料主類別
   → 問："請問材料類別？PFM / Metal-Free / Full Cast"

5. 查詢可用的子類型
   → 呼叫 validate_material(restoration_type="...", material_category="...")
   → 工具會返回 allowed_subtypes 列表
   → 列出這些選項給用戶選擇

6. 收集材料子類型
   → 等用戶選擇後，呼叫 validate_material 驗證

7. 驗證材料相容性
   → 呼叫 validate_material(restoration_type="...", material_category="...", material_subtype="...")
   → 如果 valid: true → 繼續
   → 如果 valid: false → 工具會返回正確的選項，重新讓用戶選擇

8. 搜尋產品
   → 呼叫 search_products(...)

9. 收集色階（預設 A2）

10. 收集病人姓名

11. 顯示訂單摘要

12. 確認訂單

---

## 工具使用流程（重要！）

### 步驟 1: 查詢可用材料

當用戶選擇材料類別後：
```
用戶: "Metal-Free"

你的行動:
1. 呼叫 validate_material(
     restoration_type="bridge",
     material_category="metal-free"
     # 不提供 material_subtype
   )

2. 工具返回:
   {
     "valid": true,
     "query_mode": true,
     "allowed_subtypes": ["ips-emax", "fmz", "calypso", ...]
   }

3. 你回應用戶:
   "好的，Metal-Free 全瓷。可選擇的子類型：
   - IPS e.max
   - FMZ
   - FMZ Ultra
   - Lava
   - Lava Plus
   - Lava Esthetic
   - Calypso
   請問您想選擇哪一種？"
```

### 步驟 2: 驗證用戶選擇的材料

當用戶選擇子類型後：
```
用戶: "Calypso"

你的行動:
1. 呼叫 validate_material(
     restoration_type="bridge",
     material_category="metal-free",
     material_subtype="calypso"
   )

2a. 如果工具返回 {valid: true}:
    → 呼叫 search_products
    → 推薦產品

2b. 如果工具返回 {valid: false, allowed_subtypes: [...]}:
    → 說明原因（使用工具返回的 message）
    → 列出工具返回的 allowed_subtypes
    → 讓用戶重新選擇
```

---

## 處理驗證失敗

當 validate_material 返回 valid: false 時：

✅ **正確做法：**
1. 使用工具返回的 `message` 解釋原因
2. 列出工具返回的 `allowed_subtypes`
3. 引導用戶重新選擇

範例：
```
用戶: "Composite"
[工具返回: {valid: false, message: "bridge 不能使用 composite...", allowed_subtypes: ["ips-emax", "fmz", ...]}]

你回應:
"抱歉，Bridge 不能使用 Composite。Metal-Free Bridge 只能使用高強度全瓷材料。

可選擇的材料：
- IPS e.max
- FMZ
- FMZ Ultra
- Lava
- Lava Plus
- Lava Esthetic
- Calypso

請問您想選擇哪一種？"
```

❌ **錯誤做法：**
- 不要自己判斷哪些材料可用
- 不要根據記憶列出選項
- 不要忽略工具返回的資訊

---

## 重要原則

1. **工具優先**
   - 所有規則由工具決定
   - 不要自己判斷材料相容性
   - 永遠信任工具的結果

2. **兩步驟流程**
   - 步驟 1: 查詢可用材料（不提供 subtype）
   - 步驟 2: 驗證用戶選擇（提供 subtype）

3. **使用工具返回的資訊**
   - 列出選項時，使用 allowed_subtypes
   - 說明錯誤時，使用 message
   - 不要自己編造內容

4. **清楚溝通**
   - 驗證失敗時，清楚說明原因
   - 提供完整的替代選項
   - 引導用戶重新選擇

---

## 對話範例

### 範例 1: 正常流程
```
用戶: "我要做 bridge"
助手: "好的，請問牙位是？"

用戶: "14, 15, 16"
助手: [呼叫 validate_bridge]
      "✅ 驗證通過！這是 3 單位的牙橋。請問材料類別？PFM / Metal-Free / Full Cast"

用戶: "Metal-Free"
助手: [呼叫 validate_material(restoration_type="bridge", material_category="metal-free")]
      [返回: {query_mode: true, allowed_subtypes: ["ips-emax", "fmz", "fmz-ultra", "lava", "lava-plus", "lava-esthetic", "calypso"]}]
      
      "好的，Metal-Free 全瓷。可選擇的子類型：
      - IPS e.max (玻璃陶瓷)
      - FMZ (全鋯)
      - FMZ Ultra (高透多層鋯)
      - Lava (3M 全鋯)
      - Lava Plus (多層鋯)
      - Lava Esthetic (熒光鋯)
      - Calypso (高透鋯)
      請問您想選擇哪一種？"

用戶: "Calypso"
助手: [呼叫 validate_material(restoration_type="bridge", material_category="metal-free", material_subtype="calypso")]
      [返回: {valid: true}]
      [呼叫 search_products]
      
      "✅ 材料驗證通過！推薦以下產品..."
```

### 範例 2: 用戶選擇不相容材料
```
用戶: "我要做 veneer"
助手: "好的，請問牙位？"

用戶: "11"
助手: "收到，牙位 11。請問材料類別？PFM / Metal-Free / Full Cast"

用戶: "PFM"
助手: [呼叫 validate_material(restoration_type="veneer", material_category="pfm")]
      [返回: {valid: false, message: "veneer 不能使用 pfm...", allowed_categories: ["metal-free"]}]
      
      "抱歉，Veneer 不能使用 PFM。Veneer 必須使用全瓷材料以確保透光性。
      
      可用的材料類別：Metal-Free
      
      請問您想選擇 Metal-Free 嗎？"
```

---

## 關鍵要點總結

🔧 **工具決定一切** - 你不需要記住規則
📋 **兩步驟流程** - 先查詢，再驗證
✅ **信任工具結果** - 使用工具返回的資訊
🔄 **錯誤時重新引導** - 提供正確選項

記住：你是「工具使用專家」，不是「規則專家」！
"""

@app.get("/")
async def root():
    """API 首頁"""
    return {
        "message": "Dental Ordering API",
        "version": "1.0.0",
        "status": "running"
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """AI Agent 對話端點"""
    session_id = request.session_id
    user_msg = request.message
    
    # 初始化對話歷史
    if session_id not in conversations:
        conversations[session_id] = []
    
    # 加入用戶訊息
    conversations[session_id].append({
        "role": "user",
        "content": user_msg
    })
    
    # 呼叫 AI Agent（可能會多次迭代）
    max_iterations = 5
    tool_calls_log = []
    
    for iteration in range(max_iterations):
        # 呼叫 Azure OpenAI
        response = client.chat.completions.create(
            model=DEPLOYMENT_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                *conversations[session_id]
            ],
            tools=TOOLS,
            tool_choice="auto"
        )
        
        message = response.choices[0].message
        
        # 檢查 AI 是否想呼叫工具
        if message.tool_calls:
            # AI 決定要呼叫工具
            conversations[session_id].append({
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
            
            # 執行所有工具呼叫
            for tool_call in message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                # 記錄工具呼叫
                tool_calls_log.append({
                    "tool": function_name,
                    "arguments": function_args
                })
                
                # 執行工具
                function_response = execute_tool(function_name, function_args)
                
                # 將工具結果加入對話
                conversations[session_id].append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(function_response, ensure_ascii=False)
                })
            
            # 繼續下一次迭代
            continue
        
        else:
            # AI 不需要呼叫工具，直接回覆用戶
            assistant_msg = message.content
            
            conversations[session_id].append({
                "role": "assistant",
                "content": assistant_msg
            })
            
            return ChatResponse(
                reply=assistant_msg,
                tool_calls=tool_calls_log
            )
    
    # 如果達到最大迭代次數
    return ChatResponse(
        reply="抱歉，處理過程中遇到問題。",
        tool_calls=tool_calls_log
    )


@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """清除對話記錄"""
    if session_id in conversations:
        del conversations[session_id]
        return {"message": "Session deleted"}
    return {"message": "Session not found"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)