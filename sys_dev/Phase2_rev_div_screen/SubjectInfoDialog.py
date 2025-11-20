# SubjectInfoDialog.py
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                          QLineEdit, QPushButton, QComboBox, QMessageBox, 
                          QDateEdit, QFormLayout)
from PyQt5.QtCore import QDate, Qt
from datetime import datetime


class SubjectInfoDialog(QDialog):
    """受試者資訊輸入對話框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("受試者資訊")
        self.setModal(True)
        self.setFixedSize(400, 200)
        
        # 存儲結果
        self.subject_info = None
        
        # 創建UI
        self.setup_ui()
    
    def setup_ui(self):
        layout = QFormLayout()
        
        # 受試者編號
        self.subject_id_edit = QLineEdit()
        self.subject_id_edit.setPlaceholderText("例如: S001")
        layout.addRow("受試者編號:", self.subject_id_edit)
        
        # 西元生日
        self.birth_date_edit = QDateEdit()
        self.birth_date_edit.setDate(QDate.currentDate().addYears(-25))  # 預設25歲
        self.birth_date_edit.setCalendarPopup(True)
        self.birth_date_edit.setDisplayFormat("yyyy-MM-dd")
        layout.addRow("西元生日:", self.birth_date_edit)
        
        # 性別
        self.gender_combo = QComboBox()
        self.gender_combo.addItems(["female", "male"])
        layout.addRow("性別:", self.gender_combo)
        
        # 按鈕
        button_layout = QHBoxLayout()
        
        self.ok_button = QPushButton("確定")
        self.ok_button.clicked.connect(self.accept_input)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        
        # 主佈局
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)
    
    def accept_input(self):
        # 驗證輸入
        subject_id = self.subject_id_edit.text().strip()
        if not subject_id:
            QMessageBox.warning(self, "錯誤", "請輸入受試者編號")
            return
        
        birth_date = self.birth_date_edit.date().toString("yyyyMMdd")
        gender = self.gender_combo.currentText()
        
        self.subject_info = {
            'subject_id': subject_id,
            'birth_date': birth_date,
            'gender': gender,
            'folder_name': f"{subject_id}_{birth_date}_{gender}"
        }
        
        self.accept()


class DrawingTypeDialog(QDialog):
    """繪畫類型選擇對話框"""
    
    def __init__(self, drawing_counter: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("選擇繪畫類型")
        self.setModal(True)
        self.setFixedSize(350, 200)  # 🔧 稍微加高以容納新選項
        
        # 存儲結果
        self.drawing_info = None
        self.drawing_counter = drawing_counter
        
        # 創建UI
        self.setup_ui()
    
    def setup_ui(self):
        layout = QFormLayout()
        
        # 顯示繪畫編號
        self.drawing_id_label = QLabel(f"繪畫編號: {self.drawing_counter}")
        self.drawing_id_label.setStyleSheet("font-weight: bold; color: #2196F3;")
        layout.addRow(self.drawing_id_label)
        
        # 🆕 繪畫類型（添加 pretest）
        self.drawing_type_combo = QComboBox()
        self.drawing_type_combo.addItems([
            "pretest (練習測試)",  # 🆕 新增選項
            "DAP (Draw-a-Person Test)",
            "HTP (House-Tree-Person Test)", 
            "FD (Free-Drawing Test)"
        ])
        layout.addRow("繪畫類型:", self.drawing_type_combo)
        
        # 按鈕
        button_layout = QHBoxLayout()
        
        self.ok_button = QPushButton("開始繪畫")
        self.ok_button.clicked.connect(self.accept_input)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        
        # 主佈局
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)
    
    def accept_input(self):
        selected_text = self.drawing_type_combo.currentText()
        
        # 🔧 提取類型代碼（添加 pretest 判斷）
        if "pretest" in selected_text:
            drawing_type = "pretest"
        elif "DAP" in selected_text:
            drawing_type = "DAP"
        elif "HTP" in selected_text:
            drawing_type = "HTP"
        elif "FD" in selected_text:
            drawing_type = "FD"
        else:
            drawing_type = "DAP"  # 預設
        
        # 使用當前時間戳作為日期時間字串
        current_time = datetime.now()
        datetime_str = current_time.strftime("%Y%m%d_%H%M%S")
        
        # 使用數字ID
        self.drawing_info = {
            'drawing_type': drawing_type,
            'drawing_id': self.drawing_counter,
            'datetime_str': datetime_str,
            'folder_name': f"{self.drawing_counter}_{drawing_type}_{datetime_str}"
        }
        
        self.accept()
