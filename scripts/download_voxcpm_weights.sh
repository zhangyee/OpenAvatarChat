#!/usr/bin/env bash

# VoxCPM Model Download Script

MODELS_DIR="models"
VOXCPM_DIR="$MODELS_DIR/VoxCPM-0.5B"
ZIPENHANCER_DIR="$MODELS_DIR/iic/speech_zipenhancer_ans_multiloss_16k_base"
SENSEVOICE_DIR="$MODELS_DIR/iic/SenseVoiceSmall"

# Create necessary directories
mkdir -p "$VOXCPM_DIR"
mkdir -p "$ZIPENHANCER_DIR"
mkdir -p "$SENSEVOICE_DIR"

# Install modelscope CLI
pip install -U modelscope

# Download VoxCPM main model
echo "Downloading VoxCPM-0.5B to $VOXCPM_DIR..."
modelscope download --model OpenBMB/VoxCPM-0.5B --local_dir "$VOXCPM_DIR"

# Download ZipEnhancer (for audio enhancement)
echo "Downloading ZipEnhancer to $ZIPENHANCER_DIR..."
modelscope download --model iic/speech_zipenhancer_ans_multiloss_16k_base --local_dir "$ZIPENHANCER_DIR"

# Download SenseVoiceSmall (for ASR)
echo "Downloading SenseVoiceSmall to $SENSEVOICE_DIR..."
modelscope download --model iic/SenseVoiceSmall --local_dir "$SENSEVOICE_DIR"

echo "All download commands have been executed. Please check the following directories exist:"
echo "- $VOXCPM_DIR (VoxCPM-0.5B main model)"
echo "- $ZIPENHANCER_DIR (ZipEnhancer model)"
echo "- $SENSEVOICE_DIR (SenseVoiceSmall model)"
echo "If any file is missing, please check the download logs above."
