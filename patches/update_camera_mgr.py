import sys

cam_mgr_path = r"C:\Users\mi\Documents\AgnesCode\projects\毛孩子翻译官\server\camera\camera_manager.py"

with open(cam_mgr_path, "r", encoding="utf-8") as f:
    content = f.read()

analysis_methods = """
    # 持续分析方法
    _analyzing = False
    _analysis_thread = None
    _analysis_interval = 1.0
    _frames_analyzed = 0
    _current_behavior = None

    def start_analysis(self, interval: float = 1.0):
        self._analyzing = True
        self._analysis_interval = interval
        if self._analysis_thread is None or not self._analysis_thread.is_alive():
            import threading
            self._analysis_thread = threading.Thread(target=self._analysis_loop, daemon=True)
            self._analysis_thread.start()
            logger.info(f"[{self.name}] 持续分析已启动")

    def stop_analysis(self):
        self._analyzing = False
        logger.info(f"[{self.name}] 持续分析已停止")

    def is_analyzing(self) -> bool:
        return self._analyzing

    @property
    def frames_analyzed(self) -> int:
        return self._frames_analyzed

    def get_current_behavior(self):
        return self._current_behavior

    def _analysis_loop(self):
        import time
        while self._analyzing:
            frame = self.get_latest_frame()
            if frame is not None:
                try:
                    result = self._detect_behavior(frame)
                    if result:
                        self._current_behavior = result
                        self._frames_analyzed += 1
                except Exception as e:
                    logger.warning(f"[{self.name}] 分析失败: {e}")
            time.sleep(self._analysis_interval)

    def _detect_behavior(self, frame):
        return None
"""

if "start_analysis" not in content:
    with open(cam_mgr_path, "w", encoding="utf-8") as f:
        f.write(content.rstrip() + analysis_methods)
    print("camera_manager.py 已更新")
else:
    print("分析方法已存在")

