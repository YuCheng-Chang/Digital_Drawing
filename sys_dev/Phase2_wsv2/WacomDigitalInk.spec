# -*- mode: python ; coding: utf-8 -*-

import PyInstaller.config
import os
import shutil
PyInstaller.config.CONF['distpath'] = r'G:\我的雲端硬碟\gsn984309.eed06@nctu.edu.tw 2022-09-14 12 20\Documents\研究助理\數位繪圖開發\Wacom\dist'
PyInstaller.config.CONF['workpath'] = r'G:\我的雲端硬碟\gsn984309.eed06@nctu.edu.tw 2022-09-14 12 20\Documents\研究助理\數位繪圖開發\Wacom\build'
# ✅ 確保目標資料夾存在（PyInstaller 不會自動建立）
os.makedirs(PyInstaller.config.CONF['distpath'], exist_ok=True)
os.makedirs(PyInstaller.config.CONF['workpath'],  exist_ok=True)
block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # ❌ 移除這些 .py 檔案，它們應該被編譯進 .exe
        # 只有資源檔案（如 .json, .png, .txt）才需要放在 datas
    ],
    hiddenimports=[
        # PyQt5 相關
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.sip',
        
        # 你的自定義模組
        'InkProcessingSystemMainController',
        'Config',
        'DigitalInkDataStructure',
        'EraserTool',
        'PointProcessor',
        'FeatureCalculator',
        'BufferManager',
        'RawDataCollector',
        'LSLStreamManager',
        'LSLDataRecorder',
        'LSLIntegration',
        'StrokeDetector',
        'SubjectInfoDialog',
        
        # 常用科學計算庫
        'numpy',
        'numpy.core',
        'numpy.core._methods',
        'numpy.lib',
        'numpy.lib.format',
        'scipy',
        'scipy.signal',
        'scipy.interpolate',
        'scipy.stats',
        'scipy.stats._sobol',
        'scipy.stats._qmc',
        'scipy.stats._multicomp',
        
        # importlib 相關
        'importlib',
        'importlib.resources',
        'importlib.metadata',
        'importlib._bootstrap',
        'importlib._bootstrap_external',
        'importlib.abc',
        
        # LSL 相關
        'pylsl',
        
        # 標準庫
        'logging',
        'datetime',
        'time',
        'sys',
        'os',
        'collections',
        'enum',
        'dataclasses',  # 🆕 如果你使用了 dataclass
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的大型模組
        'matplotlib',
        'pandas',
        'tkinter',
        'IPython',
        'jupyter',
        'torch',
        'torchvision',
        'torchaudio',
        'tensorflow',
        'transformers',
        'sklearn',
        'cv2',
        'PIL',
        'lxml',
        'jinja2',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='BMLDigitalDrawing',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
# ── 自動清理當前目錄下的殘留 build/ 和 dist/ ──


_spec_dir = os.path.dirname(os.path.abspath(SPEC))  # .spec 檔案所在目錄

for _folder in ('build', 'dist'):
    _path = os.path.join(_spec_dir, _folder)
    if os.path.exists(_path):
        shutil.rmtree(_path)
        print(f'🧹 已清除殘留資料夾: {_path}')
