"""Main application window"""

from pathlib import Path
from PyQt6.QtWidgets import (QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
                             QPushButton, QLabel, QFileDialog, QComboBox,
                             QStatusBar, QMessageBox, QMenuBar, QMenu,
                             QToolBar, QListWidget, QListWidgetItem, QDialog)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence, QColor
from core.image_loader import load_image_files
from core.yolo_format import load_label_mapping, save_label_mapping
from .canvas import ImageCanvas
from .dialogs import ClassManagerDialog, QuickAddClassDialog, ClassSelectionDialog


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

        # Ensure canvas gets focus for keyboard events
        self.canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

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
        # Disable keyboard navigation for the list widget to prevent focus issues
        self.image_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
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

        # Store original mouse press event and override it
        self.original_canvas_mouse_press = self.canvas.mousePressEvent
        self.canvas.mousePressEvent = self.canvas_mouse_press_event

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
            labels = load_label_mapping(self.label_mapping_file)

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

        save_label_mapping(self.canvas.classes, self.label_mapping_file)

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

        self.image_files = load_image_files(directory)

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

        # If a bounding box is selected, update its class too
        if self.canvas.selected_box:
            self.canvas.selected_box.class_index = index
            self.canvas.selected_box.class_name = self.canvas.classes[index]
            self.canvas.update()
            self.update_status_bar()

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

        # Handle single letter keys first (before list widget captures them)
        if not modifiers:  # No modifier keys pressed
            if event.key() == Qt.Key.Key_W:
                # W - Switch to previous class
                self.switch_to_previous_class()
                # Deselect any selected bounding box
                if self.canvas.selected_box:
                    self.canvas.selected_box = None
                    self.canvas.selected_boxes = []
                    self.canvas.update()
                    self.update_status_bar()
                event.accept()
                return
            elif event.key() == Qt.Key.Key_S:
                # S - Switch to next class
                self.switch_to_next_class()
                # Deselect any selected bounding box
                if self.canvas.selected_box:
                    self.canvas.selected_box = None
                    self.canvas.selected_boxes = []
                    self.canvas.update()
                    self.update_status_bar()
                event.accept()
                return
            elif event.key() == Qt.Key.Key_A:
                # A - Previous image
                self.previous_image()
                event.accept()
                return
            elif event.key() == Qt.Key.Key_D:
                # D - Next image
                self.next_image()
                event.accept()
                return

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

    def canvas_mouse_press_event(self, event):
        """Handle canvas mouse press and ensure focus"""
        # Ensure canvas has focus for keyboard events
        self.canvas.setFocus()
        # Call the original canvas mouse press event
        self.original_canvas_mouse_press(event)

    def showEvent(self, event):
        """Handle window show event"""
        super().showEvent(event)
        # Ensure canvas gets focus when window is shown
        self.canvas.setFocus()

    def closeEvent(self, event):
        """Handle application close"""
        self.save_current_annotations()
        self.save_settings()
        event.accept()
