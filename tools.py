# tools.py
from rules import validate_bridge_positions, validate_material_compatibility
from knowledge_base import kb_search

# 更新工具定義
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "validate_bridge",
            "description": "驗證牙橋牙位的連續性和跨度。當用戶提供牙位編號時使用。",
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
            "description": """驗證材料類型與修復類型的相容性。

材料系統有兩層：
1. Material Category (主類別): PFM, Metal-Free, Full Cast
2. Material Subtype (子類型): 具體材料，如 IPS e.max, High Noble, Titanium

範例：
- Crown + Metal-Free + IPS e.max ✓
- Crown + Metal-Free + Zineer ✗ (Zineer 不適用於 Crown)
- Veneer + PFM ✗ (Veneer 只能用 Metal-Free)
- Bridge + Metal-Free + Composite ✗ (Bridge 不能用 Composite)
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
                        "enum": ["PFM", "Metal-Free", "Full Cast", "pfm", "metal-free", "full-cast"]
                    },
                    "material_subtype": {
                        "type": "string",
                        "description": "材料子類型（可選）。例如：IPS e.max, High Noble, Titanium, FMZ, Calypso"
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
            "description": "搜尋牙科產品。當材料驗證通過後，自動搜尋符合條件的產品。",
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
                        "enum": ["PFM", "Metal-Free", "Full Cast", "pfm", "metal-free", "full-cast"]
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
        # 構建搜尋查詢
        restoration_type = arguments.get('restoration_type')
        material_category = arguments.get('material_category')
        material_subtype = arguments.get('material_subtype')
        position_type = arguments.get('position_type')
        
        # 使用 KB 搜尋
        results = kb_search.search_by_criteria(
            restoration_type=restoration_type,
            material=material_category,  # 主類別
            position_type=position_type
        )
        
        # 如果有子類型，進一步過濾
        if material_subtype and results:
            filtered = []
            subtype_lower = material_subtype.lower()
            
            for r in results:
                content_lower = r.get('content', '').lower()
                
                # 檢查內容是否包含子類型關鍵字
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
            'products': products,
            'search_criteria': {
                'restoration_type': restoration_type,
                'material_category': material_category,
                'material_subtype': material_subtype
            }
        }
    
    else:
        return {"error": f"Unknown tool: {tool_name}"}