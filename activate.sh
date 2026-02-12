#!/bin/bash
# Quick activation script for p2r development environment

echo "Activating p2r virtual environment..."
source venv/bin/activate

echo "✓ Virtual environment activated"
echo ""
echo "Available commands:"
echo "  p2r --help         Show help"
echo "  p2r show-config    Show configuration"
echo "  p2r config-token   Set API token"
echo "  p2r convert        Convert PDF to Markdown"
echo "  p2r upload-images  Upload images and rewrite Markdown links"
echo ""
echo "To deactivate, run: deactivate"
