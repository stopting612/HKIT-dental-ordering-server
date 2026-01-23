
import boto3
from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import AzureOpenAI
from dotenv import load_dotenv
import os
import json
from typing import Optional, Dict, List, Annotated
from datetime import datetime
import time
from botocore.exceptions import ClientError

from models import CredentialsResponse
from tools import TOOLS, execute_tool
from order_manager import order_manager
from conversation_manager import conversation_manager, session_manager
from auth_middleware import get_current_user_id, verify_supabase_token, get_optional_user_id

from knowledge_base import kb_search
from transcribe_policy import TRANSCRIBE_POLICY

if kb_search is None:
    print("\n" + "="*60)
    print("⚠️  Warning: Knowledge Base not initialized")
    print("="*60)
    print("\nServer will start with limited functionality")
    print("To enable Knowledge Base, run diagnostics:")
    print("   python quick_diagnose.py")
    print("\nOr run full test:")
    print("   python test_aws_credentials.py")
    print("\n" + "="*60 + "\n")

# Load environment variables
load_dotenv()

# Initialize FastAPI
app = FastAPI(title="Dental Ordering AI Agent")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Azure OpenAI
client = AzureOpenAI(
    azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT'),
    api_key=os.getenv('AZURE_OPENAI_KEY'),
    api_version=os.getenv('AZURE_OPENAI_API_VERSION')
)

DEPLOYMENT_NAME = os.getenv('AZURE_OPENAI_DEPLOYMENT')

# In-Memory conversation storage (cache)
conversations: Dict[str, Dict] = {}

# ============================================================================
# IMPROVED SYSTEM PROMPT - NOW HANDLES ORDER MODIFICATIONS
# ============================================================================

# UPDATED SYSTEM PROMPT - WITH TOOTH POSITION VALIDATION

SYSTEM_PROMPT = """You are a professional dental order assistant. Your task is to help dentists place orders to dental laboratories.

## 🦷 Tooth Position Validation (FDI Notation System)

**CRITICAL: ALWAYS validate tooth positions FIRST before any other validation.**

### Valid Tooth Numbering (FDI Two-Digit System):

**Upper Jaw:**
- **Quadrant 1 (Upper Right / 右上)**: 18, 17, 16, 15, 14, 13, 12, 11
- **Quadrant 2 (Upper Left / 左上)**: 21, 22, 23, 24, 25, 26, 27, 28

**Lower Jaw:**
- **Quadrant 3 (Lower Left / 左下)**: 31, 32, 33, 34, 35, 36, 37, 38
- **Quadrant 4 (Lower Right / 右下)**: 41, 42, 43, 44, 45, 46, 47, 48

**Total: 32 permanent teeth**

### Invalid Tooth Numbers (Common Errors):

❌ **Position 9 or 0**: 19, 29, 39, 49, 10, 20, 30, 40
❌ **Quadrant 5-9**: 51, 52, 99, etc.
❌ **Single digit**: 1, 2, 3, etc.
❌ **Numbers outside range**: Any number < 11 or > 48 (except valid ranges)

### Tooth Validation Workflow:

```
Step 1: User provides tooth positions
Step 2: IMMEDIATELY call validate_tooth_positions(tooth_positions="...")
Step 3: If valid → Continue to next step
        If invalid → Inform user of error and ask for correction

Example (Valid):
User: "11 號牙"
AI: [Call validate_tooth_positions("11")]
Result: ✓ Valid - upper right central incisor
AI: "收到，11 號牙（右上中門牙）。請問修復類型？"

Example (Invalid):
User: "19 號牙"
AI: [Call validate_tooth_positions("19")]
Result: ✗ Invalid - position 9 doesn't exist
AI: "抱歉，19 不是有效的牙位編號。牙位範圍為：
     • 右上 (UR): 11-18
     • 左上 (UL): 21-28
     • 左下 (LL): 31-38
     • 右下 (LR): 41-48
     請重新提供正確的牙位編號。"
```

### For Bridges - Two-Step Validation:

1. **First**: Validate tooth positions (FDI numbers)
2. **Second**: Validate bridge rules (continuity, minimum 3 units)

```
User: "我要做 bridge，14 15 16"

Step 1: Call validate_tooth_positions("14,15,16")
Result: ✓ All valid FDI numbers

Step 2: Call validate_bridge("14,15,16")
Result: ✓ Continuous, 3 units, posterior position

AI: "好的，3 單位牙橋（14-15-16），後牙位置。請問材料類別？"
```

### Error Handling Examples:

**Invalid tooth number:**
```
User: "50 號牙"
AI: [validate_tooth_positions("50")]
Result: ✗ Quadrant 5 doesn't exist
AI: "抱歉，50 不在有效範圍內。牙科使用 FDI 編號系統，只有 4 個區域：
     1 (右上), 2 (左上), 3 (左下), 4 (右下)
     請提供 11-18, 21-28, 31-38, 或 41-48 範圍內的牙位。"
```

**Non-continuous bridge:**
```
User: "bridge 11, 13, 14"
AI: [validate_tooth_positions("11,13,14")] → ✓ Valid numbers
    [validate_bridge("11,13,14")] → ✗ Not continuous (missing 12)
AI: "牙橋的牙位必須連續（相鄰）。您提供的 11, 13, 14 缺少了 12。
     請提供連續的牙位，例如：11-12-13 或 13-14-15。"
```

**Too few units for bridge:**
```
User: "bridge 11, 12"
AI: [validate_tooth_positions("11,12")] → ✓ Valid numbers
    [validate_bridge("11,12")] → ✗ Only 2 units (need 3+)
AI: "牙橋需要至少 3 個單位。您提供了 2 個牙位。
     建議：增加牙位（如 11-12-13）或改用單顆牙冠。"
```

## Material Classification System
Materials have a **two-tier structure**:
1. **Material Category** (main category): PFM / Metal-Free / Full Cast
2. **Material Subtype** (specific material): Determined by the validate_material tool

⚠️ **Important: You don't need to know which materials are available. All rules are determined by the validate_material tool.**

## 🆕 HANDLING ORDER MODIFICATIONS

**When the user wants to change previous choices:**

### Change Detection Keywords:
- "改" (change), "換" (switch), "唔要" (don't want), "唔係" (not)
- "change", "switch", "actually", "instead"
- "我想改..." (I want to change...)
- "唔係 crown，係 bridge" (Not crown, it's bridge)

### Modification Rules:

1. **Restoration Type Change (crown ↔ bridge ↔ veneer)**
   - When user changes restoration type → **RESET ALL related fields**
   - Clear: material_category, material_subtype, product_code, product_name
   - Keep: patient_name (if already collected)
   - **Re-validate tooth positions if changing to/from bridge**
   - Restart workflow from step 3 (material selection)

2. **Material Change**
   - When user changes material → **RESET product selection**
   - Clear: product_code, product_name
   - Re-run: search_products with new material
   - Keep: restoration_type, tooth_positions

3. **Tooth Position Change**
   - **ALWAYS re-validate with validate_tooth_positions first**
   - Update: tooth_positions
   - If restoration type is bridge → re-validate with validate_bridge
   - Keep: all other fields unless validation fails

4. **Product Selection Change**
   - Update: product_code, product_name
   - Keep: all other fields

### Modification Response Pattern:

```
User: "唔係 crown，我要做 bridge" (Not crown, I want bridge)

AI Reasoning:
- User is changing restoration_type from 'crown' to 'bridge'
- This is a major change → need to reset workflow
- Need to re-validate tooth positions for bridge rules

AI Response:
"明白，改為牙橋。之前的材料選擇需要重新確認。
目前資料：
- 修復類型：bridge ✅ (已更新)
- 牙位：14, 15, 16 [正在驗證...]

[Call validate_bridge("14,15,16")]

- 材料：[需要重新選擇]

請問要用什麼材料？PFM / Metal-Free / Full Cast？"
```

### Important Principles for Modifications:

✅ **DO:**
- Explicitly acknowledge the change: "好的，改為..." (OK, changing to...)
- List what was changed vs what remains
- Clear dependent fields (see dependency tree below)
- Restart validation for affected fields
- **Re-validate tooth positions if they change or restoration type changes**

❌ **DON'T:**
- Silently overwrite without acknowledgment
- Keep invalid combinations (e.g., crown material for bridge)
- Ask for information that's already been provided and is still valid
- Skip tooth position validation

### Field Dependency Tree:
```
restoration_type (root)
├── tooth_positions → [ALWAYS validate with validate_tooth_positions]
│   └── (if bridge) → validate_bridge
├── material_category
│   └── material_subtype
│       └── product selection
│           ├── product_code
│           └── product_name
├── shade
└── patient_name
```

**When a parent changes, all children must be reset and re-collected.**

## Order Collection Workflow (Strict Sequence)

1. Confirm restoration type (Crown/Bridge/Veneer/Inlay/Onlay)
2. **Collect tooth positions → VALIDATE with validate_tooth_positions**
3. 【If Bridge】**Validate bridge rules** → Call validate_bridge(tooth_positions="...")
4. Ask for material category → "What material category? PFM / Metal-Free / Full Cast"
5. Query available subtypes → Call validate_material(...) → List options
6. Collect material subtype → After user selects, call validate_material to verify
7. **Search products** → Call search_products(...) → Return product list
8. **Let user select product (IMPORTANT!)**
   - If 2+ products found → **Must list all and wait for user selection**
   - If only 1 product → Can proceed directly
   - After selection, remember product_code and product_name
9. Collect shade (default A2)
10. Collect patient name (final step)
11. Show order summary → Ask for confirmation
12. Confirm order

## Product Selection Rules (Critical)

### When search_products returns multiple products:

❌ **NEVER DO:**
- Auto-select the first product
- Jump directly to confirmation stage
- Make decisions for the user
- Call store_patient_name before product selection

✅ **MUST DO:**
1. **List all product options** with clear numbering (1, 2, 3...)
2. **Show key info for each product**:
   - Product code
   - Material name (if different)
   - Price
   - Production time
3. **Explicitly ask**: "Which product would you like? (Reply with number, product code, or material name)"
4. **Stop and wait for user response** - Don't continue to shade or patient name
5. After user selects, confirm selection and record product_code and product_name
6. Then continue to next step (shade)

## Key Distinction: Material vs Patient Name vs Product Selection

### Material-Related Terms (NEVER patient names):
- Palladium-based, High-noble, Semi-precious, Non-precious
- Emax, IPS e.max, Zirconia, FMZ
- PFM, Metal-free, Full-cast
- Gold, Titanium, Ceramic
- NP, HP, SP, Ti, Zr (material abbreviations)

### Product Selection Responses (NOT patient names):
- "1", "2", "3", "first one", "second one"
- "1100,9032", "3630" (product codes)
- "Palladium-based" (when selecting product)

### When to Call store_patient_name:

✅ **ONLY call in these situations:**
- Product selection is complete
- Shade has been collected
- You explicitly asked "Patient name?"
- User replied with a full person's name

❌ **NEVER call in these situations:**
- User is selecting material
- User is selecting product
- User said material abbreviation (NP, HP, SP)
- User said shade (A2, B1)
- User said product code

## Handling Price and Product Queries

**When user asks about price or product info:**
- ✅ Must use search_products tool
- ✅ Show found products and prices to user
- ✅ If multiple products found, follow product selection workflow

## Search Strategy When Searching Products

When you call the search_products tool, **you need to build a semantically rich query string**.

**Query Construction Principles:**
1. **Include complete context**: restoration type + material info + applicable position
2. **Use descriptive vocabulary**: Not just category names, add material characteristics
3. **Mix Chinese and English**: Improve recall rate
4. **Consider user needs**: If user mentions aesthetics, strength, etc., add to query

## Data Collection Rules

Remember the following information:
- restoration_type, tooth_positions, material_category, material_subtype
- product_code, product_name, shade, patient_name
- bridge_span, position_type

**Collection Sequence (Strictly Follow):**
```
1. restoration_type (restoration type)
2. tooth_positions (tooth positions) → VALIDATE
3. [if bridge] validate_bridge
4. material_category (material category)
5. material_subtype (material subtype)
6. search_products (search products)
7. product_selection (product selection - must wait if multiple products)
8. product_code & product_name (record selection)
9. shade (shade)
10. patient_name (patient name - final step)
```

**Before completing step 10, absolutely do not enter confirmation stage!**

## Order Summary Format
```
📋 Order Summary
Restoration Type: {restoration_type}
Tooth Position: {tooth_positions} ← Validated FDI numbers
Material: {material_category} ({material_subtype})
Product: {product_name} (Code: {product_code})
Shade: {shade}
Patient: {patient_name}

Please confirm the above information is correct? (Reply "confirm" or "modify")
```

## Important Principles

1. **Tool Priority** - All rules determined by tools
2. **Tooth Validation First** - ALWAYS validate tooth positions before other checks
3. **Two-Step Process** - Query first, then validate
4. **Trust Tool Results** - Use information returned by tools
5. **Collect in Sequence** - Don't skip steps, strictly follow 1→2→...→10 sequence
6. **Remember Information** - Remember each piece of collected information
7. **Clear Summary** - Show complete summary before confirmation
8. **Must Use Tool for Price Queries** - Must call search_products when querying prices
9. **Context Judgment** - Judge user input intent based on conversation progress
10. 🆕 **Wait for Product Selection** - Must stop and wait for user selection when multiple products
11. 🆕 **Name Collection Last** - Only collect patient name after product and shade are confirmed
12. 🆕 **Handle Modifications Gracefully** - Acknowledge changes, reset dependent fields, restart validation
13. 🆕 **Validate Tooth Positions Always** - Never skip tooth position validation, even for modifications

## Common Mistakes to Avoid

❌ **Wrong: Skip tooth validation**
```
User: "19 號牙"
AI: [直接繼續] 請問材料？  ← Wrong! Should validate first
```

✅ **Correct: Always validate**
```
User: "19 號牙"
AI: [Call validate_tooth_positions("19")]
Result: ✗ Invalid position 9
AI: "抱歉，19 不是有效牙位..."  ← Correct!
```

❌ **Wrong: Accept invalid bridge**
```
User: "bridge 11, 13"
AI: [沒驗證連續性] 好的，請問材料？  ← Wrong!
```

✅ **Correct: Validate continuity**
```
User: "bridge 11, 13"
AI: [validate_tooth_positions] → ✓
    [validate_bridge] → ✗ Not continuous
AI: "牙位必須連續，11, 13 缺少 12..."  ← Correct!
```
"""

# Pydantic Models
class ChatRequest(BaseModel):
    session_id: str
    message: str
    # user_id removed - now comes from JWT token


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
async def chat(
    request: ChatRequest, 
    background_tasks: BackgroundTasks,
    user_id: Annotated[str, Depends(get_current_user_id)]  # JWT authentication required
):
    """AI Agent conversation endpoint (with encrypted storage)"""
    session_id = request.session_id
    user_msg = request.message
    # user_id now comes from authenticated JWT token
    
    start_time = time.time()
    
    # ===== 1. Initialize conversation history (In-Memory) =====
    if session_id not in conversations:
        conversations[session_id] = {
            'messages': [],
            'order_data': {}
        }
        
        # 🆕 Create session in database
        session_manager.create_session(
            session_id=session_id,
            user_id=user_id,
            session_type='order'
        )
    
    # ===== 2. Add user message to in-memory =====
    conversations[session_id]['messages'].append({
        "role": "user",
        "content": user_msg
    })
    
    # ===== 3. 🔐 Background save user message (encrypted, non-blocking) =====
    background_tasks.add_task(
        conversation_manager.log_message,
        session_id=session_id,
        role='user',
        content=user_msg,
        user_id=user_id
    )
    
    # ===== 4. Check if order confirmation =====
    if '確認' in user_msg or 'confirm' in user_msg.lower() or 'yes' in user_msg.lower():
        order_data = conversations[session_id].get('order_data', {})
        
        required_fields = ['restoration_type', 'tooth_positions', 'material_category', 'material_subtype', 'patient_name']
        
        if all(field in order_data and order_data[field] for field in required_fields):
            print("\n" + "="*60)
            print("📋 Preparing to create order")
            print("="*60)
            for key, value in order_data.items():
                print(f"   {key}: {value}")
            print("="*60 + "\n")
            
            # Create order
            created_order = order_manager.create_order(
                session_id=session_id,
                user_id=user_id,
                order_data=order_data
            )
            
            if created_order:
                order_number = created_order['order_number']
                order_id = created_order['id']
                
                # End session
                session_manager.end_session(
                    session_id=session_id,
                    status='completed',
                    order_id=order_id
                )
                
                # Update all conversations, link to order
                background_tasks.add_task(
                    _link_conversations_to_order,
                    session_id,
                    order_id
                )
                
                # Clear order data
                conversations[session_id]['order_data'] = {}
                
                # Confirmation message
                confirmation_msg = f"""✅ Order confirmed and submitted to system!

📋 **Order Number**: {order_number}

Order Details:
- Restoration Type: {order_data.get('restoration_type')}
- Tooth Position: {order_data.get('tooth_positions')}
- Material: {order_data.get('material_category')} ({order_data.get('material_subtype')})
- Product: {order_data.get('product_name', 'N/A')} (Code: {order_data.get('product_code', 'N/A')})
- Shade: {order_data.get('shade', 'A2')}
- Patient: {order_data.get('patient_name')}

Laboratory will receive notification and start production.

---
For new order, say "new order"."""
                
                conversations[session_id]['messages'].append({
                    "role": "assistant",
                    "content": confirmation_msg
                })
                
                # 🔐 Save confirmation message
                background_tasks.add_task(
                    conversation_manager.log_message,
                    session_id=session_id,
                    role='assistant',
                    content=confirmation_msg,
                    user_id=user_id,
                    order_id=order_id
                )
                
                # Update session statistics
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
                error_msg = "❌ Order creation failed, please check network connection or try again later."
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
            error_msg = f"⚠️ Order data incomplete, missing: {', '.join(missing_fields)}. Please provide complete information before confirming."
            
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
    
    # ===== 5. Normal AI Agent flow (ReAct Loop) =====
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
            # Handle Azure OpenAI content filter errors
            error_msg = str(e)
            if 'content_filter' in error_msg or 'ResponsibleAIPolicyViolation' in error_msg:
                print(f"⚠️  Azure OpenAI content filter triggered: {error_msg[:200]}")
                
                # Give user friendly response
                friendly_msg = "Sorry, system detected possible sensitive content. Please describe in another way, or directly provide specific product code and patient information."
                
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
                # Other errors, re-raise
                raise
        
        message = response.choices[0].message
        
        # Check if AI wants to call tools
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
            
            # Execute all tools
            for tool_call in message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                print(f"🔧 Calling tool: {function_name}")
                print(f"   Arguments: {json.dumps(function_args, ensure_ascii=False)}")
                
                tool_calls_log.append({
                    "tool": function_name,
                    "arguments": function_args
                })
                
                # Execute tool
                function_response = execute_tool(function_name, function_args)
                
                print(f"   Result: {json.dumps(function_response, ensure_ascii=False)[:200]}...")
                
                # 🔐 Log tool call (encrypted)
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
                
                # Extract order data with smart update logic
                _extract_order_data(
                    session_id,
                    function_name,
                    function_args,
                    function_response
                )
                
                # Add tool result
                conversations[session_id]['messages'].append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(function_response, ensure_ascii=False)
                })
            
            continue
        
        else:
            # AI doesn't need to call tools
            assistant_msg = message.content
            
            conversations[session_id]['messages'].append({
                "role": "assistant",
                "content": assistant_msg
            })
            
            # Calculate response time
            response_time = int((time.time() - start_time) * 1000)
            
            # 🔐 Save assistant message (encrypted)
            background_tasks.add_task(
                conversation_manager.log_message,
                session_id=session_id,
                role='assistant',
                content=assistant_msg,
                user_id=user_id,
                response_time_ms=response_time
            )
            
            # Update session statistics
            background_tasks.add_task(
                session_manager.update_session_activity,
                session_id
            )
            
            # Extract order data from message
            _extract_order_data_from_message(session_id, user_msg, assistant_msg)
            
            return ChatResponse(
                reply=assistant_msg,
                tool_calls=tool_calls_log,
                state=conversations[session_id].get('order_data', {})
            )
    
    return ChatResponse(
        reply="Sorry, encountered an issue during processing.",
        tool_calls=tool_calls_log
    )


@app.post("/api/aws/credentials", response_model=CredentialsResponse)
async def get_temporary_credentials():
    """
    Generate AWS temporary credentials for Flutter App using AssumeRole
    Valid for: 1 hour
    """
    try:
        AWS_REGION = os.getenv("AWS_TRANSCRIBE_REGION", "ap-southeast-1")
        
        # Create STS client
        sts_client = boto3.client(
            'sts',
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=AWS_REGION
        )
        
        # Define inline policy for Transcribe access
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "transcribe:StartStreamTranscription",
                        "transcribe:StartStreamTranscriptionWebSocket"
                    ],
                    "Resource": "*"
                }
            ]
        }
        
        # Use AssumeRole instead of GetFederationToken
        # Replace 'YOUR_ROLE_ARN' with the actual role ARN you'll create
        response = sts_client.assume_role(
            RoleArn=os.getenv("AWS_TRANSCRIBE_ROLE_ARN"),  # Add this to .env
            RoleSessionName='DentalAppSession',
            Policy=json.dumps(policy),
            DurationSeconds=3600  # 1 hour
        )
        
        credentials = response['Credentials']
        
        return CredentialsResponse(
            access_key_id=credentials['AccessKeyId'],
            secret_access_key=credentials['SecretAccessKey'],
            session_token=credentials['SessionToken'],
            expiration=credentials['Expiration'].isoformat(),
            region=AWS_REGION
        )
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        
        raise HTTPException(
            status_code=500,
            detail=f"AWS STS Error [{error_code}]: {error_message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )


# ============================================================================
# IMPROVED HELPER FUNCTIONS - NOW HANDLES ORDER MODIFICATIONS
# ============================================================================

def _extract_order_data(session_id: str, tool_name: str, tool_args: dict, tool_result: dict):
    """
    Extract order data from tool calls
    
    🆕 Smart Update Logic:
    - Detects field changes
    - Resets dependent fields when parent changes
    - Maintains data consistency
    """
    order_data = conversations[session_id]['order_data']
    
    if tool_name == "validate_bridge":
        if tool_result.get('valid'):
            # Check if restoration type changed
            old_type = order_data.get('restoration_type')
            if old_type and old_type != 'bridge':
                print(f"   ⚠️  Restoration type changed: {old_type} → bridge")
                print(f"   🔄 Resetting dependent fields...")
                # Reset all dependent fields
                _reset_dependent_fields(order_data, 'restoration_type')
            
            order_data['restoration_type'] = 'bridge'
            order_data['tooth_positions'] = tool_args.get('tooth_positions')
            order_data['bridge_span'] = tool_result.get('bridge_span')
            order_data['position_type'] = tool_result.get('position_type')
    
    elif tool_name == "validate_material":
        if tool_result.get('valid'):
            new_restoration_type = tool_args.get('restoration_type')
            new_material_category = tool_result.get('material_category')
            new_material_subtype = tool_result.get('material_subtype')
            
            # Check if restoration type changed
            old_type = order_data.get('restoration_type')
            if old_type and old_type != new_restoration_type:
                print(f"   ⚠️  Restoration type changed: {old_type} → {new_restoration_type}")
                _reset_dependent_fields(order_data, 'restoration_type')
            
            # Check if material category changed
            old_category = order_data.get('material_category')
            if old_category and old_category != new_material_category:
                print(f"   ⚠️  Material category changed: {old_category} → {new_material_category}")
                _reset_dependent_fields(order_data, 'material_category')
            
            # Update fields
            order_data['restoration_type'] = new_restoration_type
            order_data['material_category'] = new_material_category
            order_data['material_subtype'] = new_material_subtype
    
    elif tool_name == "search_products":
        # Update if not already set
        if not order_data.get('restoration_type'):
            order_data['restoration_type'] = tool_args.get('restoration_type')
        if not order_data.get('material_category'):
            order_data['material_category'] = tool_args.get('material_category')
        if not order_data.get('material_subtype'):
            order_data['material_subtype'] = tool_args.get('material_subtype')
        
        # Only auto-fill product if exactly 1 product found
        if tool_result.get('found') and tool_result.get('products'):
            products = tool_result['products']
            if len(products) == 1:
                first_product = products[0]
                if not order_data.get('product_code'):
                    order_data['product_code'] = first_product.get('product_code')
                if not order_data.get('product_name'):
                    order_data['product_name'] = first_product.get('material_name', 'N/A')
                print(f"   ℹ️  Auto-selected single product: {first_product.get('product_code')}")
    
    elif tool_name == "store_patient_name":
        if tool_result.get('success'):
            patient_name = tool_result.get('patient_name')
            if patient_name:
                order_data['patient_name'] = patient_name
                print(f"   ✅ Order data updated: patient_name = '{patient_name}'")


def _reset_dependent_fields(order_data: dict, changed_field: str):
    """
    Reset fields that depend on the changed field
    
    Dependency Tree:
    restoration_type (root)
    ├── material_category
    │   └── material_subtype
    │       └── product_code, product_name
    └── tooth_positions (for bridge only)
    
    shade and patient_name are independent and preserved
    """
    if changed_field == 'restoration_type':
        # Reset everything except patient name
        fields_to_clear = [
            'material_category', 'material_subtype',
            'product_code', 'product_name',
            'bridge_span', 'position_type'
        ]
        for field in fields_to_clear:
            if field in order_data:
                old_value = order_data.pop(field)
                print(f"      Cleared: {field} = {old_value}")
    
    elif changed_field == 'material_category':
        # Reset material subtype and products
        fields_to_clear = [
            'material_subtype',
            'product_code', 'product_name'
        ]
        for field in fields_to_clear:
            if field in order_data:
                old_value = order_data.pop(field)
                print(f"      Cleared: {field} = {old_value}")
    
    elif changed_field == 'material_subtype':
        # Reset only products
        fields_to_clear = ['product_code', 'product_name']
        for field in fields_to_clear:
            if field in order_data:
                old_value = order_data.pop(field)
                print(f"      Cleared: {field} = {old_value}")


def _extract_order_data_from_message(session_id: str, user_msg: str, assistant_msg: str):
    """Extract order data from conversation messages"""
    order_data = conversations[session_id]['order_data']
    user_msg_lower = user_msg.lower()
    
    import re
    
    # Extract restoration type
    if 'crown' in user_msg_lower or '牙冠' in user_msg:
        if not order_data.get('restoration_type'):
            order_data['restoration_type'] = 'crown'
    
    # Extract tooth positions
    if order_data.get('restoration_type') == 'crown':
        numbers = re.findall(r'\b([1-4][1-8])\b', user_msg)
        if numbers and not order_data.get('tooth_positions'):
            order_data['tooth_positions'] = numbers[0]
    
    # Extract product code
    codes = re.findall(r'\b(\d{4})\b', user_msg)
    if codes:
        order_data['product_code'] = codes[0]
    
    # Extract shade
    shade_match = re.search(r'\b([A-D][1-4](?:\.\d)?)\b', user_msg, re.IGNORECASE)
    if shade_match:
        order_data['shade'] = shade_match.group(1).upper()


def _link_conversations_to_order(session_id: str, order_id: int):
    """Link all conversations to order"""
    try:
        from supabase import create_client
        supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_ROLE_KEY'))
        
        supabase.table('conversations')\
            .update({'order_id': order_id})\
            .eq('session_id', session_id)\
            .execute()
        
        print(f"✅ Conversations linked to order: {session_id} → Order #{order_id}")
    except Exception as e:
        print(f"⚠️  Failed to link conversations: {e}")


# ===== Other API Endpoints =====

@app.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """Clear conversation history"""
    if session_id in conversations:
        del conversations[session_id]
        return {"message": f"Session {session_id} cleared"}
    return {"message": f"Session {session_id} not found"}


@app.get("/session/{session_id}")
async def get_session(session_id: str):
    """View conversation history (in-memory)"""
    if session_id in conversations:
        return conversations[session_id]
    return {"message": f"Session {session_id} not found"}


@app.get("/conversations/{session_id}")
async def get_conversation_history(
    session_id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],  # JWT authentication required
    decrypt: bool = True
):
    """
    Query conversation history (from database, auto-decrypt)
    
    Requires permission check: users can only view their own conversations
    """
    try:
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
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/orders/recent")
async def get_recent_orders(
    user_id: Annotated[str, Depends(get_current_user_id)],  # JWT authentication required
    limit: int = 10
):
    """Get recent orders for authenticated user"""
    orders = order_manager.get_recent_orders(limit=limit, user_id=user_id)
    return {"count": len(orders), "orders": orders}


@app.get("/api/users/me/orders")
async def get_user_orders(
    user_id: Annotated[str, Depends(get_current_user_id)],  # JWT authentication required
    limit: int = 50
):
    """
    Get all orders for authenticated user
    
    Returns all orders belonging to the authenticated user with pagination support.
    """
    orders = order_manager.get_recent_orders(limit=limit, user_id=user_id)
    return {
        "user_id": user_id,
        "count": len(orders),
        "orders": orders
    }


@app.get("/api/users/me/sessions")
async def get_user_sessions(
    user_id: Annotated[str, Depends(get_current_user_id)],  # JWT authentication required
    limit: int = 50,
    status: Optional[str] = None
):
    """
    Get all sessions for authenticated user
    
    Args:
        limit: Maximum number of sessions to return (default: 50)
        status: Filter by status (active, completed, cancelled) - optional
    
    Returns all conversation sessions belonging to the authenticated user.
    """
    print(f"\n{'='*60}")
    print(f"📋 GET /api/users/me/sessions")
    print(f"{'='*60}")
    print(f"User ID: {user_id}")
    print(f"Limit: {limit}")
    print(f"Status filter: {status}")
    
    sessions = session_manager.get_sessions_by_user(
        user_id=user_id,
        limit=limit,
        status=status
    )
    
    print(f"✅ Found {len(sessions)} sessions for user {user_id}")
    if sessions:
        print(f"First session: {sessions[0].get('session_id', 'N/A')}")
    print(f"{'='*60}\n")
    
    return {
        "user_id": user_id,
        "count": len(sessions),
        "sessions": sessions
    }


@app.delete("/api/sessions/{session_id}")
async def delete_session_with_conversations(
    session_id: str,
    user_id: Annotated[str, Depends(get_current_user_id)]  # JWT authentication required
):
    """
    Delete session and all related conversations
    
    Requires authentication and ownership verification.
    Deletes both the session and all conversation messages associated with it.
    """
    success = session_manager.delete_session(
        session_id=session_id,
        user_id=user_id
    )
    
    if not success:
        raise HTTPException(
            status_code=404,
            detail="Session not found or you don't have permission to delete it"
        )
    
    # Also clear from in-memory cache if exists
    if session_id in conversations:
        del conversations[session_id]
    
    return {
        "message": f"Session {session_id} and all related conversations deleted successfully",
        "session_id": session_id
    }


@app.get("/orders/{order_number}")
async def get_order(
    order_number: str,
    auth_data: Annotated[dict, Depends(verify_supabase_token)]  # JWT authentication required
):
    """Query specific order (with ownership verification)"""
    order = order_manager.get_order(order_number)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Verify ownership
    if order.get('user_id') != auth_data['user_id']:
        raise HTTPException(status_code=403, detail="You don't have permission to access this order")
    
    return order
    return {"error": "Order not found"}


# Debug endpoints
from material_normalizer import get_cache_stats, clear_cache

@app.get("/debug/cache-stats")
async def cache_stats():
    """View material normalization cache statistics"""
    return get_cache_stats()


@app.post("/debug/clear-cache")
async def clear_normalization_cache():
    """Clear material normalization cache"""
    clear_cache()
    return {"message": "Cache cleared"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)