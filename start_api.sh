#!/bin/bash

# Chatterbox TTS API Startup Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🎤 Chatterbox TTS API Setup${NC}"
echo "================================"

# Check if we're in the chatterbox directory
if [[ ! -f "tts_api.py" ]]; then
    echo -e "${RED}Error: Please run this script from the chatterbox directory${NC}"
    exit 1
fi

# Check if conda is available
if command -v conda >/dev/null 2>&1; then
    echo -e "${GREEN}Conda detected! Using conda environment...${NC}"
    
    # Check if chatterbox environment exists
    if ! conda env list | grep -q "^chatterbox "; then
        echo -e "${YELLOW}Creating conda environment 'chatterbox'...${NC}"
        conda create -n chatterbox python=3.12 -y
    fi
    
    # Activate conda environment
    echo -e "${YELLOW}Activating conda environment 'chatterbox'...${NC}"
    eval "$(conda shell.bash hook)"
    conda activate chatterbox
    
else
    echo -e "${YELLOW}Conda not found. Using virtual environment instead...${NC}"
    
    # Create virtual environment if it doesn't exist
    VENV_DIR=".venv"
    if [[ ! -d "$VENV_DIR" ]]; then
        echo -e "${YELLOW}Creating virtual environment...${NC}"
        python3 -m venv "$VENV_DIR"
    fi
    
    # Activate virtual environment
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source "$VENV_DIR/bin/activate"
fi

# Upgrade pip
pip install --upgrade pip

# Install API dependencies
echo -e "${YELLOW}Installing API dependencies...${NC}"
pip install -r requirements.txt

# Check if chatterbox is installed
if ! python -c "import chatterbox.tts" 2>/dev/null; then
    echo -e "${YELLOW}Installing chatterbox package...${NC}"
    pip install -e .
fi

# Start the API server
echo -e "${GREEN}Starting Chatterbox TTS API server...${NC}"
echo "API will be available at: http://localhost:8000"
echo "API documentation: http://localhost:8000/docs"
echo "Demo page: Open http://localhost:8000/docs/api_demo.html in your browser"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Parse command line arguments
HOST="0.0.0.0"
PORT="8000"
RELOAD=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --host)
            HOST="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --reload)
            RELOAD="--reload"
            shift
            ;;
        *)
            echo "Unknown option $1"
            echo "Usage: $0 [--host HOST] [--port PORT] [--reload]"
            exit 1
            ;;
    esac
done

# Start the server
python tts_api.py --host "$HOST" --port "$PORT" $RELOAD
