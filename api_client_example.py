"""
Example client for Chatterbox TTS REST API

This script demonstrates how to use the API endpoints to generate TTS audio.
"""

import requests
import base64
import io
import soundfile as sf
from pathlib import Path

# API base URL (adjust if running on different host/port)
API_BASE_URL = "http://localhost:8000/api"

def ensure_test_directories():
    """Create test directories if they don't exist"""
    Path("./data/out").mkdir(parents=True, exist_ok=True)
    Path("./data/ref").mkdir(parents=True, exist_ok=True)

def test_basic_generation():
    """Test basic text-to-speech generation"""
    print("Testing basic TTS generation...")
    
    url = f"{API_BASE_URL}/generate"
    data = {
        "text": "Hello! This is a test of the Chatterbox TTS API.",
        "exaggeration": 0.7,
        "temperature": 0.8
    }
    
    response = requests.post(url, data=data)
    
    if response.status_code == 200:
        # Save the generated audio
        output_file = "./data/out/api_test_basic.wav"
        with open(output_file, "wb") as f:
            f.write(response.content)
        print(f"✓ Basic generation successful! Saved as '{output_file}'")
    else:
        print(f"✗ Error: {response.status_code} - {response.text}")

def test_with_reference_audio():
    """Test TTS generation with reference audio for voice cloning"""
    print("Testing TTS generation with reference audio...")
    
    # Look for reference audio files in samples folder or data/ref folder
    reference_paths = [
        "./data/ref/chaganti_ai_voice.wav",
        "./data/ref/male_old_movie.flac",
    ]
    
    reference_audio_path = None
    for path in reference_paths:
        if Path(path).exists():
            reference_audio_path = path
            break
    
    if not reference_audio_path:
        print(f"⚠ No reference audio file found. Checked:")
        for path in reference_paths:
            print(f"    {path}")
        print("  Create a reference audio file or update the path to test voice cloning")
        return
    
    url = f"{API_BASE_URL}/generate"
    data = {
        "text": "This should sound like the reference voice!",
        "exaggeration": 1.2,
        "temperature": 0.9,
        "cfg_weight": 0.7
    }
    
    with open(reference_audio_path, "rb") as audio_file:
        files = {"reference_audio": audio_file}
        response = requests.post(url, data=data, files=files)
    
    if response.status_code == 200:
        output_file = "./data/out/api_test_with_reference.wav"
        with open(output_file, "wb") as f:
            f.write(response.content)
        print(f"✓ Reference audio generation successful! Saved as '{output_file}'")
    else:
        print(f"✗ Error: {response.status_code} - {response.text}")

def test_json_response():
    """Test getting audio data as base64-encoded JSON"""
    print("Testing JSON response format...")
    
    url = f"{API_BASE_URL}/generate/json"
    data = {
        "text": "This will be returned as JSON with base64 audio data.",
        "exaggeration": 0.5,
        "seed": 42  # For reproducible results
    }
    
    response = requests.post(url, data=data)
    
    if response.status_code == 200:
        result = response.json()
        
        # Decode the base64 audio data
        audio_bytes = base64.b64decode(result["audio_base64"])
        
        # Save as WAV file
        output_file = "./data/out/api_test_json.wav"
        with open(output_file, "wb") as f:
            f.write(audio_bytes)
        
        print(f"✓ JSON generation successful! Saved as '{output_file}'")
        print(f"  Sample rate: {result['sample_rate']}")
        print(f"  Parameters used: {result['parameters']}")
    else:
        print(f"✗ Error: {response.status_code} - {response.text}")

def test_streaming():
    """Test streaming audio response"""
    print("Testing streaming response...")
    
    url = f"{API_BASE_URL}/generate/stream"
    data = {
        "text": "This audio is streamed directly from the API.",
        "exaggeration": 0.8
    }
    
    response = requests.post(url, data=data, stream=True)
    
    if response.status_code == 200:
        output_file = "./data/out/api_test_stream.wav"
        with open(output_file, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"✓ Streaming generation successful! Saved as '{output_file}'")
    else:
        print(f"✗ Error: {response.status_code} - {response.text}")

def test_different_formats():
    """Test different output formats"""
    print("Testing different output formats...")
    
    formats = ["wav", "mp3", "flac"]
    
    for fmt in formats:
        print(f"  Testing {fmt.upper()} format...")
        url = f"{API_BASE_URL}/generate"
        data = {
            "text": f"This is a test of {fmt.upper()} format output.",
            "output_format": fmt
        }
        
        response = requests.post(url, data=data)
        
        if response.status_code == 200:
            filename = f"./data/out/api_test_format.{fmt}"
            with open(filename, "wb") as f:
                f.write(response.content)
            print(f"    ✓ {fmt.upper()} generation successful! Saved as '{filename}'")
        else:
            print(f"    ✗ {fmt.upper()} Error: {response.status_code} - {response.text}")

def test_api_info():
    """Test API information endpoints"""
    print("Testing API information endpoints...")
    
    # Test root endpoint
    response = requests.get(f"{API_BASE_URL}/")
    if response.status_code == 200:
        info = response.json()
        print("✓ API Info:")
        print(f"  Version: {info['version']}")
        print(f"  Device: {info['device']}")
    
    # Test health check
    response = requests.get(f"{API_BASE_URL}/health")
    if response.status_code == 200:
        health = response.json()
        print("✓ Health Check:")
        print(f"  Status: {health['status']}")
        print(f"  Model loaded: {health['model_loaded']}")
    
    # Test model info
    response = requests.get(f"{API_BASE_URL}/model/info")
    if response.status_code == 200:
        model_info = response.json()
        print("✓ Model Info:")
        print(f"  Sample rate: {model_info['sample_rate']}")
        print(f"  Device: {model_info['device']}")

def main():
    """Run all tests"""
    print("🎤 Chatterbox TTS API Client Test\n")
    
    # Ensure test directories exist
    ensure_test_directories()
    
    try:
        # Test API availability
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print("❌ API is not available. Make sure the server is running.")
            return
    except requests.exceptions.RequestException:
        print("❌ Cannot connect to API. Make sure the server is running on http://localhost:8000")
        return
    
    print("✅ API is available. Running tests...\n")
    
    # Run tests
    test_api_info()
    print()
    
    test_basic_generation()
    print()
    
    test_json_response()
    print()
    
    test_streaming()
    print()
    
    test_different_formats()
    print()
    
    test_with_reference_audio()
    print()
    
    print("🎉 All tests completed!")
    print("📂 Generated audio files saved to: ./data/out/")
    print("📂 Reference audio files saved to: ./data/ref/")
    print("📂 Check the generated audio files to verify quality.")

if __name__ == "__main__":
    main()
