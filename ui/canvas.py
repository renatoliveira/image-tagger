"""Image display and annotation canvas"""

import random
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QPoint, QRect, pyqtSignal
from PyQt6.QtGui import QPixmap, QPainter, QPen, QBrush, QColor
from core.annotations import BoundingBox
from core.yolo_format import load_yolo_annotations, save_yolo_annotations


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
            from core.image_loader import load_pixmap
            self.original_pixmap = load_pixmap(image_path)
            self.scale_to_fit()
            self.bounding_boxes.clear()
            self.selected_box = None
            self.selected_boxes.clear()
            self.update()

            # Load existing annotations if they exist
            self.load_annotations(image_path)

        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
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
        if self.original_pixmap is None:
            return

        img_width = self.original_pixmap.width()
        img_height = self.original_pixmap.height()

        self.bounding_boxes = load_yolo_annotations(image_path, self.classes)

        # Update image dimensions for loaded boxes
        for box in self.bounding_boxes:
            # Convert from normalized coordinates back to pixel coordinates
            x_center = box.x + box.width / 2
            y_center = box.y + box.height / 2
            norm_width = box.width
            norm_height = box.height

            # Convert to pixel coordinates
            box.x = (x_center - norm_width / 2) * img_width
            box.y = (y_center - norm_height / 2) * img_height
            box.width = norm_width * img_width
            box.height = norm_height * img_height

    def save_annotations(self, image_path):
        """Save bounding boxes to YOLO format .txt file"""
        if self.original_pixmap is None:
            return False

        return save_yolo_annotations(
            self.bounding_boxes,
            image_path,
            self.original_pixmap.width(),
            self.original_pixmap.height()
        )

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
                    # Reset brush to transparent to avoid affecting other drawings
                    painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))

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
