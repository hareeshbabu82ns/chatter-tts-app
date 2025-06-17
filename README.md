# Chatterbox TTS REST API

A simple REST API for the Chatterbox TTS model that provides all the functionality of the original Gradio app without the web interface dependency.

## Features

- **Text-to-Speech Generation**: Convert text to high-quality speech
- **Voice Cloning**: Upload reference audio to clone specific voices
- **Emotion Control**: Adjust exaggeration for emotional expression
- **Advanced Parameters**: Fine-tune generation with temperature, CFG weight, and sampling parameters
- **Multiple Output Formats**: Support for WAV, MP3, and FLAC formats
- **Streaming Support**: Stream audio directly or download files
- **JSON API**: Get base64-encoded audio data for programmatic use

## Installation

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Make sure you have the chatterbox package installed and working.

## Running the Server

Start the API server:

```bash
python tts_api.py
```

Or with custom options:
```bash
python tts_api.py --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000` by default.

## API Endpoints

### Health Check
- **GET** `/health` - Check if the API and model are ready
- **GET** `/` - Get API information and available endpoints
- **GET** `/model/info` - Get model-specific information

### Text-to-Speech Generation

#### 1. Generate Audio File
**POST** `/generate`

Generate TTS audio and return as a downloadable file.

**Parameters:**
- `text` (required): Text to synthesize (max 300 chars)
- `reference_audio` (optional): Reference audio file for voice cloning
- `exaggeration` (optional): Emotion exaggeration (0.25-2.0, default: 0.5)
- `temperature` (optional): Sampling temperature (0.05-5.0, default: 0.8)
- `cfg_weight` (optional): CFG/Pace control (0.0-1.0, default: 0.5)
- `min_p` (optional): Min-p sampling (0.0-1.0, default: 0.05)
- `top_p` (optional): Top-p sampling (0.0-1.0, default: 1.0)
- `repetition_penalty` (optional): Repetition penalty (1.0-2.0, default: 1.2)
- `seed` (optional): Random seed (0 for random, default: 0)
- `output_format` (optional): Output format - wav, mp3, flac (default: wav)

**Response:** Audio file download

#### 2. Stream Audio
**POST** `/generate/stream`

Generate TTS audio and stream it directly.

**Parameters:** Same as `/generate` (except `output_format`)

**Response:** Streamed audio data

#### 3. JSON Response
**POST** `/generate/json`

Generate TTS audio and return as base64-encoded JSON.

**Parameters:** Same as `/generate` (except `output_format`)

**Response:**
```json
{
  "success": true,
  "audio_base64": "UklGRiQ...",
  "sample_rate": 24000,
  "format": "wav",
  "text": "Your input text",
  "parameters": {
    "exaggeration": 0.5,
    "temperature": 0.8,
    ...
  }
}
```

## Usage Examples

### cURL Examples

#### Basic generation:
```bash
curl -X POST "http://localhost:8000/generate" \
     -F "text=Hello, this is a test!" \
     -F "exaggeration=0.7" \
     -o output.wav
```

#### With reference audio:
```bash
curl -X POST "http://localhost:8000/generate" \
     -F "text=Clone this voice!" \
     -F "reference_audio=@reference.wav" \
     -F "exaggeration=1.2" \
     -o cloned_voice.wav
```

#### JSON response:
```bash
curl -X POST "http://localhost:8000/generate/json" \
     -F "text=Return as JSON" \
     -F "seed=42"
```

### Python Examples

See `api_client_example.py` for comprehensive Python examples.

#### Basic usage:
```python
import requests

response = requests.post(
    "http://localhost:8000/generate",
    data={
        "text": "Hello, world!",
        "exaggeration": 0.8,
        "temperature": 0.9
    }
)

with open("output.wav", "wb") as f:
    f.write(response.content)
```

#### With reference audio:
```python
with open("reference.wav", "rb") as audio_file:
    response = requests.post(
        "http://localhost:8000/generate",
        data={"text": "Clone my voice!"},
        files={"reference_audio": audio_file}
    )
```

### JavaScript/Web Examples

#### Using Fetch API:
```javascript
const formData = new FormData();
formData.append('text', 'Hello from JavaScript!');
formData.append('exaggeration', '0.7');

fetch('http://localhost:8000/generate', {
    method: 'POST',
    body: formData
})
.then(response => response.blob())
.then(blob => {
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.play();
});
```

#### With file upload:
```javascript
const fileInput = document.getElementById('audioFile');
const file = fileInput.files[0];

const formData = new FormData();
formData.append('text', 'Clone this voice!');
formData.append('reference_audio', file);

fetch('http://localhost:8000/generate', {
    method: 'POST',
    body: formData
})
.then(response => response.blob())
.then(blob => {
    // Handle the generated audio
});
```

## Parameter Guide

### Exaggeration (0.25 - 2.0)
Controls emotional expression in the voice:
- `0.25-0.4`: Subdued, calm
- `0.5`: Neutral (default)
- `0.8-1.2`: Expressive
- `1.5-2.0`: Very dramatic (may be unstable)

### Temperature (0.05 - 5.0)
Controls randomness in generation:
- `0.1-0.5`: Very consistent, less natural
- `0.8`: Balanced (default)
- `1.5-3.0`: More varied, creative
- `3.0+`: Very random, potentially incoherent

### CFG Weight (0.0 - 1.0)
Controls adherence to text vs. audio style:
- `0.0`: Ignore text guidance
- `0.5`: Balanced (default)
- `1.0`: Strong text adherence

### Min-P (0.0 - 1.0)
Modern sampling technique:
- `0.0`: Disabled
- `0.02-0.1`: Recommended range
- Higher values: More conservative sampling

### Top-P (0.0 - 1.0)
Classical nucleus sampling:
- `1.0`: Disabled (recommended)
- `0.8`: Traditional setting
- Lower values: More conservative

### Repetition Penalty (1.0 - 2.0)
Reduces repetitive speech:
- `1.0`: No penalty
- `1.2`: Moderate (default)
- `1.5+`: Strong penalty

## Audio Formats

- **WAV**: Uncompressed, best quality (default)
- **MP3**: Compressed, smaller file size
- **FLAC**: Lossless compression

## Performance Notes

- First request may be slower due to model loading
- GPU acceleration is used if available
- Model is loaded once and reused for subsequent requests
- Temporary files for uploads are cleaned up automatically

## Error Handling

The API returns appropriate HTTP status codes:
- `200`: Success
- `400`: Bad request (invalid parameters)
- `422`: Validation error
- `500`: Server error (generation failed)
- `503`: Service unavailable (model not loaded)

Error responses include details in JSON format:
```json
{
  "detail": "Error description"
}
```

## Development

Run with auto-reload for development:
```bash
python tts_api.py --reload
```

View API documentation at: `http://localhost:8000/docs` (automatic FastAPI docs)

## Testing

Run the test client to verify all functionality:
```bash
python api_client_example.py
```

This will test all endpoints and generate sample audio files.

## Docker Support

You can also run the API in a Docker container. Create a `Dockerfile`:

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "tts_api.py", "--host", "0.0.0.0"]
```

Build and run:
```bash
docker build -t chatterbox-api .
docker run -p 8000:8000 chatterbox-api
```

## License

Same as the Chatterbox TTS model (MIT License).
