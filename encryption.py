# encryption.py

from cryptography.fernet import Fernet
import os
import json
import hashlib
import base64
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()


class EncryptionManager:
    """加密管理器"""
    
    def __init__(self):
        self.encryption_enabled = os.getenv('ENCRYPTION_ENABLED', 'true').lower() == 'true'
        
        if self.encryption_enabled:
            key = os.getenv('ENCRYPTION_KEY')
            if not key:
                raise ValueError("❌ ENCRYPTION_KEY 未設定！請在 .env 中設定。")
            
            self.cipher = Fernet(key.encode())
            self.key_id = os.getenv('ENCRYPTION_KEY_ID', 'default')
            
            # 備用金鑰（用於金鑰輪換）
            backup_key = os.getenv('ENCRYPTION_KEY_BACKUP')
            self.backup_cipher = Fernet(backup_key.encode()) if backup_key else None
            
            print(f"✅ 加密已啟用 (Key ID: {self.key_id})")
        else:
            self.cipher = None
            self.key_id = 'none'
            print("⚠️  加密已停用（僅限開發環境）")
    
    def encrypt(self, plaintext: str) -> Dict[str, str]:
        """
        加密文本
        
        Returns:
            {
                'encrypted': 加密後的文本,
                'hash': SHA-256 hash,
                'key_id': 金鑰 ID,
                'version': 加密版本
            }
        """
        if not self.encryption_enabled or not plaintext:
            return {
                'encrypted': None,
                'hash': self._compute_hash(plaintext) if plaintext else None,
                'key_id': 'none',
                'version': 'v0-plaintext'
            }
        
        try:
            # 加密
            encrypted_bytes = self.cipher.encrypt(plaintext.encode('utf-8'))
            encrypted_base64 = base64.b64encode(encrypted_bytes).decode('utf-8')
            
            # 計算 hash
            content_hash = self._compute_hash(plaintext)
            
            return {
                'encrypted': encrypted_base64,
                'hash': content_hash,
                'key_id': self.key_id,
                'version': 'v1'
            }
        
        except Exception as e:
            print(f"❌ 加密失敗: {e}")
            raise
    
    def decrypt(self, encrypted_data: str, key_id: Optional[str] = None) -> Optional[str]:
        """解密文本"""
        if not self.encryption_enabled or not encrypted_data:
            return None
        
        try:
            encrypted_bytes = base64.b64decode(encrypted_data.encode('utf-8'))
            
            # 嘗試主金鑰
            try:
                decrypted_bytes = self.cipher.decrypt(encrypted_bytes)
                return decrypted_bytes.decode('utf-8')
            except Exception:
                # 嘗試備用金鑰
                if self.backup_cipher:
                    decrypted_bytes = self.backup_cipher.decrypt(encrypted_bytes)
                    return decrypted_bytes.decode('utf-8')
                raise
        
        except Exception as e:
            print(f"❌ 解密失敗: {e}")
            return None
    
    def encrypt_json(self, data: Dict[str, Any]) -> Dict[str, str]:
        """加密 JSON"""
        json_str = json.dumps(data, ensure_ascii=False)
        return self.encrypt(json_str)
    
    def decrypt_json(self, encrypted_data: str) -> Optional[Dict[str, Any]]:
        """解密 JSON"""
        decrypted_str = self.decrypt(encrypted_data)
        if decrypted_str:
            return json.loads(decrypted_str)
        return None
    
    def verify_integrity(self, plaintext: str, stored_hash: str) -> bool:
        """驗證完整性"""
        computed_hash = self._compute_hash(plaintext)
        return computed_hash == stored_hash
    
    @staticmethod
    def _compute_hash(text: str) -> str:
        """計算 SHA-256 hash"""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()


# 全域實例
encryption_manager = EncryptionManager()