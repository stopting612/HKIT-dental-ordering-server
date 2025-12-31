# rules.py
def validate_bridge_positions(params):
    """驗證牙橋牙位的連續性和跨度"""
    tooth_positions_str = params.get('tooth_positions', '')
    
    # 檢查是否提供牙位
    if not tooth_positions_str or tooth_positions_str.strip() == '':
        return {
            'valid': False,
            'message': '請提供牙位編號',
            'error_type': 'missing_positions'
        }
    
    # 解析牙位
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
    
    # 排序
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
    
    # 成功
    return {
        'valid': True,
        'message': f'牙位 {positions} 驗證通過',
        'bridge_span': len(positions),
        'position_type': position_type
    }


def validate_material_compatibility(params):
    """驗證材料與修復類型的相容性"""
    restoration_type = params.get('restoration_type', '').lower()
    material = params.get('material', '').lower()
    bridge_span = params.get('bridge_span', 1)
    
    # 參數驗證
    if not restoration_type:
        return {
            'valid': False,
            'message': '缺少修復類型參數',
            'error_type': 'missing_parameter'
        }
    
    if not material:
        return {
            'valid': False,
            'message': '缺少材料參數',
            'error_type': 'missing_parameter'
        }
    
    # 標準化材料名稱
    material_map = {
        'metal-free': 'metal-free',
        'all-ceramic': 'metal-free',
        '全瓷': 'metal-free',
        'pfm': 'pfm',
        'porcelain-fused-to-metal': 'pfm',
        '烤瓷': 'pfm',
        'full-cast': 'full-metal',
        'full-metal': 'full-metal',
        '全金屬': 'full-metal',
        'zirconia': 'zirconia',
        'zir': 'zirconia',
        '氧化鋯': 'zirconia'
    }
    
    material = material_map.get(material, material)
    
    # 定義材料規則
    rules = {
        'veneer': {
            'allowed': ['metal-free'],
            'reason': '貼片必須使用全瓷材料以確保透光性和美觀'
        },
        'crown': {
            'allowed': ['metal-free', 'pfm', 'full-metal', 'zirconia'],
            'reason': '單顆牙冠可以使用任何材料'
        },
        'bridge': {
            'allowed': ['metal-free', 'pfm', 'full-metal', 'zirconia'],
            'reason': '牙橋可以使用多種材料，需根據跨度選擇'
        },
        'inlay': {
            'allowed': ['metal-free', 'full-metal'],
            'reason': '嵌體建議使用全瓷或全金屬'
        },
        'onlay': {
            'allowed': ['metal-free', 'full-metal', 'zirconia'],
            'reason': '高嵌體可以使用全瓷、氧化鋯或全金屬'
        }
    }
    
    # 獲取規則
    rule = rules.get(restoration_type)
    if not rule:
        return {
            'valid': False,
            'message': f'不支援的修復類型：{restoration_type}',
            'error_type': 'unsupported_type'
        }
    
    # 驗證材料
    if material not in rule['allowed']:
        return {
            'valid': False,
            'message': f'{restoration_type} 不能使用 {material} 材料。{rule["reason"]}',
            'allowed_materials': rule['allowed'],
            'error_type': 'incompatible_material'
        }
    
    # 檢查警告
    warnings = []
    
    # Bridge 特殊檢查
    if restoration_type == 'bridge':
        if bridge_span > 3 and material == 'metal-free':
            warnings.append('跨度超過 3 單位的牙橋使用全瓷材料，建議考慮氧化鋯以獲得更好的強度')
    
    # 成功
    return {
        'valid': True,
        'message': f'{restoration_type} 使用 {material} 材料驗證通過',
        'allowed_materials': rule['allowed'],
        'warnings': warnings
    }