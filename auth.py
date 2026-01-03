# auth.py

import bcrypt
import secrets
import string
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv()

supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)


class AuthManager:
    """用戶認證管理"""
    
    # 安全設定
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 30
    PASSWORD_MIN_LENGTH = 8
    RESET_TOKEN_EXPIRY_HOURS = 24
    VERIFICATION_TOKEN_EXPIRY_HOURS = 48
    
    def __init__(self):
        self.supabase = supabase
    
    # ===== 密碼處理 =====
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash 密碼（使用 bcrypt）
        
        Args:
            password: 明文密碼
        
        Returns:
            bcrypt hash（已包含 salt）
        """
        # bcrypt 會自動生成 salt 並包含在 hash 中
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(password.encode('utf-8'), salt)
        return password_hash.decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """
        驗證密碼
        
        Args:
            password: 明文密碼
            password_hash: 儲存的 hash
        
        Returns:
            True if 密碼正確
        """
        try:
            return bcrypt.checkpw(
                password.encode('utf-8'),
                password_hash.encode('utf-8')
            )
        except Exception as e:
            print(f"❌ 密碼驗證失敗: {e}")
            return False
    
    @staticmethod
    def validate_password_strength(password: str) -> Tuple[bool, str]:
        """
        驗證密碼強度
        
        Returns:
            (is_valid, error_message)
        """
        if len(password) < AuthManager.PASSWORD_MIN_LENGTH:
            return False, f"密碼至少需要 {AuthManager.PASSWORD_MIN_LENGTH} 個字符"
        
        # 檢查是否包含數字
        if not any(char.isdigit() for char in password):
            return False, "密碼必須包含至少一個數字"
        
        # 檢查是否包含字母
        if not any(char.isalpha() for char in password):
            return False, "密碼必須包含至少一個字母"
        
        return True, ""
    
    @staticmethod
    def generate_token(length: int = 32) -> str:
        """生成隨機 token"""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    # ===== 用戶註冊 =====
    
    def register_user(
        self,
        email: str,
        password: str,
        full_name: str,
        role: str = 'dentist',
        clinic_name: Optional[str] = None,
        phone: Optional[str] = None
    ) -> Optional[Dict]:
        """
        註冊新用戶
        
        Args:
            email: Email
            password: 密碼（明文）
            full_name: 姓名
            role: 角色
            clinic_name: 診所名稱
            phone: 電話
        
        Returns:
            建立的用戶資料（不含密碼）
        """
        try:
            # 1. 驗證密碼強度
            is_valid, error_msg = self.validate_password_strength(password)
            if not is_valid:
                print(f"❌ {error_msg}")
                return None
            
            # 2. 檢查 email 是否已存在
            existing = self.supabase.table('users')\
                .select('id')\
                .eq('email', email)\
                .execute()
            
            if existing.data:
                print(f"❌ Email 已被註冊: {email}")
                return None
            
            # 3. Hash 密碼
            password_hash = self.hash_password(password)
            
            # 4. 生成驗證 token
            verification_token = self.generate_token()
            verification_expires = datetime.now() + timedelta(
                hours=self.VERIFICATION_TOKEN_EXPIRY_HOURS
            )
            
            # 5. 建立用戶
            user_data = {
                'email': email,
                'password_hash': password_hash,
                'password_updated_at': datetime.now().isoformat(),
                'full_name': full_name,
                'role': role,
                'clinic_name': clinic_name,
                'phone': phone,
                'is_active': True,
                'is_verified': False,  # 需要 email 驗證
                'verification_token': verification_token,
                'verification_token_expires_at': verification_expires.isoformat(),
                'login_attempts': 0
            }
            
            response = self.supabase.table('users').insert(user_data).execute()
            
            if response.data:
                user = response.data[0]
                
                # 移除敏感資料
                user.pop('password_hash', None)
                user.pop('verification_token', None)
                
                print(f"✅ 用戶註冊成功: {email}")
                
                # TODO: 發送驗證 email
                # send_verification_email(email, verification_token)
                
                return user
            
            return None
        
        except Exception as e:
            print(f"❌ 註冊失敗: {e}")
            return None
    
    # ===== 用戶登入 =====
    
    def login(self, email: str, password: str, ip_address: Optional[str] = None) -> Optional[Dict]:
        """
        用戶登入
        
        Args:
            email: Email
            password: 密碼（明文）
            ip_address: 登入 IP
        
        Returns:
            用戶資料（含 token）或 None
        """
        try:
            # 1. 查詢用戶
            response = self.supabase.table('users')\
                .select('*')\
                .eq('email', email)\
                .execute()
            
            if not response.data:
                print(f"❌ 用戶不存在: {email}")
                return None
            
            user = response.data[0]
            user_id = user['id']
            
            # 2. 檢查帳號是否被鎖定
            if user.get('locked_until'):
                locked_until = datetime.fromisoformat(user['locked_until'].replace('Z', '+00:00'))
                if datetime.now(locked_until.tzinfo) < locked_until:
                    remaining = (locked_until - datetime.now(locked_until.tzinfo)).seconds // 60
                    print(f"❌ 帳號已鎖定，剩餘 {remaining} 分鐘")
                    return None
                else:
                    # 鎖定期已過，重置
                    self.supabase.table('users')\
                        .update({
                            'locked_until': None,
                            'login_attempts': 0
                        })\
                        .eq('id', user_id)\
                        .execute()
            
            # 3. 檢查帳號是否啟用
            if not user.get('is_active'):
                print(f"❌ 帳號已停用: {email}")
                return None
            
            # 4. 驗證密碼
            if not self.verify_password(password, user['password_hash']):
                # 密碼錯誤，增加失敗次數
                login_attempts = user.get('login_attempts', 0) + 1
                
                update_data = {'login_attempts': login_attempts}
                
                # 如果失敗次數達到上限，鎖定帳號
                if login_attempts >= self.MAX_LOGIN_ATTEMPTS:
                    locked_until = datetime.now() + timedelta(
                        minutes=self.LOCKOUT_DURATION_MINUTES
                    )
                    update_data['locked_until'] = locked_until.isoformat()
                    
                    print(f"❌ 密碼錯誤次數過多，帳號已鎖定 {self.LOCKOUT_DURATION_MINUTES} 分鐘")
                else:
                    remaining_attempts = self.MAX_LOGIN_ATTEMPTS - login_attempts
                    print(f"❌ 密碼錯誤，剩餘嘗試次數: {remaining_attempts}")
                
                self.supabase.table('users')\
                    .update(update_data)\
                    .eq('id', user_id)\
                    .execute()
                
                return None
            
            # 5. 密碼正確，更新登入資訊
            self.supabase.table('users')\
                .update({
                    'login_attempts': 0,
                    'locked_until': None,
                    'last_login_at': datetime.now().isoformat(),
                    'last_login_ip': ip_address
                })\
                .eq('id', user_id)\
                .execute()
            
            # 6. 移除敏感資料
            user.pop('password_hash', None)
            user.pop('password_salt', None)
            user.pop('reset_token', None)
            user.pop('verification_token', None)
            
            print(f"✅ 登入成功: {email}")
            
            # TODO: 生成 JWT token
            # user['access_token'] = generate_jwt_token(user_id)
            
            return user
        
        except Exception as e:
            print(f"❌ 登入失敗: {e}")
            return None
    
    # ===== 密碼重設 =====
    
    def request_password_reset(self, email: str) -> bool:
        """
        請求重設密碼（發送 reset token）
        
        Args:
            email: Email
        
        Returns:
            成功返回 True
        """
        try:
            # 1. 查詢用戶
            response = self.supabase.table('users')\
                .select('id')\
                .eq('email', email)\
                .execute()
            
            if not response.data:
                # 為了安全，即使用戶不存在也返回成功
                # 避免被用於探測 email 是否存在
                print(f"⚠️  用戶不存在，但仍返回成功: {email}")
                return True
            
            user_id = response.data[0]['id']
            
            # 2. 生成 reset token
            reset_token = self.generate_token()
            reset_expires = datetime.now() + timedelta(
                hours=self.RESET_TOKEN_EXPIRY_HOURS
            )
            
            # 3. 更新用戶
            self.supabase.table('users')\
                .update({
                    'reset_token': reset_token,
                    'reset_token_expires_at': reset_expires.isoformat()
                })\
                .eq('id', user_id)\
                .execute()
            
            print(f"✅ 密碼重設請求成功: {email}")
            print(f"   Reset Token: {reset_token}")
            
            # TODO: 發送 reset email
            # send_reset_email(email, reset_token)
            
            return True
        
        except Exception as e:
            print(f"❌ 密碼重設請求失敗: {e}")
            return False
    
    def reset_password(self, reset_token: str, new_password: str) -> bool:
        """
        重設密碼
        
        Args:
            reset_token: 重設 token
            new_password: 新密碼
        
        Returns:
            成功返回 True
        """
        try:
            # 1. 驗證密碼強度
            is_valid, error_msg = self.validate_password_strength(new_password)
            if not is_valid:
                print(f"❌ {error_msg}")
                return False
            
            # 2. 查詢用戶
            response = self.supabase.table('users')\
                .select('*')\
                .eq('reset_token', reset_token)\
                .execute()
            
            if not response.data:
                print(f"❌ 無效的 reset token")
                return False
            
            user = response.data[0]
            
            # 3. 檢查 token 是否過期
            if user.get('reset_token_expires_at'):
                expires_at = datetime.fromisoformat(
                    user['reset_token_expires_at'].replace('Z', '+00:00')
                )
                if datetime.now(expires_at.tzinfo) > expires_at:
                    print(f"❌ Reset token 已過期")
                    return False
            
            # 4. Hash 新密碼
            password_hash = self.hash_password(new_password)
            
            # 5. 更新用戶
            self.supabase.table('users')\
                .update({
                    'password_hash': password_hash,
                    'password_updated_at': datetime.now().isoformat(),
                    'reset_token': None,
                    'reset_token_expires_at': None,
                    'login_attempts': 0,
                    'locked_until': None
                })\
                .eq('id', user['id'])\
                .execute()
            
            print(f"✅ 密碼重設成功: {user['email']}")
            
            return True
        
        except Exception as e:
            print(f"❌ 密碼重設失敗: {e}")
            return False
    
    # ===== Email 驗證 =====
    
    def verify_email(self, verification_token: str) -> bool:
        """
        驗證 Email
        
        Args:
            verification_token: 驗證 token
        
        Returns:
            成功返回 True
        """
        try:
            # 1. 查詢用戶
            response = self.supabase.table('users')\
                .select('*')\
                .eq('verification_token', verification_token)\
                .execute()
            
            if not response.data:
                print(f"❌ 無效的 verification token")
                return False
            
            user = response.data[0]
            
            # 2. 檢查 token 是否過期
            if user.get('verification_token_expires_at'):
                expires_at = datetime.fromisoformat(
                    user['verification_token_expires_at'].replace('Z', '+00:00')
                )
                if datetime.now(expires_at.tzinfo) > expires_at:
                    print(f"❌ Verification token 已過期")
                    return False
            
            # 3. 更新用戶
            self.supabase.table('users')\
                .update({
                    'is_verified': True,
                    'verification_token': None,
                    'verification_token_expires_at': None
                })\
                .eq('id', user['id'])\
                .execute()
            
            print(f"✅ Email 驗證成功: {user['email']}")
            
            return True
        
        except Exception as e:
            print(f"❌ Email 驗證失敗: {e}")
            return False


# 建立全域實例
auth_manager = AuthManager()