# update_existing_users_password.py

from auth import auth_manager

# 為現有用戶加上密碼
users_to_update = [
    ('dr.wong@dental.hk', 'Wong1234!'),
    ('dr.chan@dental.hk', 'Chan1234!'),
    ('admin@lab.hk', 'Admin1234!')
]

for email, password in users_to_update:
    password_hash = auth_manager.hash_password(password)
    
    from supabase import create_client
    import os
    supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))
    
    response = supabase.table('users')\
        .update({
            'password_hash': password_hash,
            'password_updated_at': 'NOW()'
        })\
        .eq('email', email)\
        .execute()
    
    print(f"✅ 更新密碼: {email}")

print("\n🎉 所有用戶密碼更新完成")