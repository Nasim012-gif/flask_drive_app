"""
Simple test script to verify Flask Drive API setup.
Run this after completing the authentication flow.
"""

import requests
import json

BASE_URL = "http://localhost:5000"

def test_health_check():
    """Test the health check endpoint."""
    print("Testing health check...")
    response = requests.get(f"{BASE_URL}/")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")
    return response.json().get('authenticated', False)

def test_list_files():
    """Test listing files from Google Drive."""
    print("Testing file listing...")
    response = requests.get(f"{BASE_URL}/files?page_size=5")
    print(f"Status: {response.status_code}")
    data = response.json()
    
    if response.status_code == 200:
        print(f"Found {data['count']} files:")
        for file in data.get('files', []):
            print(f"  - {file['name']} ({file['id']})")
    else:
        print(f"Error: {data.get('error', 'Unknown error')}")
    print()

def test_search_files():
    """Test searching for PDF files."""
    print("Testing file search (PDFs)...")
    query = "mimeType='application/pdf'"
    response = requests.get(f"{BASE_URL}/search", params={'q': query})
    print(f"Status: {response.status_code}")
    data = response.json()
    
    if response.status_code == 200:
        print(f"Found {data['count']} PDF files:")
        for file in data.get('files', []):
            print(f"  - {file['name']}")
    else:
        print(f"Error: {data.get('error', 'Unknown error')}")
    print()

def test_upload_file():
    """Test uploading a test file."""
    print("Testing file upload...")
    
    # Create a simple test file
    test_content = "Hello from Flask Drive API!\nThis is a test file."
    test_filename = "flask_test.txt"
    
    with open(test_filename, 'w') as f:
        f.write(test_content)
    
    # Upload the file
    with open(test_filename, 'rb') as f:
        files = {'file': f}
        response = requests.post(f"{BASE_URL}/upload", files=files)
    
    print(f"Status: {response.status_code}")
    data = response.json()
    
    if response.status_code == 200:
        print(f"Upload successful!")
        print(f"  File ID: {data['file']['id']}")
        print(f"  Name: {data['file']['name']}")
        print(f"  Link: {data['file'].get('webViewLink', 'N/A')}")
        return data['file']['id']
    else:
        print(f"Error: {data.get('error', 'Unknown error')}")
    print()
    return None

def main():
    """Run all tests."""
    print("="*60)
    print("Flask Google Drive API - Test Suite")
    print("="*60)
    print()
    
    # Check if authenticated
    is_authenticated = test_health_check()
    
    if not is_authenticated:
        print("⚠️  Not authenticated!")
        print(f"Please visit {BASE_URL}/auth to authenticate.")
        print()
        return
    
    print("✅ Authenticated successfully!\n")
    
    # Run tests
    test_list_files()
    test_search_files()
    
    # Test upload
    file_id = test_upload_file()
    
    if file_id:
        print(f"You can view the uploaded file in Google Drive")
        print(f"To delete it, run: curl -X DELETE {BASE_URL}/delete/{file_id}")
    
    print("="*60)
    print("Test suite completed!")
    print("="*60)

if __name__ == "__main__":
    main()
