"""
Test script for user-related API endpoints

This script tests the newly added user API endpoints:
1. GET /api/users/me/sessions - Get all user sessions
2. GET /api/users/me/orders - Get all user orders
3. GET /conversations/{session_id} - Get conversation history with auth
4. DELETE /api/sessions/{session_id} - Delete session and conversations
"""

import requests
import json
from typing import Optional

# Configuration
BASE_URL = "http://localhost:8000"

# Replace with a valid Supabase JWT token for testing
# You can get this from your frontend or use test/test_auth.py to login
TEST_TOKEN = "YOUR_JWT_TOKEN_HERE"


def test_get_user_sessions(token: str):
    """Test GET /api/users/me/sessions"""
    print("\n" + "="*60)
    print("Testing GET /api/users/me/sessions")
    print("="*60)
    
    response = requests.get(
        f"{BASE_URL}/api/users/me/sessions",
        headers={"Authorization": f"Bearer {token}"},
        params={"limit": 10}
    )
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Found {data['count']} sessions")
        print(f"User ID: {data['user_id']}")
        if data['sessions']:
            print("\nFirst session:")
            print(json.dumps(data['sessions'][0], indent=2))
    else:
        print(f"❌ Error: {response.text}")


def test_get_user_orders(token: str):
    """Test GET /api/users/me/orders"""
    print("\n" + "="*60)
    print("Testing GET /api/users/me/orders")
    print("="*60)
    
    response = requests.get(
        f"{BASE_URL}/api/users/me/orders",
        headers={"Authorization": f"Bearer {token}"},
        params={"limit": 10}
    )
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Found {data['count']} orders")
        print(f"User ID: {data['user_id']}")
        if data['orders']:
            print("\nFirst order:")
            print(json.dumps(data['orders'][0], indent=2))
    else:
        print(f"❌ Error: {response.text}")


def test_get_conversation_history(token: str, session_id: str):
    """Test GET /conversations/{session_id}"""
    print("\n" + "="*60)
    print(f"Testing GET /conversations/{session_id}")
    print("="*60)
    
    response = requests.get(
        f"{BASE_URL}/conversations/{session_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Found {data['message_count']} messages")
        print(f"Session ID: {data['session_id']}")
        if data['messages']:
            print("\nFirst message:")
            msg = data['messages'][0]
            print(f"Role: {msg.get('role')}")
            print(f"Content: {msg.get('content', '')[:100]}...")
    elif response.status_code == 403:
        print(f"❌ Permission denied: {response.json()}")
    elif response.status_code == 404:
        print(f"❌ Session not found: {response.json()}")
    else:
        print(f"❌ Error: {response.text}")


def test_delete_session(token: str, session_id: str):
    """Test DELETE /api/sessions/{session_id}"""
    print("\n" + "="*60)
    print(f"Testing DELETE /api/sessions/{session_id}")
    print("="*60)
    print("⚠️  This will permanently delete the session!")
    
    confirm = input("Continue? (yes/no): ")
    if confirm.lower() != "yes":
        print("Cancelled.")
        return
    
    response = requests.delete(
        f"{BASE_URL}/api/sessions/{session_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ {data['message']}")
    elif response.status_code == 403:
        print(f"❌ Permission denied")
    elif response.status_code == 404:
        print(f"❌ Session not found or no permission")
    else:
        print(f"❌ Error: {response.text}")


def main():
    """Main test runner"""
    print("\n" + "="*60)
    print("User API Endpoints Test Suite")
    print("="*60)
    
    if TEST_TOKEN == "YOUR_JWT_TOKEN_HERE":
        print("\n❌ Please set TEST_TOKEN with a valid JWT token")
        print("You can get a token by running test/test_auth.py")
        return
    
    # Test 1: Get user sessions
    test_get_user_sessions(TEST_TOKEN)
    
    # Test 2: Get user orders
    test_get_user_orders(TEST_TOKEN)
    
    # Test 3: Get conversation history (requires session_id)
    session_id = input("\nEnter session_id to test (or press Enter to skip): ").strip()
    if session_id:
        test_get_conversation_history(TEST_TOKEN, session_id)
        
        # Test 4: Delete session (optional)
        test_delete = input("\nTest delete session API? (yes/no): ").strip()
        if test_delete.lower() == "yes":
            test_delete_session(TEST_TOKEN, session_id)
    
    print("\n" + "="*60)
    print("Test suite completed!")
    print("="*60)


if __name__ == "__main__":
    main()
