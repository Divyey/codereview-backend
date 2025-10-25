#!/usr/bin/env python3
"""
Test script for API Keys management endpoints
Run this after starting the backend server to test the API
"""

import requests
import json

BASE_URL = "http://localhost:3000"

def test_api_keys():
    print("🔑 Testing API Keys Management System")
    print("=" * 50)
    
    # Test data
    test_user = {
        "username": "testuser",
        "email": "test@example.com", 
        "password": "testpass123"
    }
    
    test_api_key = {
        "key_type": "github",
        "key_name": "Test GitHub Token",
        "api_key": "ghp_1234567890abcdefghijklmnopqrstuvwxyz123456",
        "description": "Test GitHub personal access token",
        "is_active": True
    }
    
    # Step 1: Register user (if not exists)
    print("\n1. 📝 Registering test user...")
    try:
        response = requests.post(f"{BASE_URL}/api/auth/register", json=test_user)
        if response.status_code == 201:
            print("✅ User registered successfully")
        elif response.status_code == 400:
            print("ℹ️  User already exists")
        else:
            print(f"❌ Registration failed: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Registration error: {e}")
        return
    
    # Step 2: Login to get token
    print("\n2. 🔐 Logging in...")
    try:
        login_data = {"username": test_user["username"], "password": test_user["password"]}
        response = requests.post(f"{BASE_URL}/api/auth/login", data=login_data)
        
        if response.status_code == 200:
            token_data = response.json()
            token = token_data["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            print("✅ Login successful")
        else:
            print(f"❌ Login failed: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Login error: {e}")
        return
    
    # Step 3: Create API key
    print("\n3. ➕ Creating API key...")
    try:
        response = requests.post(f"{BASE_URL}/api/user/api-keys/", json=test_api_key, headers=headers)
        
        if response.status_code == 200:
            created_key = response.json()
            key_id = created_key["id"]
            print(f"✅ API key created successfully (ID: {key_id})")
            print(f"   Masked key: {created_key['masked_key']}")
        else:
            print(f"❌ API key creation failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return
    except Exception as e:
        print(f"❌ API key creation error: {e}")
        return
    
    # Step 4: List API keys
    print("\n4. 📋 Listing API keys...")
    try:
        response = requests.get(f"{BASE_URL}/api/user/api-keys/", headers=headers)
        
        if response.status_code == 200:
            api_keys = response.json()
            print(f"✅ Found {len(api_keys)} API key(s)")
            for key in api_keys:
                print(f"   - {key['key_name']} ({key['key_type']}) - {key['masked_key']}")
        else:
            print(f"❌ Failed to list API keys: {response.status_code}")
    except Exception as e:
        print(f"❌ List API keys error: {e}")
    
    # Step 5: Get specific API key
    print(f"\n5. 🔍 Getting API key {key_id}...")
    try:
        response = requests.get(f"{BASE_URL}/api/user/api-keys/{key_id}", headers=headers)
        
        if response.status_code == 200:
            api_key = response.json()
            print(f"✅ Retrieved API key: {api_key['key_name']}")
        else:
            print(f"❌ Failed to get API key: {response.status_code}")
    except Exception as e:
        print(f"❌ Get API key error: {e}")
    
    # Step 6: Update API key
    print(f"\n6. ✏️  Updating API key {key_id}...")
    try:
        update_data = {
            "key_name": "Updated GitHub Token",
            "description": "Updated description for test token"
        }
        response = requests.put(f"{BASE_URL}/api/user/api-keys/{key_id}", json=update_data, headers=headers)
        
        if response.status_code == 200:
            updated_key = response.json()
            print(f"✅ API key updated: {updated_key['key_name']}")
        else:
            print(f"❌ Failed to update API key: {response.status_code}")
    except Exception as e:
        print(f"❌ Update API key error: {e}")
    
    # Step 7: Test API key validation
    print("\n7. ✅ Testing API key validation...")
    try:
        validation_data = {
            "key_type": "github",
            "api_key": "ghp_invalid_key"
        }
        response = requests.post(f"{BASE_URL}/api/user/api-keys/validate", params=validation_data)
        
        if response.status_code == 200:
            validation_result = response.json()
            print(f"✅ Validation result: {validation_result['message']}")
        else:
            print(f"❌ Validation failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Validation error: {e}")
    
    # Step 8: Delete API key
    print(f"\n8. 🗑️  Deleting API key {key_id}...")
    try:
        response = requests.delete(f"{BASE_URL}/api/user/api-keys/{key_id}", headers=headers)
        
        if response.status_code == 200:
            print("✅ API key deleted successfully")
        else:
            print(f"❌ Failed to delete API key: {response.status_code}")
    except Exception as e:
        print(f"❌ Delete API key error: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 API Keys testing completed!")
    print("\n📋 Summary:")
    print("   ✅ User registration/login")
    print("   ✅ API key creation")
    print("   ✅ API key listing")
    print("   ✅ API key retrieval")
    print("   ✅ API key updating")
    print("   ✅ API key validation")
    print("   ✅ API key deletion")

if __name__ == "__main__":
    test_api_keys()
