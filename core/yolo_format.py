"""YOLO format I/O operations"""

import os
from pathlib import Path
from PyQt6.QtWidgets import QMessageBox
from .annotations import BoundingBox


def load_yolo_annotations(image_path, classes):
    """Load YOLO format annotations from .txt file"""
    txt_path = str(Path(image_path).with_suffix('.txt'))
    if not os.path.exists(txt_path):
        return []

    try:
        with open(txt_path, 'r') as f:
            lines = f.readlines()

        bounding_boxes = []
        img_width = 1  # Will be set by caller
        img_height = 1  # Will be set by caller

        for line in lines:
            parts = line.strip().split()
            if len(parts) == 5:
                class_idx = int(parts[0])
                x_center = float(parts[1])
                y_center = float(parts[2])
                width = float(parts[3])
                height = float(parts[4])

                # Convert from YOLO format to pixel coordinates
                x = (x_center - width / 2) * img_width
                y = (y_center - height / 2) * img_height
                w = width * img_width
                h = height * img_height

                class_name = classes[class_idx] if class_idx < len(classes) else "object"
                box = BoundingBox(x, y, w, h, class_idx, class_name)
                bounding_boxes.append(box)

        return bounding_boxes

    except Exception as e:
        print(f"Error loading annotations: {e}")
        return []


def save_yolo_annotations(bounding_boxes, image_path, img_width, img_height):
    """Save bounding boxes to YOLO format .txt file"""
    txt_path = str(Path(image_path).with_suffix('.txt'))

    try:
        with open(txt_path, 'w') as f:
            for box in bounding_boxes:
                yolo_line = box.to_yolo_format(img_width, img_height)
                f.write(yolo_line + '\n')
        return True
    except Exception as e:
        print(f"Could not save annotations: {str(e)}")
        return False


def load_label_mapping(label_mapping_file):
    """Load label mapping from label-mapping.txt file"""
    if not label_mapping_file or not label_mapping_file.exists():
        return []

    try:
        with open(label_mapping_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        labels = []
        for line in lines:
            label = line.strip()
            if label:  # Skip empty lines
                labels.append(label)

        return labels

    except Exception as e:
        print(f"Error loading label mapping: {e}")
        return []


def save_label_mapping(classes, label_mapping_file):
    """Save current classes to label-mapping.txt file"""
    if not label_mapping_file:
        return False

    try:
        with open(label_mapping_file, 'w', encoding='utf-8') as f:
            for label in classes:
                f.write(f"{label}\n")
        return True
    except Exception as e:
        print(f"Could not save label mapping: {str(e)}")
        return False
