# SubjectInfoDialog.py (修改版)
import hashlib
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
import json
import copy
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
        
        from PyQt5.QtWidgets import QMenuBar, QMenu
        
        menubar = QMenuBar()
        
        file_menu = QMenu("檔案(&F)", self)
        close_action = file_menu.addAction("❌ 關閉")
        close_action.triggered.connect(self.reject)
        menubar.addMenu(file_menu)
        
        edit_menu = QMenu("編輯(&E)", self)
        edit_action = edit_menu.addAction("✏️ 編輯 Workspace")
        edit_action.triggered.connect(self.edit_workspace)
        
        new_action = edit_menu.addAction("➕ 新增 Workspace")
        new_action.triggered.connect(self.create_new_workspace)
        
        delete_action = edit_menu.addAction("🗑️ 刪除 Workspace")
        delete_action.triggered.connect(self.delete_workspace)
        
        edit_menu.addSeparator()
        
        restore_action = edit_menu.addAction("🔄 恢復預設配置")
        restore_action.triggered.connect(self.restore_default_workspace)
        
        menubar.addMenu(edit_menu)
        
        help_menu = QMenu("說明(&H)", self)
        about_action = help_menu.addAction("ℹ️ 關於")
        about_action.triggered.connect(self.show_about)
        menubar.addMenu(help_menu)
        
        main_layout.addWidget(menubar)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setSpacing(15)
        content_layout.setContentsMargins(20, 20, 20, 20)
        
        title_label = QLabel("請選擇 Workspace 配置:")
        content_layout.addWidget(title_label)
        
        self.workspace_list = QListWidget()
        self.workspace_list.itemDoubleClicked.connect(self.on_item_double_clicked)
        content_layout.addWidget(self.workspace_list)
        
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
                display_text = f"{workspace.project_name} ({filepath.stem})"
                
                item = QListWidgetItem(display_text)
                item.setData(Qt.UserRole, str(filepath))
                self.workspace_list.addItem(item)
            except Exception as e:
                self.logger.warning(f"Failed to load workspace {filepath}: {e}")
        
        if self.workspace_list.count() > 0:
            self.workspace_list.setCurrentRow(0)
    
    def on_item_double_clicked(self, item):
        """雙擊列表項目時進入編輯模式"""
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
            
            # 🆕 傳遞原始 workspace 引用
            editor = WorkspaceEditorDialog(workspace, filepath, self)
            
            if editor.exec_() == QDialog.Accepted:
                # 🆕 只有在確認儲存後才重新載入列表
                self.load_workspaces()
                QMessageBox.information(self, "成功", "Workspace 已更新")
            # 🆕 如果按取消，workspace 物件不會被修改
            
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"編輯 Workspace 失敗: {e}")

    
    def delete_workspace(self):
        """刪除選中的 Workspace（同步刪除檔案）"""
        current_item = self.workspace_list.currentItem()
        if current_item is None:
            QMessageBox.warning(self, "錯誤", "請先選擇一個 Workspace")
            return
        
        filepath = current_item.data(Qt.UserRole)
        
        try:
            workspace = WorkspaceConfig.load_from_file(filepath)
            
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
            
            os.remove(filepath)
            self.logger.info(f"✅ 已刪除 Workspace 檔案: {filepath}")
            
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
    """Workspace 編輯器對話框（🆕 深拷貝防呆 + 順序可編輯 + 自動排序）"""
    
    def __init__(self, workspace: WorkspaceConfig, filepath: Optional[str], parent=None):
        super().__init__(parent)
        
        # 創建深拷貝，避免直接修改原始物件
        self.original_workspace = workspace
        self.workspace = copy.deepcopy(workspace)
        
        self.filepath = filepath
        self.original_project_id = workspace.project_id
        
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
        
        from PyQt5.QtWidgets import QMenuBar, QMenu
        
        menubar = QMenuBar()
        
        file_menu = QMenu("檔案(&F)", self)
        save_action = file_menu.addAction("💾 儲存")
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_workspace)
        
        file_menu.addSeparator()
        close_action = file_menu.addAction("❌ 關閉")
        close_action.triggered.connect(self.reject)
        menubar.addMenu(file_menu)
        
        edit_menu = QMenu("編輯(&E)", self)
        restore_action = edit_menu.addAction("🔄 恢復預設配置")
        restore_action.triggered.connect(self.restore_default_config)
        menubar.addMenu(edit_menu)
        
        # 🆕 修改：測試 → 測驗
        test_menu = QMenu("測驗(&T)", self)
        add_test_action = test_menu.addAction("➕ 新增測驗")
        add_test_action.triggered.connect(self.add_test)
        
        edit_test_action = test_menu.addAction("✏️ 編輯測驗")
        edit_test_action.triggered.connect(self.edit_test)
        
        delete_test_action = test_menu.addAction("🗑️ 刪除測驗")
        delete_test_action.triggered.connect(self.delete_test)
        menubar.addMenu(test_menu)
        
        main_layout.addWidget(menubar)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setSpacing(15)
        content_layout.setContentsMargins(20, 20, 20, 20)
        
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
        
        # 🆕 修改：繪畫測試序列 → 繪畫測驗清單
        sequence_label = QLabel("繪畫測驗清單")
        sequence_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #2196F3;")
        content_layout.addWidget(sequence_label)
        
        from PyQt5.QtWidgets import QTableWidget, QHeaderView
        self.test_table = QTableWidget()
        # 🆕 修改：移除「顏色選擇器」欄位，修改「顯示名稱」→「細節說明」，「類型」→「繪畫類型」
        self.test_table.setColumnCount(4)
        self.test_table.setHorizontalHeaderLabels([
            "啟用", "順序", "繪畫類型", "細節說明"
        ])
        self.test_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.test_table.setSelectionBehavior(QTableWidget.SelectRows)
        content_layout.addWidget(self.test_table)
        
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
        """載入 Workspace 數據到 UI（🆕 根據 order 排序 + 順序欄位可編輯）"""
        self.project_name_edit.setText(self.workspace.project_name)
        self.project_id_edit.setText(self.workspace.project_id)
        self.version_edit.setText(self.workspace.version)
        self.description_edit.setPlainText(self.workspace.description)
        
        # 🆕🆕🆕 根據 order 欄位排序
        sorted_tests = sorted(self.workspace.drawing_sequence, key=lambda t: t.order)
        
        self.test_table.setRowCount(len(sorted_tests))
        
        for row, test in enumerate(sorted_tests):
            from PyQt5.QtWidgets import QCheckBox, QTableWidgetItem
            
            # 啟用 checkbox
            checkbox = QCheckBox()
            checkbox.setChecked(test.enabled)
            checkbox.setStyleSheet("margin-left: 50%; margin-right: 50%;")
            self.test_table.setCellWidget(row, 0, checkbox)
            
            # 🆕🆕🆕 順序欄位（可編輯）
            order_item = QTableWidgetItem(str(test.order))
            order_item.setTextAlignment(Qt.AlignCenter)
            self.test_table.setItem(row, 1, order_item)
            
            # 繪畫類型（只讀）
            type_item = QTableWidgetItem(test.drawing_type)
            type_item.setFlags(type_item.flags() & ~Qt.ItemIsEditable)
            self.test_table.setItem(row, 2, type_item)
            
            # 細節說明（只讀）
            name_item = QTableWidgetItem(test.display_name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.test_table.setItem(row, 3, name_item)
    
    def _sync_ui_to_workspace(self):
        """🆕 將 UI 的修改同步到 workspace 物件（包含順序欄位）"""
        self.workspace.project_name = self.project_name_edit.text().strip()
        self.workspace.project_id = self.project_id_edit.text().strip()
        self.workspace.version = self.version_edit.text().strip()
        self.workspace.description = self.description_edit.toPlainText().strip()
        
        # 🆕🆕🆕 根據當前表格順序重建 drawing_sequence
        sorted_tests = sorted(self.workspace.drawing_sequence, key=lambda t: t.order)
        
        # 同步測驗啟用狀態和順序
        for row in range(self.test_table.rowCount()):
            if row >= len(sorted_tests):
                break
            
            # 同步啟用狀態
            checkbox = self.test_table.cellWidget(row, 0)
            sorted_tests[row].enabled = checkbox.isChecked()
            
            # 🆕🆕🆕 同步順序欄位
            order_item = self.test_table.item(row, 1)
            if order_item:
                try:
                    new_order = int(order_item.text().strip())
                    sorted_tests[row].order = new_order
                except ValueError:
                    self.logger.warning(f"⚠️ 無效的順序值: {order_item.text()}")
        
        # 🆕🆕🆕 重新排序 drawing_sequence
        self.workspace.drawing_sequence = sorted(sorted_tests, key=lambda t: t.order)
    
    def save_workspace(self):
        """儲存 Workspace（自動處理檔案重命名和覆寫）"""
        try:
            # 🆕🆕🆕 先同步 UI 數據（包含順序）
            self._sync_ui_to_workspace()
            
            if not self.workspace.project_name:
                QMessageBox.warning(self, "錯誤", "專案名稱不能為空")
                return
            
            if not self.workspace.project_id:
                QMessageBox.warning(self, "錯誤", "專案 ID 不能為空")
                return
            
            new_project_id = self.workspace.project_id
            new_filepath = f"./workspaces/{new_project_id}.workspace.json"
            
            # 處理檔案重命名
            if self.filepath and self.original_project_id != new_project_id:
                old_filepath = self.filepath
                if os.path.exists(old_filepath):
                    os.remove(old_filepath)
                    self.logger.info(f"✅ 已刪除舊檔案: {old_filepath}")
            
            # 儲存到檔案
            self.workspace.save_to_file(new_filepath)
            self.logger.info(f"✅ 已儲存 Workspace: {new_filepath}")
            
            # 儲存成功後，將修改同步回原始物件
            self.original_workspace.project_name = self.workspace.project_name
            self.original_workspace.project_id = self.workspace.project_id
            self.original_workspace.version = self.workspace.version
            self.original_workspace.description = self.workspace.description
            self.original_workspace.drawing_sequence = copy.deepcopy(self.workspace.drawing_sequence)
            
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
        """新增測驗"""
        # 🆕 先同步當前 UI 的專案資訊到 workspace
        self._sync_ui_to_workspace()
        
        new_test = DrawingTestConfig(
            drawing_type="custom",
            display_name="自訂測驗",
            enabled=True,
            order=len(self.workspace.drawing_sequence) + 1,
            toolbar=ToolbarConfig()
        )
        
        editor = TestConfigEditorDialog(new_test, self)
        if editor.exec_() == QDialog.Accepted:
            self.workspace.drawing_sequence.append(new_test)
            self.load_workspace_data()
    
    def edit_test(self):
        """編輯選中的測驗"""
        current_row = self.test_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "錯誤", "請先選擇一個測驗")
            return
        
        if current_row >= len(self.workspace.drawing_sequence):
            return
        
        # 🆕 先同步 UI 數據
        self._sync_ui_to_workspace()
        
        test = self.workspace.drawing_sequence[current_row]
        
        editor = TestConfigEditorDialog(test, self)
        if editor.exec_() == QDialog.Accepted:
            self.load_workspace_data()
    
    def delete_test(self):
        """刪除選中的測驗"""
        current_row = self.test_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "錯誤", "請先選擇一個測驗")
            return
        
        if current_row >= len(self.workspace.drawing_sequence):
            return
        
        # 🆕 先同步 UI 數據
        self._sync_ui_to_workspace()
        
        test = self.workspace.drawing_sequence[current_row]
        
        reply = QMessageBox.question(
            self,
            "確認刪除",
            f"確定要刪除測驗 '{test.display_name}' 嗎？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            del self.workspace.drawing_sequence[current_row]
            self.load_workspace_data()


class TestConfigEditorDialog(QDialog):
    """測驗配置編輯器對話框（🆕 修改用詞）"""
    
    def __init__(self, test_config: DrawingTestConfig, parent=None):
        super().__init__(parent)
        self.test_config = test_config
        
        # 🆕 修改標題
        self.setWindowTitle("編輯測驗配置")
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
        
        # 🆕 修改：測試類型代碼 → 繪畫類型代碼
        self.drawing_type_edit = QLineEdit()
        form_layout.addRow("繪畫類型代碼:", self.drawing_type_edit)
        
        # 🆕 修改：顯示名稱 → 細節說明
        self.display_name_edit = QLineEdit()
        form_layout.addRow("細節說明:", self.display_name_edit)
        
        self.order_spin = QComboBox()
        self.order_spin.addItems([str(i) for i in range(1, 21)])
        form_layout.addRow("順序:", self.order_spin)
        
        from PyQt5.QtWidgets import QCheckBox
        self.pen_enabled_check = QCheckBox("啟用筆工具")
        form_layout.addRow("", self.pen_enabled_check)
        
        self.eraser_enabled_check = QCheckBox("啟用橡皮擦")
        form_layout.addRow("", self.eraser_enabled_check)
        
        self.color_picker_enabled_check = QCheckBox("啟用顏色選擇器")
        form_layout.addRow("", self.color_picker_enabled_check)
        
        self.color_picker_mode_combo = QComboBox()
        # 🆕 修改：禁用 → 無
        self.color_picker_mode_combo.addItem("無", ColorPickerMode.DISABLED.value)
        self.color_picker_mode_combo.addItem("24 色調色盤", ColorPickerMode.PALETTE_24.value)
        self.color_picker_mode_combo.addItem("完整色譜", ColorPickerMode.FULL_SPECTRUM.value)
        form_layout.addRow("顏色選擇器模式:", self.color_picker_mode_combo)
        
        main_layout.addLayout(form_layout)
        
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
        """載入測驗數據到 UI"""
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
        """儲存測驗配置"""
        try:
            self.test_config.drawing_type = self.drawing_type_edit.text().strip()
            self.test_config.display_name = self.display_name_edit.text().strip()
            self.test_config.order = int(self.order_spin.currentText())
            
            if not self.test_config.drawing_type:
                # 🆕 修改用詞
                QMessageBox.warning(self, "錯誤", "繪畫類型不能為空")
                return
            
            if not self.test_config.display_name:
                # 🆕 修改用詞
                QMessageBox.warning(self, "錯誤", "細節說明不能為空")
                return
            
            self.test_config.toolbar.pen_enabled = self.pen_enabled_check.isChecked()
            self.test_config.toolbar.eraser_enabled = self.eraser_enabled_check.isChecked()
            self.test_config.toolbar.color_picker_enabled = self.color_picker_enabled_check.isChecked()
            
            mode_value = self.color_picker_mode_combo.currentData()
            self.test_config.toolbar.color_picker_mode = ColorPickerMode(mode_value)
            
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"儲存失敗: {e}")


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
    """繪畫類型選擇對話框 (🆕 只顯示已啟用的測驗)"""
    
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
        
        # 🆕🆕🆕 根據 order 排序後再添加到選單
        enabled_tests = [test for test in self.workspace.drawing_sequence if test.enabled]
        sorted_tests = sorted(enabled_tests, key=lambda t: t.order)
        
        for test in sorted_tests:
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

def generate_workspace_hash(workspace: WorkspaceConfig) -> str:
    """
    生成 Workspace 配置的唯一雜湊值
    
    Args:
        workspace: Workspace 配置物件
    
    Returns:
        str: 配置的 MD5 雜湊值
    """
    # 將配置轉換為可序列化的字典
    config_dict = {
        'project_name': workspace.project_name,
        'project_id': workspace.project_id,
        'version': workspace.version,
        'description': workspace.description,
        'drawing_sequence': [
            {
                'drawing_type': test.drawing_type,
                'display_name': test.display_name,
                'order': test.order,
                'enabled': test.enabled,
                'pen_enabled': test.toolbar.pen_enabled,
                'eraser_enabled': test.toolbar.eraser_enabled,
                'color_picker_enabled': test.toolbar.color_picker_enabled,
                'color_picker_mode': test.toolbar.color_picker_mode.value
            }
            for test in workspace.drawing_sequence
        ],
        'canvas_background_color': workspace.canvas_background_color,
        'default_pen_width': workspace.default_pen_width,
        'eraser_radius': workspace.eraser_radius,
        'enable_pressure_sensitivity': workspace.enable_pressure_sensitivity
    }
    
    # 轉換為 JSON 字串並計算雜湊
    config_str = json.dumps(config_dict, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(config_str.encode('utf-8')).hexdigest()


def extract_existing_config_hash(summary_path: str) -> Optional[str]:
    """
    從現有的配置說明檔中提取最後一次配置的雜湊值
    
    Args:
        summary_path: 配置說明檔路徑
    
    Returns:
        Optional[str]: 最後一次配置的雜湊值，如果不存在則返回 None
    """
    try:
        if not os.path.exists(summary_path):
            return None
        
        with open(summary_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 尋找最後一個配置雜湊值
        import re
        matches = re.findall(r'配置雜湊值: ([a-f0-9]{32})', content)
        
        if matches:
            return matches[-1]  # 返回最後一個
        
        return None
        
    except Exception as e:
        logging.error(f"❌ 提取配置雜湊值失敗: {e}")
        return None


def save_workspace_config_summary(workspace: WorkspaceConfig, subject_dir: str):
    """
    在受試者根目錄儲存 Workspace 配置說明檔
    
    🆕 防呆措施：
    - 如果配置與上次相同，不重複寫入
    - 如果配置不同，append 新配置到檔案末尾
    - 使用 MD5 雜湊值來比對配置是否相同
    
    Args:
        workspace: Workspace 配置物件
        subject_dir: 受試者目錄路徑
    """
    try:
        summary_path = os.path.join(subject_dir, "workspace_config_summary.txt")
        
        # 🆕 計算當前配置的雜湊值
        current_hash = generate_workspace_hash(workspace)
        
        # 🆕 檢查是否已存在配置檔案
        if os.path.exists(summary_path):
            # 提取最後一次配置的雜湊值
            last_hash = extract_existing_config_hash(summary_path)
            
            if last_hash == current_hash:
                # 配置相同，不重複寫入
                logging.info(f"✅ Workspace 配置未變更，跳過寫入: {summary_path}")
                return summary_path
            else:
                # 配置不同，append 新配置
                logging.info(f"⚠️ 偵測到 Workspace 配置變更，將 append 新配置")
                mode = 'a'  # append 模式
        else:
            # 檔案不存在，創建新檔案
            mode = 'w'
        
        # 🆕 生成配置內容
        config_content = generate_workspace_config_content(workspace, current_hash)
        
        with open(summary_path, mode, encoding='utf-8') as f:
            if mode == 'a':
                # append 模式：先加入分隔線
                f.write("\n\n")
                f.write("=" * 80 + "\n")
                f.write("⚠️ 偵測到配置變更，以下為新配置\n")
                f.write("=" * 80 + "\n\n")
            
            f.write(config_content)
        
        if mode == 'a':
            logging.info(f"✅ Workspace 配置已 append: {summary_path}")
        else:
            logging.info(f"✅ Workspace 配置說明檔已儲存: {summary_path}")
        
        return summary_path
        
    except Exception as e:
        logging.error(f"❌ 儲存 Workspace 配置說明檔失敗: {e}")
        return None


def generate_workspace_config_content(workspace: WorkspaceConfig, config_hash: str) -> str:
    """
    生成 Workspace 配置內容（字串）
    
    Args:
        workspace: Workspace 配置物件
        config_hash: 配置的雜湊值
    
    Returns:
        str: 配置內容
    """
    lines = []
    
    lines.append("=" * 80)
    lines.append("Workspace 配置說明")
    lines.append("=" * 80)
    lines.append("")
    
    # 專案資訊
    lines.append(f"專案名稱: {workspace.project_name}")
    lines.append(f"專案 ID: {workspace.project_id}")
    lines.append(f"版本: {workspace.version}")
    lines.append(f"描述: {workspace.description}")
    lines.append("")
    
    # 繪畫測驗清單
    lines.append("-" * 80)
    lines.append("繪畫測驗清單:")
    lines.append("-" * 80)
    lines.append("")
    
    for test in workspace.drawing_sequence:
        lines.append(f"【{test.order}】 {test.display_name} ({test.drawing_type})")
        lines.append(f"  啟用狀態: {'✓ 已啟用' if test.enabled else '✗ 未啟用'}")
        lines.append(f"  工具配置:")
        lines.append(f"    - 筆工具: {'✓' if test.toolbar.pen_enabled else '✗'}")
        lines.append(f"    - 橡皮擦: {'✓' if test.toolbar.eraser_enabled else '✗'}")
        lines.append(f"    - 顏色選擇器: {'✓' if test.toolbar.color_picker_enabled else '✗'}")
        
        if test.toolbar.color_picker_enabled:
            color_mode_text = {
                ColorPickerMode.DISABLED: "無",
                ColorPickerMode.PALETTE_24: "24 色調色盤",
                ColorPickerMode.FULL_SPECTRUM: "完整色譜"
            }.get(test.toolbar.color_picker_mode, "無")
            lines.append(f"    - 顏色選擇器模式: {color_mode_text}")
        
        lines.append("")
    
    # 全域設定
    lines.append("-" * 80)
    lines.append("全域設定:")
    lines.append("-" * 80)
    lines.append("")
    lines.append(f"畫布背景色: {workspace.canvas_background_color}")
    lines.append(f"預設筆寬: {workspace.default_pen_width}")
    lines.append(f"橡皮擦半徑: {workspace.eraser_radius}")
    lines.append(f"壓力感應: {'✓ 啟用' if workspace.enable_pressure_sensitivity else '✗ 停用'}")
    lines.append("")
    
    # 🆕 添加配置雜湊值和生成時間
    lines.append("=" * 80)
    lines.append(f"配置雜湊值: {config_hash}")
    lines.append(f"生成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 80)
    
    return "\n".join(lines) + "\n"



def save_drawing_config_to_metadata(metadata_path: str, test_config: DrawingTestConfig):
    """
    🆕🆕🆕 將繪畫測驗配置添加到 metadata.json
    
    Args:
        metadata_path: metadata.json 的路徑
        test_config: 當前繪畫測驗配置
    """
    try:
        # 讀取現有的 metadata
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # 🆕 添加繪畫測驗配置
        metadata['drawing_test_config'] = {
            'drawing_type': test_config.drawing_type,
            'display_name': test_config.display_name,
            'order': test_config.order,
            'enabled_tools': {
                'pen': test_config.toolbar.pen_enabled,
                'eraser': test_config.toolbar.eraser_enabled,
                'color_picker': test_config.toolbar.color_picker_enabled
            },
            'color_picker_mode': test_config.toolbar.color_picker_mode.value,
            'constraints': {
                'time_limit_enabled': test_config.constraints.time_limit_enabled,
                'time_limit_seconds': test_config.constraints.time_limit_seconds,
                'stroke_limit_enabled': test_config.constraints.stroke_limit_enabled,
                'stroke_limit_count': test_config.constraints.stroke_limit_count
            }
        }
        
        # 寫回檔案
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        logging.info(f"✅ 繪畫測驗配置已添加到 metadata.json")
        
    except Exception as e:
        logging.error(f"❌ 添加繪畫測驗配置到 metadata 失敗: {e}")
