# knowledge_base.py
import boto3
import os
from typing import List, Dict, Optional
import sys
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

from material_normalizer import normalize_material

class KnowledgeBaseSearch:
    """
    AWS Bedrock Knowledge Base 搜尋類（生產版本）
    
    功能：
    1. 直接連接 AWS Bedrock Knowledge Base
    2. 執行向量搜尋
    3. 根據訂單條件過濾產品
    """
    
    def __init__(self):
        """初始化 Knowledge Base 客戶端"""
        
        # 驗證必要的環境變數
        required_env_vars = {
            'AWS_ACCESS_KEY_ID': os.getenv('AWS_ACCESS_KEY_ID'),
            'AWS_SECRET_ACCESS_KEY': os.getenv('AWS_SECRET_ACCESS_KEY'),
            'AWS_REGION': os.getenv('AWS_REGION'),
            'KNOWLEDGE_BASE_ID': os.getenv('KNOWLEDGE_BASE_ID')
        }
        
        # 檢查缺失的環境變數
        missing_vars = [key for key, value in required_env_vars.items() if not value]
        
        if missing_vars:
            error_msg = f"❌ 缺少必要的環境變數: {', '.join(missing_vars)}"
            print(error_msg)
            print("\n請在 .env 檔案中設定：")
            for var in missing_vars:
                print(f"  {var}=your-value-here")
            print("\n伺服器將無法正常運作，請設定後重新啟動。\n")
            raise EnvironmentError(error_msg)
        
        # 初始化 Bedrock Agent Runtime 客戶端
        try:
            self.client = boto3.client(
                'bedrock-agent-runtime',
                region_name=required_env_vars['AWS_REGION'],
                aws_access_key_id=required_env_vars['AWS_ACCESS_KEY_ID'],
                aws_secret_access_key=required_env_vars['AWS_SECRET_ACCESS_KEY']
            )
            self.kb_id = required_env_vars['KNOWLEDGE_BASE_ID']
            self.region = required_env_vars['AWS_REGION']
            
            print("=" * 60)
            print("✅ AWS Bedrock Knowledge Base 已成功連接")
            print("=" * 60)
            print(f"Knowledge Base ID: {self.kb_id}")
            print(f"AWS Region: {self.region}")
            print("=" * 60)
            print()
            
        except Exception as e:
            error_msg = f"❌ AWS Bedrock 初始化失敗: {str(e)}"
            print(error_msg)
            print("\n請檢查：")
            print("  1. AWS 憑證是否正確")
            print("  2. Region 是否正確")
            print("  3. Knowledge Base ID 是否存在")
            print("  4. IAM 權限是否足夠（需要 bedrock:Retrieve）\n")
            raise ConnectionError(error_msg)
    
    def search_products(self, query: str, num_results: int = 10) -> List[Dict]:
        """
        使用 Knowledge Base 搜尋產品
        
        Args:
            query: 搜尋查詢字串
            num_results: 返回結果數量
            
        Returns:
            List[Dict]: 搜尋結果列表，每個結果包含 content 和 score
        """
        try:
            response = self.client.retrieve(
                knowledgeBaseId=self.kb_id,
                retrievalQuery={'text': query},
                retrievalConfiguration={
                    'vectorSearchConfiguration': {
                        'numberOfResults': num_results
                    }
                }
            )
            
            results = []
            for item in response.get('retrievalResults', []):
                results.append({
                    'content': item.get('content', {}).get('text', ''),
                    'score': item.get('score', 0)
                })
            
            return results
            
        except Exception as e:
            print(f"❌ Knowledge Base 查詢失敗: {e}")
            import traceback
            traceback.print_exc()
            return []


# ============================================================
# 獨立函數：search_products（供 tools.py 調用）
# ============================================================

def search_products(restoration_type: str, material_category: str, material_subtype: str) -> dict:
    """搜尋產品"""
    
    print(f"\n🔍 搜尋產品")
    
    # ✅ 檢查 kb_search 是否可用
    if kb_search is None:
        error_msg = "Knowledge Base 未初始化，請檢查 AWS 設定"
        print(f"   ❌ {error_msg}")
        return {
            "error": True,
            "message": error_msg,
            "products": [],
            "count": 0
        }
    
    # 標準化材料
    normalized_subtype = normalize_material(material_subtype, material_category, use_llm=False)
    
    # 構建查詢
    query = f"{restoration_type} {material_category} {normalized_subtype}"
    print(f"   查詢: '{query}'")
    
    try:
        # 呼叫 Knowledge Base
        results = kb_search.search_products(query, num_results=10)
        
        if not results:
            return {
                "found": False,
                "message": f"沒有找到 {material_category} ({normalized_subtype}) 的 {restoration_type} 產品",
                "products": [],
                "count": 0
            }
        
        # 🆕 格式化產品資訊（突出價格）
        formatted_products = []
        
        for idx, result in enumerate(results[:5], 1):  # 最多返回 5 個
            content = result.get('content', '')
            score = result.get('score', 0)
            
            # 🆕 提取價格資訊（使用正則表達式）
            import re
            
            # 🆕 提取價格資訊（匹配 "**價格範圍**: HKD 12,000 - 15,000"）
            price_match = re.search(r'(?:價格(?:範圍)?|price|費用)[*\s:：]*(?:HK\$|HKD|港幣)?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:-|至|to)?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)?', content, re.IGNORECASE)
            
            if price_match:
                min_price = price_match.group(1)
                max_price = price_match.group(2)
                if max_price:
                    price = f"{min_price} - {max_price}"
                else:
                    price = min_price
            else:
                price = "請查詢"
            
            # 🆕 提取製作時間
            time_match = re.search(r'(?:製作時間|delivery|工作天)[:：\s]*(\d+-?\d*)\s*(?:天|days?|工作天)', content, re.IGNORECASE)
            delivery_time = time_match.group(1) if time_match else "5-7"
            
            # 🆕 提取產品代碼（匹配 "**產品代碼**: 1200" 或 "**產品代碼**: 1100, 9033"）
            code_match = re.search(r'(?:產品代碼|product\s*code|代碼)[*\s:：]*([\d,\s]+)', content, re.IGNORECASE)
            if code_match:
                # 提取所有代碼，去除空格
                product_code = code_match.group(1).replace(' ', '')
            else:
                product_code = f"{1000 + idx}"
            
            # 🆕 提取材料名稱（用於區分相同代碼的產品）
            material_match = re.search(r'\*\*材料\*\*[:\s：]*([^\n*]+)', content, re.IGNORECASE)
            material_name = material_match.group(1).strip() if material_match else ""
            
            # 限制內容長度
            content_preview = content[:200] + "..." if len(content) > 200 else content
            
            formatted_products.append({
                "rank": idx,
                "content": content_preview,
                "price": price,
                "delivery_time": f"{delivery_time} 工作天",
                "product_code": product_code,
                "material_name": material_name,
                "score": round(score, 2)
            })
        
        # 🆕 構建友好的回應訊息
        summary = f"找到 {len(formatted_products)} 個 {material_category} ({normalized_subtype}) 的 {restoration_type} 產品：\n\n"
        
        for p in formatted_products:
            # 如果有材料名稱，顯示以幫助區分
            material_info = f" ({p['material_name']})" if p['material_name'] else ""
            summary += f"{p['rank']}. 產品代碼 {p['product_code']}{material_info}\n"
            summary += f"   💰 價格: HK${p['price']}\n"
            summary += f"   ⏰ 製作時間: {p['delivery_time']}\n"
            summary += f"   📋 {p['content'][:100]}...\n\n"
        
        print(f"   ✅ 找到 {len(formatted_products)} 個產品")
        
        return {
            "found": True,
            "message": summary,
            "products": formatted_products,
            "count": len(formatted_products),
            "restoration_type": restoration_type,
            "material_category": material_category,
            "material_subtype": normalized_subtype
        }
    
    except Exception as e:
        print(f"   ❌ 搜尋失敗: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            "error": True,
            "message": f"搜尋失敗: {str(e)}",
            "products": [],
            "count": 0
        }
    
    
    
    

# 建立全域實例
kb_search = None  # 先設為 None
try:
    print("\n" + "="*60)
    print("🔧 初始化 Bedrock Knowledge Base...")
    print("="*60)
    
    # 檢查環境變數
    required_vars = ['AWS_REGION', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'KNOWLEDGE_BASE_ID']
    missing = [v for v in required_vars if not os.getenv(v)]
    
    if missing:
        print(f"\n⚠️  缺少環境變數: {', '.join(missing)}")
        print(f"\n請在 .env 中設定：")
        for var in missing:
            print(f"   {var}=...")
        print(f"\n⚠️  Knowledge Base 功能將被禁用")
        print(f"="*60 + "\n")
        kb_search = None
    else:
        # 初始化
        kb_search = KnowledgeBaseSearch()
        
        print(f"\n✅ Knowledge Base 初始化成功")
        print(f"="*60 + "\n")

except ValueError as e:
    # 環境變數缺失 - 僅警告，不停止啟動
    print(f"\n⚠️  Knowledge Base 初始化失敗: {e}")
    print(f"\n⚠️  Knowledge Base 功能將被禁用，但伺服器可以啟動")
    print(f"="*60 + "\n")
    kb_search = None

except Exception as e:
    # 其他錯誤 - 也僅警告
    print(f"\n⚠️  Knowledge Base 初始化失敗: {e}")
    print(f"\n完整錯誤：")
    import traceback
    traceback.print_exc()
    print(f"\n⚠️  Knowledge Base 功能將被禁用，但伺服器可以啟動")
    print(f"="*60 + "\n")
    kb_search = None