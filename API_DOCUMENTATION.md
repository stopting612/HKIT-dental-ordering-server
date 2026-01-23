# User API Endpoints Documentation

This document describes the user-related API endpoints with authentication guards.

## Authentication

All endpoints require JWT authentication via Supabase. Include the token in the Authorization header:

```
Authorization: Bearer <your-jwt-token>
```

## Endpoints Overview

### 1. Get User Sessions

**GET** `/api/users/me/sessions`

Retrieves all conversation sessions for the authenticated user.

**Query Parameters:**
- `limit` (optional, default: 50): Maximum number of sessions to return
- `status` (optional): Filter by session status (`active`, `completed`, `cancelled`)

**Response:**
```json
{
  "user_id": "uuid-string",
  "count": 5,
  "sessions": [
    {
      "session_id": "uuid-string",
      "user_id": "uuid-string",
      "session_type": "order",
      "status": "completed",
      "message_count": 15,
      "tool_call_count": 8,
      "started_at": "2026-01-23T10:30:00",
      "last_activity_at": "2026-01-23T10:45:00",
      "ended_at": "2026-01-23T10:45:00",
      "duration_seconds": 900,
      "order_created": true,
      "order_id": 123
    }
  ]
}
```

**cURL Example:**
```bash
curl -X GET "http://localhost:8000/api/users/me/sessions?limit=10" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

### 2. Get User Orders

**GET** `/api/users/me/orders`

Retrieves all orders for the authenticated user.

**Query Parameters:**
- `limit` (optional, default: 50): Maximum number of orders to return

**Response:**
```json
{
  "user_id": "uuid-string",
  "count": 3,
  "orders": [
    {
      "id": 123,
      "order_number": "ORD-20260123-001",
      "user_id": "uuid-string",
      "session_id": "uuid-string",
      "status": "pending",
      "restoration_type": "crown",
      "tooth_positions": "16,17",
      "material_category": "metal-free",
      "material_subtype": "emax",
      "product_code": "EMAX-001",
      "product_name": "IPS e.max CAD",
      "shade": "A2",
      "patient_name": "張小明",
      "created_at": "2026-01-23T10:45:00"
    }
  ]
}
```

**cURL Example:**
```bash
curl -X GET "http://localhost:8000/api/users/me/orders?limit=20" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

### 3. Get Conversation History

**GET** `/conversations/{session_id}`

Retrieves all conversation messages for a specific session. Automatically decrypts encrypted content.

**Path Parameters:**
- `session_id` (required): The session ID to retrieve conversations for

**Query Parameters:**
- `decrypt` (optional, default: true): Whether to decrypt encrypted content

**Authorization:**
- User must own the session (ownership verification performed)

**Response:**
```json
{
  "session_id": "uuid-string",
  "message_count": 10,
  "messages": [
    {
      "id": 1,
      "session_id": "uuid-string",
      "role": "user",
      "content": "我需要訂購一個牙冠",
      "created_at": "2026-01-23T10:30:00"
    },
    {
      "id": 2,
      "session_id": "uuid-string",
      "role": "assistant",
      "content": "好的，請問是哪一顆牙齒呢？",
      "created_at": "2026-01-23T10:30:05"
    }
  ]
}
```

**Error Responses:**
- `403 Forbidden`: User doesn't have permission to access this session
- `404 Not Found`: Session not found

**cURL Example:**
```bash
curl -X GET "http://localhost:8000/conversations/SESSION_ID" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

### 4. Delete Session and Conversations

**DELETE** `/api/sessions/{session_id}`

Deletes a session and all associated conversation messages. This action is permanent.

**Path Parameters:**
- `session_id` (required): The session ID to delete

**Authorization:**
- User must own the session (ownership verification performed)

**Response:**
```json
{
  "message": "Session uuid-string and all related conversations deleted successfully",
  "session_id": "uuid-string"
}
```

**Error Responses:**
- `403 Forbidden`: User doesn't have permission to delete this session
- `404 Not Found`: Session not found or already deleted

**cURL Example:**
```bash
curl -X DELETE "http://localhost:8000/api/sessions/SESSION_ID" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## Legacy Endpoints (Still Available)

### Get Recent Orders

**GET** `/orders/recent`

Original endpoint for getting recent orders. Similar to `/api/users/me/orders` but with a default limit of 10.

### Get Specific Order

**GET** `/orders/{order_number}`

Get details of a specific order by order number. Includes ownership verification.

---

## Testing

Use the provided test script to verify all endpoints:

```bash
# First, activate virtual environment
source venv/bin/activate

# Run the test script
python test/test_user_apis.py
```

You'll need a valid JWT token. Get one by:

1. Running `python test/test_auth.py` to login
2. Or extracting it from your frontend application

---

## Implementation Details

### Security Features

1. **JWT Authentication**: All endpoints require valid Supabase JWT tokens
2. **Ownership Verification**: Users can only access their own data
3. **Automatic Decryption**: Encrypted PII is automatically decrypted for authorized users
4. **Integrity Verification**: Content hash verification ensures data hasn't been tampered with

### Database Operations

- **Sessions Table**: Stores session metadata (status, timestamps, message counts)
- **Conversations Table**: Stores encrypted conversation messages
- **Orders Table**: Stores order details with foreign key to sessions

### Performance Considerations

- Conversation decryption happens on-demand (can be disabled with `decrypt=false`)
- Pagination supported via `limit` parameter
- Database queries use indexes on `user_id` and `session_id` for performance

---

## Error Handling

All endpoints follow consistent error response format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

Common HTTP status codes:
- `200 OK`: Success
- `401 Unauthorized`: Missing or invalid JWT token
- `403 Forbidden`: User doesn't have permission for this resource
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server-side error

---

## Frontend Integration Example

```typescript
// TypeScript/JavaScript example
const API_BASE_URL = 'http://localhost:8000';

async function getUserSessions(token: string, limit = 50) {
  const response = await fetch(
    `${API_BASE_URL}/api/users/me/sessions?limit=${limit}`,
    {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    }
  );
  
  if (!response.ok) {
    throw new Error(`Failed to fetch sessions: ${response.statusText}`);
  }
  
  return await response.json();
}

async function deleteSession(token: string, sessionId: string) {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}`,
    {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${token}`
      }
    }
  );
  
  if (!response.ok) {
    throw new Error(`Failed to delete session: ${response.statusText}`);
  }
  
  return await response.json();
}
```

---

## Database Schema Reference

### Sessions Table
```sql
CREATE TABLE sessions (
  id SERIAL PRIMARY KEY,
  session_id UUID UNIQUE NOT NULL,
  user_id UUID,
  session_type VARCHAR(50) DEFAULT 'order',
  status VARCHAR(50) DEFAULT 'active',
  message_count INTEGER DEFAULT 0,
  tool_call_count INTEGER DEFAULT 0,
  started_at TIMESTAMP,
  last_activity_at TIMESTAMP,
  ended_at TIMESTAMP,
  duration_seconds INTEGER,
  order_created BOOLEAN DEFAULT FALSE,
  order_id INTEGER
);
```

### Conversations Table
```sql
CREATE TABLE conversations (
  id SERIAL PRIMARY KEY,
  session_id UUID NOT NULL,
  user_id UUID,
  role VARCHAR(50),
  content TEXT,
  content_encrypted TEXT,
  content_hash VARCHAR(64),
  created_at TIMESTAMP,
  -- ... other encryption and metadata fields
);
```
