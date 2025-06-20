#!/usr/bin/env python3
"""
Quick test script to verify the TTS API is working correctly.
Run this after starting the API server.
"""

import requests
import sys
from pathlib import Path

def ensure_test_directories():
    """Create test directories if they don't exist"""
    Path("./data/out").mkdir(parents=True, exist_ok=True)
    Path("./data/ref").mkdir(parents=True, exist_ok=True)

def test_api():
    """Test the basic functionality of the TTS API"""
    base_url = "http://localhost:8000/api"
    
    # Ensure test directories exist
    ensure_test_directories()
    
    print("🧪 Testing Chatterbox TTS API")
    print("=" * 40)
    
    # Test 1: Health check
    print("1. Testing health check...")
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            health_data = response.json()
            print(f"   ✅ Health check passed")
            print(f"   📊 Status: {health_data['status']}")
            print(f"   🎯 Device: {health_data['device']}")
            print(f"   🤖 Model loaded: {health_data['model_loaded']}")
        else:
            print(f"   ❌ Health check failed: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Cannot connect to API: {e}")
        print("   💡 Make sure the API server is running: ./start_api.sh")
        return False
    
    print()
    
    # Test 2: Model info
    print("2. Testing model info...")
    try:
        response = requests.get(f"{base_url}/model/info", timeout=5)
        if response.status_code == 200:
            model_data = response.json()
            print(f"   ✅ Model info retrieved")
            print(f"   🎵 Sample rate: {model_data['sample_rate']}")
            print(f"   💻 Device: {model_data['device']}")
        else:
            print(f"   ❌ Model info failed: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Model info request failed: {e}")
    
    print()
    
    # Test 3: Basic generation
    print("3. Testing basic audio generation...")
    test_text = "Hello! This is a test of the Chatterbox TTS API."
    
    try:
        response = requests.post(
            f"{base_url}/generate",
            data={
                "text": test_text,
                "exaggeration": 0.5,
                "temperature": 0.8
            },
            timeout=30  # Generation can take a while
        )
        
        if response.status_code == 200:
            # Save the audio file to test output
            output_file = "./data/out/api_test_basic.wav"
            with open(output_file, "wb") as f:
                f.write(response.content)
            print(f"   ✅ Audio generation successful")
            print(f"   💾 Saved as: {output_file}")
            print(f"   📦 Audio size: {len(response.content)} bytes")
        else:
            print(f"   ❌ Audio generation failed: {response.status_code}")
            print(f"   📄 Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Audio generation request failed: {e}")
        return False
    
    print()
    
    # Test 4: JSON response
    print("4. Testing JSON response format...")
    try:
        response = requests.post(
            f"{base_url}/generate/json",
            data={
                "text": "JSON test response.",
                "seed": 42
            },
            timeout=30
        )
        
        if response.status_code == 200:
            json_data = response.json()
            print(f"   ✅ JSON generation successful")
            print(f"   🎵 Sample rate: {json_data['sample_rate']}")
            print(f"   📝 Text: {json_data['text']}")
            print(f"   ⚙️  Seed: {json_data['parameters']['seed']}")
            audio_size = len(json_data['audio_base64']) * 3 // 4  # Rough base64 decode size
            print(f"   📦 Audio data size: ~{audio_size} bytes (base64)")
        else:
            print(f"   ❌ JSON generation failed: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ JSON generation request failed: {e}")
    
    print()
    print("🎉 API test completed!")
    print("📂 Test files saved to: ./data/out/")
    print("📂 Demo HTML file: open api_demo.html in your browser")
    print("📖 Full documentation: API_README.md")
    print("🧪 Run comprehensive tests: python3 api_client_example.py")
    
    return True

if __name__ == "__main__":
    success = test_api()
    sys.exit(0 if success else 1)
