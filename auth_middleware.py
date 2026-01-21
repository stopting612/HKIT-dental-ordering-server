# auth_middleware.py

from fastapi import HTTPException, Header, Depends, status
from typing import Optional, Annotated
from supabase import create_client, Client
from functools import lru_cache
import os
from dotenv import load_dotenv

load_dotenv()

# ===== Supabase Client (單例模式) =====
@lru_cache()
def get_supabase_client() -> Client:
    """
    創建並緩存 Supabase client
    使用 lru_cache 確保整個應用只有一個實例
    """
    return create_client(
        os.getenv('SUPABASE_URL'),
        os.getenv('SUPABASE_SERVICE_ROLE_KEY')  # ⚠️ 使用 service_role key（後端用）
    )


# ===== 驗證函數（可重用） =====
async def verify_supabase_token(
    authorization: Annotated[str, Header()] = None
) -> dict:
    """
    驗證 Supabase JWT Token 並返回用戶資訊
    
    前端呼叫時需在 Header 加入：
    Authorization: Bearer <access_token>
    
    Returns:
        dict: {
            'user_id': str,
            'email': str,
            'user_metadata': dict
        }
    
    Raises:
        HTTPException: 401 如果 token 無效或缺失
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 提取 token
    try:
        scheme, token = authorization.split()
        if scheme.lower() != 'bearer':
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication scheme",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 驗證 token
    try:
        supabase = get_supabase_client()
        
        # 方法 1: 使用 get_user (推薦)
        user_response = supabase.auth.get_user(token)
        
        if not user_response or not user_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user = user_response.user
        
        return {
            'user_id': user.id,
            'email': user.email,
            'user_metadata': user.user_metadata or {},
            'app_metadata': user.app_metadata or {},
            'role': user.role or 'authenticated',
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Token 驗證失敗: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_id(
    auth_data: Annotated[dict, Depends(verify_supabase_token)]
) -> str:
    """

    @app.get("/api/orders")
    async def get_orders(user_id: Annotated[str, Depends(get_current_user_id)]):
        # user_id 
        pass
    """
    return auth_data['user_id']


# ===== 可選驗證（允許匿名） =====
async def get_optional_user_id(
    authorization: Annotated[str, Header()] = None
) -> Optional[str]:
    """
    可選驗證：有 token 就驗證，沒有就返回 None
    
    用法：
    @app.get("/api/public-data")
    async def get_data(user_id: Annotated[Optional[str], Depends(get_optional_user_id)]):
        if user_id:
            # 已登入用戶
        else:
            # 匿名用戶
    """
    if not authorization:
        return None
    
    try:
        auth_data = await verify_supabase_token(authorization)
        return auth_data['user_id']
    except HTTPException:
        return None


# ===== 角色權限驗證 =====
def require_role(*allowed_roles: str):
    """
    檢查用戶是否有特定角色
    
    用法：
    @app.delete("/api/admin/users/{user_id}")
    async def delete_user(
        user_id: str,
        auth_data: Annotated[dict, Depends(require_role("admin", "super_admin"))]
    ):
        # 只有 admin 或 super_admin 可以呼叫
        pass
    """
    async def role_checker(
        auth_data: Annotated[dict, Depends(verify_supabase_token)]
    ) -> dict:
        user_role = auth_data.get('role', 'authenticated')
        
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {', '.join(allowed_roles)}"
            )
        
        return auth_data
    
    return role_checker


# ===== 自定義權限驗證 =====
async def verify_order_ownership(
    order_id: int,
    auth_data: Annotated[dict, Depends(verify_supabase_token)]
) -> dict:
    """
    驗證用戶是否擁有該訂單
    
    用法：
    @app.get("/api/orders/{order_id}")
    async def get_order(
        order_id: int,
        auth_data: Annotated[dict, Depends(verify_order_ownership)]
    ):
        # 已驗證用戶擁有該訂單
        pass
    """
    from order_manager import order_manager
    
    user_id = auth_data['user_id']
    order = order_manager.get_order_by_id(order_id)
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    if order.get('user_id') != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this order"
        )
    
    return auth_data