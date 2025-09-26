def test_system_without_hardware():
  """
  不需要實際硬體設備的測試版本
  使用模擬數據來測試系統功能
  """
  
  # 創建配置
  config = ProcessingConfig(
      device_type="simulator",  # 使用模擬器
      target_sampling_rate=100,
      smoothing_enabled=True,
      feature_types=['basic', 'kinematic']
  )
  
  # 創建系統實例
  ink_system = InkProcessingSystem(config)
  
  # 模擬設備配置
  device_config = {
      'device_type': 'simulator',
      'simulate_writing': True,
      'simulation_duration': 30,  # 模擬30秒的書寫
      'strokes_per_minute': 10    # 每分鐘10個筆劃
  }
  
  print("=== 測試墨水處理系統 (模擬模式) ===")
  
  # 統計變數
  stroke_count = 0
  feature_count = 0
  
  # 回調函數
  def on_stroke_completed(data):
      nonlocal stroke_count
      stroke_count += 1
      stroke = data['stroke']
      print(f"✓ 筆劃 {stroke_count} 完成: {len(stroke.points)} 個點")
  
  def on_features_calculated(data):
      nonlocal feature_count
      feature_count += 1
      features = data['features']
      print(f"✓ 特徵計算完成 (筆劃 {feature_count}): {len(features)} 個特徵")
      
      # 顯示一些特徵值
      if 'basic' in features:
          basic_features = features['basic']
          print(f"  - 基本特徵: 長度={basic_features.get('length', 0):.2f}, "
                f"持續時間={basic_features.get('duration', 0):.3f}s")
  
  def on_status_update(data):
      if data['status'] == 'processing_update':
          stats = data['statistics']
          print(f"📊 狀態更新: {stats['total_strokes']} 筆劃, "
                f"{stats['total_features']} 特徵, "
                f"{stats['raw_points_per_second']:.1f} 點/秒")
  
  def on_error(data):
      print(f"❌ 錯誤: {data['error_type']} - {data['message']}")
  
  # 註冊回調
  ink_system.register_callback('on_stroke_completed', on_stroke_completed)
  ink_system.register_callback('on_features_calculated', on_features_calculated)
  ink_system.register_callback('on_status_update', on_status_update)
  ink_system.register_callback('on_error', on_error)
  
  # 初始化系統
  print("🔧 初始化系統...")
  if not ink_system.initialize(device_config):
      print("❌ 系統初始化失敗")
      return
  
  print("✅ 系統初始化成功")
  
  # 開始處理
  print("🚀 開始處理 (模擬30秒書寫)...")
  if ink_system.start_processing():
      try:
          # 運行30秒
          for i in range(30):
              time.sleep(1)
              if i % 5 == 0:
                  print(f"⏱️  運行中... {i+1}/30 秒")
          
          print("\n📈 最終統計:")
          stats = ink_system.get_processing_statistics()
          print(f"  - 總原始點數: {stats['total_raw_points']}")
          print(f"  - 總處理點數: {stats['total_processed_points']}")
          print(f"  - 總筆劃數: {stats['total_strokes']}")
          print(f"  - 總特徵數: {stats['total_features']}")
          print(f"  - 平均採樣率: {stats['raw_points_per_second']:.1f} 點/秒")
          print(f"  - 筆劃完成率: {stats['strokes_per_minute']:.1f} 筆劃/分鐘")
          
      except KeyboardInterrupt:
          print("\n⚠️  使用者中斷")
      
      finally:
          print("🛑 停止處理...")
          ink_system.stop_processing()
  
  else:
      print("❌ 無法開始處理")
  
  # 關閉系統
  print("🔒 關閉系統...")
  ink_system.shutdown()
  print("✅ 測試完成")

# ===== 簡化的互動式測試 =====

def interactive_test():
  """
  互動式測試 - 讓你選擇測試模式
  """
  print("=== 數位墨水處理系統測試 ===")
  print("請選擇測試模式:")
  print("1. 模擬模式 (不需要硬體)")
  print("2. 實際硬體模式 (需要 Wacom 或觸控設備)")
  print("3. 查看系統配置")
  
  choice = input("請輸入選擇 (1-3): ").strip()
  
  if choice == "1":
      print("\n🎯 執行模擬模式測試...")
      test_system_without_hardware()
  
  elif choice == "2":
      print("\n🎯 執行硬體模式測試...")
      device_type = input("請輸入設備類型 (wacom/touch/mouse): ").strip().lower()
      if device_type in ['wacom', 'touch', 'mouse']:
          basic_usage_example_with_device(device_type)
      else:
          print("❌ 不支援的設備類型")
  
  elif choice == "3":
      print("\n📋 系統配置資訊:")
      config = ProcessingConfig()
      print(f"  - 預設設備類型: {config.device_type}")
      print(f"  - 目標採樣率: {config.target_sampling_rate} Hz")
      print(f"  - 平滑化: {'啟用' if config.smoothing_enabled else '停用'}")
      print(f"  - 特徵類型: {', '.join(config.feature_types)}")
      print(f"  - 筆劃超時: {config.stroke_timeout} 秒")
  
  else:
      print("❌ 無效選擇")

def basic_usage_example_with_device(device_type: str):
  """
  指定設備類型的基本使用範例
  """
  config = ProcessingConfig(
      device_type=device_type,
      target_sampling_rate=200 if device_type == 'wacom' else 100,
      smoothing_enabled=True,
      feature_types=['basic', 'kinematic', 'pressure'] if device_type == 'wacom' else ['basic', 'kinematic']
  )
  
  ink_system = InkProcessingSystem(config)
  
  # 根據設備類型設定配置
  if device_type == 'wacom':
      device_config = {
          'device_type': 'wacom',
          'device_path': '/dev/input/wacom',
          'sampling_rate': 200
      }
  elif device_type == 'touch':
      device_config = {
          'device_type': 'touch',
          'device_path': '/dev/input/touchscreen',
          'sampling_rate': 100
      }
  else:  # mouse
      device_config = {
          'device_type': 'mouse',
          'sampling_rate': 100
      }
  
  print(f"🔧 初始化 {device_type.upper()} 設備...")
  
  if not ink_system.initialize(device_config):
      print(f"❌ {device_type.upper()} 設備初始化失敗")
      print("可能原因:")
      print("  - 設備未連接")
      print("  - 驅動程式問題")
      print("  - 權限不足")
      return
  
  # ... 其餘處理邏輯類似 basic_usage_example()

# ===== 執行建議 =====

if __name__ == "__main__":
  # 推薦的執行方式
  interactive_test()