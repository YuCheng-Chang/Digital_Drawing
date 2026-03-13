# SubjectInfoDialog.py (修改版)
import hashlib
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                          QLineEdit, QPushButton, QComboBox, QMessageBox, 
                          QDateEdit, QFormLayout, QListWidget, QListWidgetItem, QWidget,QFileDialog)
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
        
        # 🆕🆕🆕 新增複製功能
        duplicate_action = edit_menu.addAction("📋 複製 Workspace")
        duplicate_action.triggered.connect(self.duplicate_workspace)
        
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

    def duplicate_workspace(self):
        """複製選中的 Workspace（含 JSON 檔案）"""
        current_item = self.workspace_list.currentItem()
        if current_item is None:
            QMessageBox.warning(self, "錯誤", "請先選擇一個 Workspace")
            return
        
        filepath = current_item.data(Qt.UserRole)
        
        try:
            # 載入原始 Workspace
            source_workspace = WorkspaceConfig.load_from_file(filepath)
            
            # 🆕 彈出命名對話框
            dialog = WorkspaceDuplicateDialog(
                source_name=source_workspace.project_name,
                source_id=source_workspace.project_id,
                parent=self
            )
            
            if dialog.exec_() != QDialog.Accepted:
                return
            
            new_name = dialog.new_name
            new_id = dialog.new_id
            
            # 🆕 檢查新 ID 是否已存在
            new_filepath = f"./workspaces/{new_id}.workspace.json"
            if os.path.exists(new_filepath):
                reply = QMessageBox.question(
                    self,
                    "檔案已存在",
                    f"Workspace ID '{new_id}' 已存在！\n確定要覆寫嗎？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return
            
            # 🆕 深拷貝並修改名稱/ID
            new_workspace = copy.deepcopy(source_workspace)
            new_workspace.project_name = new_name
            new_workspace.project_id = new_id
            
            # 🆕 儲存新的 JSON 檔案
            new_workspace.save_to_file(new_filepath)
            self.logger.info(f"✅ 已複製 Workspace: {filepath} → {new_filepath}")
            
            # 🆕 重新整理列表並自動選中新項目
            self.load_workspaces()
            self._select_workspace_by_id(new_id)
            
            QMessageBox.information(
                self,
                "成功",
                f"Workspace 已複製！\n"
                f"原始: {source_workspace.project_name}\n"
                f"新建: {new_name} ({new_id})"
            )
            
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"複製失敗: {e}")
            self.logger.error(f"❌ 複製 Workspace 失敗: {e}")

    def _select_workspace_by_id(self, project_id: str):
        """🆕 根據 project_id 自動選中列表中的項目"""
        for i in range(self.workspace_list.count()):
            item = self.workspace_list.item(i)
            filepath = item.data(Qt.UserRole)
            # 從檔名判斷（格式為 {project_id}.workspace.json）
            if Path(filepath).stem == f"{project_id}.workspace":
                self.workspace_list.setCurrentRow(i)
                self.logger.info(f"✅ 已自動選中: {project_id}")
                return
        
        # 如果找不到，選最後一項
        if self.workspace_list.count() > 0:
            self.workspace_list.setCurrentRow(self.workspace_list.count() - 1)

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

class WorkspaceDuplicateDialog(QDialog):
    """Workspace 複製命名對話框"""
    
    def __init__(self, source_name: str, source_id: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("複製 Workspace")
        self.setModal(True)
        self.setFixedSize(500, 280)
        
        self.setStyleSheet("""
            QLabel {
                font-size: 16px;
            }
            QLineEdit {
                font-size: 16px;
                padding: 5px;
                min-height: 35px;
            }
            QPushButton {
                font-size: 16px;
                font-weight: bold;
                min-height: 40px;
                border-radius: 5px;
            }
        """)
        
        self.new_name = ""
        self.new_id = ""
        
        self._setup_ui(source_name, source_id)
    
    def _setup_ui(self, source_name: str, source_id: str):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(25, 25, 25, 25)
        
        # 標題說明
        hint_label = QLabel(f"複製來源：{source_name} ({source_id})")
        hint_label.setStyleSheet("font-size: 14px; color: #666666;")
        main_layout.addWidget(hint_label)
        
        # 表單
        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        
        # 新專案名稱（預填 原名稱_copy）
        self.name_edit = QLineEdit()
        self.name_edit.setText(f"{source_name}_copy")
        self.name_edit.selectAll()  # 預設全選，方便直接輸入
        form_layout.addRow("新專案名稱:", self.name_edit)
        
        # 新專案 ID（預填 原ID_copy）
        self.id_edit = QLineEdit()
        self.id_edit.setText(f"{source_id}_copy")
        form_layout.addRow("新專案 ID:", self.id_edit)
        
        # 🆕 ID 說明提示
        id_hint = QLabel("⚠️ 專案 ID 將作為檔案名稱，請勿包含特殊字元")
        id_hint.setStyleSheet("font-size: 12px; color: #FF6600;")
        form_layout.addRow("", id_hint)
        
        main_layout.addLayout(form_layout)
        main_layout.addStretch()
        
        # 按鈕
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        
        confirm_btn = QPushButton("📋 確認複製")
        confirm_btn.setStyleSheet("background-color: #2196F3; color: white;")
        confirm_btn.clicked.connect(self._on_confirm)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("background-color: #f44336; color: white;")
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(confirm_btn)
        button_layout.addWidget(cancel_btn)
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)
        
        # 🆕 自動聚焦到名稱欄位
        self.name_edit.setFocus()
    
    def _on_confirm(self):
        """確認複製"""
        new_name = self.name_edit.text().strip()
        new_id = self.id_edit.text().strip()
        
        if not new_name:
            QMessageBox.warning(self, "錯誤", "請輸入新的專案名稱")
            self.name_edit.setFocus()
            return
        
        if not new_id:
            QMessageBox.warning(self, "錯誤", "請輸入新的專案 ID")
            self.id_edit.setFocus()
            return
        
        # 🆕 檢查 ID 是否含有非法字元（不能作為檔名的字元）
        import re
        if re.search(r'[\\/:*?"<>|]', new_id):
            QMessageBox.warning(
                self,
                "錯誤",
                "專案 ID 不能包含以下字元：\\ / : * ? \" < > |"
            )
            self.id_edit.setFocus()
            return
        
        self.new_name = new_name
        self.new_id = new_id
        self.accept()


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
        self.test_table.cellDoubleClicked.connect(self._on_test_double_clicked)
        # 在 setup_ui() 中，self.test_table 建立後加入：
        self.test_table.itemChanged.connect(self._on_table_item_changed)

        # 🆕 防重入旗標（避免 load_workspace_data 觸發 itemChanged 造成無限循環）
        self._is_loading_data = False

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
        """載入 Workspace 數據到 UI（根據 order 排序 + 順序欄位可編輯）"""
        # 🆕🆕🆕 設置防重入旗標，避免 setItem() 觸發 itemChanged callback
        self._is_loading_data = True
        
        try:
            self.project_name_edit.setText(self.workspace.project_name)
            self.project_id_edit.setText(self.workspace.project_id)
            self.version_edit.setText(self.workspace.version)
            self.description_edit.setPlainText(self.workspace.description)
            
            sorted_tests = sorted(self.workspace.drawing_sequence, key=lambda t: t.order)
            
            self.test_table.setRowCount(len(sorted_tests))
            
            for row, test in enumerate(sorted_tests):
                from PyQt5.QtWidgets import QCheckBox, QTableWidgetItem
                
                checkbox = QCheckBox()
                checkbox.setChecked(test.enabled)
                checkbox.setStyleSheet("margin-left: 50%; margin-right: 50%;")
                self.test_table.setCellWidget(row, 0, checkbox)
                
                order_item = QTableWidgetItem(str(test.order))
                order_item.setTextAlignment(Qt.AlignCenter)
                self.test_table.setItem(row, 1, order_item)
                
                type_item = QTableWidgetItem(test.drawing_type)
                type_item.setFlags(type_item.flags() & ~Qt.ItemIsEditable)
                self.test_table.setItem(row, 2, type_item)
                
                name_item = QTableWidgetItem(test.display_name)
                name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
                self.test_table.setItem(row, 3, name_item)
        
        finally:
            # 🆕🆕🆕 無論如何都要解除旗標
            self._is_loading_data = False

    
    def _on_table_item_changed(self, item):
        """
        🆕 表格內容變更時觸發（主要處理順序欄位的即時重排）
        
        防重入：load_workspace_data() 執行時設置 _is_loading_data = True
        避免 setItem() 觸發此 callback 造成無限循環
        """
        if self._is_loading_data:
            return  # 正在載入資料，忽略此事件
        
        # 只處理「順序」欄位（column 1）
        if item.column() != 1:
            return
        
        # 驗證輸入是否為有效整數
        try:
            new_order = int(item.text().strip())
        except ValueError:
            self.logger.warning(f"⚠️ 順序欄位輸入無效: '{item.text()}'，忽略重排")
            return
        
        self.logger.info(f"🔄 偵測到順序變更 (row={item.row()}, new_order={new_order})，觸發即時重排")
        
        # 同步所有 UI 資料到 workspace（包含剛修改的順序）
        self._sync_ui_to_workspace()
        
        # 重新載入並排序顯示（會根據新的 order 重排表格）
        self.load_workspace_data()

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
    
    def _on_test_double_clicked(self, row: int, column: int):
        """🆕 雙擊表格列直接編輯測驗"""
        self.logger.info(f"✏️ 雙擊編輯測驗: row={row}, column={column}")
        self._edit_test_at_row(row)

    def edit_test(self):
        """編輯選中的測驗（透過選單或按鈕觸發）"""
        current_row = self.test_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "錯誤", "請先選擇一個測驗")
            return
        self._edit_test_at_row(current_row)

    def _edit_test_at_row(self, row: int):
        """🆕 編輯指定 row 的測驗（雙擊和選單共用的核心邏輯）"""
        # 先同步 UI 數據（包含順序欄位的修改）
        self._sync_ui_to_workspace()
        
        if row >= len(self.workspace.drawing_sequence):
            self.logger.warning(f"⚠️ row={row} 超出範圍，drawing_sequence 長度={len(self.workspace.drawing_sequence)}")
            return
        
        test = self.workspace.drawing_sequence[row]
        self.logger.info(f"✏️ 開始編輯測驗: {test.display_name} (row={row})")
        
        editor = TestConfigEditorDialog(test, self)
        if editor.exec_() == QDialog.Accepted:
            self.logger.info(f"✅ 測驗已更新: {test.display_name}")
            self.load_workspace_data()  # 重新整理表格

    
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
        self.setFixedSize(600, 680)

        
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
        # 🆕 螢幕方向選擇
        self.screen_orientation_combo = QComboBox()
        self.screen_orientation_combo.addItem("橫向 (Landscape)", "landscape")
        self.screen_orientation_combo.addItem("直向 (Portrait)", "portrait")
        form_layout.addRow("副螢幕方向:", self.screen_orientation_combo)

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
        
        # 分隔標題
        instruction_label = QLabel("── 指導語檔案 ──")
        instruction_label.setStyleSheet("font-size: 14px; color: #888888;")
        form_layout.addRow(instruction_label)

        # 施測者指導語檔案
        experimenter_layout = QHBoxLayout()
        self.experimenter_file_edit = QLineEdit()
        self.experimenter_file_edit.setPlaceholderText("（未設定）")
        self.experimenter_file_edit.setReadOnly(True)
        experimenter_browse_btn = QPushButton("瀏覽...")
        experimenter_browse_btn.setFixedWidth(80)
        experimenter_browse_btn.setMinimumHeight(0)  # 覆蓋全域樣式的 min-height
        experimenter_browse_btn.setMaximumHeight(35)
        experimenter_browse_btn.clicked.connect(self._browse_experimenter_file)
        experimenter_clear_btn = QPushButton("清除")
        experimenter_clear_btn.setFixedWidth(60)
        experimenter_clear_btn.setMaximumHeight(35)
        experimenter_clear_btn.clicked.connect(lambda: self.experimenter_file_edit.clear())
        experimenter_layout.addWidget(self.experimenter_file_edit)
        experimenter_layout.addWidget(experimenter_browse_btn)
        experimenter_layout.addWidget(experimenter_clear_btn)
        form_layout.addRow("施測者指導語:", experimenter_layout)

        # 受試者指導語檔案
        participant_layout = QHBoxLayout()
        self.participant_file_edit = QLineEdit()
        self.participant_file_edit.setPlaceholderText("（未設定）")
        self.participant_file_edit.setReadOnly(True)
        participant_browse_btn = QPushButton("瀏覽...")
        participant_browse_btn.setFixedWidth(80)
        participant_browse_btn.setMaximumHeight(35)
        participant_browse_btn.clicked.connect(self._browse_participant_file)
        participant_clear_btn = QPushButton("清除")
        participant_clear_btn.setFixedWidth(60)
        participant_clear_btn.setMaximumHeight(35)
        participant_clear_btn.clicked.connect(lambda: self.participant_file_edit.clear())
        participant_layout.addWidget(self.participant_file_edit)
        participant_layout.addWidget(participant_browse_btn)
        participant_layout.addWidget(participant_clear_btn)
        form_layout.addRow("受試者指導語:", participant_layout)

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

    def _browse_experimenter_file(self):
        """瀏覽施測者指導語檔案"""
        path, _ = QFileDialog.getOpenFileName(
            self, "選擇施測者指導語檔案", "",
            "所有支援格式 (*.pdf *.txt *.png *.jpg *.jpeg *.bmp *.docx);;"
            "PDF 文件 (*.pdf);;"
            "文字檔 (*.txt);;"
            "圖片 (*.png *.jpg *.jpeg *.bmp);;"
            "Word 文件 (*.docx)"
        )
        if path:
            self.experimenter_file_edit.setText(path)

    def _browse_participant_file(self):
        """瀏覽受試者指導語檔案"""
        path, _ = QFileDialog.getOpenFileName(
            self, "選擇受試者指導語檔案", "",
            "所有支援格式 (*.pdf *.txt *.png *.jpg *.jpeg *.bmp *.docx);;"
            "PDF 文件 (*.pdf);;"
            "文字檔 (*.txt);;"
            "圖片 (*.png *.jpg *.jpeg *.bmp);;"
            "Word 文件 (*.docx)"
        )
        if path:
            self.participant_file_edit.setText(path)


    def load_test_data(self):
        """載入測驗數據到 UI"""
        self.drawing_type_edit.setText(self.test_config.drawing_type)
        self.display_name_edit.setText(self.test_config.display_name)
        self.order_spin.setCurrentText(str(self.test_config.order))
        # 🆕 載入螢幕方向
        orientation_index = self.screen_orientation_combo.findData(
            self.test_config.screen_orientation
        )
        if orientation_index >= 0:
            self.screen_orientation_combo.setCurrentIndex(orientation_index)

        
        self.pen_enabled_check.setChecked(self.test_config.toolbar.pen_enabled)
        self.eraser_enabled_check.setChecked(self.test_config.toolbar.eraser_enabled)
        self.color_picker_enabled_check.setChecked(self.test_config.toolbar.color_picker_enabled)
        
        mode_index = self.color_picker_mode_combo.findData(self.test_config.toolbar.color_picker_mode.value)
        if mode_index >= 0:
            self.color_picker_mode_combo.setCurrentIndex(mode_index)
        self.experimenter_file_edit.setText(
            self.test_config.instructions.experimenter_instruction_file
        )
        self.participant_file_edit.setText(
            self.test_config.instructions.participant_instruction_file
        )

    
    def save_test_config(self):
        """儲存測驗配置"""
        try:
            self.test_config.drawing_type = self.drawing_type_edit.text().strip()
            self.test_config.display_name = self.display_name_edit.text().strip()
            self.test_config.order = int(self.order_spin.currentText())
            # 🆕 儲存螢幕方向
            self.test_config.screen_orientation = self.screen_orientation_combo.currentData()

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
            # save_test_config() 中，self.accept() 前新增
            self.test_config.instructions.experimenter_instruction_file = \
                self.experimenter_file_edit.text().strip()
            self.test_config.instructions.participant_instruction_file = \
                self.participant_file_edit.text().strip()

            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"儲存失敗: {e}")


class SubjectInfoDialog(QDialog):
    """受試者資訊輸入對話框（🆕 新增姓名欄位）"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("受試者資訊")
        self.setModal(True)
        self.setFixedSize(600, 460)  # 🆕 高度從 400 增加到 460（多一個欄位）
        
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
        
        # 受試者編號
        self.subject_id_edit = QLineEdit()
        self.subject_id_edit.setPlaceholderText("例如: S001")
        layout.addRow("受試者編號:", self.subject_id_edit)
        
        # 🆕🆕🆕 新增姓名欄位
        self.subject_name_edit = QLineEdit()
        self.subject_name_edit.setPlaceholderText("例如: 陳大明")
        layout.addRow("姓名:", self.subject_name_edit)
        
        # 生日
        self.birth_date_edit = QDateEdit()
        self.birth_date_edit.setDate(QDate.currentDate().addYears(-25))
        self.birth_date_edit.setCalendarPopup(True)
        self.birth_date_edit.setDisplayFormat("yyyy-MM-dd")
        layout.addRow("西元生日:", self.birth_date_edit)
        
        # 性別
        self.gender_combo = QComboBox()
        self.gender_combo.addItems(["female", "male"])
        layout.addRow("性別:", self.gender_combo)
        
        # 按鈕
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
        
        # 🆕🆕🆕 新增姓名驗證
        subject_name = self.subject_name_edit.text().strip()
        if not subject_name:
            QMessageBox.warning(self, "錯誤", "請輸入受試者姓名")
            return
        
        birth_date = self.birth_date_edit.date().toString("yyyyMMdd")
        gender = self.gender_combo.currentText()
        
        # 🆕🆕🆕 收案時間（年月日_時間）
        session_datetime = datetime.now()
        session_date_str = session_datetime.strftime("%Y%m%d")      # 收案年月日
        session_time_str = session_datetime.strftime("%H%M%S")      # 當下時間24時制
        session_datetime_str = f"{session_date_str}_{session_time_str}"
        
        self.subject_info = {
            'subject_id': subject_id,
            'subject_name': subject_name,                           # 🆕 姓名
            'birth_date': birth_date,
            'gender': gender,
            # 🆕🆕🆕 第一層目錄：受試者ID_姓名_生日
            'subject_folder_name': f"{subject_id}_{subject_name}_{birth_date}",
            # 🆕🆕🆕 第二層目錄：受試者ID_姓名_收案年月日_時間
            'session_folder_name': f"{subject_id}_{subject_name}_{session_datetime_str}",
            # 🆕 向下相容（舊代碼使用 folder_name 的地方）
            'folder_name': f"{subject_id}_{subject_name}_{birth_date}",
        }
        
        self.accept()



class DrawingTypeDialog(QDialog):
    """繪畫類型選擇對話框 (🆕 只顯示已啟用的測驗)"""
    
    def __init__(self, drawing_counter: int, workspace: WorkspaceConfig, 
                canvas_ref=None, parent=None):  # 🆕 新增 canvas_ref
        super().__init__(parent)
        self.setWindowTitle("選擇繪畫類型")
        self.setModal(True)
        self.setFixedSize(550, 430)  # 🆕 高度從 350 增加到 430（多一個按鈕）
        
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
        self.canvas_ref = canvas_ref        # 🆕
        self._artwork_showing = False       # 🆕 展示狀態旗標
        self._artwork_window = None         # 🆕 展示視窗參考
        
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
        
        # 🆕 展示繪畫成品按鈕（藍色，獨立一行）
        self.show_artwork_button = QPushButton("🖼️ 展示繪畫成品")
        self.show_artwork_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-size: 20px;
                font-weight: bold;
                min-height: 60px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #90CAF9;
                color: #ffffff;
            }
        """)
        self.show_artwork_button.clicked.connect(self._toggle_artwork)
        # 🆕 若無 canvas_ref 則隱藏此按鈕
        if self.canvas_ref is None:
            self.show_artwork_button.hide()

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
        main_layout.addWidget(self.show_artwork_button)  # 🆕 展示按鈕在上
        main_layout.addLayout(button_layout)             # 開始/取消在下

        self.setLayout(main_layout)

    def _toggle_artwork(self):
        """🆕 切換展示/關閉繪畫成品"""
        logger = logging.getLogger('DrawingTypeDialog')  # 🔧 移到開頭
        if not self._artwork_showing:
            # ── 展示成品 ──
            if self.canvas_ref is not None:
                self._artwork_window = self.canvas_ref.show_artwork_display()
            self.show_artwork_button.setText("❌ 關閉成品")
            self.ok_button.setEnabled(False)
            self.cancel_button.setEnabled(False)
            self._artwork_showing = True
            logger.info("🖼️ 展示繪畫成品")
        else:
            # ── 關閉成品 ──
            if self.canvas_ref is not None:
                self.canvas_ref.hide_artwork_display()
            self._artwork_window = None
            self.show_artwork_button.setText("🖼️ 展示繪畫成品")
            self.ok_button.setEnabled(True)
            self.cancel_button.setEnabled(True)
            self._artwork_showing = False
            logger.info("❌ 關閉繪畫成品展示")

    def reject(self):
        """🆕 覆寫 reject，確保關閉對話框時也關閉展示視窗"""
        if self._artwork_showing and self.canvas_ref is not None:
            self.canvas_ref.hide_artwork_display()
            self._artwork_showing = False
        super().reject()


    def accept_input(self):
        drawing_type = self.drawing_type_combo.currentData()
        
        if not drawing_type:
            drawing_type = "DAP"
        
        current_time = datetime.now()
        # 🆕🆕🆕 第三層目錄格式：編號_繪畫類型_收案年月日_時間
        date_str = current_time.strftime("%Y%m%d")
        time_str = current_time.strftime("%H%M%S")
        datetime_str = f"{date_str}_{time_str}"
        
        self.drawing_info = {
            'drawing_type': drawing_type,
            'drawing_id': self.drawing_counter,
            'datetime_str': datetime_str,
            # 🆕🆕🆕 第三層目錄：編號_繪畫類型_收案年月日_時間
            'folder_name': f"{self.drawing_counter}_{drawing_type}_{datetime_str}"
        }
        
        self.accept()

class ParticipantInstructionDialog(QDialog):
    """受試者指導語對話框（支援 Qt 畫面旋轉）"""
    
    def __init__(self, instruction_file: str, drawing_type_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"指導語 — {drawing_type_name}")
        self.setModal(True)
        self.setWindowFlags(
            Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.logger = logging.getLogger('ParticipantInstructionDialog')
        self._rotation = 0  # 旋轉角度（0 或 -90）
        self._instruction_file = instruction_file
        self._drawing_type_name = drawing_type_name
        self._setup_ui(instruction_file, drawing_type_name)

    def set_rotation(self, angle: int):
        """
        設定旋轉角度並重建 UI
        必須在 showFullScreen() 之前呼叫
        
        Args:
            angle: 0 = 不旋轉，-90 = 逆時針 90°（直向）
        """
        self._rotation = angle

    def showFullScreen(self):
        """覆寫 showFullScreen，在顯示前根據旋轉角度重建 UI"""
        if self._rotation == -90:
            self._rebuild_for_portrait()
        super().showFullScreen()

    def _rebuild_for_portrait(self):
        """
        直向模式：用 QGraphicsView + QGraphicsProxyWidget 旋轉整個內容
        
        原理：
        1. 建立一個「內容容器」widget（橫向尺寸）
        2. 用 QGraphicsProxyWidget 把它放進 QGraphicsScene
        3. 對 scene 套用 -90° 旋轉
        4. 用 QGraphicsView 顯示，視覺上看起來是直向
        """
        from PyQt5.QtWidgets import (QGraphicsView, QGraphicsScene,
                                      QGraphicsProxyWidget, QSizePolicy)
        from PyQt5.QtCore import QRectF

        # ── 1. 取得螢幕尺寸 ──
        from PyQt5.QtWidgets import QDesktopWidget
        desktop = QDesktopWidget()
        # 找到對話框所在的螢幕
        screen_idx = desktop.screenNumber(self)
        if screen_idx < 0:
            screen_idx = 1 if desktop.screenCount() > 1 else 0
        screen = desktop.screenGeometry(screen_idx)
        screen_w = screen.width()   # 實體橫向長邊，例如 1920
        screen_h = screen.height()  # 實體橫向短邊，例如 1080

        # ── 2. 建立內容容器（邏輯尺寸 = 旋轉後的直向尺寸）──
        # 旋轉 -90° 後：邏輯寬 = screen_h，邏輯高 = screen_w
        content_w = screen_h   # 例如 1080（直向的寬）
        content_h = screen_w   # 例如 1920（直向的高）

        content_widget = QWidget()
        content_widget.setFixedSize(content_w, content_h)
        content_widget.setStyleSheet("background-color: white;")

        # ── 3. 在內容容器中建立 UI ──
        self._build_content_layout(content_widget, content_w, content_h)

        # ── 4. 建立 QGraphicsScene + QGraphicsProxyWidget ──
        scene = QGraphicsScene()
        proxy = QGraphicsProxyWidget()
        proxy.setWidget(content_widget)
        scene.addItem(proxy)

        # ── 5. 套用旋轉變換 ──
        # 旋轉 -90° 後，原本 (content_w x content_h) 的 widget
        # 視覺上變成 (content_h x content_w) = (screen_w x screen_h)
        proxy.setTransformOriginPoint(content_w / 2, content_h / 2)
        proxy.setRotation(-90)

        # ── 6. 設定 scene 範圍（旋轉後的視覺尺寸）──
        # 旋轉後視覺寬 = content_h = screen_w
        # 旋轉後視覺高 = content_w = screen_h
        scene.setSceneRect(
            -(content_h - content_w) / 2,   # x 偏移
            -(content_w - content_h) / 2,   # y 偏移
            content_h,                       # 視覺寬 = screen_w
            content_w                        # 視覺高 = screen_h
        )

        # ── 7. 建立 QGraphicsView 填滿整個對話框 ──
        view = QGraphicsView(scene)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setFrameShape(view.NoFrame)
        view.setStyleSheet("background-color: white; border: none;")
        view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # ── 8. 替換對話框的 layout ──
        old_layout = self.layout()
        if old_layout is not None:
            # 清空舊 layout
            while old_layout.count():
                item = old_layout.takeAt(0)
                if item.widget():
                    item.widget().setParent(None)
            import sip
            sip.delete(old_layout)

        new_layout = QVBoxLayout()
        new_layout.setContentsMargins(0, 0, 0, 0)
        new_layout.setSpacing(0)
        new_layout.addWidget(view)
        self.setLayout(new_layout)

        self.logger.info(
            f"✅ 直向指導語 UI 已重建: "
            f"content={content_w}x{content_h}, "
            f"visual={screen_w}x{screen_h}"
        )

    def _build_content_layout(self, parent_widget: QWidget,
                               content_w: int, content_h: int):
        """
        在指定的 parent_widget 中建立指導語 UI 內容
        
        Args:
            parent_widget: 要放置 UI 的容器
            content_w: 容器寬度
            content_h: 容器高度
        """
        layout = QVBoxLayout(parent_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)

        # 標題
        title_label = QLabel(f"【{self._drawing_type_name}】指導語")
        title_label.setStyleSheet(
            "font-size: 28px; font-weight: bold; color: #2196F3;"
        )
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # 內容區域
        content_widget = self._load_content(self._instruction_file)
        layout.addWidget(content_widget, stretch=1)

        # 確定按鈕
        confirm_btn = QPushButton("✅ 我已閱讀，開始繪畫")
        confirm_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 24px;
                font-weight: bold;
                min-height: 70px;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        confirm_btn.clicked.connect(self.accept)
        layout.addWidget(confirm_btn)

        parent_widget.setLayout(layout)

    def _setup_ui(self, instruction_file: str, drawing_type_name: str):
        """建立預設（橫向）UI"""
        main_layout = QVBoxLayout()
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(40, 40, 40, 40)
        self.setStyleSheet("background-color: white;")

        # 標題
        title_label = QLabel(f"【{drawing_type_name}】指導語")
        title_label.setStyleSheet(
            "font-size: 28px; font-weight: bold; color: #2196F3;"
        )
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        # 內容區域
        content_widget = self._load_content(instruction_file)
        main_layout.addWidget(content_widget, stretch=1)

        # 確定按鈕
        confirm_btn = QPushButton("✅ 我已閱讀，開始繪畫")
        confirm_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 24px;
                font-weight: bold;
                min-height: 70px;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        confirm_btn.clicked.connect(self.accept)
        main_layout.addWidget(confirm_btn)

        self.setLayout(main_layout)

    def _load_content(self, instruction_file: str) -> QWidget:
        """根據檔案類型載入內容（不變）"""
        from PyQt5.QtWidgets import QScrollArea, QTextEdit, QLabel
        from PyQt5.QtGui import QPixmap

        ext = Path(instruction_file).suffix.lower() if instruction_file else ''

        if ext in ('.png', '.jpg', '.jpeg', '.bmp', '.gif'):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            img_label = QLabel()
            img_label.setAlignment(Qt.AlignCenter)
            pixmap = QPixmap(instruction_file)
            if not pixmap.isNull():
                img_label.setPixmap(
                    pixmap.scaled(1200, 700, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
            else:
                img_label.setText(f"⚠️ 無法載入圖片：{instruction_file}")
                img_label.setStyleSheet("font-size: 18px; color: red;")
            scroll.setWidget(img_label)
            return scroll

        elif ext == '.txt':
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setStyleSheet("font-size: 20px; line-height: 1.8;")
            try:
                with open(instruction_file, 'r', encoding='utf-8') as f:
                    text_edit.setPlainText(f.read())
            except Exception as e:
                text_edit.setPlainText(f"⚠️ 無法讀取檔案：{e}")
            scroll.setWidget(text_edit)
            return scroll

        else:
            label = QLabel(
                f"📄 指導語檔案已在另一個視窗開啟\n\n"
                f"檔案：{Path(instruction_file).name}\n\n"
                f"請閱讀完畢後按下方按鈕開始繪畫"
            )
            label.setStyleSheet("font-size: 20px; color: #333333;")
            label.setAlignment(Qt.AlignCenter)
            label.setWordWrap(True)
            return label


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
                'screen_orientation': test.screen_orientation,  # ✅ 新增
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
        
        # ✅ 新增：副螢幕方向
        orientation_text = "直向 (Portrait)" if test.screen_orientation == "portrait" else "橫向 (Landscape)"
        lines.append(f"  副螢幕方向: {orientation_text}")
        
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
