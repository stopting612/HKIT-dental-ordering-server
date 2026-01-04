# order_manager.py

from supabase import create_client, Client
from datetime import datetime
from typing import Dict, List, Optional
import os
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

# 初始化 Supabase 客戶端
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)


class OrderManager:
    """訂單管理類別"""
    
    def __init__(self):
        self.supabase = supabase
    
    def create_order(
        self,
        session_id: str,
        user_id: Optional[str],
        order_data: Dict
    ) -> Optional[Dict]:
        """
        建立新訂單
        
        Args:
            session_id: 對話 Session ID
            user_id: 用戶 ID（UUID）
            order_data: 訂單資料字典
                必要欄位：
                - restoration_type
                - tooth_positions
                - material_category
                - material_subtype
                - patient_name
                可選欄位：
                - product_code
                - product_name
                - shade (預設 A2)
                - bridge_span
                - position_type
                - patient_id
                - notes
        
        Returns:
            建立的訂單資料，失敗返回 None
        """
        try:
            # 生成訂單編號
            order_number = self._generate_order_number(session_id)
            
            # 準備訂單資料
            order = {
                # 訂單編號
                'order_number': order_number,
                
                # 關聯
                'user_id': user_id,
                'session_id': session_id,
                
                # 訂單基本資訊
                'restoration_type': order_data.get('restoration_type'),
                'tooth_positions': order_data.get('tooth_positions'),
                
                # 材料資訊
                'material_category': order_data.get('material_category'),
                'material_subtype': order_data.get('material_subtype'),
                'material': self._format_material(
                    order_data.get('material_category'),
                    order_data.get('material_subtype')
                ),
                
                # 產品資訊
                'product_code': order_data.get('product_code'),
                'product_name': order_data.get('product_name'),
                
                # 病人資訊
                'patient_name': order_data.get('patient_name'),
                'patient_id': order_data.get('patient_id'),
                
                # 臨床資訊
                'shade': order_data.get('shade', 'A2'),
                'bridge_span': order_data.get('bridge_span'),
                'position_type': order_data.get('position_type'),
                
                # 訂單狀態
                'status': 'confirmed',
                'confirmed_at': datetime.now().isoformat(),
                
                # 價格與時間（可選）
                'estimated_price': order_data.get('estimated_price'),
                'estimated_delivery_days': order_data.get('estimated_delivery_days'),
                
                # 備註
                'notes': order_data.get('notes'),
                
                # 元數據（存儲完整的 order_data）
                'metadata': order_data
            }
            
            # 插入到 Supabase
            print(f"\n💾 插入訂單到 Supabase: {order_number}")
            print(f"   用戶 ID: {user_id}")
            print(f"   Session ID: {session_id}")
            
            response = self.supabase.table('orders').insert(order).execute()
            
            if response.data and len(response.data) > 0:
                created_order = response.data[0]
                print(f"✅ 訂單建立成功: {order_number}")
                print(f"   訂單 ID: {created_order['id']}")
                print(f"   修復類型: {created_order['restoration_type']}")
                print(f"   病人: {created_order['patient_name']}")
                
                return created_order
            else:
                print(f"❌ 訂單建立失敗: 無回應資料")
                return None
        
        except Exception as e:
            print(f"❌ 訂單建立失敗: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_order(self, order_number: str) -> Optional[Dict]:
        """
        查詢特定訂單
        
        Args:
            order_number: 訂單編號
        
        Returns:
            訂單資料，找不到返回 None
        """
        try:
            response = self.supabase.table('orders')\
                .select('*')\
                .eq('order_number', order_number)\
                .execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            
            return None
        
        except Exception as e:
            print(f"❌ 查詢訂單失敗: {e}")
            return None
    
    def get_order_by_id(self, order_id: int) -> Optional[Dict]:
        """
        查詢特定訂單（by ID）
        
        Args:
            order_id: 訂單 ID
        
        Returns:
            訂單資料，找不到返回 None
        """
        try:
            response = self.supabase.table('orders')\
                .select('*')\
                .eq('id', order_id)\
                .execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            
            return None
        
        except Exception as e:
            print(f"❌ 查詢訂單失敗: {e}")
            return None
    
    def get_recent_orders(self, limit: int = 10, user_id: Optional[str] = None) -> List[Dict]:
        """
        取得最近的訂單
        
        Args:
            limit: 返回數量
            user_id: 用戶 ID（可選，如果提供則只返回該用戶的訂單）
        
        Returns:
            訂單列表
        """
        try:
            query = self.supabase.table('orders').select('*')
            
            # 如果提供 user_id，只查詢該用戶的訂單
            if user_id:
                query = query.eq('user_id', user_id)
            
            response = query.order('created_at', desc=True).limit(limit).execute()
            
            return response.data if response.data else []
        
        except Exception as e:
            print(f"❌ 查詢最近訂單失敗: {e}")
            return []
    
    def get_orders_by_patient(self, patient_name: str, user_id: Optional[str] = None) -> List[Dict]:
        """
        查詢特定病人的訂單
        
        Args:
            patient_name: 病人姓名
            user_id: 用戶 ID（可選）
        
        Returns:
            訂單列表
        """
        try:
            query = self.supabase.table('orders')\
                .select('*')\
                .eq('patient_name', patient_name)
            
            if user_id:
                query = query.eq('user_id', user_id)
            
            response = query.order('created_at', desc=True).execute()
            
            return response.data if response.data else []
        
        except Exception as e:
            print(f"❌ 查詢病人訂單失敗: {e}")
            return []
    
    def get_orders_by_session(self, session_id: str) -> List[Dict]:
        """
        查詢特定 session 的訂單
        
        Args:
            session_id: Session ID
        
        Returns:
            訂單列表
        """
        try:
            response = self.supabase.table('orders')\
                .select('*')\
                .eq('session_id', session_id)\
                .order('created_at', desc=True)\
                .execute()
            
            return response.data if response.data else []
        
        except Exception as e:
            print(f"❌ 查詢 session 訂單失敗: {e}")
            return []
    
    def update_order_status(
        self,
        order_number: str,
        status: str,
        notes: Optional[str] = None
    ) -> bool:
        """
        更新訂單狀態
        
        Args:
            order_number: 訂單編號
            status: 新狀態 (pending, confirmed, processing, completed, cancelled, rejected)
            notes: 備註（可選）
        
        Returns:
            成功返回 True，失敗返回 False
        """
        try:
            # 驗證狀態
            valid_statuses = ['pending', 'confirmed', 'processing', 'completed', 'cancelled', 'rejected']
            if status not in valid_statuses:
                print(f"❌ 無效的狀態: {status}")
                return False
            
            update_data = {'status': status}
            
            # 根據狀態更新對應的時間戳
            if status == 'completed':
                update_data['completed_at'] = datetime.now().isoformat()
            
            if notes:
                update_data['notes'] = notes
            
            response = self.supabase.table('orders')\
                .update(update_data)\
                .eq('order_number', order_number)\
                .execute()
            
            if response.data and len(response.data) > 0:
                print(f"✅ 訂單 {order_number} 狀態更新為: {status}")
                return True
            
            return False
        
        except Exception as e:
            print(f"❌ 更新訂單狀態失敗: {e}")
            return False
    
    def cancel_order(
        self,
        order_number: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        取消訂單
        
        Args:
            order_number: 訂單編號
            reason: 取消原因（可選）
        
        Returns:
            成功返回 True，失敗返回 False
        """
        try:
            update_data = {
                'status': 'cancelled',
                'rejection_reason': reason
            }
            
            response = self.supabase.table('orders')\
                .update(update_data)\
                .eq('order_number', order_number)\
                .execute()
            
            if response.data and len(response.data) > 0:
                print(f"✅ 訂單 {order_number} 已取消")
                if reason:
                    print(f"   原因: {reason}")
                return True
            
            return False
        
        except Exception as e:
            print(f"❌ 取消訂單失敗: {e}")
            return False
    
    def delete_order(self, order_number: str) -> bool:
        """
        刪除訂單
        
        Args:
            order_number: 訂單編號
        
        Returns:
            成功返回 True，失敗返回 False
        """
        try:
            response = self.supabase.table('orders')\
                .delete()\
                .eq('order_number', order_number)\
                .execute()
            
            if response.data:
                print(f"✅ 訂單 {order_number} 已刪除")
                return True
            
            return False
        
        except Exception as e:
            print(f"❌ 刪除訂單失敗: {e}")
            return False
    
    def get_order_statistics(self, user_id: Optional[str] = None) -> Dict:
        """
        取得訂單統計
        
        Args:
            user_id: 用戶 ID（可選，如果提供則只統計該用戶的訂單）
        
        Returns:
            統計資料字典
        """
        try:
            query = self.supabase.table('orders').select('*')
            
            if user_id:
                query = query.eq('user_id', user_id)
            
            response = query.execute()
            
            if not response.data:
                return {
                    'total_orders': 0,
                    'by_status': {},
                    'by_restoration_type': {},
                    'by_material': {}
                }
            
            orders = response.data
            
            # 統計
            stats = {
                'total_orders': len(orders),
                'by_status': {},
                'by_restoration_type': {},
                'by_material': {},
                'total_patients': len(set(o['patient_name'] for o in orders))
            }
            
            # 按狀態統計
            for order in orders:
                status = order.get('status', 'unknown')
                stats['by_status'][status] = stats['by_status'].get(status, 0) + 1
                
                # 按修復類型統計
                resto_type = order.get('restoration_type', 'unknown')
                stats['by_restoration_type'][resto_type] = stats['by_restoration_type'].get(resto_type, 0) + 1
                
                # 按材料統計
                material = order.get('material', 'unknown')
                stats['by_material'][material] = stats['by_material'].get(material, 0) + 1
            
            return stats
        
        except Exception as e:
            print(f"❌ 取得訂單統計失敗: {e}")
            return {
                'total_orders': 0,
                'by_status': {},
                'by_restoration_type': {},
                'by_material': {}
            }
    
    # ===== 輔助方法 =====
    
    @staticmethod
    def _generate_order_number(session_id: str) -> str:
        """
        生成訂單編號
        
        格式: ORD-YYYYMMDD-HHMMSS-XXX
        例如: ORD-20260103-143022-abc
        """
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        session_suffix = session_id[-3:] if len(session_id) >= 3 else '001'
        return f"ORD-{timestamp}-{session_suffix}"
    
    @staticmethod
    def _format_material(category: Optional[str], subtype: Optional[str]) -> Optional[str]:
        """
        格式化材料字串
        
        例如: "metal-free (emax)"
        """
        if not category:
            return None
        
        if subtype:
            return f"{category} ({subtype})"
        
        return category


# 建立全域實例
order_manager = OrderManager()


# ===== 測試用函數 =====

def test_order_manager():
    """測試 OrderManager 功能"""
    
    print("\n" + "="*60)
    print("測試 OrderManager")
    print("="*60)
    
    # 測試資料
    test_order_data = {
        'restoration_type': 'crown',
        'tooth_positions': '11',
        'material_category': 'metal-free',
        'material_subtype': 'emax',
        'product_code': '3630',
        'product_name': 'IPS e.max Crown',
        'patient_name': '測試病人',
        'shade': 'A2',
        'notes': '這是測試訂單'
    }
    
    # 取得測試用戶 ID
    test_user = supabase.table('users').select('id').limit(1).execute()
    if not test_user.data:
        print("❌ 找不到測試用戶，請先建立用戶")
        return
    
    user_id = test_user.data[0]['id']
    session_id = f"test-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # 1. 建立訂單
    print("\n📋 測試 1: 建立訂單")
    order = order_manager.create_order(
        session_id=session_id,
        user_id=user_id,
        order_data=test_order_data
    )
    
    if order:
        order_number = order['order_number']
        print(f"✅ 訂單建立成功: {order_number}")
        
        # 2. 查詢訂單
        print("\n📋 測試 2: 查詢訂單")
        found_order = order_manager.get_order(order_number)
        if found_order:
            print(f"✅ 訂單查詢成功")
            print(f"   病人: {found_order['patient_name']}")
            print(f"   狀態: {found_order['status']}")
        
        # 3. 更新狀態
        print("\n📋 測試 3: 更新訂單狀態")
        success = order_manager.update_order_status(
            order_number=order_number,
            status='processing',
            notes='開始製作'
        )
        if success:
            print(f"✅ 狀態更新成功")
        
        # 4. 查詢最近訂單
        print("\n📋 測試 4: 查詢最近訂單")
        recent = order_manager.get_recent_orders(limit=5)
        print(f"✅ 找到 {len(recent)} 個最近訂單")
        
        # 5. 統計
        print("\n📋 測試 5: 訂單統計")
        stats = order_manager.get_order_statistics()
        print(f"✅ 統計資料:")
        print(f"   總訂單數: {stats['total_orders']}")
        print(f"   按狀態: {stats['by_status']}")
        print(f"   按類型: {stats['by_restoration_type']}")
    
    print("\n" + "="*60)
    print("🎉 測試完成")
    print("="*60)


if __name__ == "__main__":
    # 執行測試
    test_order_manager()