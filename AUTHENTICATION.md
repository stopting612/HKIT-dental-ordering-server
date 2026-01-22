# Authentication Architecture

## Security Model

### ❌ WRONG: Don't pass Supabase keys from frontend!

```javascript
// NEVER DO THIS!
const response = await fetch('/api/chat', {
  headers: {
    'supabase-key': 'YOUR_SERVICE_ROLE_KEY'  // ❌ Security vulnerability!
  }
})
```

### ✅ CORRECT: JWT Token-based Authentication

## How It Works

### 1. Frontend Authentication (Flutter/React)

```dart
// Flutter example
import 'package:supabase_flutter/supabase_flutter.dart';

// Initialize Supabase with ANON KEY (safe to expose)
await Supabase.initialize(
  url: 'https://ixixrmhdhfqbpmtmzjpa.supabase.co',
  anonKey: 'your_anon_key_here',  // ✅ Public key, safe
);

// Sign in user
final AuthResponse res = await supabase.auth.signInWithPassword(
  email: 'user@example.com',
  password: 'password',
);

// Get JWT access token
final String? accessToken = res.session?.accessToken;

// Call backend API with Bearer token
final response = await http.post(
  Uri.parse('https://your-api.com/chat'),
  headers: {
    'Authorization': 'Bearer $accessToken',  // ✅ JWT token only
    'Content-Type': 'application/json',
  },
  body: jsonEncode({
    'session_id': 'uuid-here',
    'message': 'I want to order a crown'
  }),
);
```

### 2. Backend Verification (FastAPI)

```python
# auth_middleware.py

# Backend uses SERVICE_ROLE_KEY (from .env, never exposed)
supabase = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_SERVICE_ROLE_KEY')  # ✅ Server-side only
)

async def verify_supabase_token(authorization: str) -> dict:
    """Verify JWT token sent from frontend"""
    
    # Extract Bearer token
    token = authorization.split()[1]
    
    # Verify token using service role key (backend validates)
    user_response = supabase.auth.get_user(token)
    
    return {
        'user_id': user_response.user.id,
        'email': user_response.user.email
    }
```

### 3. Protected Endpoints

```python
# main.py

@app.post("/chat")
async def chat(
    request: ChatRequest,
    user_id: Annotated[str, Depends(get_current_user_id)]  # ✅ Auto-validated
):
    """
    User doesn't pass user_id manually!
    It's extracted from verified JWT token.
    """
    # user_id is guaranteed authentic
    conversation_manager.log_message(
        session_id=request.session_id,
        user_id=user_id,  # From JWT, not from request body
        content=request.message
    )
```

## Environment Variables

### Frontend (.env - Flutter/React)
```env
# ✅ Safe to commit to public repo
SUPABASE_URL=https://ixixrmhdhfqbpmtmzjpa.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...  # Public key
```

### Backend (.env - FastAPI)
```env
# ❌ NEVER expose these keys!
SUPABASE_URL=https://ixixrmhdhfqbpmtmzjpa.supabase.co
SUPABASE_SERVICE_ROLE_KEY=sb_secret_HS8xcGfDW...  # Secret! Backend only!
```

## Key Differences

| Key Type | Usage | Exposed to Frontend? | Permissions |
|----------|-------|---------------------|-------------|
| **ANON_KEY** | Frontend initialization | ✅ Yes (safe) | Limited by RLS policies |
| **SERVICE_ROLE_KEY** | Backend operations | ❌ NO! | Bypass RLS, full access |

## Authentication Flow Diagram

```
┌─────────────┐
│   Flutter   │
│   Frontend  │
└──────┬──────┘
       │ 1. Sign in with email/password
       │    (using ANON_KEY)
       ▼
┌─────────────┐
│  Supabase   │
│    Auth     │
└──────┬──────┘
       │ 2. Returns JWT access_token
       │    (expires in 1 hour)
       ▼
┌─────────────┐
│   Flutter   │
│   Frontend  │
└──────┬──────┘
       │ 3. API call with Authorization header
       │    Authorization: Bearer <jwt_token>
       ▼
┌─────────────┐
│   FastAPI   │
│   Backend   │
└──────┬──────┘
       │ 4. Verify token with SERVICE_ROLE_KEY
       │    (backend has secret key in .env)
       ▼
┌─────────────┐
│  Supabase   │
│    Auth     │
└──────┬──────┘
       │ 5. Returns user info (user_id, email)
       ▼
┌─────────────┐
│   FastAPI   │
│   Backend   │
└──────┬──────┘
       │ 6. Process request with verified user_id
       │    (user_id is authentic, can't be spoofed)
       ▼
┌─────────────┐
│  Database   │
│  Operations │
└─────────────┘
```

## Common Mistakes

### ❌ Mistake 1: Passing user_id in request body
```python
# INSECURE!
class ChatRequest(BaseModel):
    session_id: str
    message: str
    user_id: str  # ❌ User can fake this!
```

### ✅ Solution: Extract from JWT
```python
@app.post("/chat")
async def chat(
    request: ChatRequest,
    user_id: Annotated[str, Depends(get_current_user_id)]  # ✅ From JWT
):
    # user_id is verified, can't be spoofed
```

### ❌ Mistake 2: Using service role key in frontend
```dart
// NEVER DO THIS!
final supabase = SupabaseClient(
  'https://xxx.supabase.co',
  'sb_secret_HS8xcGfDW...',  // ❌ Exposed to users!
);
```

### ✅ Solution: Use anon key
```dart
await Supabase.initialize(
  url: 'https://xxx.supabase.co',
  anonKey: 'eyJhbGciOiJIUzI1NiIs...',  // ✅ Public key
);
```

## Testing Authentication

### Get JWT Token (Frontend)
```bash
# Sign in via Supabase client
curl -X POST 'https://ixixrmhdhfqbpmtmzjpa.supabase.co/auth/v1/token?grant_type=password' \
  -H 'apikey: YOUR_ANON_KEY' \
  -H 'Content-Type: application/json' \
  -d '{
    "email": "test@example.com",
    "password": "password123"
  }'

# Response includes access_token
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 3600
}
```

### Call Protected Endpoint (Backend)
```bash
# Use Bearer token in Authorization header
curl -X POST 'http://localhost:8000/chat' \
  -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...' \
  -H 'Content-Type: application/json' \
  -d '{
    "session_id": "uuid-here",
    "message": "I want a crown"
  }'
```

## Security Checklist

- [ ] ✅ Frontend uses `SUPABASE_ANON_KEY` only
- [ ] ✅ Backend uses `SUPABASE_SERVICE_ROLE_KEY` (in `.env`, not exposed)
- [ ] ✅ All sensitive endpoints require JWT authentication
- [ ] ✅ User ID extracted from JWT, not request body
- [ ] ✅ `.env` file in `.gitignore` (never committed)
- [ ] ✅ Service role key rotated regularly
- [ ] ✅ JWT tokens have expiration (1 hour default)
- [ ] ✅ Frontend refreshes tokens before expiration

## Debugging

If you see: `❌ Token 驗證失敗: supabase_key is required`

**Check:**
1. `.env` has `SUPABASE_SERVICE_ROLE_KEY` (not `SUPABASE_KEY`)
2. Backend loaded `.env` correctly (`python-dotenv`)
3. Not passing key from frontend (should only send JWT token)

**Fix:**
```bash
# Check .env
grep SUPABASE_SERVICE_ROLE_KEY .env

# Restart server to reload .env
pkill -f "python main.py"
python main.py
```
