from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import torch
import numpy as np
import io
import os
import random
from typing import Optional
import soundfile as sf
from pathlib import Path
import shutil
from datetime import datetime
import logging
import sys
import time
import signal
import threading

from chatterbox.tts import ChatterboxTTS

app = FastAPI(title="Chatterbox TTS API", version="1.0.0")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables
# Device detection with priority: ENV_VAR > CUDA > MPS > CPU
def detect_device():
    """Detect the best available device with proper error handling"""
    # Check for environment variable override
    env_device = os.environ.get('TORCH_DEVICE', '').lower()
    if env_device in ['cuda', 'mps', 'cpu']:
        logger.info(f"🔧 Device override from environment: {env_device}")
        
        # Validate the requested device is actually available
        if env_device == 'cuda':
            if not torch.cuda.is_available():
                logger.warning(f"⚠️ CUDA requested but not available, falling back to auto-detection")
            else:
                try:
                    torch.cuda.get_device_name(0)
                    return "cuda"
                except Exception as e:
                    logger.warning(f"⚠️ CUDA requested but not accessible: {e}")
        
        elif env_device == 'mps':
            if not torch.backends.mps.is_available():
                logger.warning(f"⚠️ MPS requested but not available, falling back to auto-detection")
            else:
                try:
                    test_tensor = torch.randn(1).to("mps")
                    return "mps"
                except Exception as e:
                    logger.warning(f"⚠️ MPS requested but not accessible: {e}")
        
        elif env_device == 'cpu':
            return "cpu"
    
    # Auto-detection if no valid environment override
    try:
        if torch.cuda.is_available():
            # Verify CUDA device is actually accessible
            torch.cuda.get_device_name(0)
            return "cuda"
    except Exception as e:
        logger.warning(f"⚠️ CUDA detected but not accessible: {e}")
    
    try:
        if torch.backends.mps.is_available():
            # Verify MPS is actually usable
            test_tensor = torch.randn(1).to("mps")
            return "mps"
    except Exception as e:
        logger.warning(f"⚠️ MPS detected but not accessible: {e}")
    
    logger.info("💻 Falling back to CPU device")
    return "cpu"

DEVICE = detect_device()
model = None

# Initialize logging early
logger.info("🔧 System Information:")
logger.info(f"🐍 Python: {sys.version}")
logger.info(f"🔥 PyTorch: {torch.__version__}")
logger.info(f"🎯 CUDA Available: {torch.cuda.is_available()}")
logger.info(f"🍎 MPS Available: {torch.backends.mps.is_available()}")
logger.info(f"📱 Selected Device: {DEVICE}")
if torch.cuda.is_available():
    logger.info(f"🎮 GPU: {torch.cuda.get_device_name(0)}")
    logger.info(f"💾 GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
elif torch.backends.mps.is_available():
    logger.info(f"🍎 MPS Device: Apple Silicon GPU")
    logger.info(f"💾 MPS Memory Management: Unified Memory Architecture")

# Data directories
DATA_DIR = Path("./data")
REF_AUDIO_DIR = DATA_DIR / "ref"
OUTPUT_AUDIO_DIR = DATA_DIR / "out"

def ensure_directories():
    """Create data directories if they don't exist"""
    logger.info(f"📁 Creating directory: {REF_AUDIO_DIR}")
    REF_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"📁 Creating directory: {OUTPUT_AUDIO_DIR}")
    OUTPUT_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("📁 All directories ready")

def set_seed(seed: int):
    """Set random seed for reproducibility"""
    torch.manual_seed(seed)
    np.random.seed(seed)
    random.seed(seed)
    
    # Set device-specific seeds
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    
    # MPS doesn't have a separate manual_seed function as of PyTorch 2.x
    # The torch.manual_seed should handle MPS devices

def load_model_with_timeout(timeout_seconds=300):
    """Load the TTS model with timeout handling"""
    logger.info("🔄 Starting model loading with timeout...")
    
    result = {'model': None, 'error': None, 'completed': False}
    
    def model_loader():
        try:
            logger.info(f"📱 Device: {DEVICE}")
            logger.info("🌐 Checking internet connectivity...")
            
            # Test internet connection
            import urllib.request
            try:
                urllib.request.urlopen('https://huggingface.co', timeout=10)
                logger.info("✅ Internet connectivity confirmed")
            except Exception as e:
                logger.error(f"❌ Internet connectivity issue: {e}")
                result['error'] = f"Internet connectivity issue: {e}"
                return
            
            logger.info("⬇️ Starting model download/loading from Hugging Face...")
            logger.info("📦 This may take several minutes for first-time download...")
            
            # Log environment info
            logger.info(f"🔧 Python executable: {sys.executable}")
            logger.info(f"🔧 PyTorch version: {torch.__version__}")
            logger.info(f"🎯 CUDA available: {torch.cuda.is_available()}")
            logger.info(f"🍎 MPS available: {torch.backends.mps.is_available()}")
            if torch.cuda.is_available() and DEVICE == "cuda":
                logger.info(f"🎮 CUDA device: {torch.cuda.get_device_name(0)}")
            elif torch.backends.mps.is_available() and DEVICE == "mps":
                logger.info(f"🍎 MPS device: Apple Silicon GPU")
            
            start_time = time.time()
            model = ChatterboxTTS.from_pretrained(DEVICE)
            load_time = time.time() - start_time
            
            logger.info(f"✅ Model loaded successfully in {load_time:.1f} seconds!")
            result['model'] = model
            result['completed'] = True
            
        except Exception as e:
            logger.error(f"❌ Model loading failed: {e}")
            result['error'] = str(e)
    
    # Start model loading in a separate thread
    thread = threading.Thread(target=model_loader)
    thread.daemon = True
    thread.start()
    
    # Wait for completion or timeout
    start_time = time.time()
    while thread.is_alive() and (time.time() - start_time) < timeout_seconds:
        elapsed = time.time() - start_time
        if elapsed % 30 < 1:  # Log every 30 seconds
            logger.info(f"⏳ Model loading in progress... {elapsed:.0f}s elapsed (timeout: {timeout_seconds}s)")
        time.sleep(1)
    
    if thread.is_alive():
        logger.error(f"⏰ Model loading timed out after {timeout_seconds} seconds")
        return None, f"Model loading timed out after {timeout_seconds} seconds"
    
    if result['error']:
        return None, result['error']
    
    return result['model'], None

def load_model():
    """Load the TTS model"""
    global model
    if model is None:
        logger.info("🚀 Initializing model loading...")
        model, error = load_model_with_timeout(timeout_seconds=600)  # 10 minute timeout
        if error:
            logger.error(f"❌ Failed to load model: {error}")
            raise RuntimeError(f"Model loading failed: {error}")
        logger.info("✅ Model successfully initialized!")
    return model

@app.on_event("startup")
async def startup_event():
    """Load model and create directories on startup"""
    logger.info("🚀 ========================================")
    logger.info("🚀 Starting Chatterbox TTS API...")
    logger.info("🚀 ========================================")
    
    try:
        logger.info("📁 Step 1/2: Creating data directories...")
        ensure_directories()
        logger.info("✅ Directories created successfully")
        
        logger.info("🤖 Step 2/2: Loading TTS model...")
        logger.info("⚠️  This step may take several minutes on first run...")
        
        load_model()
        
        logger.info("✅ ========================================")
        logger.info("✅ Startup completed successfully!")
        logger.info("✅ API is ready to receive requests")
        logger.info("✅ ========================================")
        
    except Exception as e:
        logger.error("❌ ========================================")
        logger.error(f"❌ Startup failed: {e}")
        logger.error("❌ ========================================")
        raise

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Chatterbox TTS API",
        "version": "1.0.0",
        "device": DEVICE,
        "endpoints": {
            "demo": "/api_demo.html - Interactive API demo page",
            "generate": "/generate - Generate TTS audio",
            "generate_stream": "/generate/stream - Generate and stream TTS audio",
            "health": "/health - Health check",
            "model_info": "/model/info - Model information",
            "reference_audio_list": "/reference-audio/list - List reference audio files",
            "reference_audio_upload": "/reference-audio/upload - Upload reference audio file",
            "reference_audio_delete": "/reference-audio/delete/{filename} - Delete reference audio file",
            "output_audio_list": "/output-audio/list - List generated output audio files",
            "output_audio_delete": "/output-audio/delete/{filename} - Delete generated output audio file",
            "output_audio_download": "/output-audio/download/{filename} - Download generated output audio file"
        }
    }

@app.get("/api_demo.html", response_class=HTMLResponse)
async def api_demo():
    """Serve the API demo HTML page"""
    try:
        with open("api_demo.html", "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Demo page not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error serving demo page: {str(e)}")

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
    reference_audio_file: Optional[str] = Form(None, description="Existing reference audio filename from ./data/ref/"),
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
        elif reference_audio_file:
            # Use existing reference audio file
            ref_path = REF_AUDIO_DIR / reference_audio_file
            if not ref_path.exists():
                raise HTTPException(status_code=404, detail=f"Reference audio file not found: {reference_audio_file}")
            audio_prompt_path = str(ref_path)
        
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
    reference_audio_file: Optional[str] = Form(None, description="Existing reference audio filename from ./data/ref/"),
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
        elif reference_audio_file:
            # Use existing reference audio file
            ref_path = REF_AUDIO_DIR / reference_audio_file
            if not ref_path.exists():
                raise HTTPException(status_code=404, detail=f"Reference audio file not found: {reference_audio_file}")
            audio_prompt_path = str(ref_path)
        
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
    reference_audio_file: Optional[str] = Form(None, description="Existing reference audio filename from ./data/ref/"),
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
        elif reference_audio_file:
            # Use existing reference audio file
            ref_path = REF_AUDIO_DIR / reference_audio_file
            if not ref_path.exists():
                raise HTTPException(status_code=404, detail=f"Reference audio file not found: {reference_audio_file}")
            audio_prompt_path = str(ref_path)
        
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

@app.get("/reference-audio/list")
async def list_reference_audio():
    """List available reference audio files"""
    try:
        ref_files = []
        if REF_AUDIO_DIR.exists():
            for file_path in REF_AUDIO_DIR.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in ['.wav', '.mp3', '.flac', '.ogg', '.m4a']:
                    # Get file info
                    file_stat = file_path.stat()
                    ref_files.append({
                        "filename": file_path.name,
                        "path": str(file_path),
                        "size": file_stat.st_size,
                        "modified": datetime.fromtimestamp(file_stat.st_mtime).isoformat()
                    })
        
        return {
            "reference_files": sorted(ref_files, key=lambda x: x["filename"]),
            "count": len(ref_files)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing reference audio files: {str(e)}")

@app.post("/reference-audio/upload")
async def upload_reference_audio(
    file: UploadFile = File(..., description="Reference audio file to upload")
):
    """Upload a new reference audio file"""
    try:
        # Validate file type
        if not file.filename.lower().endswith(('.wav', '.mp3', '.flac', '.ogg', '.m4a')):
            raise HTTPException(
                status_code=400, 
                detail="Invalid file type. Supported formats: WAV, MP3, FLAC, OGG, M4A"
            )
        
        # Create unique filename to avoid conflicts
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = Path(file.filename).stem
        extension = Path(file.filename).suffix
        unique_filename = f"{base_name}_{timestamp}{extension}"
        
        # Save file
        file_path = REF_AUDIO_DIR / unique_filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Get file info
        file_stat = file_path.stat()
        
        return {
            "message": "Reference audio uploaded successfully",
            "filename": unique_filename,
            "path": str(file_path),
            "size": file_stat.st_size,
            "original_filename": file.filename
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading reference audio: {str(e)}")

@app.delete("/reference-audio/delete/{filename}")
async def delete_reference_audio(filename: str):
    """Delete a reference audio file"""
    try:
        # Validate filename to prevent path traversal attacks
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")
        
        file_path = REF_AUDIO_DIR / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"Reference audio file not found: {filename}")
        
        if not file_path.is_file():
            raise HTTPException(status_code=400, detail="Not a valid file")
        
        # Delete the file
        file_path.unlink()
        
        return {
            "message": "Reference audio deleted successfully",
            "filename": filename
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting reference audio: {str(e)}")

@app.get("/output-audio/list")
async def list_output_audio():
    """List available generated output audio files"""
    try:
        output_files = []
        if OUTPUT_AUDIO_DIR.exists():
            for file_path in OUTPUT_AUDIO_DIR.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in ['.wav', '.mp3', '.flac', '.ogg', '.m4a']:
                    # Get file info
                    file_stat = file_path.stat()
                    output_files.append({
                        "filename": file_path.name,
                        "path": str(file_path),
                        "size": file_stat.st_size,
                        "modified": datetime.fromtimestamp(file_stat.st_mtime).isoformat()
                    })
        
        return {
            "output_files": sorted(output_files, key=lambda x: x["modified"], reverse=True),  # Newest first
            "count": len(output_files)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing output audio files: {str(e)}")

@app.delete("/output-audio/delete/{filename}")
async def delete_output_audio(filename: str):
    """Delete a generated output audio file"""
    try:
        # Validate filename to prevent path traversal attacks
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")
        
        file_path = OUTPUT_AUDIO_DIR / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"Output audio file not found: {filename}")
        
        if not file_path.is_file():
            raise HTTPException(status_code=400, detail="Not a valid file")
        
        # Delete the file
        file_path.unlink()
        
        return {
            "message": "Output audio deleted successfully",
            "filename": filename
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting output audio: {str(e)}")

@app.get("/output-audio/download/{filename}")
async def download_output_audio(filename: str):
    """Download a generated output audio file"""
    try:
        # Validate filename to prevent path traversal attacks
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")
        
        file_path = OUTPUT_AUDIO_DIR / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"Output audio file not found: {filename}")
        
        if not file_path.is_file():
            raise HTTPException(status_code=400, detail="Not a valid file")
        
        # Determine media type based on file extension
        extension = file_path.suffix.lower()
        if extension == '.mp3':
            media_type = "audio/mpeg"
        elif extension == '.flac':
            media_type = "audio/flac"
        elif extension == '.ogg':
            media_type = "audio/ogg"
        else:  # Default to WAV
            media_type = "audio/wav"
        
        # Read and return file
        with open(file_path, "rb") as f:
            content = f.read()
        
        return StreamingResponse(
            io.BytesIO(content),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error downloading output audio: {str(e)}")

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
    
    logger.info("🚀 ========================================")
    logger.info("🚀 Chatterbox TTS API Server Starting...")
    logger.info("🚀 ========================================")
    
    parser = argparse.ArgumentParser(description="Chatterbox TTS REST API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    
    args = parser.parse_args()
    
    logger.info(f"🌐 Starting server on {args.host}:{args.port}")
    logger.info(f"🔄 Auto-reload: {args.reload}")
    
    uvicorn.run(
        "tts_api:app" if not args.reload else "tts_api:app",
        host=args.host,
        port=args.port,
        reload=args.reload
    )
