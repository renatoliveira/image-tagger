"""Bounding box data structures and utilities"""

from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtGui import QColor


class BoundingBox:
    """Represents a bounding box with class information"""

    def __init__(self, x, y, width, height, class_index=0, class_name="object"):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.class_index = class_index
        self.class_name = class_name
        self.selected = False

    def to_yolo_format(self, img_width, img_height):
        """Convert to YOLO format coordinates"""
        x_center = (self.x + self.width / 2) / img_width
        y_center = (self.y + self.height / 2) / img_height
        norm_width = self.width / img_width
        norm_height = self.height / img_height
        return f"{self.class_index} {x_center:.6f} {y_center:.6f} {norm_width:.6f} {norm_height:.6f}"

    def contains_point(self, point):
        """Check if point is inside bounding box"""
        return (self.x <= point.x() <= self.x + self.width and
                self.y <= point.y() <= self.y + self.height)

    def get_rect(self):
        """Get QRect representation"""
        return QRect(int(self.x), int(self.y), int(self.width), int(self.height))
