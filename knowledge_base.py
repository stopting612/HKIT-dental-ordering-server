# knowledge_base.py
import boto3
import os
from typing import List, Dict

class KnowledgeBaseSearch:
    def __init__(self):
        self.client = boto3.client(
            'bedrock-agent-runtime',
            region_name=os.getenv('AWS_REGION', 'us-east-2'),
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
        )
        self.kb_id = os.getenv('KNOWLEDGE_BASE_ID')
    
    def search_products(self, query: str, filters: Dict = None) -> List[Dict]:
        """
        搜尋產品
        
        Args:
            query: 搜尋查詢（例如："全瓷 crown 前牙"）
            filters: 篩選條件
        
        Returns:
            產品列表
        """
        try:
            # 執行搜尋
            response = self.client.retrieve(
                knowledgeBaseId=self.kb_id,
                retrievalQuery={'text': query},
                retrievalConfiguration={
                    'vectorSearchConfiguration': {
                        'numberOfResults': 5
                    }
                }
            )
            
            # 解析結果
            results = []
            for item in response.get('retrievalResults', []):
                results.append({
                    'content': item.get('content', {}).get('text', ''),
                    'score': item.get('score', 0),
                    'metadata': item.get('metadata', {}),
                    'source': item.get('location', {})
                })
            
            return results
            
        except Exception as e:
            print(f"Knowledge Base 搜尋錯誤: {e}")
            return []
    
    def search_by_criteria(self, restoration_type: str, material: str = None, 
                          position_type: str = None) -> List[Dict]:
        """
        根據訂單條件搜尋產品
        
        Args:
            restoration_type: 修復類型（crown, bridge, veneer）
            material: 材料（metal-free, pfm, zirconia, full-metal）
            position_type: 位置類型（anterior, posterior）
        
        Returns:
            產品列表
        """
        # 建立搜尋查詢
        query_parts = [restoration_type]
        
        if material:
            material_names = {
                'metal-free': '全瓷',
                'pfm': '烤瓷',
                'zirconia': '氧化鋯',
                'full-metal': '全金屬'
            }
            query_parts.append(material_names.get(material, material))
        
        if position_type:
            position_names = {
                'anterior': '前牙',
                'posterior': '後牙'
            }
            query_parts.append(position_names.get(position_type, position_type))
        
        query = ' '.join(query_parts)
        
        return self.search_products(query)


# 建立全域實例
kb_search = KnowledgeBaseSearch()