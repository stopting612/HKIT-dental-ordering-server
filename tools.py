# tools.py
from rules import validate_bridge_positions, validate_material_compatibility
from knowledge_base import kb_search

# 定義所有可用的工具
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
            "description": "驗證材料與修復類型的相容性。當用戶選擇材料後使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "restoration_type": {
                        "type": "string",
                        "description": "修復類型",
                        "enum": ["crown", "bridge", "veneer", "inlay", "onlay"]
                    },
                    "material": {
                        "type": "string",
                        "description": "材料類型"
                    },
                    "bridge_span": {
                        "type": "integer",
                        "description": "牙橋跨度（如果是 bridge）"
                    }
                },
                "required": ["restoration_type", "material"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "搜尋牙科產品。當需要推薦產品或用戶詢問產品資訊時使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "restoration_type": {
                        "type": "string",
                        "description": "修復類型",
                        "enum": ["crown", "bridge", "veneer", "inlay", "onlay"]
                    },
                    "material": {
                        "type": "string",
                        "description": "材料類型"
                    },
                    "position_type": {
                        "type": "string",
                        "description": "位置類型：anterior（前牙）或 posterior（後牙）",
                        "enum": ["anterior", "posterior"]
                    }
                },
                "required": ["restoration_type"]
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
            material=arguments.get('material'),
            position_type=arguments.get('position_type')
        )
        
        # 格式化結果
        products = []
        for result in results[:3]:  # 只返回前 3 個
            products.append({
                'content': result.get('content', '')[:200],  # 限制長度
                'score': result.get('score', 0)
            })
        
        return {
            'found': len(products) > 0,
            'count': len(products),
            'products': products
        }
    
    else:
        return {"error": f"Unknown tool: {tool_name}"}