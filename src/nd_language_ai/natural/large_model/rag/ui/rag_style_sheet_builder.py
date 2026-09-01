class RagStyleSheetBuilder:
    def build(self) -> str:
        return """
        QWidget {
            background: #f6f6f4;
            color: #2f3440;
            font-family: Sans Serif;
            font-size: 14px;
        }

        QMainWindow,
        QScrollArea,
        QScrollArea > QWidget > QWidget {
            background: #f6f6f4;
            border: 0;
        }

        QLabel {
            background: transparent;
            border: 0;
        }

        QLabel#titleLabel {
            font-size: 29px;
            font-weight: 800;
            color: #303746;
        }

        QLabel#subtitleLabel {
            font-size: 14px;
            color: #6d7480;
            margin-bottom: 4px;
        }

        QLabel#sectionTitle {
            font-size: 17px;
            font-weight: 750;
            color: #353b48;
        }

        QLabel#fieldLabel {
            font-size: 13px;
            font-weight: 650;
            color: #555c68;
        }

        QFrame#card {
            background: #fcfcfb;
            border: 1px solid #dedfdd;
            border-radius: 14px;
        }

        QLineEdit,
        QPlainTextEdit,
        QListWidget {
            background: #ffffff;
            color: #252a34;
            border: 1px solid #cfd3d8;
            border-radius: 10px;
            padding: 8px;
            selection-background-color: #b7cae8;
            selection-color: #25344a;
        }

        QLineEdit {
            min-height: 34px;
        }

        QLineEdit:focus,
        QPlainTextEdit:focus,
        QListWidget:focus {
            border: 1px solid #9eb8df;
        }

        QPlainTextEdit {
            padding: 10px;
        }

        QPushButton {
            min-height: 34px;
            border-radius: 9px;
            padding: 0 14px;
            font-weight: 700;
            color: #354052;
        }

        QPushButton#blueButton {
            background: #dce9f7;
            border: 1px solid #b8cde6;
        }

        QPushButton#blueButton:hover {
            background: #cfdef0;
        }

        QPushButton#greenButton {
            background: #dcebd9;
            border: 1px solid #b9d0b5;
        }

        QPushButton#greenButton:hover {
            background: #cfe2cb;
        }

        QPushButton#peachButton {
            min-width: 130px;
            background: #f4d8c7;
            border: 1px solid #dfb9a2;
        }

        QPushButton#peachButton:hover {
            background: #edcbbb;
        }

        QPushButton#secondaryButton,
        QPushButton#smallButton {
            background: #e7def3;
            color: #55466b;
            border: 1px solid #cfc1df;
        }

        QPushButton#secondaryButton:hover,
        QPushButton#smallButton:hover {
            background: #ddd1eb;
        }

        QPushButton#smallButton {
            min-height: 30px;
            padding: 0 11px;
        }

        QPushButton:disabled {
            background: #eeeeec;
            color: #a3a6aa;
            border: 1px solid #ddddda;
        }

        QListWidget#tagList {
            background: #ffffff;
            border: 1px solid #cfd3d8;
            border-radius: 10px;
            padding: 7px;
        }

        QListWidget#tagList::item {
            background: #dcebd9;
            color: #405742;
            border: 1px solid #b9d0b5;
            border-radius: 9px;
            padding: 5px 10px;
            margin: 2px;
        }

        QListWidget#tagList::item:selected {
            background: #c9ddc5;
            color: #304632;
            border: 1px solid #a8c4a3;
        }

        QScrollBar:vertical {
            background: transparent;
            width: 11px;
            margin: 2px;
        }

        QScrollBar::handle:vertical {
            background: #c8cbd0;
            border-radius: 5px;
            min-height: 24px;
        }

        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {
            height: 0;
        }
        """
