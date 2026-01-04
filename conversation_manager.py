# conversation_manager.py

from encryption import encryption_manager
from supabase import create_client, Client
from datetime import datetime
from typing import Dict, List, Optional
import os
import json

supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)


class ConversationManager:
    """對話管理（加密版本）"""
    
    def __init__(self):
        self.supabase = supabase
        self.encryption = encryption_manager
    
    def log_message(
        self,
        session_id: str,
        role: str,
        content: str,
        user_id: Optional[str] = None,
        order_id: Optional[int] = None,
        tool_calls: Optional[List] = None,
        tool_call_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        tool_arguments: Optional[Dict] = None,
        tool_result: Optional[Dict] = None,
        response_time_ms: Optional[int] = None,
        metadata: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        記錄對話訊息（加密版本）
        
        重要：這個函數不會阻塞，適合在背景執行
        """
        try:
            # ===== 1. 加密對話內容 =====
            encrypted_content = None
            content_hash = None
            
            if content:
                enc_result = self.encryption.encrypt(content)
                encrypted_content = enc_result['encrypted']
                content_hash = enc_result['hash']
            
            # ===== 2. 加密 tool arguments 和 result =====
            encrypted_arguments = None
            encrypted_result = None
            
            if tool_arguments:
                enc_args = self.encryption.encrypt_json(tool_arguments)
                encrypted_arguments = enc_args['encrypted']
            
            if tool_result:
                enc_res = self.encryption.encrypt_json(tool_result)
                encrypted_result = enc_res['encrypted']
            
            # ===== 3. 準備資料 =====
            message = {
                'session_id': session_id,
                'user_id': user_id,
                'order_id': order_id,
                'role': role,
                
                # 🔐 加密欄位
                'content_encrypted': encrypted_content,
                'content_hash': content_hash,
                'tool_arguments_encrypted': encrypted_arguments,
                'tool_result_encrypted': encrypted_result,
                
                # 明文欄位（開發環境可用，生產環境為 NULL）
                'content': content if not self.encryption.encryption_enabled else None,
                
                # 元數據
                'tool_calls': tool_calls,
                'tool_call_id': tool_call_id,
                'tool_name': tool_name,
                'message_length': len(content) if content else 0,
                'response_time_ms': response_time_ms,
                
                # 加密元數據
                'encryption_version': enc_result['version'] if encrypted_content else None,
                'encrypted_at': datetime.now().isoformat() if encrypted_content else None,
                
                'metadata': metadata or {}
            }
            
            # ===== 4. 寫入資料庫 =====
            response = self.supabase.table('conversations').insert(message).execute()
            
            if response.data:
                # print(f"✅ 對話已加密儲存: {session_id} ({role})")
                return response.data[0]
            
            return None
        
        except Exception as e:
            print(f"❌ 記錄對話失敗: {e}")
            return None
    
    def get_conversation_history(
        self,
        session_id: str,
        decrypt: bool = True,
        user_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """取得對話歷史（自動解密）"""
        try:
            response = self.supabase.table('conversations')\
                .select('*')\
                .eq('session_id', session_id)\
                .order('created_at', desc=False)\
                .limit(limit)\
                .execute()
            
            if not response.data:
                return []
            
            decrypted_messages = []
            
            for msg in response.data:
                if decrypt and msg.get('content_encrypted'):
                    # 解密內容
                    try:
                        decrypted_content = self.encryption.decrypt(
                            msg['content_encrypted']
                        )
                        
                        # 驗證完整性
                        if msg.get('content_hash') and decrypted_content:
                            is_valid = self.encryption.verify_integrity(
                                decrypted_content,
                                msg['content_hash']
                            )
                            if not is_valid:
                                print(f"⚠️  內容完整性驗證失敗: {msg['id']}")
                        
                        msg['content'] = decrypted_content
                    except Exception as e:
                        print(f"❌ 解密失敗: {e}")
                        msg['content'] = "[解密失敗]"
                    
                    # 解密 tool arguments
                    if msg.get('tool_arguments_encrypted'):
                        try:
                            msg['tool_arguments'] = self.encryption.decrypt_json(
                                msg['tool_arguments_encrypted']
                            )
                        except:
                            pass
                    
                    # 解密 tool result
                    if msg.get('tool_result_encrypted'):
                        try:
                            msg['tool_result'] = self.encryption.decrypt_json(
                                msg['tool_result_encrypted']
                            )
                        except:
                            pass
                
                decrypted_messages.append(msg)
            
            return decrypted_messages
        
        except Exception as e:
            print(f"❌ 取得對話歷史失敗: {e}")
            return []


class SessionManager:
    """會話管理"""
    
    def __init__(self):
        self.supabase = supabase
    
    def create_session(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        session_type: str = 'order'
    ) -> Optional[Dict]:
        """建立新 session"""
        try:
            # 檢查是否已存在
            existing = self.supabase.table('sessions')\
                .select('id')\
                .eq('session_id', session_id)\
                .execute()
            
            if existing.data:
                # print(f"⚠️  Session 已存在: {session_id}")
                return existing.data[0]
            
            session = {
                'session_id': session_id,
                'user_id': user_id,
                'session_type': session_type,
                'status': 'active',
                'message_count': 0,
                'tool_call_count': 0,
                'started_at': datetime.now().isoformat(),
                'last_activity_at': datetime.now().isoformat()
            }
            
            response = self.supabase.table('sessions').insert(session).execute()
            
            if response.data:
                print(f"✅ Session 建立: {session_id}")
                return response.data[0]
            
            return None
        
        except Exception as e:
            print(f"❌ Session 建立失敗: {e}")
            return None
    
    def update_session_activity(self, session_id: str):
        """更新 session 活動時間和統計"""
        try:
            # 計算訊息數
            count_response = self.supabase.table('conversations')\
                .select('id', count='exact')\
                .eq('session_id', session_id)\
                .execute()
            
            message_count = count_response.count if count_response.count else 0
            
            # 計算 tool call 數
            tool_count = self.supabase.table('conversations')\
                .select('id', count='exact')\
                .eq('session_id', session_id)\
                .eq('role', 'tool')\
                .execute()
            
            tool_call_count = tool_count.count if tool_count.count else 0
            
            # 更新
            self.supabase.table('sessions')\
                .update({
                    'message_count': message_count,
                    'tool_call_count': tool_call_count,
                    'last_activity_at': datetime.now().isoformat()
                })\
                .eq('session_id', session_id)\
                .execute()
        
        except Exception as e:
            print(f"⚠️  更新 session 活動失敗: {e}")
    
    def end_session(
        self,
        session_id: str,
        status: str = 'completed',
        order_id: Optional[int] = None
    ) -> bool:
        """結束 session"""
        try:
            # 取得開始時間
            session_data = self.supabase.table('sessions')\
                .select('started_at')\
                .eq('session_id', session_id)\
                .single()\
                .execute()
            
            if session_data.data:
                started_at = datetime.fromisoformat(
                    session_data.data['started_at'].replace('Z', '+00:00')
                )
                duration = int((datetime.now(started_at.tzinfo) - started_at).total_seconds())
                
                update_data = {
                    'status': status,
                    'ended_at': datetime.now().isoformat(),
                    'duration_seconds': duration
                }
                
                if order_id:
                    update_data['order_created'] = True
                    update_data['order_id'] = order_id
                
                self.supabase.table('sessions')\
                    .update(update_data)\
                    .eq('session_id', session_id)\
                    .execute()
                
                print(f"✅ Session 結束: {session_id} ({duration}s)")
                return True
            
            return False
        
        except Exception as e:
            print(f"❌ 結束 session 失敗: {e}")
            return False


# 全域實例
conversation_manager = ConversationManager()
session_manager = SessionManager()