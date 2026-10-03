"""Style plat de Finish, appliqué à la fenêtre principale."""

APP_STYLE = """
QMainWindow, QWidget#app {
    color: #212529;
    font-family: "Segoe UI", sans-serif;
    font-size: 14px;
}
QWidget#app, QStackedWidget {
    background: transparent;
}
QScrollArea, QWidget#scrollViewport, QWidget#prepareForm {
    background: transparent;
    border: none;
}
QLabel#screenTitle {
    font-size: 22px;
    font-weight: 700;
    color: #212529;
}
QLabel#courseTitle {
    font-size: 28px;
    font-weight: 700;
}
QLabel#muted, QLabel#hint {
    color: #6c757d;
}
QLabel#hint {
    font-size: 13px;
    background: rgba(255, 255, 255, 180);
    border-radius: 6px;
    padding: 4px 8px;
}
QFrame#card, QWidget#side, QTreeWidget, QListWidget {
    background: rgba(255, 255, 255, 196);
    border: 1px solid rgba(255, 255, 255, 170);
    border-radius: 10px;
}
QFrame#header {
    background: #111111;
    border: none;
}
QLabel#cardTitle {
    font-size: 13px;
    font-weight: 700;
    color: #6c757d;
    letter-spacing: 0.4px;
}
QPushButton#accordion {
    background: transparent;
    border: none;
    color: #6c757d;
    font-size: 13px;
    font-weight: 700;
    text-align: left;
    padding: 2px 0px;
    min-height: 28px;
}
QPushButton#accordion:hover {
    background: transparent;
    color: #212529;
}
QLineEdit, QComboBox {
    background: #ffffff;
    border: 1px solid #ced4da;
    border-radius: 6px;
    padding: 8px 10px;
    min-height: 22px;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #0d6efd;
}
QPushButton {
    background: #ffffff;
    color: #212529;
    border: 1px solid #ced4da;
    border-radius: 6px;
    padding: 8px 14px;
    min-height: 36px;
    font-weight: 600;
}
QPushButton:hover {
    background: #f8f9fa;
}
QPushButton:disabled {
    color: #adb5bd;
    background: #f8f9fa;
}
QPushButton#primary {
    background: #0d6efd;
    color: #ffffff;
    border: none;
}
QPushButton#primary:hover {
    background: #0b5ed7;
}
QPushButton#primary:disabled {
    background: #9ec5fe;
    color: #ffffff;
}
QPushButton#danger {
    background: #dc3545;
    color: #ffffff;
    border: none;
}
QPushButton#danger:hover {
    background: #bb2d3b;
}
QPushButton#danger:disabled {
    background: #f1aeb5;
    color: #ffffff;
}
QWidget#side QPushButton {
    min-height: 26px;
    padding: 4px 8px;
    font-size: 13px;
}
QPushButton#nav, QPushButton#nav[active="true"] {
    background: transparent;
    border: none;
    color: #dee2e6;
    font-weight: 700;
    min-height: 32px;
}
QPushButton#nav:checked {
    color: #ffffff;
    background: #2b2f33;
    border-radius: 6px;
}
QSlider::groove:horizontal {
    height: 6px;
    background: #dee2e6;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    width: 16px;
    margin: -6px 0;
    background: #0d6efd;
    border-radius: 8px;
}
QTreeWidget, QListWidget {
    padding: 4px;
}
QTreeWidget::item, QListWidget::item {
    padding: 6px;
}
QTreeWidget::item:selected, QListWidget::item:selected {
    background: #e7f1ff;
    color: #212529;
}
"""
