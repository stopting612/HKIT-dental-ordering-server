# test_auth.py

from auth import auth_manager

def test_user_registration():
    """測試用戶註冊"""
    print("\n" + "="*60)
    print("測試 1: 用戶註冊")
    print("="*60)
    
    # 註冊用戶
    user = auth_manager.register_user(
        email='test@dental.hk',
        password='Test1234!',
        full_name='測試醫生',
        role='dentist',
        clinic_name='測試診所',
        phone='91234567'
    )
    
    if user:
        print(f"\n✅ 註冊成功！")
        print(f"   ID: {user['id']}")
        print(f"   Email: {user['email']}")
        print(f"   姓名: {user['full_name']}")
        print(f"   已驗證: {user['is_verified']}")
    else:
        print(f"\n❌ 註冊失敗")


def test_weak_password():
    """測試弱密碼"""
    print("\n" + "="*60)
    print("測試 2: 弱密碼（應該失敗）")
    print("="*60)
    
    user = auth_manager.register_user(
        email='weak@dental.hk',
        password='123',  # 太短
        full_name='弱密碼用戶'
    )
    
    if not user:
        print(f"\n✅ 正確拒絕弱密碼")
    else:
        print(f"\n❌ 不應該允許弱密碼")


def test_login_success():
    """測試登入成功"""
    print("\n" + "="*60)
    print("測試 3: 登入（正確密碼）")
    print("="*60)
    
    user = auth_manager.login(
        email='test@dental.hk',
        password='Test1234!',
        ip_address='127.0.0.1'
    )
    
    if user:
        print(f"\n✅ 登入成功！")
        print(f"   Email: {user['email']}")
        print(f"   姓名: {user['full_name']}")
        print(f"   最後登入: {user.get('last_login_at')}")
    else:
        print(f"\n❌ 登入失敗")


def test_login_failure():
    """測試登入失敗"""
    print("\n" + "="*60)
    print("測試 4: 登入（錯誤密碼）")
    print("="*60)
    
    user = auth_manager.login(
        email='test@dental.hk',
        password='WrongPassword123',
        ip_address='127.0.0.1'
    )
    
    if not user:
        print(f"\n✅ 正確拒絕錯誤密碼")
    else:
        print(f"\n❌ 不應該允許錯誤密碼登入")


def test_password_reset():
    """測試密碼重設"""
    print("\n" + "="*60)
    print("測試 5: 密碼重設")
    print("="*60)
    
    # 1. 請求重設
    success = auth_manager.request_password_reset('test@dental.hk')
    
    if success:
        print(f"\n✅ 重設請求成功")
        
        # 2. 從資料庫取得 reset token（實際應該從 email 中取得）
        from supabase import create_client
        import os
        supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))
        
        response = supabase.table('users')\
            .select('reset_token')\
            .eq('email', 'test@dental.hk')\
            .execute()
        
        if response.data:
            reset_token = response.data[0]['reset_token']
            print(f"   Reset Token: {reset_token[:20]}...")
            
            # 3. 使用 token 重設密碼
            success = auth_manager.reset_password(reset_token, 'NewPassword123!')
            
            if success:
                print(f"\n✅ 密碼重設成功")
                
                # 4. 用新密碼登入測試
                user = auth_manager.login('test@dental.hk', 'NewPassword123!')
                if user:
                    print(f"✅ 用新密碼登入成功")
                else:
                    print(f"❌ 用新密碼登入失敗")
    else:
        print(f"\n❌ 重設請求失敗")


if __name__ == "__main__":
    # 執行所有測試
    test_user_registration()
    test_weak_password()
    test_login_success()
    test_login_failure()
    test_password_reset()
    
    print("\n" + "="*60)
    print("🎉 所有測試完成")
    print("="*60)