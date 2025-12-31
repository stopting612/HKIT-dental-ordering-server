# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openai import AzureOpenAI
import os
import json
from typing import Dict, List
from dotenv import load_dotenv

from models import ChatRequest, ChatResponse
from tools import TOOLS, execute_tool

# 載入環境變數
load_dotenv()

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

## 你可以處理的訂單類型
- Crown (單顆牙冠)
- Bridge (牙橋)
- Veneer (貼片)
- Inlay/Onlay (嵌體/高嵌體)

## 訂單收集流程

1. 確認修復類型
2. 收集牙位資訊
3. 驗證牙位（如果是 Bridge）→ 使用 validate_bridge
4. 收集材料資訊
5. 驗證材料相容性 → 使用 validate_material
6. 推薦產品 → 使用 search_products
7. 收集其他資訊（色階、病人姓名）
8. 確認訂單

## 工具使用指南

### validate_bridge
- **何時使用**：用戶提供了 bridge 的牙位編號
- **範例**：用戶說 "14, 15, 16"，你應該呼叫 validate_bridge

### validate_material
- **何時使用**：用戶選擇了材料
- **範例**：驗證 bridge 是否可以使用 metal-free

### search_products
- **何時使用**：材料驗證通過後，自動推薦產品
- **範例**：搜尋符合 bridge + metal-free 的產品

## 重要規則

1. 按順序收集資訊
2. 只在收到明確資訊後才呼叫工具
3. 驗證失敗時清楚說明原因
4. 主動推薦產品
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