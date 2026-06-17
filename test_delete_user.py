#!/usr/bin/env python3
"""
Quick test script to verify the delete user functionality works.
This tests the backend API endpoint directly.
"""

import requests
import json
import os
from datetime import datetime

# Configuration
API_BASE_URL = os.environ.get("VITE_API_URL", "http://localhost:8000")
ADMIN_EMAIL = "admin@example.com"  # Replace with actual admin email
ADMIN_PASSWORD = "admin123"  # Replace with actual admin password

def test_delete_user_functionality():
    """Test the delete user API endpoint."""
    
    print("🧪 Testing Delete User Functionality")
    print("=" * 50)
    
    # Step 1: Login as admin to get token
    print("1. Logging in as admin...")
    login_response = requests.post(f"{API_BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    
    if login_response.status_code != 200:
        print(f"❌ Admin login failed: {login_response.status_code}")
        print(f"Response: {login_response.text}")
        return False
    
    admin_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}
    print("✅ Admin login successful")
    
    # Step 2: Create a test user to delete
    print("2. Creating test user...")
    test_email = f"test_delete_{datetime.now().strftime('%Y%m%d_%H%M%S')}@example.com"
    create_response = requests.post(f"{API_BASE_URL}/api/auth/register", json={
        "email": test_email,
        "password": "testpass123"
    })
    
    if create_response.status_code != 200:
        print(f"❌ Test user creation failed: {create_response.status_code}")
        print(f"Response: {create_response.text}")
        return False
    
    test_user_id = create_response.json()["user_id"]
    print(f"✅ Test user created with ID: {test_user_id}")
    
    # Step 3: Verify user exists in admin users list
    print("3. Verifying user exists...")
    users_response = requests.get(f"{API_BASE_URL}/api/admin/users", headers=headers)
    
    if users_response.status_code != 200:
        print(f"❌ Failed to get users list: {users_response.status_code}")
        return False
    
    users_data = users_response.json()
    user_exists = any(user["id"] == test_user_id for user in users_data["users"])
    
    if not user_exists:
        print(f"❌ Test user {test_user_id} not found in users list")
        return False
    
    print(f"✅ Test user found in users list")
    
    # Step 4: Delete the user
    print("4. Deleting test user...")
    delete_response = requests.delete(f"{API_BASE_URL}/api/admin/users/{test_user_id}", headers=headers)
    
    if delete_response.status_code != 200:
        print(f"❌ User deletion failed: {delete_response.status_code}")
        print(f"Response: {delete_response.text}")
        return False
    
    delete_data = delete_response.json()
    if not delete_data.get("ok") or delete_data.get("id") != test_user_id:
        print(f"❌ Unexpected delete response: {delete_data}")
        return False
    
    print(f"✅ User {test_user_id} deleted successfully")
    
    # Step 5: Verify user no longer exists
    print("5. Verifying user was deleted...")
    users_response_after = requests.get(f"{API_BASE_URL}/api/admin/users", headers=headers)
    
    if users_response_after.status_code != 200:
        print(f"❌ Failed to get users list after deletion: {users_response_after.status_code}")
        return False
    
    users_data_after = users_response_after.json()
    user_still_exists = any(user["id"] == test_user_id for user in users_data_after["users"])
    
    if user_still_exists:
        print(f"❌ Test user {test_user_id} still exists after deletion")
        return False
    
    print(f"✅ User {test_user_id} successfully removed from users list")
    
    # Step 6: Test deleting non-existent user (should return 404)
    print("6. Testing deletion of non-existent user...")
    fake_user_id = 999999
    delete_fake_response = requests.delete(f"{API_BASE_URL}/api/admin/users/{fake_user_id}", headers=headers)
    
    if delete_fake_response.status_code != 404:
        print(f"❌ Expected 404 for non-existent user, got: {delete_fake_response.status_code}")
        return False
    
    print(f"✅ Correctly returned 404 for non-existent user")
    
    print("\n🎉 All delete user functionality tests passed!")
    return True

if __name__ == "__main__":
    success = test_delete_user_functionality()
    exit(0 if success else 1)

# Made with Bob
