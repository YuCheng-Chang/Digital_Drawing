# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['test_wacom_with_system.py'],
    pathex=[],
    binaries=[],
    datas=[
        # 包含所有你的 Python 模組檔案
        ('Config.py', '.'),
        ('DigitalInkDataStructure.py', '.'),
        ('InkProcessingSystemMainController.py', '.'),
        ('PointProcessor.py', '.'),
        ('FeatureCalculator.py', '.'),
        ('BufferManager.py', '.'),
        ('RawDataCollector.py', '.'),
        ('LSLStreamManager.py', '.'),
        ('LSLDataRecorder.py', '.'),
        ('LSLIntegration.py', '.'),
        ('StrokeDetector.py', '.'),
        ('reconstruct.py', '.'),
        ('EraserTool.py', '.'),
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
        'reconstruct',
        
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
        
        # ← 關鍵修復：添加 importlib 相關模組
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
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的大型模組以減小檔案大小
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
    name='WacomDigitalInk',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)