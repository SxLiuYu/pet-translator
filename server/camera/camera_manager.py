"""
camera/camera_manager.py
摄像头管理器
支持三种接入方式:
  1. RTSP 网络摄像头 (小米/萤石/Hikvision 等家用摄像头)
  2. USB 本地摄像头 (OpenCV VideoCapture)
  3. ESP32-CAM (HTTP 快照拉取)
"""
import io
import logging
import threading
import time
from abc import ABC, abstractmethod
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger("pet_translator.camera")


class CameraFrame:
    """摄像头帧数据封装"""
    def __init__(self, image: np.ndarray, timestamp: float, source: str):
        self.image = image          # BGR uint8 ndarray
        self.timestamp = timestamp  # 时间戳
        self.source = source        # 来源标识

    @property
    def jpeg_bytes(self) -> bytes:
        """编码为 JPEG 字节流 (用于 Web/WebSocket 推送)"""
        success, buf = cv2.imencode(".jpg", self.image, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return buf.tobytes() if success else b""

    @property
    def shape(self):
        return self.image.shape


# ========== 三种摄像头接入实现 ==========

class BaseCamera(ABC):
    """摄像头抽象基类"""
    def __init__(self, name: str):
        self.name = name
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._latest_frame: Optional[CameraFrame] = None
        self._lock = threading.Lock()
        self._fps = 0.0

    @abstractmethod
    def _open(self) -> bool:
        """打开摄像头连接，返回是否成功"""

    @abstractmethod
    def _read_frame(self) -> Optional[np.ndarray]:
        """读取一帧，返回 ndarray 或 None"""

    @abstractmethod
    def _release(self):
        """释放摄像头资源"""

    def start(self):
        """启动后台采集线程"""
        if self._running:
            return
        if not self._open():
            raise RuntimeError(f"无法打开摄像头: {self.name}")
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info(f"📷 摄像头 [{self.name}] 已启动")

    def stop(self):
        """停止采集"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        self._release()
        logger.info(f"📷 摄像头 [{self.name}] 已停止")

    def get_latest_frame(self) -> Optional[CameraFrame]:
        """获取最新帧 (线程安全)"""
        with self._lock:
            return self._latest_frame

    def get_fps(self) -> float:
        return self._fps

    def _loop(self):
        """后台采集循环"""
        frame_count = 0
        fps_start = time.time()
        while self._running:
            frame = self._read_frame()
            if frame is not None:
                cf = CameraFrame(frame, time.time(), self.name)
                with self._lock:
                    self._latest_frame = cf
                frame_count += 1

            # 每秒更新一次 FPS
            now = time.time()
            if now - fps_start >= 1.0:
                self._fps = frame_count / (now - fps_start)
                frame_count = 0
                fps_start = now


class RTSPCamera(BaseCamera):
    """
    RTSP 网络摄像头
    支持小米、萤石、海康威视、TP-Link 等几乎所有家用 IP 摄像头

    配置示例:
      小米摄像头: rtsp://admin:password@192.168.1.100:554/h264Preview_01_main
      萤石摄像头: rtsp://admin:password@192.168.1.100:554/Streaming/Channels/101
    """
    def __init__(self, rtsp_url: str, name: str = "rtsp_cam"):
        super().__init__(name)
        self.rtsp_url = rtsp_url
        self._cap: Optional[cv2.VideoCapture] = None

    def _open(self) -> bool:
        # FFMPEG 后端 + TCP 传输 (RTSP 更稳定)
        os_env = self._get_ffmpeg_opts()
        import os
        for k, v in os_env.items():
            os.environ[k] = v

        self._cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
        # 设置缓冲区大小，降低延迟
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._cap.set(cv2.CAP_PROP_FPS, 15)
        return self._cap.isOpened()

    def _get_ffmpeg_opts(self) -> dict:
        return {
            "OPENCV_FFMPEG_CAPTURE_OPTIONS": "rtsp_transport;tcp",
            "OPENCV_FFMPEG_READ_OPTIONS": "rtsp_transport;tcp|analyzeduration;1000000|probesize;32768",
        }

    def _read_frame(self) -> Optional[np.ndarray]:
        if self._cap is None:
            return None
        ret, frame = self._cap.read()
        if not ret:
            logger.warning(f"[{self.name}] 读取帧失败，尝试重连...")
            self._cap.release()
            time.sleep(1)
            self._open()
            return None
        return frame

    def _release(self):
        if self._cap:
            self._cap.release()
            self._cap = None


class USBCamera(BaseCamera):
    """
    USB 本地摄像头
    直接连接在运行服务器的电脑上
    """
    def __init__(self, device_index: int = 0, name: str = "usb_cam"):
        super().__init__(name)
        self.device_index = device_index
        self._cap: Optional[cv2.VideoCapture] = None

    def _open(self) -> bool:
        # 尝试 DirectShow (Windows) / V4L2 (Linux)
        import platform
        if platform.system() == "Windows":
            self._cap = cv2.VideoCapture(self.device_index, cv2.CAP_DSHOW)
        else:
            self._cap = cv2.VideoCapture(self.device_index)

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self._cap.set(cv2.CAP_PROP_FPS, 15)
        return self._cap.isOpened()

    def _read_frame(self) -> Optional[np.ndarray]:
        if self._cap is None:
            return None
        ret, frame = self._cap.read()
        if not ret:
            logger.warning(f"[{self.name}] USB 摄像头读取失败")
            return None
        return frame

    def _release(self):
        if self._cap:
            self._cap.release()
            self._cap = None


class ESP32CAMCamera(BaseCamera):
    """
    ESP32-CAM (AI-Thinker) 摄像头
    通过 HTTP 快照接口拉取图片

    接线: ESP32-CAM 烧录 camera_web_server 示例固件
    访问: http://192.168.1.100:81/stream (视频流) 或 /capture (单帧)
    """
    def __init__(self, host: str, port: int = 81, name: str = "esp32cam"):
        super().__init__(name)
        self.base_url = f"http://{host}:{port}"
        self._session = None

    def _open(self) -> bool:
        try:
            import requests
            self._session = requests.Session()
            # 测试连接
            resp = self._session.get(f"{self.base_url}/capture", timeout=5)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"[{self.name}] ESP32-CAM 连接失败: {e}")
            return False

    def _read_frame(self) -> Optional[np.ndarray]:
        if self._session is None:
            return None
        try:
            resp = self._session.get(f"{self.base_url}/capture", timeout=3)
            if resp.status_code == 200:
                arr = np.frombuffer(resp.content, dtype=np.uint8)
                frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                return frame
        except Exception as e:
            logger.debug(f"[{self.name}] 抓帧失败: {e}")
        return None

    def _release(self):
        if self._session:
            self._session.close()
            self._session = None


# ========== 摄像头管理器 (工厂 + 路由) ==========

class CameraManager:
    """
    统一管理所有摄像头源
    支持多摄像头同时运行，按 source_name 索引
    """

    def __init__(self):
        self._cameras: dict[str, BaseCamera] = {}

    def register_rtsp(self, name: str, rtsp_url: str) -> RTSPCamera:
        cam = RTSPCamera(rtsp_url=rtsp_url, name=name)
        self._cameras[name] = cam
        logger.info(f"📷 注册 RTSP 摄像头 [{name}]: {rtsp_url}")
        return cam

    def register_usb(self, name: str, device_index: int = 0) -> USBCamera:
        cam = USBCamera(device_index=device_index, name=name)
        self._cameras[name] = cam
        logger.info(f"📷 注册 USB 摄像头 [{name}]: /dev/video{device_index}")
        return cam

    def register_esp32cam(self, name: str, host: str, port: int = 81) -> ESP32CAMCamera:
        cam = ESP32CAMCamera(host=host, port=port, name=name)
        self._cameras[name] = cam
        logger.info(f"📷 注册 ESP32-CAM [{name}]: {host}:{port}")
        return cam

    def get(self, name: str) -> Optional[BaseCamera]:
        return self._cameras.get(name)

    def get_frame(self, name: str) -> Optional[CameraFrame]:
        cam = self._cameras.get(name)
        if cam:
            return cam.get_latest_frame()
        return None

    def start_all(self):
        for name, cam in self._cameras.items():
            try:
                cam.start()
            except Exception as e:
                logger.error(f"❌ 摄像头 [{name}] 启动失败: {e}")

    def stop_all(self):
        for cam in self._cameras.values():
            try:
                cam.stop()
            except Exception:
                pass

    def status(self) -> dict:
        result = {}
        for name, cam in self._cameras.items():
            frame = cam.get_latest_frame()
            result[name] = {
                "running": cam._running,
                "fps": round(cam.get_fps(), 1),
                "has_frame": frame is not None,
                "source": cam.name,
            }
        return result


# 全局单例
_manager: Optional[CameraManager] = None

def get_camera_manager() -> CameraManager:
    global _manager
    if _manager is None:
        _manager = CameraManager()
    return _manager
