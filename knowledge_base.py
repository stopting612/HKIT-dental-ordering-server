# knowledge_base.py
import boto3
import os
from typing import List, Dict, Optional
import sys

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
    
    
    def search_products(self, query: str, num_results: int = 5) -> List[Dict]:
        """
        搜尋產品
        
        Args:
            query: 搜尋查詢字串（例如："crown 全瓷 前牙"）
            num_results: 返回結果數量（預設 5，最大 100）
        
        Returns:
            產品列表，每個產品包含：
            {
                'content': str,      # 產品描述文字
                'score': float,      # 相關度分數 (0-1)
                'metadata': dict,    # 產品 metadata
                'source': dict       # 來源資訊 (S3 URI 等)
            }
        
        Raises:
            ValueError: 如果 num_results 超出範圍
            Exception: 如果 API 呼叫失敗
        """
        
        # 驗證參數
        if num_results < 1 or num_results > 100:
            raise ValueError(f"num_results 必須在 1-100 之間，目前值：{num_results}")
        
        try:
            print(f"🔍 搜尋 Knowledge Base")
            print(f"   查詢: '{query}'")
            print(f"   返回數量: {num_results}")
            
            # 呼叫 Bedrock Knowledge Base API
            response = self.client.retrieve(
                knowledgeBaseId=self.kb_id,
                retrievalQuery={
                    'text': query
                },
                retrievalConfiguration={
                    'vectorSearchConfiguration': {
                        'numberOfResults': num_results
                    }
                }
            )
            
            # 解析結果
            results = []
            retrieval_results = response.get('retrievalResults', [])
            
            if not retrieval_results:
                print(f"   ⚠️  沒有找到相關產品")
                return []
            
            print(f"   ✅ 找到 {len(retrieval_results)} 個結果")
            
            for idx, item in enumerate(retrieval_results):
                # 提取內容
                content = item.get('content', {}).get('text', '')
                score = item.get('score', 0)
                metadata = item.get('metadata', {})
                location = item.get('location', {})
                
                # 構建結果
                result = {
                    'content': content,
                    'score': score,
                    'metadata': metadata,
                    'source': location
                }
                
                results.append(result)
                
                # Debug 輸出（顯示前 100 字）
                preview = content[:100].replace('\n', ' ')
                print(f"   [{idx+1}] Score: {score:.3f} | {preview}...")
            
            print()
            return results
            
        except self.client.exceptions.ResourceNotFoundException:
            error_msg = f"❌ Knowledge Base 不存在: {self.kb_id}"
            print(error_msg)
            print("   請檢查 KNOWLEDGE_BASE_ID 是否正確")
            raise
            
        except self.client.exceptions.AccessDeniedException:
            error_msg = "❌ 權限不足：無法存取 Knowledge Base"
            print(error_msg)
            print("   請檢查 IAM 權限，需要：bedrock:Retrieve")
            raise
            
        except Exception as e:
            error_msg = f"❌ Knowledge Base 搜尋失敗"
            print(error_msg)
            print(f"   錯誤類型: {type(e).__name__}")
            print(f"   錯誤訊息: {str(e)}")
            raise
    
    
    def search_by_criteria(self, 
                          restoration_type: str, 
                          material: Optional[str] = None, 
                          position_type: Optional[str] = None) -> List[Dict]:
        """
        根據訂單條件搜尋產品
        
        Args:
            restoration_type: 修復類型（crown, bridge, veneer, inlay, onlay）
            material: 材料類型（metal-free, pfm, zirconia, full-metal）
            position_type: 位置類型（anterior, posterior）
        
        Returns:
            產品列表（最多 3 個）
        """
        
        # 材料名稱標準化（中文 → 英文）
        material_map = {
            # 英文
            'metal-free': 'metal-free',
            'all-ceramic': 'metal-free',
            'ceramic': 'metal-free',
            'pfm': 'pfm',
            'porcelain-fused-to-metal': 'pfm',
            'porcelain': 'pfm',
            'full-metal': 'full-metal',
            'full-cast': 'full-metal',
            'metal': 'full-metal',
            'zirconia': 'zirconia',
            'zir': 'zirconia',
            # 中文
            '全瓷': 'metal-free',
            '陶瓷': 'metal-free',
            '烤瓷': 'pfm',
            '全金屬': 'full-metal',
            '全金': 'full-metal',
            '金屬': 'full-metal',
            '氧化鋯': 'zirconia',
            '鋯': 'zirconia'
        }
        
        # 標準化材料名稱
        normalized_material = None
        if material:
            normalized_material = material_map.get(material.lower(), material)
        
        # 建立搜尋查詢（中英文混合，提高召回率）
        query_parts = []
        
        # 1. 修復類型（中英文）
        restoration_names = {
            'crown': 'crown 牙冠',
            'bridge': 'bridge 牙橋',
            'veneer': 'veneer 貼片',
            'inlay': 'inlay 嵌體',
            'onlay': 'onlay 高嵌體'
        }
        query_parts.append(restoration_names.get(restoration_type.lower(), restoration_type))
        
        # 2. 材料（中英文 + 常見品牌）
        if normalized_material:
            material_queries = {
                'metal-free': '全瓷 metal-free ceramic emax IPS',
                'pfm': '烤瓷 PFM porcelain fused',
                'zirconia': '氧化鋯 zirconia FMZ Lava',
                'full-metal': '全金屬 full-metal gold 黃金'
            }
            query_parts.append(material_queries.get(normalized_material, normalized_material))
        
        # 3. 位置（中英文）
        if position_type:
            position_names = {
                'anterior': '前牙 anterior front',
                'posterior': '後牙 posterior back molar'
            }
            query_parts.append(position_names.get(position_type.lower(), position_type))
        
        # 組合查詢
        query = ' '.join(query_parts)
        
        print(f"\n📋 條件搜尋")
        print(f"   修復類型: {restoration_type}")
        print(f"   材料: {normalized_material if normalized_material else '未指定'}")
        print(f"   位置: {position_type if position_type else '未指定'}")
        print(f"   查詢字串: '{query}'")
        
        # 執行搜尋（多返回一些以便過濾）
        results = self.search_products(query, num_results=10)
        
        if not results:
            return []
        
        # 如果有指定材料，進行二次過濾
        if normalized_material:
            filtered = []
            
            # 定義材料關鍵字（用於內容匹配）
            material_keywords = {
                'metal-free': ['全瓷', 'metal-free', 'ceramic', 'emax', 'e.max', 'ips'],
                'pfm': ['pfm', '烤瓷', 'porcelain fused', 'porcelain-fused'],
                'zirconia': ['zirconia', 'zir', '氧化鋯', 'fmz', 'lava'],
                'full-metal': ['full-metal', 'full cast', '全金', '黃金', 'gold', 'titanium', '鈦']
            }
            
            keywords = material_keywords.get(normalized_material, [])
            
            for r in results:
                # 優先檢查 metadata
                metadata_material = r.get('metadata', {}).get('material', '').lower()
                
                if metadata_material == normalized_material:
                    filtered.append(r)
                    continue
                
                # 檢查內容文字
                content_lower = r.get('content', '').lower()
                
                if any(keyword.lower() in content_lower for keyword in keywords):
                    filtered.append(r)
            
            if filtered:
                print(f"   🔎 過濾後: {len(filtered)} 個產品匹配材料 '{normalized_material}'")
                # 返回前 3 個最相關的
                return filtered[:3]
            else:
                print(f"   ⚠️  過濾後沒有產品匹配材料 '{normalized_material}'，返回原始結果")
        
        # 返回前 3 個結果
        return results[:3]
    
    
    def format_products_for_display(self, products: List[Dict]) -> str:
        """
        格式化產品列表為可讀文字
        
        Args:
            products: 產品列表
        
        Returns:
            格式化的產品描述文字
        """
        
        if not products:
            return "沒有找到相關產品。"
        
        formatted = []
        
        for idx, product in enumerate(products, 1):
            content = product.get('content', '')
            score = product.get('score', 0)
            
            # 提取產品代碼（如果有）
            product_code = product.get('metadata', {}).get('product_code', '')
            
            # 限制內容長度（最多 300 字）
            if len(content) > 300:
                content = content[:297] + '...'
            
            formatted.append(f"{idx}. {content}\n   (相關度: {score:.2f})")
        
        return '\n\n'.join(formatted)


# 建立全域實例
try:
    kb_search = KnowledgeBaseSearch()
except (EnvironmentError, ConnectionError) as e:
    print(f"\n{'='*60}")
    print("⚠️  Knowledge Base 初始化失敗")
    print(f"{'='*60}")
    print("伺服器將無法正常運作。")
    print("請修正 .env 設定後重新啟動。\n")
    # 不要直接 sys.exit()，讓 FastAPI 可以啟動並顯示錯誤訊息
    kb_search = None