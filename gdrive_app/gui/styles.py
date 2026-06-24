# QSS Custom Theme Stylesheet for GDrive Mount Linux app

THEME_STYLE = """
/* Global styling */
QWidget {
    background-color: #121214;
    color: #e3e3e6;
    font-family: "Segoe UI", "Inter", "Roboto", "Noto Sans", sans-serif;
    font-size: 13px;
    border: none;
}

/* Card Widget (elevated panel) */
QFrame#Card {
    background-color: #1a1a1e;
    border: 1px solid #2d2d34;
    border-radius: 12px;
}

QFrame#InnerCard {
    background-color: #212126;
    border: 1px solid #33333b;
    border-radius: 8px;
}

/* Titles and Headers */
QLabel#Title {
    font-size: 20px;
    font-weight: bold;
    color: #ffffff;
    background: transparent;
}

QLabel#SubTitle {
    font-size: 13px;
    color: #a0a0a9;
    background: transparent;
}

QLabel#Header {
    font-size: 16px;
    font-weight: bold;
    color: #ffffff;
    background: transparent;
}

QLabel#StatusLabel {
    font-size: 14px;
    font-weight: 600;
    background: transparent;
}

QLabel {
    background: transparent;
}

/* Input Fields (Text edits, line edits) */
QLineEdit {
    background-color: #1a1a1e;
    border: 1px solid #2d2d34;
    border-radius: 6px;
    padding: 8px 12px;
    color: #ffffff;
    font-size: 13px;
}

QLineEdit:focus {
    border: 1px solid #4285F4;
}

QLineEdit:disabled {
    background-color: #151517;
    color: #6e6e73;
    border: 1px solid #222226;
}

QTextEdit#LogConsole {
    background-color: #0b0b0c;
    border: 1px solid #25252a;
    border-radius: 8px;
    padding: 10px;
    font-family: "Cascadia Code", "Fira Code", "Noto Mono", monospace;
    font-size: 11px;
    color: #a3be8c; /* light green terminal look */
}

/* Buttons styling */
QPushButton {
    background-color: #232328;
    border: 1px solid #33333a;
    border-radius: 8px;
    padding: 8px 16px;
    color: #e3e3e6;
    font-weight: 600;
    min-height: 20px;
}

QPushButton:hover {
    background-color: #2c2c33;
    border-color: #44444f;
}

QPushButton:pressed {
    background-color: #1d1d22;
}

QPushButton:disabled {
    background-color: #161619;
    border-color: #202024;
    color: #57575f;
}

/* Highlight Primary buttons (Google Blue) */
QPushButton#Primary {
    background-color: #4285F4;
    border: 1px solid #357ae8;
    color: #ffffff;
}

QPushButton#Primary:hover {
    background-color: #5591f5;
    border-color: #4285F4;
}

QPushButton#Primary:pressed {
    background-color: #2a75e8;
}

QPushButton#Primary:disabled {
    background-color: #203554;
    border-color: #253a5b;
    color: #647b9b;
}

/* Destructive action buttons (Google Red) */
QPushButton#Destructive {
    background-color: #2a1b1b;
    border: 1px solid #eb4335;
    color: #ff8c82;
}

QPushButton#Destructive:hover {
    background-color: #eb4335;
    color: #ffffff;
}

QPushButton#Destructive:pressed {
    background-color: #c53023;
}

/* Tab Bar styling */
QTabWidget::pane {
    border-top: 1px solid #2d2d34;
    background-color: #121214;
}

QTabBar::tab {
    background-color: #121214;
    color: #8e8e93;
    border: none;
    border-bottom: 2px solid transparent;
    padding: 10px 16px;
    font-weight: 600;
}

QTabBar::tab:hover {
    color: #d1d1d6;
}

QTabBar::tab:selected {
    color: #4285F4;
    border-bottom: 2px solid #4285F4;
}

/* Progress bar styling */
QProgressBar {
    background-color: #1a1a1e;
    border: 1px solid #2d2d34;
    border-radius: 6px;
    text-align: center;
    color: #ffffff;
    font-weight: bold;
    height: 16px;
}

QProgressBar::chunk {
    background-color: #4285F4;
    border-radius: 5px;
}

QProgressBar#DiskUsage {
    background-color: #212126;
    border: 1px solid #33333b;
    border-radius: 8px;
    height: 20px;
}

QProgressBar#DiskUsage::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #34A853, stop:1 #4285F4);
    border-radius: 7px;
}

/* Checkbox styling */
QCheckBox {
    spacing: 8px;
    color: #e3e3e6;
    background: transparent;
}

/* Scrollbar styling */
QScrollBar:vertical {
    border: none;
    background-color: #121214;
    width: 8px;
    margin: 0px 0 0px 0;
}

QScrollBar::handle:vertical {
    background-color: #2d2d34;
    border-radius: 4px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #4285F4;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none;
    background: none;
    height: 0px;
}

/* Status Indicator Dot */
QFrame#StatusDot {
    border-radius: 6px;
    max-width: 12px;
    max-height: 12px;
    min-width: 12px;
    min-height: 12px;
}

/* Tooltip styling */
QToolTip {
    background-color: #1a1a1e;
    color: #ffffff;
    border: 1px solid #2d2d34;
    border-radius: 4px;
    padding: 4px 8px;
}

/* ComboBox styling */
QComboBox {
    background-color: #1a1a1e;
    border: 1px solid #2d2d34;
    border-radius: 6px;
    padding: 6px 12px;
    color: #ffffff;
    min-height: 20px;
}

QComboBox:focus {
    border: 1px solid #4285F4;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 25px;
    border-left-width: 0px;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
}

QComboBox::down-arrow {
    image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0id2hpdGUiIHdpZHRoPSIxOHB4IiBoZWlnaHQ9IjE4cHgiPjxwYXRoIGQ9Ik03IDEwbDUgNSA1LTVIN3oiLz48L3N2Zz4=);
    width: 18px;
    height: 18px;
}

QComboBox QAbstractItemView {
    background-color: #1a1a1e;
    border: 1px solid #2d2d34;
    border-radius: 6px;
    selection-background-color: #2c2c33;
    selection-color: #ffffff;
    padding: 4px;
}

/* GroupBox styling */
QGroupBox {
    border: 1px solid #2d2d34;
    border-radius: 8px;
    margin-top: 16px;
    padding-top: 18px;
    font-weight: bold;
    color: #ffffff;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 5px;
}
"""
