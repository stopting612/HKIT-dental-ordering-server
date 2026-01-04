# tools.py
from rules import validate_bridge_positions, validate_material_compatibility
from knowledge_base import kb_search, search_products
from material_normalizer import normalize_material
from typing import Dict, Any
import re
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "validate_bridge",
            "description": """驗證牙橋牙位的連續性和跨度。

【何時使用】
當用戶提供了 bridge 的牙位編號時。

【範例】
用戶: "14, 15, 16" → 立即呼叫 validate_bridge(tooth_positions="14,15,16")
用戶: "13到15" → 立即呼叫 validate_bridge(tooth_positions="13,14,15")

【不要使用】
用戶只說 "我要 bridge"（還沒提供牙位）
""",
            "parameters": {
                "type": "object",
                "properties": {
                    "tooth_positions": {
                        "type": "string",
                        "description": "牙位編號，用逗號分隔。例如：14,15,16"
                    }
                },
                "required": ["tooth_positions"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "validate_material",
            "description": """驗證材料相容性或查詢可用材料列表。

這個工具有兩種使用模式：

【模式 1: 查詢可用材料】
當用戶選擇了材料類別，但還沒選擇子類型時使用。
- 不提供 material_subtype 參數（留空）
- 工具會返回該組合下所有可用的子類型
- 範例：
  用戶: "Metal-Free"
  → validate_material(restoration_type="bridge", material_category="metal-free")
  → 返回: {valid: true, query_mode: true, allowed_subtypes: [...]}
  → 你列出這些選項給用戶選擇

【模式 2: 驗證特定材料】
當用戶選擇了具體的材料子類型時使用。
- 提供完整的 material_subtype 參數
- 工具會驗證該材料是否可用
- 範例：
  用戶: "Calypso"
  → validate_material(restoration_type="bridge", material_category="metal-free", material_subtype="calypso")
  → 返回: {valid: true} 或 {valid: false, allowed_subtypes: [...]}

【重要】
- 所有材料規則由工具決定，不要自己判斷
- 驗證失敗時，工具會返回正確的選項列表
- 使用工具返回的資訊回應用戶
""",
            "parameters": {
                "type": "object",
                "properties": {
                    "restoration_type": {
                        "type": "string",
                        "description": "修復類型",
                        "enum": ["crown", "bridge", "veneer", "inlay", "onlay"]
                    },
                    "material_category": {
                        "type": "string",
                        "description": "材料主類別",
                        "enum": ["pfm", "metal-free", "full-cast"]
                    },
                    "material_subtype": {
                        "type": "string",
                        "description": "材料子類型（可選）。如果不提供，工具會返回所有可用的子類型列表"
                    },
                    "bridge_span": {
                        "type": "integer",
                        "description": "牙橋跨度（如果是 bridge）"
                    }
                },
                "required": ["restoration_type", "material_category"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": """搜尋產品目錄並返回產品資訊（包括產品名稱、代碼、價格、製作時間等）。

**何時使用此工具：**
1. 用戶詢問產品資訊（例如：「有什麼 emax 產品？」）
2. 用戶詢問價格（例如：「emax 多少錢？」「全瓷冠價格？」）
3. 用戶詢問製作時間（例如：「要做多久？」）
4. 需要推薦具體產品給用戶選擇
5. 驗證材料後，需要展示可用產品

**重要：**
- 這是唯一能查詢產品價格和詳細資訊的工具
- 必須在收集完 restoration_type, material_category, material_subtype 後呼叫
- 返回的產品包含：產品名稱、代碼、價格、製作時間、技術規格等""",
            "parameters": {
                "type": "object",
                "properties": {
                    "restoration_type": {
                        "type": "string",
                        "enum": ["crown", "bridge", "veneer", "inlay", "onlay"],
                        "description": "修復類型"
                    },
                    "material_category": {
                        "type": "string",
                        "enum": ["pfm", "metal-free", "full-cast"],
                        "description": "材料主類別"
                    },
                    "material_subtype": {
                        "type": "string",
                        "description": "材料子類型（例如：emax, fmz, non-precious, semi-precious 等）"
                    }
                },
                "required": ["restoration_type", "material_category", "material_subtype"]
            }
        }
    },
{
    "type": "function",
    "function": {
        "name": "store_patient_name",
        "description": """儲存病人姓名到訂單資料。

⚠️ **重要：只在收集病人姓名時呼叫，不要把材料名稱誤認為病人姓名！**

**何時呼叫：**
- ✅ 已收集完：restoration_type, tooth_positions, material, product, shade
- ✅ 現在正在詢問病人姓名
- ✅ 用戶提供的是人名（如：陳大明、John Smith、Mary Wong）

**何時不要呼叫：**
- ❌ 用戶說的是材料名稱（如：Palladium-based, Emax, Zirconia）
- ❌ 用戶說的是產品代碼（如：1100, 3630）
- ❌ 還在收集材料或產品資訊階段

**範例：**

正確 ✅:
- 上下文：已收集完材料和產品，正在問「請問病人姓名？」
- 用戶說："陳大明" 
- 動作：呼叫 store_patient_name(patient_name="陳大明")

錯誤 ❌:
- 上下文：剛搜尋完產品，正在選擇材料
- 用戶說："Palladium-based"
- 動作：這是在選擇材料，**不要呼叫 store_patient_name**

**只儲存純粹的姓名，不包含任何前綴。**
""",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_name": {
                    "type": "string",
                    "description": "病人的姓名（純粹的人名，不是材料名稱或產品代碼）"
                }
            },
            "required": ["patient_name"]
        }
    }
}
]

def store_patient_name(patient_name: str) -> Dict[str, Any]:
    """
    儲存病人姓名到訂單資料，並進行嚴格驗證以避免誤判

    主要防呆目標：
    - 材料相關詞彙/縮寫（NP, HP, SP, Zr, Ti...）
    - 色階格式（A1, A2, B1, BL2, 0M1...）
    - 產品代碼（4位數字）
    - 過短、無意義、純數字等不合理姓名

    Args:
        patient_name: 用戶提供的姓名字串（應由 LLM 提取）

    Returns:
        包含 success, message, patient_name 等欄位的字典
    """
    print(f"\n📝 store_patient_name 被呼叫，原始輸入: '{patient_name}'")

    # 1. 基本清理
    cleaned = patient_name.strip()

    # 移除常見前綴/後綴（中英文混雜）
    prefixes = [
        '病人:', '病人：', '病患:', '病患：', '患者:', '患者：',
        'patient:', 'patient：', 'Patient:', 'Patient：',
        '姓名:', '姓名：', 'name:', 'Name:', '姓名 ', 'name '
    ]
    for prefix in prefixes:
        if cleaned.lower().startswith(prefix.lower()):
            cleaned = cleaned[len(prefix):].strip()

    # 移除尾部標點與多餘空格
    cleaned = re.sub(r'[，。！？\s,.;:!?]+$', '', cleaned).strip()

    if not cleaned:
        return {
            "success": False,
            "message": "姓名不能為空",
            "patient_name": None,
            "error_type": "empty_after_clean"
        }

    cleaned_lower = cleaned.lower().replace(' ', '').replace('-', '')

    # 2. 常見誤判 - 第一層：極高機率是材料/色階/代碼的阻擋
    material_abbrs = {
        'np', 'n-p', 'nonprecious', 'non-precious', 'nonpreciousmetal',
        'hp', 'h-p', 'highprecious', 'high-precious', 'highnoble',
        'sp', 's-p', 'semiprecious', 'semi-precious',
        'ti', 'titanium', 'zr', 'zirconia', 'fmz', 'fullzirconia',
        'emax', 'e.max', 'ips', 'au', 'gold', 'pd', 'palladium',
        'cocr', 'co-cr', 'cobaltchrome', 'cobalt-chrome'
    }

    if cleaned_lower in material_abbrs:
        return {
            "success": False,
            "message": f"「{cleaned}」是常見牙科材料縮寫，不是病人姓名",
            "patient_name": None,
            "error_type": "material_abbreviation"
        }

    # 3. 第二層：色階格式（最常被誤認的短字串）
    shade_patterns = [
        r'^[a-d][1-4]$',                  # A1, B2, C3...
        r'^[a-d][1-4]\.5$',               # A1.5, B2.5...
        r'^bl[1-4]$',                     # BL1~BL4
        r'^0m[1-3]$',                     # 0M1, 0M2...
        r'^[a-d][1-4]o$',                 # A1O, A2O...
        r'^[1-5]m[1-3]$',                 # 1M1, 2M2...
    ]

    for pattern in shade_patterns:
        if re.match(pattern, cleaned_lower):
            return {
                "success": False,
                "message": f"「{cleaned}」符合色階（shade）格式，不是病人姓名",
                "patient_name": None,
                "error_type": "shade_format"
            }

    # 4. 第三層：產品代碼風格（4位數字最常見）
    if re.match(r'^\d{4}$', cleaned):  # 單一4位數
        return {
            "success": False,
            "message": f"「{cleaned}」看起來像是產品代碼，不是病人姓名",
            "patient_name": None,
            "error_type": "product_code_like"
        }

    # 5. 第四層：姓名合理性檢查
    # 太短（中文字1個、英文3個字母以下） → 極大概率不是真實姓名
    if len(cleaned) <= 1 or (len(cleaned) <= 3 and cleaned.isascii()):
        return {
            "success": False,
            "message": f"姓名「{cleaned}」過短，不像是真實姓名",
            "patient_name": None,
            "error_type": "too_short"
        }

    # 全數字（即使有空格也不行）
    if cleaned.replace(' ', '').isdigit():
        return {
            "success": False,
            "message": "姓名不能全部是數字",
            "patient_name": None,
            "error_type": "all_digits"
        }

    # 6. 通過所有檢查 → 視為合理姓名
    print(f"   ✅ 通過所有防呆檢查，接受姓名: '{cleaned}'")

    return {
        "success": True,
        "message": f"病人姓名已記錄：{cleaned}",
        "patient_name": cleaned,
        "cleaned_name": cleaned  # 可選：讓後端再做一次確認
    }

def execute_tool(tool_name: str, arguments: dict):
    """執行工具"""
    
    if tool_name == "validate_bridge":
        return validate_bridge_positions(arguments)
    
    elif tool_name == "validate_material":
        return validate_material_compatibility(arguments)
    
    elif tool_name == "search_products":
        restoration_type = arguments.get('restoration_type')
        material_category = arguments.get('material_category')
        material_subtype = arguments.get('material_subtype')
        position_type = arguments.get('position_type')
        
        # 直接調用 search_products 函數
        result = search_products(
            restoration_type=restoration_type,
            material_category=material_category,
            material_subtype=material_subtype
        )
        
        return result

    elif tool_name == "store_patient_name":
        return store_patient_name(**arguments)
    else:
        return {"error": f"Unknown tool: {tool_name}"}
