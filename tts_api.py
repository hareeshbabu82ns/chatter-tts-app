from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import torch
import numpy as np
import io
import tempfile
import os
import random
from typing import Optional
import librosa
import soundfile as sf
from pathlib import Path
import shutil
from datetime import datetime

from chatterbox.tts import ChatterboxTTS

app = FastAPI(title="Chatterbox TTS API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
model = None

# Data directories
DATA_DIR = Path("./data")
REF_AUDIO_DIR = DATA_DIR / "ref"
OUTPUT_AUDIO_DIR = DATA_DIR / "out"

def ensure_directories():
    """Create data directories if they don't exist"""
    REF_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

def set_seed(seed: int):
    """Set random seed for reproducibility"""
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    random.seed(seed)
    np.random.seed(seed)

def load_model():
    """Load the TTS model"""
    global model
    if model is None:
        model = ChatterboxTTS.from_pretrained(DEVICE)
    return model

@app.on_event("startup")
async def startup_event():
    """Load model and create directories on startup"""
    ensure_directories()
    load_model()

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Chatterbox TTS API",
        "version": "1.0.0",
        "device": DEVICE,
        "endpoints": {
            "generate": "/generate - Generate TTS audio",
            "generate_stream": "/generate/stream - Generate and stream TTS audio",
            "health": "/health - Health check",
            "model_info": "/model/info - Model information"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "device": DEVICE,
        "model_loaded": model is not None
    }

@app.get("/model/info")
async def model_info():
    """Get model information"""
    global model
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    return {
        "sample_rate": model.sr,
        "device": model.device,
        "model_type": "ChatterboxTTS"
    }

@app.post("/generate")
async def generate_tts(
    text: str = Form(..., description="Text to synthesize (max 300 chars)"),
    reference_audio: Optional[UploadFile] = File(None, description="Reference audio file for voice cloning"),
    exaggeration: float = Form(0.5, ge=0.25, le=2.0, description="Emotion exaggeration (0.25-2.0, neutral=0.5)"),
    temperature: float = Form(0.8, ge=0.05, le=5.0, description="Sampling temperature"),
    cfg_weight: float = Form(0.5, ge=0.0, le=1.0, description="CFG/Pace control"),
    min_p: float = Form(0.05, ge=0.0, le=1.0, description="Min-p sampling parameter"),
    top_p: float = Form(1.0, ge=0.0, le=1.0, description="Top-p sampling parameter"),
    repetition_penalty: float = Form(1.2, ge=1.0, le=2.0, description="Repetition penalty"),
    seed: int = Form(0, description="Random seed (0 for random)"),
    output_format: str = Form("wav", description="Output format (wav, mp3, flac)")
):
    """Generate TTS audio and return as downloadable file"""
    try:
        # Load model if not already loaded
        tts_model = load_model()
        
        # Set seed if specified
        if seed != 0:
            set_seed(seed)
        
        # Handle reference audio if provided
        audio_prompt_path = None
        if reference_audio:
            try:
                audio_prompt_path = await save_uploaded_audio(reference_audio)
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Error processing reference audio: {str(e)}")
        
        # Generate audio
        wav = tts_model.generate(
            text=text,
            audio_prompt_path=audio_prompt_path,
            exaggeration=exaggeration,
            temperature=temperature,
            cfg_weight=cfg_weight,
            min_p=min_p,
            top_p=top_p,
            repetition_penalty=repetition_penalty,
        )
        
        # Note: Keep reference audio file in ref folder for future use
        # No longer deleting: if audio_prompt_path and os.path.exists(audio_prompt_path): os.unlink(audio_prompt_path)
        
        # Convert to numpy array
        audio_data = wav.squeeze(0).numpy()
        
        # Generate timestamped filename for output
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create audio file in memory
        output_buffer = io.BytesIO()
        
        if output_format.lower() == "mp3":
            # For MP3, we need to use a temporary file since soundfile doesn't support MP3 in memory
            output_filename = f"generated_{timestamp}.mp3"
            output_file_path = OUTPUT_AUDIO_DIR / output_filename
            sf.write(str(output_file_path), audio_data, tts_model.sr, format='MP3')
            with open(output_file_path, 'rb') as f:
                output_buffer.write(f.read())
            media_type = "audio/mpeg"
            filename = output_filename
        elif output_format.lower() == "flac":
            output_filename = f"generated_{timestamp}.flac"
            output_file_path = OUTPUT_AUDIO_DIR / output_filename
            sf.write(output_buffer, audio_data, tts_model.sr, format='FLAC')
            # Also save to disk
            sf.write(str(output_file_path), audio_data, tts_model.sr, format='FLAC')
            media_type = "audio/flac"
            filename = output_filename
        else:  # Default to WAV
            output_filename = f"generated_{timestamp}.wav"
            output_file_path = OUTPUT_AUDIO_DIR / output_filename
            sf.write(output_buffer, audio_data, tts_model.sr, format='WAV')
            # Also save to disk
            sf.write(str(output_file_path), audio_data, tts_model.sr, format='WAV')
            media_type = "audio/wav"
            filename = output_filename
        
        output_buffer.seek(0)
        
        return StreamingResponse(
            io.BytesIO(output_buffer.read()),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating audio: {str(e)}")

@app.post("/generate/stream")
async def generate_tts_stream(
    text: str = Form(..., description="Text to synthesize (max 300 chars)"),
    reference_audio: Optional[UploadFile] = File(None, description="Reference audio file for voice cloning"),
    exaggeration: float = Form(0.5, ge=0.25, le=2.0, description="Emotion exaggeration (0.25-2.0, neutral=0.5)"),
    temperature: float = Form(0.8, ge=0.05, le=5.0, description="Sampling temperature"),
    cfg_weight: float = Form(0.5, ge=0.0, le=1.0, description="CFG/Pace control"),
    min_p: float = Form(0.05, ge=0.0, le=1.0, description="Min-p sampling parameter"),
    top_p: float = Form(1.0, ge=0.0, le=1.0, description="Top-p sampling parameter"),
    repetition_penalty: float = Form(1.2, ge=1.0, le=2.0, description="Repetition penalty"),
    seed: int = Form(0, description="Random seed (0 for random)")
):
    """Generate TTS audio and stream it directly"""
    try:
        # Load model if not already loaded
        tts_model = load_model()
        
        # Set seed if specified
        if seed != 0:
            set_seed(seed)
        
        # Handle reference audio if provided
        audio_prompt_path = None
        if reference_audio:
            try:
                audio_prompt_path = await save_uploaded_audio(reference_audio)
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Error processing reference audio: {str(e)}")
        
        # Generate audio
        wav = tts_model.generate(
            text=text,
            audio_prompt_path=audio_prompt_path,
            exaggeration=exaggeration,
            temperature=temperature,
            cfg_weight=cfg_weight,
            min_p=min_p,
            top_p=top_p,
            repetition_penalty=repetition_penalty,
        )
        
        # Note: Keep reference audio file in ref folder for future use
        # No longer deleting: if audio_prompt_path and os.path.exists(audio_prompt_path): os.unlink(audio_prompt_path)
        
        # Convert to numpy array
        audio_data = wav.squeeze(0).numpy()
        
        # Generate timestamped filename and save to out folder
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"generated_stream_{timestamp}.wav"
        output_file_path = OUTPUT_AUDIO_DIR / output_filename
        
        # Create WAV file in memory for streaming
        output_buffer = io.BytesIO()
        sf.write(output_buffer, audio_data, tts_model.sr, format='WAV')
        output_buffer.seek(0)
        
        # Also save to disk in out folder
        sf.write(str(output_file_path), audio_data, tts_model.sr, format='WAV')
        
        return StreamingResponse(
            io.BytesIO(output_buffer.read()),
            media_type="audio/wav",
            headers={
                "Content-Disposition": f"inline; filename={output_filename}",
                "Cache-Control": "no-cache"
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating audio: {str(e)}")

@app.post("/generate/json")
async def generate_tts_json(
    text: str = Form(..., description="Text to synthesize (max 300 chars)"),
    reference_audio: Optional[UploadFile] = File(None, description="Reference audio file for voice cloning"),
    exaggeration: float = Form(0.5, ge=0.25, le=2.0, description="Emotion exaggeration (0.25-2.0, neutral=0.5)"),
    temperature: float = Form(0.8, ge=0.05, le=5.0, description="Sampling temperature"),
    cfg_weight: float = Form(0.5, ge=0.0, le=1.0, description="CFG/Pace control"),
    min_p: float = Form(0.05, ge=0.0, le=1.0, description="Min-p sampling parameter"),
    top_p: float = Form(1.0, ge=0.0, le=1.0, description="Top-p sampling parameter"),
    repetition_penalty: float = Form(1.2, ge=1.0, le=2.0, description="Repetition penalty"),
    seed: int = Form(0, description="Random seed (0 for random)")
):
    """Generate TTS audio and return audio data as base64 encoded JSON"""
    import base64
    
    try:
        # Load model if not already loaded
        tts_model = load_model()
        
        # Set seed if specified
        if seed != 0:
            set_seed(seed)
        
        # Handle reference audio if provided
        audio_prompt_path = None
        if reference_audio:
            try:
                audio_prompt_path = await save_uploaded_audio(reference_audio)
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Error processing reference audio: {str(e)}")
        
        # Generate audio
        wav = tts_model.generate(
            text=text,
            audio_prompt_path=audio_prompt_path,
            exaggeration=exaggeration,
            temperature=temperature,
            cfg_weight=cfg_weight,
            min_p=min_p,
            top_p=top_p,
            repetition_penalty=repetition_penalty,
        )
        
        # Note: Keep reference audio file in ref folder for future use
        # No longer deleting: if audio_prompt_path and os.path.exists(audio_prompt_path): os.unlink(audio_prompt_path)
        
        # Convert to numpy array
        audio_data = wav.squeeze(0).numpy()
        
        # Generate timestamped filename and save to out folder
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"generated_json_{timestamp}.wav"
        output_file_path = OUTPUT_AUDIO_DIR / output_filename
        
        # Create WAV file in memory
        output_buffer = io.BytesIO()
        sf.write(output_buffer, audio_data, tts_model.sr, format='WAV')
        output_buffer.seek(0)
        
        # Also save to disk in out folder
        sf.write(str(output_file_path), audio_data, tts_model.sr, format='WAV')
        
        # Encode as base64
        audio_base64 = base64.b64encode(output_buffer.read()).decode('utf-8')
        
        return JSONResponse({
            "success": True,
            "audio_base64": audio_base64,
            "sample_rate": tts_model.sr,
            "format": "wav",
            "text": text,
            "parameters": {
                "exaggeration": exaggeration,
                "temperature": temperature,
                "cfg_weight": cfg_weight,
                "min_p": min_p,
                "top_p": top_p,
                "repetition_penalty": repetition_penalty,
                "seed": seed
            }
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating audio: {str(e)}")

# Helper function for robust audio handling
async def save_uploaded_audio(reference_audio: UploadFile) -> str:
    """
    Save uploaded audio file with validation and return file path in ref folder
    """
    if not reference_audio.filename:
        raise HTTPException(status_code=400, detail="No filename provided for reference audio")
    
    # Check file extension
    allowed_extensions = {'.wav', '.mp3', '.flac', '.m4a', '.ogg', '.aac'}
    file_ext = os.path.splitext(reference_audio.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported audio format: {file_ext}. Supported formats: {', '.join(allowed_extensions)}"
        )
    
    # Generate timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"ref_{timestamp}_{reference_audio.filename}"
    ref_file_path = REF_AUDIO_DIR / safe_filename
    
    # Save uploaded file to ref folder
    content = await reference_audio.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file")
    if len(content) > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(status_code=400, detail="Audio file too large (max 50MB)")
    
    with open(ref_file_path, "wb") as f:
        f.write(content)
    
    return str(ref_file_path)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Chatterbox TTS REST API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    
    args = parser.parse_args()
    
    uvicorn.run(
        "tts_api:app" if not args.reload else "tts_api:app",
        host=args.host,
        port=args.port,
        reload=args.reload
    )
