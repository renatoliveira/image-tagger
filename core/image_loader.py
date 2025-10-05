"""Image loading and processing utilities"""

import os
from pathlib import Path
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QMessageBox


def load_image_files(directory):
    """Load all image files from directory"""
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}
    image_files = []

    for file_path in Path(directory).iterdir():
        if file_path.suffix.lower() in image_extensions:
            image_files.append(str(file_path))

    return sorted(image_files)


def load_pixmap(image_path):
    """Load QPixmap from image file"""
    try:
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            raise ValueError("Could not load image")
        return pixmap
    except Exception as e:
        raise ValueError(f"Could not load image: {str(e)}")


def get_image_info(image_path):
    """Get basic image information"""
    try:
        pixmap = load_pixmap(image_path)
        return {
            'width': pixmap.width(),
            'height': pixmap.height(),
            'size': pixmap.size()
        }
    except Exception as e:
        return None
