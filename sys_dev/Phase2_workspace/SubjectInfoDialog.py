# SubjectInfoDialog.py (完整修改版)

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                          QLineEdit, QPushButton, QComboBox, QMessageBox, 
                          QDateEdit, QFormLayout, QListWidget, QListWidgetItem, QWidget)
from PyQt5.QtCore import QDate, Qt
from datetime import datetime
from Config import WorkspaceConfig, get_default_workspace, ColorPickerMode, DrawingTestConfig, ToolbarConfig
from pathlib import Path
import logging
from typing import Optional
import os

class WorkspaceSelectionDialog(QDialog):
    """Workspace 選擇對話框（增強版：雙擊編輯 + 刪除功能 + 自動覆寫）"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("選擇 Workspace")
        self.setModal(True)
        self.setFixedSize(700, 500)
        
        self.setStyleSheet("""
            QLabel {
                font-size: 20px;
                font-weight: bold;
            }
            QListWidget {
                font-size: 18px;
                min-height: 200px;
            }
            QPushButton {
                font-size: 18px;
                font-weight: bold;
                min-height: 45px;
                border-radius: 5px;
            }
            QMenuBar {
                font-size: 16px;
                background-color: #f5f5f5;
                border-bottom: 2px solid #cccccc;
            }
            QMenuBar::item {
                padding: 8px 16px;
                background-color: transparent;
            }
            QMenuBar::item:selected {
                background-color: #e0e0e0;
            }
            QMenu {
                font-size: 16px;
                background-color: white;
                border: 1px solid #cccccc;
            }
            QMenu::item {
                padding: 8px 32px 8px 16px;
            }
            QMenu::item:selected {
                background-color: #2196F3;
                color: white;
            }
        """)
        
        self.selected_workspace = None
        self.logger = logging.getLogger('WorkspaceSelectionDialog')
        self.setup_ui()
        self.load_workspaces()
    
    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 創建選單列
        from PyQt5.QtWidgets import QMenuBar, QMenu
        
        menubar = QMenuBar()
        
        # === 檔案選單 ===
        file_menu = QMenu("檔案(&F)", self)
        
        close_action = file_menu.addAction("❌ 關閉")
        close_action.triggered.connect(self.reject)
        
        menubar.addMenu(file_menu)
        
        # === 編輯選單 ===
        edit_menu = QMenu("編輯(&E)", self)
        
        edit_action = edit_menu.addAction("✏️ 編輯 Workspace")
        edit_action.triggered.connect(self.edit_workspace)
        
        new_action = edit_menu.addAction("➕ 新增 Workspace")
        new_action.triggered.connect(self.create_new_workspace)
        
        # 🆕🆕🆕 新增刪除功能
        delete_action = edit_menu.addAction("🗑️ 刪除 Workspace")
        delete_action.triggered.connect(self.delete_workspace)
        
        edit_menu.addSeparator()
        
        restore_action = edit_menu.addAction("🔄 恢復預設配置")
        restore_action.triggered.connect(self.restore_default_workspace)
        
        menubar.addMenu(edit_menu)
        
        # === 說明選單 ===
        help_menu = QMenu("說明(&H)", self)
        
        about_action = help_menu.addAction("ℹ️ 關於")
        about_action.triggered.connect(self.show_about)
        
        menubar.addMenu(help_menu)
        
        main_layout.addWidget(menubar)
        
        # 內容區域
        content_widget = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setSpacing(15)
        content_layout.setContentsMargins(20, 20, 20, 20)
        
        # 標題
        title_label = QLabel("請選擇 Workspace 配置:")
        content_layout.addWidget(title_label)
        
        # Workspace 列表
        self.workspace_list = QListWidget()
        # 🆕🆕🆕 連接雙擊事件
        self.workspace_list.itemDoubleClicked.connect(self.on_item_double_clicked)
        content_layout.addWidget(self.workspace_list)
        
        # 確定/取消按鈕
        button_layout = QHBoxLayout()
        button_layout.setSpacing(20)
        
        self.ok_button = QPushButton("確定")
        self.ok_button.setStyleSheet("background-color: #4CAF50; color: white;")
        self.ok_button.clicked.connect(self.accept_selection)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setStyleSheet("background-color: #f44336; color: white;")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        
        content_layout.addLayout(button_layout)
        
        content_widget.setLayout(content_layout)
        main_layout.addWidget(content_widget)
        
        self.setLayout(main_layout)
    
    def load_workspaces(self):
        """載入可用的 Workspace 列表（顯示最新的 project_id）"""
        self.workspace_list.clear()
        
        workspace_dir = Path("./workspaces")
        
        if not workspace_dir.exists():
            workspace_dir.mkdir(parents=True)
            default_workspace = get_default_workspace()
            default_workspace.save_to_file("./workspaces/default_clinical.workspace.json")
        
        workspace_files = list(workspace_dir.glob("*.workspace.json"))
        
        for filepath in workspace_files:
            try:
                workspace = WorkspaceConfig.load_from_file(str(filepath))
                # 🆕🆕🆕 顯示格式：專案名稱 (當前檔案名)
                display_text = f"{workspace.project_name} ({filepath.stem})"
                
                item = QListWidgetItem(display_text)
                item.setData(Qt.UserRole, str(filepath))
                self.workspace_list.addItem(item)
            except Exception as e:
                self.logger.warning(f"Failed to load workspace {filepath}: {e}")
        
        if self.workspace_list.count() > 0:
            self.workspace_list.setCurrentRow(0)
    
    def on_item_double_clicked(self, item):
        """🆕🆕🆕 雙擊列表項目時進入編輯模式"""
        self.edit_workspace()
    
    def accept_selection(self):
        """確認選擇"""
        current_item = self.workspace_list.currentItem()
        if current_item is None:
            QMessageBox.warning(self, "錯誤", "請選擇一個 Workspace")
            return
        
        filepath = current_item.data(Qt.UserRole)
        try:
            self.selected_workspace = WorkspaceConfig.load_from_file(filepath)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"載入 Workspace 失敗: {e}")
    
    def edit_workspace(self):
        """編輯選中的 Workspace"""
        current_item = self.workspace_list.currentItem()
        if current_item is None:
            QMessageBox.warning(self, "錯誤", "請先選擇一個 Workspace")
            return
        
        filepath = current_item.data(Qt.UserRole)
        try:
            workspace = WorkspaceConfig.load_from_file(filepath)
            
            editor = WorkspaceEditorDialog(workspace, filepath, self)
            if editor.exec_() == QDialog.Accepted:
                # 🆕🆕🆕 編輯完成後重新載入列表（會顯示最新的檔名）
                self.load_workspaces()
                QMessageBox.information(self, "成功", "Workspace 已更新")
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"編輯 Workspace 失敗: {e}")
    
    def delete_workspace(self):
        """🆕🆕🆕 刪除選中的 Workspace（同步刪除檔案）"""
        current_item = self.workspace_list.currentItem()
        if current_item is None:
            QMessageBox.warning(self, "錯誤", "請先選擇一個 Workspace")
            return
        
        filepath = current_item.data(Qt.UserRole)
        
        try:
            workspace = WorkspaceConfig.load_from_file(filepath)
            
            # 確認刪除
            reply = QMessageBox.question(
                self,
                "確認刪除",
                f"確定要刪除 Workspace '{workspace.project_name}' 嗎？\n"
                f"檔案 '{Path(filepath).name}' 也會被刪除！",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                return
            
            # 刪除檔案
            os.remove(filepath)
            self.logger.info(f"✅ 已刪除 Workspace 檔案: {filepath}")
            
            # 重新載入列表
            self.load_workspaces()
            
            QMessageBox.information(self, "成功", f"Workspace '{workspace.project_name}' 已刪除")
            
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"刪除失敗: {e}")
    
    def create_new_workspace(self):
        """創建新 Workspace（自動創建檔案）"""
        new_workspace = WorkspaceConfig(
            project_name="新專案",
            project_id=f"project_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            version="1.0",
            description="新建的 Workspace"
        )
        
        editor = WorkspaceEditorDialog(new_workspace, None, self)
        if editor.exec_() == QDialog.Accepted:
            self.load_workspaces()
            QMessageBox.information(self, "成功", "新 Workspace 已創建")
    
    def restore_default_workspace(self):
        """恢復預設 Workspace 配置"""
        reply = QMessageBox.question(
            self,
            "確認恢復",
            "確定要恢復預設 Workspace 配置嗎？\n這將覆蓋現有的 default_clinical.workspace.json",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        try:
            default_workspace = get_default_workspace()
            default_path = "./workspaces/default_clinical.workspace.json"
            default_workspace.save_to_file(default_path)
            
            self.load_workspaces()
            
            QMessageBox.information(
                self,
                "成功",
                "預設 Workspace 配置已恢復！\n檔案: default_clinical.workspace.json"
            )
            
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"恢復預設配置失敗: {e}")
    
    def show_about(self):
        """顯示關於對話框"""
        QMessageBox.information(
            self,
            "關於",
            "Wacom 繪圖測試系統\n\n"
            "版本: 1.0\n"
            "支援多種繪畫測試類型配置\n\n"
            "功能:\n"
            "- 自訂 Workspace 配置\n"
            "- 雙擊編輯 Workspace\n"
            "- 自動覆寫配置檔案\n"
            "- 多測試類型管理\n"
            "- LSL 數據記錄"
        )


class WorkspaceEditorDialog(QDialog):
    """Workspace 編輯器對話框（增強版：自動覆寫舊檔案）"""
    
    def __init__(self, workspace: WorkspaceConfig, filepath: Optional[str], parent=None):
        super().__init__(parent)
        self.workspace = workspace
        self.filepath = filepath
        self.original_project_id = workspace.project_id  # 🆕 記錄原始 project_id
        
        self.setWindowTitle("編輯 Workspace")
        self.setModal(True)
        self.setFixedSize(900, 700)
        
        self.setStyleSheet("""
            QLabel {
                font-size: 16px;
            }
            QLineEdit, QTextEdit {
                font-size: 16px;
                padding: 5px;
            }
            QTableWidget {
                font-size: 14px;
            }
            QPushButton {
                font-size: 16px;
                font-weight: bold;
                min-height: 40px;
                border-radius: 5px;
            }
            QMenuBar {
                font-size: 14px;
                background-color: #f5f5f5;
                border-bottom: 2px solid #cccccc;
            }
            QMenuBar::item {
                padding: 6px 12px;
                background-color: transparent;
            }
            QMenuBar::item:selected {
                background-color: #e0e0e0;
            }
            QMenu {
                font-size: 14px;
                background-color: white;
                border: 1px solid #cccccc;
            }
            QMenu::item {
                padding: 6px 24px 6px 12px;
            }
            QMenu::item:selected {
                background-color: #2196F3;
                color: white;
            }
        """)
        
        self.logger = logging.getLogger('WorkspaceEditorDialog')
        self.setup_ui()
        self.load_workspace_data()
    
    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 創建選單列
        from PyQt5.QtWidgets import QMenuBar, QMenu
        
        menubar = QMenuBar()
        
        # === 檔案選單 ===
        file_menu = QMenu("檔案(&F)", self)
        
        save_action = file_menu.addAction("💾 儲存")
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_workspace)
        
        file_menu.addSeparator()
        
        close_action = file_menu.addAction("❌ 關閉")
        close_action.triggered.connect(self.reject)
        
        menubar.addMenu(file_menu)
        
        # === 編輯選單 ===
        edit_menu = QMenu("編輯(&E)", self)
        
        restore_action = edit_menu.addAction("🔄 恢復預設配置")
        restore_action.triggered.connect(self.restore_default_config)
        
        menubar.addMenu(edit_menu)
        
        # === 測試選單 ===
        test_menu = QMenu("測試(&T)", self)
        
        add_test_action = test_menu.addAction("➕ 新增測試")
        add_test_action.triggered.connect(self.add_test)
        
        edit_test_action = test_menu.addAction("✏️ 編輯測試")
        edit_test_action.triggered.connect(self.edit_test)
        
        delete_test_action = test_menu.addAction("🗑️ 刪除測試")
        delete_test_action.triggered.connect(self.delete_test)
        
        menubar.addMenu(test_menu)
        
        main_layout.addWidget(menubar)
        
        # 內容區域
        content_widget = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setSpacing(15)
        content_layout.setContentsMargins(20, 20, 20, 20)
        
        # === 專案資訊區域 ===
        info_group = QVBoxLayout()
        
        title_label = QLabel("專案資訊")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #2196F3;")
        info_group.addWidget(title_label)
        
        info_form = QFormLayout()
        
        self.project_name_edit = QLineEdit()
        info_form.addRow("專案名稱:", self.project_name_edit)
        
        self.project_id_edit = QLineEdit()
        info_form.addRow("專案 ID:", self.project_id_edit)
        
        self.version_edit = QLineEdit()
        info_form.addRow("版本:", self.version_edit)
        
        from PyQt5.QtWidgets import QTextEdit
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(60)
        info_form.addRow("描述:", self.description_edit)
        
        info_group.addLayout(info_form)
        content_layout.addLayout(info_group)
        
        # === 繪畫測試序列區域 ===
        sequence_label = QLabel("繪畫測試序列")
        sequence_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #2196F3;")
        content_layout.addWidget(sequence_label)
        
        # 測試列表表格
        from PyQt5.QtWidgets import QTableWidget, QHeaderView
        self.test_table = QTableWidget()
        self.test_table.setColumnCount(5)
        self.test_table.setHorizontalHeaderLabels([
            "啟用", "順序", "類型", "顯示名稱", "顏色選擇器"
        ])
        self.test_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.test_table.setSelectionBehavior(QTableWidget.SelectRows)
        content_layout.addWidget(self.test_table)
        
        # 確定/取消按鈕
        button_layout = QHBoxLayout()
        button_layout.setSpacing(20)
        
        self.save_button = QPushButton("💾 儲存")
        self.save_button.setStyleSheet("background-color: #4CAF50; color: white;")
        self.save_button.clicked.connect(self.save_workspace)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setStyleSheet("background-color: #f44336; color: white;")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        
        content_layout.addLayout(button_layout)
        
        content_widget.setLayout(content_layout)
        main_layout.addWidget(content_widget)
        
        self.setLayout(main_layout)
    
    def load_workspace_data(self):
        """載入 Workspace 數據到 UI"""
        self.project_name_edit.setText(self.workspace.project_name)
        self.project_id_edit.setText(self.workspace.project_id)
        self.version_edit.setText(self.workspace.version)
        self.description_edit.setPlainText(self.workspace.description)
        
        self.test_table.setRowCount(len(self.workspace.drawing_sequence))
        
        for row, test in enumerate(self.workspace.drawing_sequence):
            from PyQt5.QtWidgets import QCheckBox, QTableWidgetItem
            checkbox = QCheckBox()
            checkbox.setChecked(test.enabled)
            checkbox.setStyleSheet("margin-left: 50%; margin-right: 50%;")
            self.test_table.setCellWidget(row, 0, checkbox)
            
            self.test_table.setItem(row, 1, QTableWidgetItem(str(test.order)))
            self.test_table.setItem(row, 2, QTableWidgetItem(test.drawing_type))
            self.test_table.setItem(row, 3, QTableWidgetItem(test.display_name))
            
            color_mode_text = {
                ColorPickerMode.DISABLED: "禁用",
                ColorPickerMode.PALETTE_24: "24色",
                ColorPickerMode.FULL_SPECTRUM: "完整"
            }.get(test.toolbar.color_picker_mode, "禁用")
            self.test_table.setItem(row, 4, QTableWidgetItem(color_mode_text))
    
    def save_workspace(self):
        """🆕🆕🆕 儲存 Workspace（自動處理檔案重命名和覆寫）"""
        try:
            # 更新專案資訊
            self.workspace.project_name = self.project_name_edit.text().strip()
            new_project_id = self.project_id_edit.text().strip()
            self.workspace.project_id = new_project_id
            self.workspace.version = self.version_edit.text().strip()
            self.workspace.description = self.description_edit.toPlainText().strip()
            
            # 驗證
            if not self.workspace.project_name:
                QMessageBox.warning(self, "錯誤", "專案名稱不能為空")
                return
            
            if not self.workspace.project_id:
                QMessageBox.warning(self, "錯誤", "專案 ID 不能為空")
                return
            
            # 更新測試序列的啟用狀態
            for row in range(self.test_table.rowCount()):
                checkbox = self.test_table.cellWidget(row, 0)
                if row < len(self.workspace.drawing_sequence):
                    self.workspace.drawing_sequence[row].enabled = checkbox.isChecked()
            
            # 🆕🆕🆕 處理檔案路徑
            new_filepath = f"./workspaces/{new_project_id}.workspace.json"
            
            # 🆕🆕🆕 如果 project_id 改變了，刪除舊檔案
            if self.filepath and self.original_project_id != new_project_id:
                old_filepath = self.filepath
                if os.path.exists(old_filepath):
                    os.remove(old_filepath)
                    self.logger.info(f"✅ 已刪除舊檔案: {old_filepath}")
            
            # 🆕🆕🆕 儲存到新檔案（覆寫模式）
            self.workspace.save_to_file(new_filepath)
            self.logger.info(f"✅ 已儲存 Workspace: {new_filepath}")
            
            # 🆕🆕🆕 更新 filepath 以便下次儲存
            self.filepath = new_filepath
            self.original_project_id = new_project_id
            
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"儲存失敗: {e}")
            self.logger.error(f"❌ 儲存失敗: {e}")
    
    def restore_default_config(self):
        """恢復預設配置"""
        reply = QMessageBox.question(
            self,
            "確認恢復",
            "確定要恢復預設配置嗎？\n這將清除當前所有修改！",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        try:
            default_workspace = get_default_workspace()
            self.workspace = default_workspace
            self.load_workspace_data()
            
            QMessageBox.information(
                self,
                "成功",
                "已恢復預設配置！\n請記得儲存以套用變更。"
            )
            
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"恢復預設配置失敗: {e}")
    
    def add_test(self):
        """新增測試"""
        new_test = DrawingTestConfig(
            drawing_type="custom",
            display_name="自訂測試",
            enabled=True,
            order=len(self.workspace.drawing_sequence) + 1,
            toolbar=ToolbarConfig()
        )
        
        editor = TestConfigEditorDialog(new_test, self)
        if editor.exec_() == QDialog.Accepted:
            self.workspace.drawing_sequence.append(new_test)
            self.load_workspace_data()
    
    def edit_test(self):
        """編輯選中的測試"""
        current_row = self.test_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "錯誤", "請先選擇一個測試")
            return
        
        if current_row >= len(self.workspace.drawing_sequence):
            return
        
        test = self.workspace.drawing_sequence[current_row]
        
        editor = TestConfigEditorDialog(test, self)
        if editor.exec_() == QDialog.Accepted:
            self.load_workspace_data()
    
    def delete_test(self):
        """刪除選中的測試"""
        current_row = self.test_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "錯誤", "請先選擇一個測試")
            return
        
        if current_row >= len(self.workspace.drawing_sequence):
            return
        
        test = self.workspace.drawing_sequence[current_row]
        
        reply = QMessageBox.question(
            self,
            "確認刪除",
            f"確定要刪除測試 '{test.display_name}' 嗎？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            del self.workspace.drawing_sequence[current_row]
            self.load_workspace_data()


class TestConfigEditorDialog(QDialog):
    """測試配置編輯器對話框（簡化版）"""
    
    def __init__(self, test_config: DrawingTestConfig, parent=None):
        super().__init__(parent)
        self.test_config = test_config
        
        self.setWindowTitle("編輯測試配置")
        self.setModal(True)
        self.setFixedSize(600, 500)
        
        self.setStyleSheet("""
            QLabel {
                font-size: 16px;
            }
            QLineEdit {
                font-size: 16px;
                padding: 5px;
            }
            QComboBox {
                font-size: 16px;
                padding: 5px;
            }
            QCheckBox {
                font-size: 16px;
            }
            QPushButton {
                font-size: 16px;
                font-weight: bold;
                min-height: 40px;
                border-radius: 5px;
            }
        """)
        
        self.setup_ui()
        self.load_test_data()
    
    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        form_layout = QFormLayout()
        
        # 基本資訊
        self.drawing_type_edit = QLineEdit()
        form_layout.addRow("測試類型代碼:", self.drawing_type_edit)
        
        self.display_name_edit = QLineEdit()
        form_layout.addRow("顯示名稱:", self.display_name_edit)
        
        self.order_spin = QComboBox()
        self.order_spin.addItems([str(i) for i in range(1, 21)])
        form_layout.addRow("順序:", self.order_spin)
        
        # 工具欄配置
        from PyQt5.QtWidgets import QCheckBox
        self.pen_enabled_check = QCheckBox("啟用筆工具")
        form_layout.addRow("", self.pen_enabled_check)
        
        self.eraser_enabled_check = QCheckBox("啟用橡皮擦")
        form_layout.addRow("", self.eraser_enabled_check)
        
        self.color_picker_enabled_check = QCheckBox("啟用顏色選擇器")
        form_layout.addRow("", self.color_picker_enabled_check)
        
        self.color_picker_mode_combo = QComboBox()
        self.color_picker_mode_combo.addItem("禁用", ColorPickerMode.DISABLED.value)
        self.color_picker_mode_combo.addItem("24 色調色盤", ColorPickerMode.PALETTE_24.value)
        self.color_picker_mode_combo.addItem("完整色譜", ColorPickerMode.FULL_SPECTRUM.value)
        form_layout.addRow("顏色選擇器模式:", self.color_picker_mode_combo)
        
        main_layout.addLayout(form_layout)
        
        # 按鈕
        button_layout = QHBoxLayout()
        button_layout.setSpacing(20)
        
        self.save_button = QPushButton("💾 儲存")
        self.save_button.setStyleSheet("background-color: #4CAF50; color: white;")
        self.save_button.clicked.connect(self.save_test_config)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setStyleSheet("background-color: #f44336; color: white;")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)
    
    def load_test_data(self):
        """載入測試數據到 UI"""
        self.drawing_type_edit.setText(self.test_config.drawing_type)
        self.display_name_edit.setText(self.test_config.display_name)
        self.order_spin.setCurrentText(str(self.test_config.order))
        
        self.pen_enabled_check.setChecked(self.test_config.toolbar.pen_enabled)
        self.eraser_enabled_check.setChecked(self.test_config.toolbar.eraser_enabled)
        self.color_picker_enabled_check.setChecked(self.test_config.toolbar.color_picker_enabled)
        
        mode_index = self.color_picker_mode_combo.findData(self.test_config.toolbar.color_picker_mode.value)
        if mode_index >= 0:
            self.color_picker_mode_combo.setCurrentIndex(mode_index)
    
    def save_test_config(self):
        """儲存測試配置"""
        try:
            self.test_config.drawing_type = self.drawing_type_edit.text().strip()
            self.test_config.display_name = self.display_name_edit.text().strip()
            self.test_config.order = int(self.order_spin.currentText())
            
            if not self.test_config.drawing_type:
                QMessageBox.warning(self, "錯誤", "測試類型不能為空")
                return
            
            if not self.test_config.display_name:
                QMessageBox.warning(self, "錯誤", "顯示名稱不能為空")
                return
            
            self.test_config.toolbar.pen_enabled = self.pen_enabled_check.isChecked()
            self.test_config.toolbar.eraser_enabled = self.eraser_enabled_check.isChecked()
            self.test_config.toolbar.color_picker_enabled = self.color_picker_enabled_check.isChecked()
            
            mode_value = self.color_picker_mode_combo.currentData()
            self.test_config.toolbar.color_picker_mode = ColorPickerMode(mode_value)
            
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"儲存失敗: {e}")


# SubjectInfoDialog 和 DrawingTypeDialog 保持不變...
class SubjectInfoDialog(QDialog):
    """受試者資訊輸入對話框 (放大版)"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("受試者資訊")
        self.setModal(True)
        self.setFixedSize(600, 400)
        
        self.setStyleSheet("""
            QLabel {
                font-size: 20px;
                font-weight: bold;
            }
            QLineEdit {
                font-size: 20px;
                padding: 5px;
                min-height: 40px;
            }
            QDateEdit {
                font-size: 20px;
                padding: 5px;
                min-height: 40px;
            }
            QComboBox {
                font-size: 20px;
                padding: 5px;
                min-height: 40px;
            }
            QPushButton {
                font-size: 20px;
                font-weight: bold;
                min-height: 50px;
                border-radius: 5px;
            }
        """)
        
        self.subject_info = None
        self.setup_ui()
    
    def setup_ui(self):
        layout = QFormLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        self.subject_id_edit = QLineEdit()
        self.subject_id_edit.setPlaceholderText("例如: S001")
        layout.addRow("受試者編號:", self.subject_id_edit)
        
        self.birth_date_edit = QDateEdit()
        self.birth_date_edit.setDate(QDate.currentDate().addYears(-25))
        self.birth_date_edit.setCalendarPopup(True)
        self.birth_date_edit.setDisplayFormat("yyyy-MM-dd")
        layout.addRow("西元生日:", self.birth_date_edit)
        
        self.gender_combo = QComboBox()
        self.gender_combo.addItems(["female", "male"])
        layout.addRow("性別:", self.gender_combo)
        
        button_layout = QHBoxLayout()
        button_layout.setSpacing(20)
        
        self.ok_button = QPushButton("確定")
        self.ok_button.clicked.connect(self.accept_input)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addSpacing(20)
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)
    
    def accept_input(self):
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
    """繪畫類型選擇對話框 (放大版)"""
    
    def __init__(self, drawing_counter: int, workspace: WorkspaceConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("選擇繪畫類型")
        self.setModal(True)
        self.setFixedSize(550, 350)
        
        self.setStyleSheet("""
            QLabel {
                font-size: 22px;
            }
            QComboBox {
                font-size: 20px;
                padding: 5px;
                min-height: 50px;
            }
            QComboBox QAbstractItemView {
                font-size: 20px;
            }
            QPushButton {
                font-size: 20px;
                font-weight: bold;
                min-height: 60px;
                border-radius: 8px;
            }
        """)
        
        self.drawing_info = None
        self.drawing_counter = drawing_counter
        self.workspace = workspace
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QFormLayout()
        layout.setSpacing(25)
        layout.setContentsMargins(30, 30, 30, 30)
        
        self.drawing_id_label = QLabel(f"繪畫編號: {self.drawing_counter}")
        self.drawing_id_label.setStyleSheet("font-weight: bold; color: #2196F3; font-size: 28px;")
        layout.addRow(self.drawing_id_label)
        
        self.drawing_type_combo = QComboBox()
        
        for test in self.workspace.drawing_sequence:
            if test.enabled:
                self.drawing_type_combo.addItem(
                    f"{test.display_name}",
                    test.drawing_type
                )
        
        layout.addRow("繪畫類型:", self.drawing_type_combo)
        
        button_layout = QHBoxLayout()
        button_layout.setSpacing(20)
        
        self.ok_button = QPushButton("開始繪畫")
        self.ok_button.setStyleSheet("background-color: #4CAF50; color: white;")
        self.ok_button.clicked.connect(self.accept_input)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setStyleSheet("background-color: #f44336; color: white;")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addStretch()
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)
    
    def accept_input(self):
        drawing_type = self.drawing_type_combo.currentData()
        
        if not drawing_type:
            drawing_type = "DAP"
        
        current_time = datetime.now()
        datetime_str = current_time.strftime("%Y%m%d_%H%M%S")
        
        self.drawing_info = {
            'drawing_type': drawing_type,
            'drawing_id': self.drawing_counter,
            'datetime_str': datetime_str,
            'folder_name': f"{self.drawing_counter}_{drawing_type}_{datetime_str}"
        }
        
        self.accept()
