# -*- mode: python ; coding: utf-8 -*-

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
    upx=False,  # 🔧 建議設為 False，避免壓縮問題
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 🔧 開發階段建議 True，可以看到錯誤訊息
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 🆕 如果有圖示可以加上，例如 'icon.ico'
)
