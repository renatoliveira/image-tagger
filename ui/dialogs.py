"""Modal dialogs for the image tagger application"""

import random
from PyQt6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout, QLineEdit,
                             QColorDialog, QPushButton, QLabel, QVBoxLayout,
                             QHBoxLayout, QListWidget, QListWidgetItem)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor


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
        from PyQt6.QtWidgets import QComboBox
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
