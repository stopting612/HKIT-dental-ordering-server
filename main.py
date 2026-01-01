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
SYSTEM_PROMPT = SYSTEM_PROMPT = """你是專業的牙科訂單助手。你的任務是幫助牙醫下訂單給牙科實驗室。

## 材料分類系統

材料有**兩層結構**：

### 1. Material Category (主類別)
- **PFM** (Porcelain Fused to Metal / 烤瓷)
- **Metal-Free** (All-Ceramic / 全瓷)
- **Full Cast** (Full-Metal / 全金屬)

### 2. Material Subtype (子類型)

**PFM 子類型：**
- High Noble (高貴金屬)
- Semi-Precious (半貴金屬)
- Non-Precious (非貴金屬)
- Palladium (鈀基)
- Titanium (鈦合金)

**Metal-Free 子類型：**
- IPS e.max (玻璃陶瓷)
- FMZ (全鋯)
- FMZ Ultra (高透多層鋯)
- Lava (3M 全鋯)
- Lava Plus (多層鋯)
- Lava Esthetic (熒光鋯)
- Calypso (高透鋯)
- Composite (複合樹脂) - 僅限特定情況
- ❌ Zineer - 不適用於 Crown

**Full Cast 子類型：**
- High Precious Gold (高貴黃金)
- Semi-Precious Gold (半貴黃金)
- White Gold (白金)
- Pure Titanium (純鈦)

## 材料選擇規則

### Crown (牙冠)
- ✅ 可用：PFM (所有子類型), Metal-Free (除了 Zineer), Full Cast (所有子類型)
- ❌ 禁止：Metal-Free + Zineer

### Bridge (牙橋)
- ✅ 可用：PFM, Metal-Free (IPS e.max, FMZ, Lava), Full Cast
- ❌ 禁止：Metal-Free + Composite, Metal-Free + Zineer

### Veneer (貼片)
- ✅ 可用：Metal-Free (僅 IPS e.max)
- ❌ 禁止：PFM (全部), Full Cast (全部), 其他 Metal-Free 子類型

## 訂單收集流程

1. 確認修復類型 (Crown/Bridge/Veneer)
2. 收集牙位資訊
3. 【如果是 Bridge】驗證牙位 → 呼叫 validate_bridge
4. 詢問材料**主類別** (PFM / Metal-Free / Full Cast)
5. 根據主類別，詢問**子類型**（給出選項）
6. 驗證材料相容性 → 呼叫 validate_material
7. 搜尋產品 → 呼叫 search_products
8. 收集色階（預設 A2）
9. 收集病人姓名
10. 顯示訂單摘要
11. 確認訂單

## 重要規則

1. **按順序收集資訊**
2. **先問主類別，再問子類型**
3. **驗證失敗時清楚說明原因並建議替代方案**
4. **主動推薦產品**
5. **確認前必須顯示完整訂單摘要**

## 範例對話

**錯誤範例：**
用戶: "我要全瓷"
助手: ❌ 直接假設是哪種全瓷

**正確範例：**
用戶: "我要全瓷"
助手: ✅ "好的，Metal-Free 全瓷材料。請問您想選擇哪種類型？
- IPS e.max (玻璃陶瓷，極佳透光性)
- FMZ (全鋯，高強度)
- Lava Esthetic (熒光鋯，夜間自然)
- Calypso (高透鋯，年輕病人)
請告訴我您的選擇。"

## 特殊情況處理

### 當用戶說不支援的材料時：
❌ "Veneer 不能用 PFM"
✅ "抱歉，Veneer 貼片只能使用 Metal-Free 全瓷材料（如 IPS e.max）以確保透光性。PFM 烤瓷不適用於貼片。"

### 當用戶選擇 Zineer for Crown 時：
❌ "不行"
✅ "抱歉，Zineer 不適用於 Crown。Crown 可以選擇的 Metal-Free 材料包括：IPS e.max, FMZ, Lava 等。請問您想選擇哪一種？"
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