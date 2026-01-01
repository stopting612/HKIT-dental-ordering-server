# rules.py

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
    驗證材料類型與修復類型的相容性（嚴格版本）
    
    材料分類系統：
    1. 主類別 (Main Category): PFM, Metal-Free, Full Cast
    2. 子類型 (Subtype): 具體材料，如 High Noble, IPS e.max, Titanium
    """
    
    restoration_type = params.get('restoration_type', '').lower()
    material_category = params.get('material_category', '').lower()  # PFM, Metal-Free, Full Cast
    material_subtype = params.get('material_subtype', '').lower()    # 具體材料
    bridge_span = params.get('bridge_span', 1)
    
    # === 參數驗證 ===
    if not restoration_type:
        return {
            'valid': False,
            'message': 'Missing restoration type parameter',
            'error_type': 'missing_parameter'
        }
    
    if not material_category:
        return {
            'valid': False,
            'message': 'Missing material category parameter',
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
    
    # === 子類型標準化 ===
    subtype_map = {
        # PFM 子類型
        'high-noble': 'high-noble',
        'high noble': 'high-noble',
        '高貴金屬': 'high-noble',
        
        'semi-precious': 'semi-precious',
        'semi precious': 'semi-precious',
        '半貴金屬': 'semi-precious',
        
        'non-precious': 'non-precious',
        'non precious': 'non-precious',
        '非貴金屬': 'non-precious',
        
        'palladium': 'palladium',
        '鈀基': 'palladium',
        
        'titanium': 'titanium',
        '鈦合金': 'titanium',
        '鈦': 'titanium',
        
        # Metal-Free 子類型
        'ips-emax': 'ips-emax',
        'ips e.max': 'ips-emax',
        'emax': 'ips-emax',
        'e.max': 'ips-emax',
        
        'fmz': 'fmz',
        '全鋯': 'fmz',
        
        'fmz-ultra': 'fmz-ultra',
        'fmz ultra': 'fmz-ultra',
        '高透多層鋯': 'fmz-ultra',
        
        'lava': 'lava',
        '3m lava': 'lava',
        
        'lava-plus': 'lava-plus',
        'lava plus': 'lava-plus',
        
        'lava-esthetic': 'lava-esthetic',
        'lava esthetic': 'lava-esthetic',
        
        'calypso': 'calypso',
        
        'composite': 'composite',
        '複合樹脂': 'composite',
        
        'zineer': 'zineer',  # 通常不用於 Crown
        
        # Full Cast 子類型
        'high-precious-gold': 'high-precious-gold',
        'high precious gold': 'high-precious-gold',
        '高貴黃金': 'high-precious-gold',
        
        'semi-precious-gold': 'semi-precious-gold',
        'semi precious gold': 'semi-precious-gold',
        '半貴黃金': 'semi-precious-gold',
        
        'low-precious-gold': 'low-precious-gold',
        'low precious gold': 'low-precious-gold',
        '低貴黃金': 'low-precious-gold',
        
        'white-gold': 'white-gold',
        'white gold': 'white-gold',
        '白金': 'white-gold',
        
        'pure-titanium': 'pure-titanium',
        'pure titanium': 'pure-titanium',
        '純鈦': 'pure-titanium'
    }
    
    normalized_subtype = subtype_map.get(material_subtype, material_subtype) if material_subtype else None
    
    # === 定義相容性規則 ===
    compatibility_rules = {
        'crown': {
            'pfm': {
                'allowed_subtypes': ['high-noble', 'semi-precious', 'non-precious', 'palladium', 'titanium'],
                'reason': 'PFM Crown 可以使用各種金屬基底'
            },
            'metal-free': {
                'allowed_subtypes': ['ips-emax', 'fmz', 'fmz-ultra', 'lava', 'lava-plus', 'lava-esthetic', 'calypso', 'composite'],
                'forbidden_subtypes': ['zineer'],  # Zineer 不適用於 Crown
                'reason': 'Metal-Free Crown 可以使用多種全瓷材料'
            },
            'full-cast': {
                'allowed_subtypes': ['high-precious-gold', 'semi-precious-gold', 'low-precious-gold', 'white-gold', 'pure-titanium', 'non-precious'],
                'reason': 'Full Cast Crown 可以使用各種金屬'
            }
        },
        'bridge': {
            'pfm': {
                'allowed_subtypes': ['titanium', 'non-precious', 'high-noble', 'semi-precious'],
                'reason': 'PFM Bridge 需要較強的金屬基底'
            },
            'metal-free': {
                'allowed_subtypes': ['ips-emax', 'fmz', 'lava'],
                'forbidden_subtypes': ['composite', 'zineer'],  # 這些不適用於 Bridge
                'reason': 'Metal-Free Bridge 只能使用高強度全瓷材料'
            },
            'full-cast': {
                'allowed_subtypes': ['high-precious-gold', 'titanium'],
                'reason': 'Full Cast Bridge 較少使用，需要極高強度'
            }
        },
        'veneer': {
            'pfm': {
                'allowed_subtypes': [],  # Veneer 不能用 PFM
                'reason': 'Veneer 必須使用全瓷材料以確保透光性'
            },
            'metal-free': {
                'allowed_subtypes': ['ips-emax'],  # Veneer 只能用特定全瓷
                'forbidden_subtypes': ['composite', 'zineer', 'fmz'],  # 這些不適合
                'reason': 'Veneer 需要極佳透光性的全瓷材料'
            },
            'full-cast': {
                'allowed_subtypes': [],  # Veneer 不能用金屬
                'reason': 'Veneer 必須使用全瓷材料'
            }
        },
        'inlay': {
            'pfm': {
                'allowed_subtypes': [],
                'reason': 'Inlay 不適用 PFM'
            },
            'metal-free': {
                'allowed_subtypes': ['ips-emax', 'composite'],
                'reason': 'Inlay 建議使用全瓷或複合樹脂'
            },
            'full-cast': {
                'allowed_subtypes': ['high-precious-gold', 'pure-titanium'],
                'reason': 'Inlay 可使用全金屬'
            }
        },
        'onlay': {
            'pfm': {
                'allowed_subtypes': [],
                'reason': 'Onlay 不適用 PFM'
            },
            'metal-free': {
                'allowed_subtypes': ['ips-emax', 'fmz'],
                'reason': 'Onlay 建議使用全瓷'
            },
            'full-cast': {
                'allowed_subtypes': ['high-precious-gold', 'pure-titanium'],
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
    
    # === 驗證子類型（如果提供） ===
    if normalized_subtype:
        # 檢查是否在禁止列表
        if normalized_subtype in category_rules.get('forbidden_subtypes', []):
            return {
                'valid': False,
                'message': f'{restoration_type} 不能使用 {normalized_subtype}。請選擇其他材料。',
                'error_type': 'forbidden_subtype',
                'allowed_subtypes': category_rules['allowed_subtypes']
            }
        
        # 檢查是否在允許列表
        if normalized_subtype not in category_rules['allowed_subtypes']:
            return {
                'valid': False,
                'message': f'{restoration_type} + {normalized_category} 不支援 {normalized_subtype}',
                'error_type': 'incompatible_subtype',
                'allowed_subtypes': category_rules['allowed_subtypes']
            }
    
    # === 特殊檢查：Bridge 跨度 ===
    warnings = []
    if restoration_type == 'bridge' and bridge_span > 3:
        if normalized_category == 'metal-free' and normalized_subtype not in ['fmz', 'lava']:
            warnings.append(f'跨度超過 3 單位的牙橋使用 {normalized_subtype}，建議改用 FMZ 或 Lava 以獲得更好的強度')
    
    # === 驗證通過 ===
    return {
        'valid': True,
        'message': f'{restoration_type} 使用 {normalized_category}' + (f' ({normalized_subtype})' if normalized_subtype else '') + ' 驗證通過',
        'material_category': normalized_category,
        'material_subtype': normalized_subtype,
        'allowed_subtypes': category_rules['allowed_subtypes'],
        'warnings': warnings
    }