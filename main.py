import sys
import os
import random
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                             QWidget, QPushButton, QLabel, QFileDialog, QComboBox,
                             QSpinBox, QStatusBar, QMessageBox, QMenuBar, QMenu,
                             QToolBar, QFrame, QScrollArea, QListWidget, QListWidgetItem,
                             QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QColorDialog)
from PyQt6.QtCore import Qt, QPoint, QRect, QSize, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap, QPainter, QPen, QBrush, QColor, QAction, QKeySequence, QClipboard
from PIL import Image
import json


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


class ImageCanvas(QWidget):
    """Custom widget for displaying images and drawing bounding boxes"""

    # Signals
    bounding_box_created = pyqtSignal(object)
    bounding_box_selected = pyqtSignal(object)
    bounding_box_deleted = pyqtSignal(object)
    bounding_box_class_edit_requested = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.setMinimumSize(800, 600)
        self.setMouseTracking(True)

        # Image and display properties
        self.original_pixmap = None
        self.scaled_pixmap = None
        self.scale_factor = 1.0
        self.offset = QPoint(0, 0)

        # Bounding box properties
        self.bounding_boxes = []
        self.current_box = None
        self.drawing = False
        self.start_point = QPoint()
        self.selected_box = None
        self.selected_boxes = []  # For multi-selection
        self.clipboard_boxes = []  # For copy/paste operations

        # Class management
        self.classes = ["object"]  # Default class
        self.current_class_index = 0
        self.class_colors = [QColor(255, 0, 0)]  # Default red color

        # Mouse tracking
        self.last_mouse_pos = QPoint()
        self.panning = False

        # Resize handle properties
        self.handle_size = 8
        self.resize_handle = None  # Which handle is being dragged
        self.moving_box = False    # Whether we're moving the entire box
        self.drag_start_pos = QPoint()
        self.drag_start_box = None  # Original box state when drag started

    def set_image(self, image_path):
        """Load and display an image"""
        try:
            self.original_pixmap = QPixmap(image_path)
            if self.original_pixmap.isNull():
                raise ValueError("Could not load image")

            self.scale_to_fit()
            self.bounding_boxes.clear()
            self.selected_box = None
            self.selected_boxes.clear()
            self.update()

            # Load existing annotations if they exist
            self.load_annotations(image_path)

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not load image: {str(e)}")

    def scale_to_fit(self):
        """Scale image to fit widget while maintaining aspect ratio"""
        if self.original_pixmap is None:
            return

        widget_size = self.size()
        pixmap_size = self.original_pixmap.size()

        scale_x = widget_size.width() / pixmap_size.width()
        scale_y = widget_size.height() / pixmap_size.height()
        self.scale_factor = min(scale_x, scale_y, 1.0)  # Don't scale up

        scaled_size = pixmap_size * self.scale_factor
        self.scaled_pixmap = self.original_pixmap.scaled(
            scaled_size, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        # Center the image
        self.offset = QPoint(
            (widget_size.width() - scaled_size.width()) // 2,
            (widget_size.height() - scaled_size.height()) // 2
        )

    def load_annotations(self, image_path):
        """Load YOLO format annotations from .txt file"""
        txt_path = str(Path(image_path).with_suffix('.txt'))
        if not os.path.exists(txt_path):
            return

        try:
            with open(txt_path, 'r') as f:
                lines = f.readlines()

            self.bounding_boxes.clear()
            img_width = self.original_pixmap.width()
            img_height = self.original_pixmap.height()

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

                    class_name = self.classes[class_idx] if class_idx < len(self.classes) else "object"
                    box = BoundingBox(x, y, w, h, class_idx, class_name)
                    self.bounding_boxes.append(box)

        except Exception as e:
            print(f"Error loading annotations: {e}")

    def save_annotations(self, image_path):
        """Save bounding boxes to YOLO format .txt file"""
        txt_path = str(Path(image_path).with_suffix('.txt'))

        try:
            with open(txt_path, 'w') as f:
                for box in self.bounding_boxes:
                    yolo_line = box.to_yolo_format(
                        self.original_pixmap.width(),
                        self.original_pixmap.height()
                    )
                    f.write(yolo_line + '\n')
            return True
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not save annotations: {str(e)}")
            return False

    def add_class(self, class_name, color=None):
        """Add a new class"""
        if class_name not in self.classes:
            self.classes.append(class_name)
            if color is None:
                # Generate a new color
                hue = (len(self.classes) - 1) * 137.5  # Golden angle
                color = QColor.fromHsv(int(hue) % 360, 255, 255)
            self.class_colors.append(color)

    def set_current_class(self, class_index):
        """Set the current class for new bounding boxes"""
        if 0 <= class_index < len(self.classes):
            self.current_class_index = class_index

    def select_all_boxes(self):
        """Select all bounding boxes in the current image"""
        self.selected_boxes = self.bounding_boxes.copy()
        if self.bounding_boxes:
            self.selected_box = self.bounding_boxes[0]  # Set primary selection
        self.update()

    def copy_boxes(self):
        """Copy selected boxes to clipboard"""
        if self.selected_boxes:
            self.clipboard_boxes = []
            for box in self.selected_boxes:
                # Create a copy of the box
                copied_box = BoundingBox(
                    box.x, box.y, box.width, box.height,
                    box.class_index, box.class_name
                )
                self.clipboard_boxes.append(copied_box)

    def cut_boxes(self):
        """Cut selected boxes to clipboard and remove them"""
        if self.selected_boxes:
            self.copy_boxes()
            for box in self.selected_boxes:
                if box in self.bounding_boxes:
                    self.bounding_boxes.remove(box)
            self.selected_boxes = []
            self.selected_box = None
            self.update()

    def paste_boxes(self):
        """Paste boxes from clipboard"""
        if self.clipboard_boxes:
            for box in self.clipboard_boxes:
                # Create a new box with slight offset to avoid overlap
                new_x = box.x + 10
                new_y = box.y + 10

                # Constrain to image bounds
                x, y, width, height = self.constrain_to_image_bounds(
                    new_x, new_y, box.width, box.height
                )

                new_box = BoundingBox(
                    x, y, width, height,
                    box.class_index, box.class_name
                )
                self.bounding_boxes.append(new_box)
            self.update()

    def generate_random_color(self):
        """Generate a random color with RGB values between 50 and 205"""
        r = random.randint(50, 205)
        g = random.randint(50, 205)
        b = random.randint(50, 205)
        return QColor(r, g, b)

    def switch_to_next_class(self):
        """Switch to the next class in the list"""
        if len(self.classes) > 1:
            self.current_class_index = (self.current_class_index + 1) % len(self.classes)

    def switch_to_previous_class(self):
        """Switch to the previous class in the list"""
        if len(self.classes) > 1:
            self.current_class_index = (self.current_class_index - 1) % len(self.classes)

    def constrain_to_image_bounds(self, x, y, width, height):
        """Constrain bounding box coordinates to stay within image bounds"""
        if self.original_pixmap is None:
            return x, y, width, height

        img_width = self.original_pixmap.width()
        img_height = self.original_pixmap.height()

        # Ensure minimum size
        width = max(10, width)
        height = max(10, height)

        # Constrain position and size to image bounds
        x = max(0, min(x, img_width - width))
        y = max(0, min(y, img_height - height))

        # Ensure the box doesn't exceed image boundaries
        if x + width > img_width:
            width = img_width - x
        if y + height > img_height:
            height = img_height - y

        return x, y, width, height

    def get_image_coordinates(self, widget_point):
        """Convert widget coordinates to image coordinates"""
        if self.scaled_pixmap is None:
            return QPoint()

        # Account for offset and scale
        img_point = widget_point - self.offset
        img_point = img_point / self.scale_factor
        return img_point

    def get_widget_coordinates(self, image_point):
        """Convert image coordinates to widget coordinates"""
        if self.scaled_pixmap is None:
            return QPoint()

        # Account for scale and offset
        widget_point = image_point * self.scale_factor + self.offset
        return widget_point

    def get_resize_handles(self, box):
        """Get resize handles for a bounding box in widget coordinates"""
        widget_point = self.get_widget_coordinates(QPoint(int(box.x), int(box.y)))
        widget_width = int(box.width * self.scale_factor)
        widget_height = int(box.height * self.scale_factor)

        handles = {}
        half_handle = self.handle_size // 2

        # Corner handles
        handles['top-left'] = QRect(widget_point.x() - half_handle, widget_point.y() - half_handle,
                                   self.handle_size, self.handle_size)
        handles['top-right'] = QRect(widget_point.x() + widget_width - half_handle, widget_point.y() - half_handle,
                                    self.handle_size, self.handle_size)
        handles['bottom-left'] = QRect(widget_point.x() - half_handle, widget_point.y() + widget_height - half_handle,
                                      self.handle_size, self.handle_size)
        handles['bottom-right'] = QRect(widget_point.x() + widget_width - half_handle, widget_point.y() + widget_height - half_handle,
                                       self.handle_size, self.handle_size)

        # Edge handles
        handles['top'] = QRect(widget_point.x() + widget_width // 2 - half_handle, widget_point.y() - half_handle,
                              self.handle_size, self.handle_size)
        handles['bottom'] = QRect(widget_point.x() + widget_width // 2 - half_handle, widget_point.y() + widget_height - half_handle,
                                 self.handle_size, self.handle_size)
        handles['left'] = QRect(widget_point.x() - half_handle, widget_point.y() + widget_height // 2 - half_handle,
                               self.handle_size, self.handle_size)
        handles['right'] = QRect(widget_point.x() + widget_width - half_handle, widget_point.y() + widget_height // 2 - half_handle,
                                self.handle_size, self.handle_size)

        return handles

    def get_handle_at_point(self, point, box):
        """Get which resize handle (if any) is at the given point"""
        handles = self.get_resize_handles(box)
        for handle_name, handle_rect in handles.items():
            if handle_rect.contains(point):
                return handle_name
        return None

    def get_cursor_for_handle(self, handle_name):
        """Get the appropriate cursor for a resize handle"""
        cursor_map = {
            'top-left': Qt.CursorShape.SizeFDiagCursor,
            'top-right': Qt.CursorShape.SizeBDiagCursor,
            'bottom-left': Qt.CursorShape.SizeBDiagCursor,
            'bottom-right': Qt.CursorShape.SizeFDiagCursor,
            'top': Qt.CursorShape.SizeVerCursor,
            'bottom': Qt.CursorShape.SizeVerCursor,
            'left': Qt.CursorShape.SizeHorCursor,
            'right': Qt.CursorShape.SizeHorCursor,
        }
        return cursor_map.get(handle_name, Qt.CursorShape.ArrowCursor)

    def paintEvent(self, event):
        """Paint the image and bounding boxes"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Fill background
        painter.fillRect(self.rect(), QColor(50, 50, 50))

        # Draw image
        if self.scaled_pixmap:
            painter.drawPixmap(self.offset, self.scaled_pixmap)

            # Draw bounding boxes
            for i, box in enumerate(self.bounding_boxes):
                # Convert image coordinates to widget coordinates
                widget_point = self.get_widget_coordinates(QPoint(int(box.x), int(box.y)))
                widget_rect = QRect(
                    int(widget_point.x()), int(widget_point.y()),
                    int(box.width * self.scale_factor), int(box.height * self.scale_factor)
                )

                # Set color based on class
                color = self.class_colors[box.class_index] if box.class_index < len(self.class_colors) else QColor(255, 0, 0)

                # Draw box
                pen = QPen(color, 2)
                if box == self.selected_box or box in self.selected_boxes:
                    pen.setWidth(3)
                    pen.setStyle(Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.drawRect(widget_rect)

                # Draw class label
                painter.setPen(QPen(QColor(255, 255, 255), 1))
                painter.drawText(widget_rect.topLeft() + QPoint(5, 15), box.class_name)

                # Draw resize handles for selected box
                if box == self.selected_box:
                    handles = self.get_resize_handles(box)
                    painter.setPen(QPen(QColor(255, 255, 255), 2))
                    painter.setBrush(QBrush(QColor(255, 255, 255)))
                    for handle_rect in handles.values():
                        painter.drawRect(handle_rect)

            # Draw current box being drawn
            if self.drawing and self.current_box:
                widget_point = self.get_widget_coordinates(QPoint(int(self.current_box.x), int(self.current_box.y)))
                widget_rect = QRect(
                    int(widget_point.x()), int(widget_point.y()),
                    int(self.current_box.width * self.scale_factor),
                    int(self.current_box.height * self.scale_factor)
                )
                color = self.class_colors[self.current_class_index]
                pen = QPen(color, 2, Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.drawRect(widget_rect)

    def mousePressEvent(self, event):
        """Handle mouse press events"""
        if event.button() == Qt.MouseButton.LeftButton:
            img_point = self.get_image_coordinates(event.pos())

            # Check if clicking on resize handle first
            if self.selected_box:
                handle = self.get_handle_at_point(event.pos(), self.selected_box)
                if handle:
                    self.resize_handle = handle
                    self.drag_start_pos = event.pos()
                    self.drag_start_box = BoundingBox(
                        self.selected_box.x, self.selected_box.y,
                        self.selected_box.width, self.selected_box.height,
                        self.selected_box.class_index, self.selected_box.class_name
                    )
                    return

            # Check if clicking on existing bounding box
            clicked_box = None
            for box in reversed(self.bounding_boxes):  # Check from top to bottom
                if box.contains_point(img_point):
                    clicked_box = box
                    break

            if clicked_box:
                # Select existing box and prepare for moving
                self.selected_box = clicked_box
                self.moving_box = True
                self.drag_start_pos = event.pos()
                self.drag_start_box = BoundingBox(
                    clicked_box.x, clicked_box.y,
                    clicked_box.width, clicked_box.height,
                    clicked_box.class_index, clicked_box.class_name
                )
                self.bounding_box_selected.emit(clicked_box)
            else:
                # Start drawing new box
                self.drawing = True
                self.start_point = img_point
                self.current_box = BoundingBox(
                    img_point.x(), img_point.y(), 0, 0,
                    self.current_class_index,
                    self.classes[self.current_class_index]
                )
                self.selected_box = None

        elif event.button() == Qt.MouseButton.RightButton:
            # Pan mode
            self.panning = True
            self.last_mouse_pos = event.pos()

        self.update()

    def mouseMoveEvent(self, event):
        """Handle mouse move events"""
        if self.drawing and self.current_box:
            # Update current box
            img_point = self.get_image_coordinates(event.pos())
            self.current_box.width = img_point.x() - self.start_point.x()
            self.current_box.height = img_point.y() - self.start_point.y()
            self.update()

        elif self.resize_handle and self.selected_box and self.drag_start_box:
            # Resize the selected box
            self.resize_box(event.pos())
            self.update()

        elif self.moving_box and self.selected_box and self.drag_start_box:
            # Move the selected box
            self.move_box(event.pos())
            self.update()

        elif self.panning:
            # Pan the image
            delta = event.pos() - self.last_mouse_pos
            self.offset += delta
            self.last_mouse_pos = event.pos()
            self.update()
        else:
            # Update cursor based on what's under the mouse
            self.update_cursor(event.pos())

    def mouseReleaseEvent(self, event):
        """Handle mouse release events"""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.drawing:
                # Finish drawing box
                if self.current_box and abs(self.current_box.width) > 5 and abs(self.current_box.height) > 5:
                    # Ensure positive width and height
                    if self.current_box.width < 0:
                        self.current_box.x += self.current_box.width
                        self.current_box.width = abs(self.current_box.width)
                    if self.current_box.height < 0:
                        self.current_box.y += self.current_box.height
                        self.current_box.height = abs(self.current_box.height)

                    # Constrain to image bounds
                    x, y, width, height = self.constrain_to_image_bounds(
                        self.current_box.x, self.current_box.y,
                        self.current_box.width, self.current_box.height
                    )
                    self.current_box.x = x
                    self.current_box.y = y
                    self.current_box.width = width
                    self.current_box.height = height

                    self.bounding_boxes.append(self.current_box)
                    self.bounding_box_created.emit(self.current_box)
                    self.selected_box = self.current_box

                self.drawing = False
                self.current_box = None

            elif self.resize_handle:
                # Finish resizing
                self.resize_handle = None
                self.drag_start_box = None

            elif self.moving_box:
                # Finish moving
                self.moving_box = False
                self.drag_start_box = None

            self.update()

        elif event.button() == Qt.MouseButton.RightButton:
            self.panning = False

    def mouseDoubleClickEvent(self, event):
        """Handle mouse double-click events"""
        if event.button() == Qt.MouseButton.LeftButton:
            img_point = self.get_image_coordinates(event.pos())

            # Find the bounding box that was double-clicked
            clicked_box = None
            for box in reversed(self.bounding_boxes):  # Check from top to bottom
                if box.contains_point(img_point):
                    clicked_box = box
                    break

            if clicked_box:
                # Emit signal to open class selection dialog
                self.bounding_box_class_edit_requested.emit(clicked_box)

    def wheelEvent(self, event):
        """Handle mouse wheel for zooming"""
        if self.scaled_pixmap is None:
            return

        # Get mouse position relative to image
        mouse_pos = event.position().toPoint()
        img_point = self.get_image_coordinates(mouse_pos)

        # Zoom factor
        zoom_factor = 1.1 if event.angleDelta().y() > 0 else 1/1.1
        new_scale = self.scale_factor * zoom_factor

        # Limit zoom range
        new_scale = max(0.1, min(5.0, new_scale))

        if new_scale != self.scale_factor:
            # Calculate new offset to zoom towards mouse position
            new_pixmap_size = self.original_pixmap.size() * new_scale
            new_offset = mouse_pos - img_point * new_scale

            self.scale_factor = new_scale
            self.scaled_pixmap = self.original_pixmap.scaled(
                new_pixmap_size, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.offset = new_offset
            self.update()

    def keyPressEvent(self, event):
        """Handle keyboard events"""
        if event.key() == Qt.Key.Key_Escape:
            # Cancel current operation
            self.drawing = False
            self.current_box = None
            self.selected_box = None
            self.update()
        else:
            super().keyPressEvent(event)

    def resize_box(self, current_pos):
        """Resize the selected box based on the current mouse position"""
        if not self.selected_box or not self.drag_start_box:
            return

        # Calculate the delta in image coordinates
        start_img_pos = self.get_image_coordinates(self.drag_start_pos)
        current_img_pos = self.get_image_coordinates(current_pos)
        delta_x = current_img_pos.x() - start_img_pos.x()
        delta_y = current_img_pos.y() - start_img_pos.y()

        # Apply resize based on which handle is being dragged
        handle = self.resize_handle

        if 'left' in handle:
            self.selected_box.x = self.drag_start_box.x + delta_x
            self.selected_box.width = self.drag_start_box.width - delta_x
        if 'right' in handle:
            self.selected_box.width = self.drag_start_box.width + delta_x
        if 'top' in handle:
            self.selected_box.y = self.drag_start_box.y + delta_y
            self.selected_box.height = self.drag_start_box.height - delta_y
        if 'bottom' in handle:
            self.selected_box.height = self.drag_start_box.height + delta_y

        # Constrain to image bounds
        x, y, width, height = self.constrain_to_image_bounds(
            self.selected_box.x, self.selected_box.y,
            self.selected_box.width, self.selected_box.height
        )
        self.selected_box.x = x
        self.selected_box.y = y
        self.selected_box.width = width
        self.selected_box.height = height

    def move_box(self, current_pos):
        """Move the selected box based on the current mouse position"""
        if not self.selected_box or not self.drag_start_box:
            return

        # Calculate the delta in image coordinates
        start_img_pos = self.get_image_coordinates(self.drag_start_pos)
        current_img_pos = self.get_image_coordinates(current_pos)
        delta_x = current_img_pos.x() - start_img_pos.x()
        delta_y = current_img_pos.y() - start_img_pos.y()

        # Apply the delta to the original position
        new_x = self.drag_start_box.x + delta_x
        new_y = self.drag_start_box.y + delta_y

        # Constrain to image bounds
        x, y, width, height = self.constrain_to_image_bounds(
            new_x, new_y, self.selected_box.width, self.selected_box.height
        )
        self.selected_box.x = x
        self.selected_box.y = y

    def update_cursor(self, pos):
        """Update cursor based on what's under the mouse"""
        if self.selected_box:
            handle = self.get_handle_at_point(pos, self.selected_box)
            if handle:
                cursor = self.get_cursor_for_handle(handle)
                self.setCursor(cursor)
                return

        # Default cursor
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def resizeEvent(self, event):
        """Handle widget resize"""
        if self.original_pixmap:
            self.scale_to_fit()
        super().resizeEvent(event)


class ClassManagerDialog(QDialog):
    """Dialog for managing classes"""

    def __init__(self, classes, colors, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Classes")
        self.setModal(True)
        self.resize(400, 300)

        self.classes = classes.copy()
        self.colors = colors.copy()

        layout = QVBoxLayout()

        # Class list
        self.class_list = QListWidget()
        for i, (class_name, color) in enumerate(zip(self.classes, self.colors)):
            item = QListWidgetItem(class_name)
            item.setBackground(color)
            self.class_list.addItem(item)

        layout.addWidget(QLabel("Classes:"))
        layout.addWidget(self.class_list)

        # Buttons
        button_layout = QHBoxLayout()

        self.add_button = QPushButton("Add Class")
        self.add_button.clicked.connect(self.add_class)

        self.edit_button = QPushButton("Edit Class")
        self.edit_button.clicked.connect(self.edit_class)

        self.delete_button = QPushButton("Delete Class")
        self.delete_button.clicked.connect(self.delete_class)

        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.edit_button)
        button_layout.addWidget(self.delete_button)

        layout.addLayout(button_layout)

        # Dialog buttons
        dialog_buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        dialog_buttons.accepted.connect(self.accept)
        dialog_buttons.rejected.connect(self.reject)
        layout.addWidget(dialog_buttons)

        self.setLayout(layout)

    def add_class(self):
        """Add a new class"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Class")
        layout = QFormLayout()

        name_edit = QLineEdit()
        color_button = QPushButton("Choose Color")
        color = QColor(255, 0, 0)

        def choose_color():
            nonlocal color
            color = QColorDialog.getColor(color, self)
            if color.isValid():
                color_button.setStyleSheet(f"background-color: {color.name()}")

        color_button.clicked.connect(choose_color)
        color_button.setStyleSheet(f"background-color: {color.name()}")

        layout.addRow("Class Name:", name_edit)
        layout.addRow("Color:", color_button)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        dialog.setLayout(layout)

        if dialog.exec() == QDialog.DialogCode.Accepted and name_edit.text().strip():
            class_name = name_edit.text().strip()
            if class_name not in self.classes:
                self.classes.append(class_name)
                self.colors.append(color)

                item = QListWidgetItem(class_name)
                item.setBackground(color)
                self.class_list.addItem(item)

    def edit_class(self):
        """Edit selected class"""
        current_item = self.class_list.currentItem()
        if not current_item:
            return

        current_row = self.class_list.currentRow()
        old_name = self.classes[current_row]

        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Class")
        layout = QFormLayout()

        name_edit = QLineEdit(old_name)
        color_button = QPushButton("Choose Color")
        color = self.colors[current_row]

        def choose_color():
            nonlocal color
            color = QColorDialog.getColor(color, self)
            if color.isValid():
                color_button.setStyleSheet(f"background-color: {color.name()}")

        color_button.clicked.connect(choose_color)
        color_button.setStyleSheet(f"background-color: {color.name()}")

        layout.addRow("Class Name:", name_edit)
        layout.addRow("Color:", color_button)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        dialog.setLayout(layout)

        if dialog.exec() == QDialog.DialogCode.Accepted and name_edit.text().strip():
            new_name = name_edit.text().strip()
            if new_name != old_name and new_name not in self.classes:
                self.classes[current_row] = new_name
                self.colors[current_row] = color

                current_item.setText(new_name)
                current_item.setBackground(color)

    def delete_class(self):
        """Delete selected class"""
        current_row = self.class_list.currentRow()
        if current_row >= 0 and len(self.classes) > 1:  # Keep at least one class
            self.classes.pop(current_row)
            self.colors.pop(current_row)
            self.class_list.takeItem(current_row)


class QuickAddClassDialog(QDialog):
    """Quick dialog for adding a new class with keyboard shortcut"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Class")
        self.setModal(True)
        self.resize(300, 150)

        layout = QFormLayout()

        # Class name input
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter class name...")
        layout.addRow("Class Name:", self.name_edit)

        # Color button
        self.color_button = QPushButton("Choose Color")
        self.color = self.generate_random_color()
        self.color_button.setStyleSheet(f"background-color: {self.color.name()}")
        self.color_button.clicked.connect(self.choose_color)
        layout.addRow("Color:", self.color_button)

        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

        # Focus on name input and select all text
        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def generate_random_color(self):
        """Generate a random color with RGB values between 50 and 205"""
        r = random.randint(50, 205)
        g = random.randint(50, 205)
        b = random.randint(50, 205)
        return QColor(r, g, b)

    def choose_color(self):
        """Open color dialog to choose color"""
        color = QColorDialog.getColor(self.color, self)
        if color.isValid():
            self.color = color
            self.color_button.setStyleSheet(f"background-color: {color.name()}")

    def get_class_name(self):
        """Get the entered class name"""
        return self.name_edit.text().strip()

    def get_color(self):
        """Get the selected color"""
        return self.color


class ClassSelectionDialog(QDialog):
    """Dialog for selecting a class for a bounding box"""

    def __init__(self, classes, colors, current_class_index, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Class")
        self.setModal(True)
        self.resize(300, 120)

        self.classes = classes
        self.colors = colors
        self.selected_index = current_class_index


        layout = QVBoxLayout()

        # Class selection dropdown
        self.class_combo = QComboBox()
        for i, (class_name, color) in enumerate(zip(self.classes, self.colors)):
            self.class_combo.addItem(class_name)
            # Set item color (this is a simplified approach)
            self.class_combo.setItemData(i, color, Qt.ItemDataRole.BackgroundRole)

        self.class_combo.setCurrentIndex(current_class_index)
        layout.addWidget(QLabel("Select Class:"))
        layout.addWidget(self.class_combo)

        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

        # Focus on combo box and make it ready for keyboard navigation
        self.class_combo.setFocus()
        self.class_combo.showPopup()

    def keyPressEvent(self, event):
        """Handle keyboard events for arrow navigation"""
        if event.key() == Qt.Key.Key_Up:
            # Move to previous class
            current_index = self.class_combo.currentIndex()
            new_index = (current_index - 1) % len(self.classes)
            self.class_combo.setCurrentIndex(new_index)
        elif event.key() == Qt.Key.Key_Down:
            # Move to next class
            current_index = self.class_combo.currentIndex()
            new_index = (current_index + 1) % len(self.classes)
            self.class_combo.setCurrentIndex(new_index)
        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            # Accept selection
            self.accept()
        else:
            super().keyPressEvent(event)

    def get_selected_class_index(self):
        """Get the selected class index"""
        return self.class_combo.currentIndex()


class ImageTaggerMainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Tagger - YOLO Format")
        self.setGeometry(100, 100, 1200, 800)

        # Application state
        self.current_image_path = None
        self.image_files = []
        self.current_image_index = -1
        self.current_directory = None
        self.label_mapping_file = None

        # Create UI
        self.create_menu_bar()
        self.create_central_widget()  # Create canvas first
        self.create_toolbar()
        self.create_status_bar()

        # Connect signals
        self.setup_connections()

        # Load settings
        self.load_settings()

    def create_menu_bar(self):
        """Create the menu bar"""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        open_dir_action = QAction("&Open Directory", self)
        open_dir_action.setShortcut(QKeySequence.StandardKey.Open)
        open_dir_action.triggered.connect(self.open_directory)
        file_menu.addAction(open_dir_action)

        file_menu.addSeparator()

        save_action = QAction("&Save Annotations", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.save_annotations)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("&Edit")

        manage_classes_action = QAction("&Manage Classes", self)
        manage_classes_action.triggered.connect(self.manage_classes)
        edit_menu.addAction(manage_classes_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        fit_to_window_action = QAction("&Fit to Window", self)
        fit_to_window_action.triggered.connect(self.fit_to_window)
        view_menu.addAction(fit_to_window_action)

    def create_toolbar(self):
        """Create the toolbar"""
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)

        # Directory selection
        self.open_dir_button = QPushButton("Open Directory")
        self.open_dir_button.clicked.connect(self.open_directory)
        toolbar.addWidget(self.open_dir_button)

        toolbar.addSeparator()

        # Navigation
        self.prev_button = QPushButton("◀ Previous")
        self.prev_button.clicked.connect(self.previous_image)
        self.prev_button.setEnabled(False)
        toolbar.addWidget(self.prev_button)

        self.next_button = QPushButton("Next ▶")
        self.next_button.clicked.connect(self.next_image)
        self.next_button.setEnabled(False)
        toolbar.addWidget(self.next_button)

        toolbar.addSeparator()

        # Class selection
        toolbar.addWidget(QLabel("Class:"))
        self.class_combo = QComboBox()
        # Initialize with canvas classes to ensure synchronization
        for class_name in self.canvas.classes:
            self.class_combo.addItem(class_name)
        self.class_combo.currentIndexChanged.connect(self.on_class_changed)
        toolbar.addWidget(self.class_combo)

        # Manage classes button
        self.manage_classes_button = QPushButton("Manage Classes")
        self.manage_classes_button.clicked.connect(self.manage_classes)
        toolbar.addWidget(self.manage_classes_button)

        toolbar.addSeparator()

        # Save button
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_annotations)
        self.save_button.setEnabled(False)
        toolbar.addWidget(self.save_button)

    def create_central_widget(self):
        """Create the central widget"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QHBoxLayout()

        # Image canvas
        self.canvas = ImageCanvas()
        layout.addWidget(self.canvas, 1)

        # Image list (optional sidebar)
        self.image_list = QListWidget()
        self.image_list.setMaximumWidth(200)
        self.image_list.itemClicked.connect(self.on_image_selected)
        layout.addWidget(self.image_list)

        central_widget.setLayout(layout)

    def create_status_bar(self):
        """Create the status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready - Open a directory to start")

    def setup_connections(self):
        """Setup signal connections"""
        self.canvas.bounding_box_created.connect(self.on_bounding_box_created)
        self.canvas.bounding_box_selected.connect(self.on_bounding_box_selected)
        self.canvas.bounding_box_deleted.connect(self.on_bounding_box_deleted)
        self.canvas.bounding_box_class_edit_requested.connect(self.on_bounding_box_class_edit_requested)

    def load_settings(self):
        """Load application settings"""
        # This could be expanded to load from a config file
        pass

    def save_settings(self):
        """Save application settings"""
        # This could be expanded to save to a config file
        pass

    def load_label_mapping(self):
        """Load label mapping from label-mapping.txt file"""
        if not self.label_mapping_file or not self.label_mapping_file.exists():
            # Create default label mapping file
            self.create_default_label_mapping()
            return

        try:
            with open(self.label_mapping_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Parse labels from file
            labels = []
            for line in lines:
                label = line.strip()
                if label:  # Skip empty lines
                    labels.append(label)

            if labels:
                # Update canvas classes
                self.canvas.classes = labels
                # Generate colors for each class
                self.canvas.class_colors = []
                for i in range(len(labels)):
                    hue = i * 137.5  # Golden angle for good color distribution
                    color = QColor.fromHsv(int(hue) % 360, 255, 255)
                    self.canvas.class_colors.append(color)

                # Update class combo box
                self.class_combo.clear()
                for label in labels:
                    self.class_combo.addItem(label)

                # Reset current class index
                self.canvas.current_class_index = 0
                self.class_combo.setCurrentIndex(0)
            else:
                # Empty file, create default
                self.create_default_label_mapping()

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not load label mapping: {str(e)}")
            self.create_default_label_mapping()

    def create_default_label_mapping(self):
        """Create default label-mapping.txt file"""
        if not self.label_mapping_file:
            return

        try:
            # Create default classes
            default_classes = ["object"]
            self.canvas.classes = default_classes
            self.canvas.class_colors = [QColor(255, 0, 0)]  # Default red color


            # Update class combo box
            self.class_combo.clear()
            self.class_combo.addItem("object")
            self.canvas.current_class_index = 0
            self.class_combo.setCurrentIndex(0)

            # Save to file
            self.save_label_mapping()

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not create label mapping: {str(e)}")

    def save_label_mapping(self):
        """Save current classes to label-mapping.txt file"""
        if not self.label_mapping_file:
            return

        try:
            with open(self.label_mapping_file, 'w', encoding='utf-8') as f:
                for label in self.canvas.classes:
                    f.write(f"{label}\n")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not save label mapping: {str(e)}")

    def open_directory(self):
        """Open a directory containing images"""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Image Directory", "",
            QFileDialog.Option.ShowDirsOnly
        )

        if directory:
            self.load_directory(directory)

    def load_directory(self, directory):
        """Load all images from directory"""
        self.current_directory = directory
        self.label_mapping_file = Path(directory) / "label-mapping.txt"

        # Load label mapping first
        self.load_label_mapping()

        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}
        self.image_files = []

        for file_path in Path(directory).iterdir():
            if file_path.suffix.lower() in image_extensions:
                self.image_files.append(str(file_path))

        self.image_files.sort()

        if self.image_files:
            self.current_image_index = 0
            self.load_image(self.image_files[0])
            self.update_navigation_buttons()
            self.update_image_list()
            self.status_bar.showMessage(f"Loaded {len(self.image_files)} images")
        else:
            QMessageBox.information(self, "No Images", "No image files found in the selected directory.")

    def load_image(self, image_path):
        """Load and display an image"""
        self.current_image_path = image_path
        self.canvas.set_image(image_path)
        self.update_status_bar()
        self.save_button.setEnabled(True)

    def update_image_list(self):
        """Update the image list sidebar"""
        self.image_list.clear()
        for i, image_path in enumerate(self.image_files):
            filename = Path(image_path).name
            item = QListWidgetItem(filename)
            if i == self.current_image_index:
                item.setBackground(QColor(100, 150, 255))
            self.image_list.addItem(item)

    def update_navigation_buttons(self):
        """Update navigation button states"""
        self.prev_button.setEnabled(self.current_image_index > 0)
        self.next_button.setEnabled(self.current_image_index < len(self.image_files) - 1)

    def update_status_bar(self):
        """Update status bar with current image info"""
        if self.current_image_path:
            filename = Path(self.current_image_path).name
            box_count = len(self.canvas.bounding_boxes)
            selected_count = len(self.canvas.selected_boxes)
            selected_info = ""
            if selected_count > 0:
                if selected_count == 1 and self.canvas.selected_box:
                    selected_info = f" - Selected: {self.canvas.selected_box.class_name} (Press Delete/Backspace to remove)"
                else:
                    selected_info = f" - {selected_count} boxes selected"
            self.status_bar.showMessage(
                f"Image {self.current_image_index + 1}/{len(self.image_files)}: {filename} - {box_count} bounding boxes{selected_info}"
            )

    def previous_image(self):
        """Go to previous image"""
        if self.current_image_index > 0:
            self.save_current_annotations()
            self.current_image_index -= 1
            self.load_image(self.image_files[self.current_image_index])
            self.update_navigation_buttons()
            self.update_image_list()

    def next_image(self):
        """Go to next image"""
        if self.current_image_index < len(self.image_files) - 1:
            self.save_current_annotations()
            self.current_image_index += 1
            self.load_image(self.image_files[self.current_image_index])
            self.update_navigation_buttons()
            self.update_image_list()

    def on_image_selected(self, item):
        """Handle image selection from list"""
        row = self.image_list.row(item)
        if row != self.current_image_index:
            self.save_current_annotations()
            self.current_image_index = row
            self.load_image(self.image_files[self.current_image_index])
            self.update_navigation_buttons()
            self.update_image_list()

    def on_class_changed(self, index):
        """Handle class selection change"""
        self.canvas.set_current_class(index)

    def manage_classes(self):
        """Open class management dialog"""
        dialog = ClassManagerDialog(self.canvas.classes, self.canvas.class_colors, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.canvas.classes = dialog.classes
            self.canvas.class_colors = dialog.colors

            # Update class combo box
            self.class_combo.clear()
            for class_name in self.canvas.classes:
                self.class_combo.addItem(class_name)

            # Update existing bounding boxes with new class info
            for box in self.canvas.bounding_boxes:
                if box.class_index >= len(self.canvas.classes):
                    box.class_index = 0
                    box.class_name = self.canvas.classes[0]
                else:
                    box.class_name = self.canvas.classes[box.class_index]

            # Save label mapping to file
            self.save_label_mapping()
            self.canvas.update()

    def fit_to_window(self):
        """Fit image to window"""
        self.canvas.scale_to_fit()
        self.canvas.update()

    def save_annotations(self):
        """Save current annotations"""
        if self.current_image_path:
            if self.canvas.save_annotations(self.current_image_path):
                self.status_bar.showMessage("Annotations saved successfully")
            else:
                self.status_bar.showMessage("Failed to save annotations")

    def save_current_annotations(self):
        """Save annotations for current image before switching"""
        if self.current_image_path:
            self.canvas.save_annotations(self.current_image_path)

    def on_bounding_box_created(self, box):
        """Handle new bounding box creation"""
        self.update_status_bar()

    def on_bounding_box_selected(self, box):
        """Handle bounding box selection"""
        # Update class combo to match selected box
        if box.class_index < len(self.canvas.classes):
            self.class_combo.setCurrentIndex(box.class_index)

        # Update status bar to show selection
        self.update_status_bar()

    def on_bounding_box_deleted(self, box):
        """Handle bounding box deletion"""
        self.update_status_bar()

    def quick_add_class(self):
        """Open quick add class dialog"""
        dialog = QuickAddClassDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            class_name = dialog.get_class_name()
            if class_name and class_name not in self.canvas.classes:
                color = dialog.get_color()
                self.canvas.add_class(class_name, color)

                # Update class combo box
                self.class_combo.addItem(class_name)

                # Set the new class as current
                new_index = len(self.canvas.classes) - 1
                self.class_combo.setCurrentIndex(new_index)
                self.canvas.set_current_class(new_index)

                # Save label mapping to file
                self.save_label_mapping()

    def select_all_boxes(self):
        """Select all bounding boxes in current image"""
        self.canvas.select_all_boxes()
        self.update_status_bar()

    def copy_boxes(self):
        """Copy selected boxes to clipboard"""
        self.canvas.copy_boxes()

    def cut_boxes(self):
        """Cut selected boxes to clipboard"""
        self.canvas.cut_boxes()
        self.update_status_bar()

    def paste_boxes(self):
        """Paste boxes from clipboard"""
        self.canvas.paste_boxes()
        self.update_status_bar()

    def switch_to_next_class(self):
        """Switch to next class"""
        self.canvas.switch_to_next_class()
        self.class_combo.setCurrentIndex(self.canvas.current_class_index)

    def switch_to_previous_class(self):
        """Switch to previous class"""
        self.canvas.switch_to_previous_class()
        self.class_combo.setCurrentIndex(self.canvas.current_class_index)

    def on_bounding_box_class_edit_requested(self, box):
        """Handle request to edit bounding box class"""
        # Ensure we have classes available
        if not self.canvas.classes:
            self.canvas.classes = ["object"]
            self.canvas.class_colors = [QColor(255, 0, 0)]

        dialog = ClassSelectionDialog(
            self.canvas.classes,
            self.canvas.class_colors,
            box.class_index,
            self
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_class_index = dialog.get_selected_class_index()
            if new_class_index != box.class_index:
                # Update the bounding box class
                box.class_index = new_class_index
                box.class_name = self.canvas.classes[new_class_index]

                # Update the canvas
                self.canvas.update()
                self.update_status_bar()

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        modifiers = event.modifiers()

        # Handle Cmd/Ctrl combinations
        if modifiers & Qt.KeyboardModifier.ControlModifier or modifiers & Qt.KeyboardModifier.MetaModifier:
            if event.key() == Qt.Key.Key_A:
                # Cmd+A - Select all tags
                self.select_all_boxes()
            elif event.key() == Qt.Key.Key_C:
                # Cmd+C - Copy all tags
                self.copy_boxes()
            elif event.key() == Qt.Key.Key_V:
                # Cmd+V - Paste all tags
                self.paste_boxes()
            elif event.key() == Qt.Key.Key_X:
                # Cmd+X - Cut all tags
                self.cut_boxes()
            elif event.key() == Qt.Key.Key_N:
                # Cmd+N - New tag
                self.quick_add_class()
            elif event.key() == Qt.Key.Key_Up:
                # Cmd+Up - Move to previous class
                self.switch_to_previous_class()
            elif event.key() == Qt.Key.Key_Down:
                # Cmd+Down - Move to next class
                self.switch_to_next_class()
            elif event.key() == Qt.Key.Key_Left:
                # Cmd+Left - Move to previous image
                self.previous_image()
            elif event.key() == Qt.Key.Key_Right:
                # Cmd+Right - Move to next image
                self.next_image()
            else:
                super().keyPressEvent(event)
        # Handle Tab combinations
        elif event.key() == Qt.Key.Key_Tab:
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                # Shift+Tab - Switch to previous class
                self.switch_to_previous_class()
            else:
                # Tab - Switch to next class
                self.switch_to_next_class()
        # Handle other keys
        elif event.key() == Qt.Key.Key_Space:
            self.next_image()
        elif event.key() == Qt.Key.Key_Backspace:
            # Check if a bounding box is selected first
            if self.canvas.selected_box:
                # Delete the selected bounding box
                if self.canvas.selected_box in self.canvas.bounding_boxes:
                    self.canvas.bounding_boxes.remove(self.canvas.selected_box)
                    self.canvas.bounding_box_deleted.emit(self.canvas.selected_box)
                    self.canvas.selected_box = None
                    self.canvas.update()
            else:
                # No box selected, go to previous image
                self.previous_image()
        elif event.key() == Qt.Key.Key_Delete:
            # Delete selected bounding box
            if self.canvas.selected_box:
                if self.canvas.selected_box in self.canvas.bounding_boxes:
                    self.canvas.bounding_boxes.remove(self.canvas.selected_box)
                    self.canvas.bounding_box_deleted.emit(self.canvas.selected_box)
                    self.canvas.selected_box = None
                    self.canvas.update()
        elif event.key() == Qt.Key.Key_F:
            self.fit_to_window()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        """Handle application close"""
        self.save_current_annotations()
        self.save_settings()
        event.accept()


def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    app.setApplicationName("Image Tagger")
    app.setApplicationVersion("1.0")

    window = ImageTaggerMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
