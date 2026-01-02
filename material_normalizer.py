# material_normalizer.py

from difflib import get_close_matches
from openai import AzureOpenAI
import os
import json
from typing import Optional

# === 標準材料定義（Single Source of Truth）===
STANDARD_MATERIALS = {
    'pfm': [
        'high-noble',
        'semi-precious', 
        'non-precious',
        'palladium',
        'titanium'
    ],
    'metal-free': [
        'emax',
        'fmz',
        'fmz-ultra',
        'lava',
        'lava-plus',
        'lava-esthetic',
        'calypso',
        'composite',
        'zineer'
    ],
    'full-cast': [
        'high-precious-gold',
        'semi-precious-gold',
        'low-precious-gold',
        'white-gold',
        'pure-titanium',
        'non-precious'
    ]
}

# === 緩存（避免重複 LLM 呼叫）===
_normalization_cache = {}


def _normalize_simple(material_input: str) -> Optional[str]:
    """
    階段 1: 簡單規則匹配
    
    處理常見縮寫和變體
    """
    simple_rules = {
        # emax 變體
        'emax': 'emax',
        'e.max': 'emax',
        'emx': 'emax',
        'ips': 'emax',
        'ipsemax': 'emax',
        'ipsemax': 'emax',
        
        # 其他常見縮寫
        'np': 'non-precious',
        'pd': 'palladium',
        'ti': 'titanium',
        'cpst': 'composite',
        'comp': 'composite',
    }
    
    # 清理輸入
    cleaned = material_input.lower().replace(' ', '').replace('-', '').replace('.', '')
    
    result = simple_rules.get(cleaned)
    
    if result:
        print(f"   ✅ 階段 1 (簡單規則): '{material_input}' → '{result}'")
    
    return result


def _normalize_fuzzy(material_input: str, material_category: str) -> Optional[str]:
    """
    階段 2: 模糊字串匹配
    
    使用演算法找到最相似的標準材料名稱
    """
    materials_list = STANDARD_MATERIALS.get(material_category, [])
    
    if not materials_list:
        return None
    
    # 清理輸入
    cleaned_input = material_input.lower().replace(' ', '').replace('.', '').replace('-', '')
    
    # 建立清理後的標準名稱映射
    cleaned_standards = {
        mat.lower().replace(' ', '').replace('.', '').replace('-', ''): mat
        for mat in materials_list
    }
    
    # 1. 精確匹配
    if cleaned_input in cleaned_standards:
        result = cleaned_standards[cleaned_input]
        print(f"   ✅ 階段 2a (精確匹配): '{material_input}' → '{result}'")
        return result
    
    # 2. 部分匹配（包含關係）
    for cleaned, original in cleaned_standards.items():
        # 檢查是否互相包含
        if cleaned_input in cleaned or cleaned in cleaned_input:
            print(f"   ✅ 階段 2b (部分匹配): '{material_input}' → '{original}'")
            return original
    
    # 3. 模糊匹配（相似度）
    matches = get_close_matches(
        cleaned_input, 
        list(cleaned_standards.keys()),
        n=1,           # 只取最佳匹配
        cutoff=0.6     # 相似度閾值（0-1），0.6 表示 60% 相似
    )
    
    if matches:
        result = cleaned_standards[matches[0]]
        print(f"   ✅ 階段 2c (模糊匹配): '{material_input}' → '{result}'")
        return result
    
    return None


def _normalize_llm(material_input: str, material_category: str) -> Optional[str]:
    """
    階段 3: LLM 智能匹配
    
    使用 AI 處理多語言、拼寫錯誤等複雜情況
    """
    materials_list = STANDARD_MATERIALS.get(material_category, [])
    
    if not materials_list:
        return None
    
    try:
        # 初始化 Azure OpenAI 客戶端
        client = AzureOpenAI(
            azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT'),
            api_key=os.getenv('AZURE_OPENAI_KEY'),
            api_version=os.getenv('AZURE_OPENAI_API_VERSION')
        )
        
        # 建立 Prompt
        prompt = f"""You are a dental material name normalizer.

Task: Match the user's input to the closest standard material name.

User input: "{material_input}"
Material category: {material_category}
Standard materials: {json.dumps(materials_list)}

Rules:
1. Ignore case, spaces, dots, and hyphens
2. Handle typos and abbreviations
3. Support multiple languages (English, Chinese, etc.)
4. Examples:
   - "IPS e.max", "emax", "伊馬克斯" → "emax"
   - "Calypso", "卡呂普索" → "calypso"
   - "全鋯", "FMZ" → "fmz"

Return ONLY valid JSON format:
{{"matched": "standard_name"}}

If no match found, return:
{{"matched": null}}

JSON:"""

        # 呼叫 LLM
        response = client.chat.completions.create(
            model=os.getenv('AZURE_OPENAI_DEPLOYMENT'),
            messages=[
                {
                    "role": "system", 
                    "content": "You are a material name normalizer. Return only valid JSON, no explanations."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            temperature=0,  # 確保一致性
            max_tokens=50   # 只需要短回應
        )
        
        # 解析結果
        result = response.choices[0].message.content
        
        # 清理可能的 markdown 格式
        result = result.replace('```json', '').replace('```', '').strip()
        
        # 解析 JSON
        parsed = json.loads(result)
        matched = parsed.get('matched')
        
        if matched:
            print(f"   ✅ 階段 3 (LLM 匹配): '{material_input}' → '{matched}'")
        else:
            print(f"   ⚠️  階段 3 (LLM): 未找到匹配")
        
        return matched
    
    except Exception as e:
        print(f"   ❌ 階段 3 (LLM) 失敗: {e}")
        return None


def normalize_material(
    material_input: str, 
    material_category: str, 
    use_llm: bool = True
) -> str:
    """
    智能材料標準化（三階段混合方案）
    
    階段 1: 簡單規則匹配（快速，處理常見縮寫）
    階段 2: 模糊字串匹配（中速，處理拼寫錯誤）
    階段 3: LLM 智能匹配（慢速，處理多語言）
    
    Args:
        material_input: 用戶輸入的材料名稱
        material_category: 材料類別 (pfm, metal-free, full-cast)
        use_llm: 是否啟用 LLM（可關閉以節省成本）
    
    Returns:
        標準化的材料名稱
    
    Examples:
        >>> normalize_material('IPS e.max', 'metal-free')
        'emax'
        
        >>> normalize_material('Calypso', 'metal-free')
        'calypso'
        
        >>> normalize_material('伊馬克斯', 'metal-free', use_llm=True)
        'emax'
    """
    
    if not material_input:
        return None
    
    # 檢查緩存
    cache_key = f"{material_category}:{material_input.lower()}"
    if cache_key in _normalization_cache:
        cached_result = _normalization_cache[cache_key]
        print(f"🔍 標準化材料 (緩存): '{material_input}' → '{cached_result}'")
        return cached_result
    
    print(f"🔍 標準化材料: '{material_input}' (類別: {material_category})")
    
    # 階段 1: 簡單規則
    result = _normalize_simple(material_input)
    if result:
        _normalization_cache[cache_key] = result
        return result
    
    # 階段 2: 模糊匹配
    result = _normalize_fuzzy(material_input, material_category)
    if result:
        _normalization_cache[cache_key] = result
        return result
    
    # 階段 3: LLM（可選）
    if use_llm:
        print(f"   🤖 前兩階段失敗，使用 LLM...")
        result = _normalize_llm(material_input, material_category)
        if result:
            _normalization_cache[cache_key] = result
            return result
    
    # 所有階段都失敗：返回原始輸入（小寫）
    print(f"   ⚠️  所有階段失敗，使用原始輸入（小寫）")
    fallback = material_input.lower()
    _normalization_cache[cache_key] = fallback
    return fallback


def clear_cache():
    """清除標準化緩存"""
    global _normalization_cache
    _normalization_cache = {}
    print("✅ 標準化緩存已清除")


def get_cache_stats():
    """取得緩存統計"""
    return {
        'cache_size': len(_normalization_cache),
        'cached_items': list(_normalization_cache.keys())
    }