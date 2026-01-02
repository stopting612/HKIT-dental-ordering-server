# rules.py
from material_normalizer import normalize_material, STANDARD_MATERIALS

def validate_bridge_positions(params):
    """驗證牙橋牙位的連續性和跨度"""
    tooth_positions_str = params.get('tooth_positions', '')
    
    if not tooth_positions_str or tooth_positions_str.strip() == '':
        return {
            'valid': False,
            'message': '請提供牙位編號',
            'error_type': 'missing_positions'
        }
    
    try:
        positions = [int(p.strip()) for p in tooth_positions_str.split(',') if p.strip()]
    except ValueError:
        return {
            'valid': False,
            'message': '牙位格式錯誤，請使用數字',
            'error_type': 'invalid_format'
        }
    
    if not positions:
        return {
            'valid': False,
            'message': '請提供有效的牙位',
            'error_type': 'missing_positions'
        }
    
    positions = sorted(positions)
    
    # 檢查連續性
    for i in range(len(positions) - 1):
        if positions[i+1] - positions[i] != 1:
            return {
                'valid': False,
                'message': f'牙位不連續：{positions[i]} 和 {positions[i+1]} 之間缺少 {positions[i]+1} 號牙',
                'error_type': 'discontinuous',
                'positions': positions
            }
    
    # 檢查長度
    if len(positions) > 4:
        return {
            'valid': False,
            'message': f'牙橋最多支援 4 顆牙（您選擇了 {len(positions)} 顆）',
            'error_type': 'too_long',
            'positions': positions
        }
    
    # 判斷位置類型
    is_anterior = any(11 <= p <= 23 for p in positions)
    position_type = 'anterior' if is_anterior else 'posterior'
    
    return {
        'valid': True,
        'message': f'牙位 {positions} 驗證通過',
        'bridge_span': len(positions),
        'position_type': position_type,
        'positions': positions
    }


def validate_material_compatibility(params):
    """
    驗證材料類型與修復類型的相容性
    
    支援兩種模式：
    1. 驗證模式：提供 material_subtype，驗證是否可用
    2. 查詢模式：不提供 material_subtype，返回可用的子類型列表
    """
    
    restoration_type = params.get('restoration_type', '').lower()
    material_category = params.get('material_category', '').lower()
    material_subtype = params.get('material_subtype', '')
    bridge_span = params.get('bridge_span', 1)
    
    # === 參數驗證 ===
    if not restoration_type:
        return {
            'valid': False,
            'message': '缺少修復類型參數',
            'error_type': 'missing_parameter'
        }
    
    if not material_category:
        return {
            'valid': False,
            'message': '缺少材料類別參數',
            'error_type': 'missing_parameter'
        }
    
    # === 材料類別標準化 ===
    category_map = {
        'pfm': 'pfm',
        'porcelain-fused-to-metal': 'pfm',
        'porcelain': 'pfm',
        '烤瓷': 'pfm',
        
        'metal-free': 'metal-free',
        'all-ceramic': 'metal-free',
        'ceramic': 'metal-free',
        '全瓷': 'metal-free',
        
        'full-cast': 'full-cast',
        'full-metal': 'full-cast',
        'full cast': 'full-cast',
        '全金屬': 'full-cast',
        '全金': 'full-cast'
    }
    
    normalized_category = category_map.get(material_category, material_category)
    
    # === 使用智能標準化處理子類型 ===
    if material_subtype:
        normalized_subtype = normalize_material(
            material_input=material_subtype,
            material_category=normalized_category,
            use_llm=True  # 啟用 LLM（可以改為 False 以節省成本）
        )
    else:
        normalized_subtype = None
    
    # === 定義相容性規則 ===
    compatibility_rules = {
        'crown': {
            'pfm': {
                'allowed_subtypes': ['high-noble', 'semi-precious', 'non-precious', 'palladium', 'titanium'],
                'forbidden_subtypes': [],
                'reason': 'PFM Crown 可以使用各種金屬基底'
            },
            'metal-free': {
                'allowed_subtypes': ['emax', 'fmz', 'fmz-ultra', 'lava', 'lava-plus', 'lava-esthetic', 'calypso', 'composite'],
                'forbidden_subtypes': ['zineer'],
                'reason': 'Metal-Free Crown 可以使用多種全瓷材料，但 Zineer 不適用'
            },
            'full-cast': {
                'allowed_subtypes': ['high-precious-gold', 'semi-precious-gold', 'low-precious-gold', 'white-gold', 'pure-titanium', 'non-precious'],
                'forbidden_subtypes': [],
                'reason': 'Full Cast Crown 可以使用各種金屬'
            }
        },
        'bridge': {
            'pfm': {
                'allowed_subtypes': ['high-noble', 'semi-precious', 'non-precious', 'palladium', 'titanium'],
                'forbidden_subtypes': [],
                'reason': 'PFM Bridge 需要較強的金屬基底'
            },
            'metal-free': {
                'allowed_subtypes': ['emax', 'fmz', 'fmz-ultra', 'lava', 'lava-plus', 'lava-esthetic', 'calypso'],
                'forbidden_subtypes': ['composite', 'zineer'],
                'reason': 'Metal-Free Bridge 只能使用高強度全瓷材料'
            },
            'full-cast': {
                'allowed_subtypes': ['high-precious-gold', 'semi-precious-gold', 'white-gold', 'pure-titanium', 'non-precious'],
                'forbidden_subtypes': [],
                'reason': 'Full Cast Bridge 需要極高強度'
            }
        },
        'veneer': {
            'pfm': {
                'allowed_subtypes': [],
                'forbidden_subtypes': [],
                'reason': 'Veneer 必須使用全瓷材料以確保透光性，不能使用 PFM'
            },
            'metal-free': {
                'allowed_subtypes': ['emax', 'zineer', 'composite'],
                'forbidden_subtypes': ['fmz', 'fmz-ultra', 'lava', 'lava-plus', 'lava-esthetic', 'calypso'],
                'reason': 'Veneer 需要極佳透光性的全瓷材料，高強度鋯瓷不適用'
            },
            'full-cast': {
                'allowed_subtypes': [],
                'forbidden_subtypes': [],
                'reason': 'Veneer 必須使用全瓷材料，不能使用金屬'
            }
        },
        'inlay': {
            'pfm': {
                'allowed_subtypes': [],
                'forbidden_subtypes': [],
                'reason': 'Inlay 不適用 PFM'
            },
            'metal-free': {
                'allowed_subtypes': ['emax', 'composite'],
                'forbidden_subtypes': [],
                'reason': 'Inlay 建議使用全瓷或複合樹脂'
            },
            'full-cast': {
                'allowed_subtypes': ['high-precious-gold', 'semi-precious-gold', 'low-precious-gold', 'white-gold', 'pure-titanium', 'non-precious'],
                'forbidden_subtypes': [],
                'reason': 'Inlay 可使用全金屬'
            }
        },
        'onlay': {
            'pfm': {
                'allowed_subtypes': [],
                'forbidden_subtypes': [],
                'reason': 'Onlay 不適用 PFM'
            },
            'metal-free': {
                'allowed_subtypes': ['emax', 'fmz'],
                'forbidden_subtypes': [],
                'reason': 'Onlay 建議使用全瓷'
            },
            'full-cast': {
                'allowed_subtypes': ['high-precious-gold', 'pure-titanium'],
                'forbidden_subtypes': [],
                'reason': 'Onlay 可使用全金屬'
            }
        }
    }
    
    # === 驗證修復類型 ===
    if restoration_type not in compatibility_rules:
        return {
            'valid': False,
            'message': f'不支援的修復類型：{restoration_type}',
            'error_type': 'unsupported_restoration_type'
        }
    
    # === 驗證材料類別 ===
    restoration_rules = compatibility_rules[restoration_type]
    
    if normalized_category not in restoration_rules:
        return {
            'valid': False,
            'message': f'{restoration_type} 不支援 {normalized_category} 類別',
            'error_type': 'unsupported_category'
        }
    
    category_rules = restoration_rules[normalized_category]
    
    # === 檢查類別是否完全禁止 ===
    if not category_rules['allowed_subtypes']:
        return {
            'valid': False,
            'message': f'{restoration_type} 不能使用 {normalized_category}。{category_rules["reason"]}',
            'error_type': 'forbidden_category',
            'allowed_categories': [cat for cat, rules in restoration_rules.items() if rules['allowed_subtypes']]
        }
    
    # === 查詢模式：返回可用的子類型列表 ===
    if not normalized_subtype:
        return {
            'valid': True,
            'query_mode': True,
            'message': f'{restoration_type} + {normalized_category} 的可用子類型',
            'material_category': normalized_category,
            'allowed_subtypes': category_rules['allowed_subtypes'],
            'reason': category_rules['reason']
        }
    
    # === 驗證模式：驗證特定子類型 ===
    
    # 檢查是否在禁止列表
    if normalized_subtype in category_rules.get('forbidden_subtypes', []):
        return {
            'valid': False,
            'message': f'{restoration_type} 不能使用 {normalized_subtype}。{category_rules["reason"]}',
            'error_type': 'forbidden_subtype',
            'allowed_subtypes': category_rules['allowed_subtypes']
        }
    
    # 檢查是否在允許列表
    if normalized_subtype not in category_rules['allowed_subtypes']:
        return {
            'valid': False,
            'message': f'{restoration_type} + {normalized_category} 不支援 {normalized_subtype}。{category_rules["reason"]}',
            'error_type': 'incompatible_subtype',
            'allowed_subtypes': category_rules['allowed_subtypes']
        }
    
    # === 特殊檢查：Bridge 跨度 ===
    warnings = []
    if restoration_type == 'bridge' and bridge_span > 3:
        if normalized_category == 'metal-free' and normalized_subtype not in ['fmz', 'fmz-ultra', 'lava']:
            warnings.append(f'跨度超過 3 單位的牙橋使用 {normalized_subtype}，建議改用 FMZ、FMZ Ultra 或 Lava 以獲得更好的強度')
    
    # === 驗證通過 ===
    return {
        'valid': True,
        'message': f'{restoration_type} 使用 {normalized_category} ({normalized_subtype}) 驗證通過',
        'material_category': normalized_category,
        'material_subtype': normalized_subtype,
        'allowed_subtypes': category_rules['allowed_subtypes'],
        'warnings': warnings
    }