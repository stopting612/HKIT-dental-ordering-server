# tools.py
from rules import validate_bridge_positions, validate_material_compatibility
from knowledge_base import kb_search

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
            "description": """搜尋牙科產品。

【何時使用】
材料驗證通過後（validate_material 返回 valid: true），自動搜尋符合條件的產品。

【重要】
只在 validate_material 驗證通過後才呼叫此工具。
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
                        "description": "材料主類別"
                    },
                    "material_subtype": {
                        "type": "string",
                        "description": "材料子類型（可選）"
                    },
                    "position_type": {
                        "type": "string",
                        "description": "位置類型",
                        "enum": ["anterior", "posterior"]
                    }
                },
                "required": ["restoration_type", "material_category"]
            }
        }
    }
]


def execute_tool(tool_name: str, arguments: dict):
    """執行工具"""
    
    if tool_name == "validate_bridge":
        return validate_bridge_positions(arguments)
    
    elif tool_name == "validate_material":
        return validate_material_compatibility(arguments)
    
    elif tool_name == "search_products":
        results = kb_search.search_by_criteria(
            restoration_type=arguments.get('restoration_type'),
            material=arguments.get('material_category'),
            position_type=arguments.get('position_type')
        )
        
        # 如果有子類型，進一步過濾
        material_subtype = arguments.get('material_subtype')
        if material_subtype and results:
            filtered = []
            subtype_lower = material_subtype.lower()
            
            for r in results:
                content_lower = r.get('content', '').lower()
                if subtype_lower in content_lower:
                    filtered.append(r)
            
            if filtered:
                results = filtered
        
        # 格式化結果
        products = []
        for result in results[:3]:
            products.append({
                'content': result.get('content', '')[:300],
                'score': result.get('score', 0)
            })
        
        return {
            'found': len(products) > 0,
            'count': len(products),
            'products': products
        }
    
    else:
        return {"error": f"Unknown tool: {tool_name}"}