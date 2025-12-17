#!/usr/bin/env bash

# VoxCPM Model Download Script
# Downloads VoxCPM TTS model and its dependencies using ModelScope CLI
# Requires: pip install modelscope

MODELS_DIR="models"
VOXCPM_DIR="$MODELS_DIR/VoxCPM-0.5B"
ZIPENHANCER_DIR="$MODELS_DIR/iic/speech_zipenhancer_ans_multiloss_16k_base"

# Create models directory if not exists
mkdir -p "$MODELS_DIR"
mkdir -p "$MODELS_DIR/iic"

echo "============================================"
echo "VoxCPM Model Download Script"
echo "============================================"
echo ""
echo "This script will download:"
echo "  1. VoxCPM-0.5B main model (~500MB)"
echo "  2. ZipEnhancer audio enhancement model"
echo ""

# Check if modelscope CLI is installed
if ! command -v modelscope &> /dev/null; then
    echo "⚠️  ModelScope CLI not found!"
    echo "Installing ModelScope..."
    pip install -U modelscope
    if [ $? -ne 0 ]; then
        echo "✗ Failed to install ModelScope"
        echo "Please manually install: pip install -U modelscope"
        exit 1
    fi
fi

# Download VoxCPM main model
if [ ! -d "$VOXCPM_DIR" ] || [ -z "$(ls -A $VOXCPM_DIR)" ]; then
  echo ""
  echo "[1/2] Downloading VoxCPM-0.5B main model..."
  echo "This may take several minutes depending on your network speed."

  modelscope download --model OpenBMB/VoxCPM-0.5B --local_dir "$VOXCPM_DIR"

  if [ $? -eq 0 ]; then
    echo "✓ VoxCPM-0.5B downloaded successfully to $VOXCPM_DIR"
  else
    echo "✗ Failed to download VoxCPM-0.5B"
    echo "You can try manually downloading from: https://modelscope.cn/models/OpenBMB/VoxCPM-0.5B"
    exit 1
  fi
else
  echo "[1/2] VoxCPM-0.5B already exists at $VOXCPM_DIR"
fi

# Download ZipEnhancer (required for audio denoising)
if [ ! -d "$ZIPENHANCER_DIR" ] || [ -z "$(ls -A $ZIPENHANCER_DIR)" ]; then
  echo ""
  echo "[2/2] Downloading ZipEnhancer model (for audio enhancement)..."

  modelscope download --model iic/speech_zipenhancer_ans_multiloss_16k_base --local_dir "$ZIPENHANCER_DIR"

  if [ $? -eq 0 ]; then
    echo "✓ ZipEnhancer downloaded successfully to $ZIPENHANCER_DIR"
  else
    echo "✗ Failed to download ZipEnhancer"
    echo "You can try manually downloading from: https://modelscope.cn/models/iic/speech_zipenhancer_ans_multiloss_16k_base"
    exit 1
  fi
else
  echo "[2/2] ZipEnhancer already exists at $ZIPENHANCER_DIR"
fi

echo ""
echo "============================================"
echo "✅ Download Complete!"
echo "============================================"
echo "Downloaded models:"
echo "  ✓ VoxCPM-0.5B         → $VOXCPM_DIR"
echo "  ✓ ZipEnhancer         → $ZIPENHANCER_DIR"
echo "============================================"
