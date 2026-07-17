"""
camera/behavior_detector.py
视觉行为检测器 (YOLOv8)
检测宠物姿态、动作，识别: 拆家、跑酷、躺卧、站立、打架等
与声纹结果融合，输出更准确的行为判断
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict

import numpy as np

logger = logging.getLogger("pet_translator.vision")


@dataclass
class Detection:
    """单次检测结果"""
    class_name: str       # "dog", "cat", "person"...
    confidence: float
    bbox: List[int]       # [x1, y1, x2, y2]
    track_id: Optional[int] = None


@dataclass
class VisualBehavior:
    """视觉行为分析结果"""
    timestamp: float
    detections: List[Detection] = field(default_factory=list)
    behavior: str = "unknown"           # 行为标签
    confidence: float = 0.0
    activity_level: str = "low"         # low / medium / high
    is_destructive: bool = False        # 是否拆家行为
    description: str = ""
    annotated_image: Optional[bytes] = None  # 带标注的 JPEG


class BehaviorDetector:
    """
    YOLOv8 宠物行为检测器

    检测能力:
    - 动物检测: dog, cat (COCO 预训练)
    - 姿态估计: 关键点检测 (可选，需要 yolov8-pose)
    - 行为分类: 结合时序信息判断行为

    行为标签映射:
      dog bark + 狗站立/前爪上抬 → 吠叫 (确认)
      cat 高速移动 + 猫声纹 → 跑酷
      狗/猫 长时间啃咬物体 → 拆家
      狗/猫 静止/躺卧 + 呼噜声 → 休息
    """

    # COCO 数据集宠物类别
    PET_CLASSES = {16: "bird", 17: "cat", 18: "dog"}

    # 物体类别 (可能与宠物互动)
    OBJECT_CLASSES = {0: "person", 39: "bottle", 41: "cup", 56: "chair",
                      57: "couch", 58: "potted plant", 63: "laptop",
                      67: "cell phone", 73: "book", 76: "scissors"}

    # 可能被拆的物品
    CHEW_TARGETS = {39: "bottle", 41: "cup", 73: "book", 67: "cell phone",
                    76: "scissors", 56: "chair", 57: "couch"}

    def __init__(self, model_size: str = "yolov8n.pt", conf_threshold: float = 0.5):
        self.model_size = model_size
        self.conf_threshold = conf_threshold
        self.model = None
        self._tracker: Optional[Dict[int, List[Detection]]] = {}
        self._load_model()

    def _load_model(self):
        """加载 YOLOv8 模型"""
        try:
            from ultralytics import YOLO
            self.model = YOLO(self.model_size)
            logger.info(f"✅ YOLOv8 模型加载成功: {self.model_size}")
        except ImportError:
            logger.warning("⚠️ 未安装 ultralytics，视觉检测不可用 (pip install ultralytics)")
        except Exception as e:
            logger.error(f"❌ YOLOv8 加载失败: {e}")
            self.model = None

    def detect(self, frame: np.ndarray, track_history: int = 5) -> VisualBehavior:
        """
        对单帧图像进行行为检测

        Args:
            frame: BGR 图像 ndarray
            track_history: 用于运动分析的历史帧数

        Returns:
            VisualBehavior 分析结果
        """
        ts = time.time()

        if self.model is None:
            return VisualBehavior(timestamp=ts, description="模型未加载")

        # 推理
        results = self.model.predict(
            frame,
            conf=self.conf_threshold,
            verbose=False,
            classes=list(self.PET_CLASSES.keys()) + list(self.OBJECT_CLASSES.keys()),
        )

        if not results:
            return VisualBehavior(timestamp=ts)

        r = results[0]
        detections = self._parse_results(r)
        behavior, confidence, activity, is_destructive, desc = self._analyze_behavior(detections)

        # 生成标注图
        annotated = self._draw_annotations(frame, detections, behavior)

        return VisualBehavior(
            timestamp=ts,
            detections=detections,
            behavior=behavior,
            confidence=confidence,
            activity_level=activity,
            is_destructive=is_destructive,
            description=desc,
            annotated_image=annotated,
        )

    def _parse_results(self, result) -> List[Detection]:
        """解析 YOLO 输出"""
        detections = []
        if result.boxes is None or len(result.boxes) == 0:
            return detections

        boxes = result.boxes.xyxy.cpu().numpy()
        confs = result.boxes.conf.cpu().numpy()
        cls_ids = result.boxes.cls.cpu().numpy().astype(int)

        for i, (box, conf, cls_id) in enumerate(zip(boxes, confs, cls_ids)):
            detections.append(Detection(
                class_name=result.names.get(int(cls_id), str(cls_id)),
                confidence=float(conf),
                bbox=[int(v) for v in box[:4]],
                track_id=i,  # TODO: 接入 DeepSORT/BT-Tracker
            ))
        return detections

    def _analyze_behavior(self, detections: List[Detection]) -> tuple:
        """
        根据检测结果推断行为
        返回: (behavior_label, confidence, activity_level, is_destructive, description)
        """
        pet_detections = [d for d in detections if d.class_name in ("dog", "cat")]
        obj_detections = [d for d in detections if d.class_id is not None
                          and d.class_id in self.CHEW_TARGETS]

        if not pet_detections:
            return "no_pet_detected", 0.0, "low", False, "画面中未检测到宠物"

        pet = pet_detections[0]
        pet_name = pet.class_name  # "dog" / "cat"
        pet_conf = pet.confidence

        # 检查拆家: 宠物 bounding box 与可被啃咬物体的 bbox 重叠
        is_destructive = False
        for obj in obj_detections:
            if self._bbox_overlaps(pet.bbox, obj.bbox, threshold=0.2):
                is_destructive = True
                break

        # 行为推断 (简化版，实际需要时序分析)
        bbox = pet.bbox
        area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
        aspect_ratio = (bbox[2] - bbox[0]) / max(bbox[3] - bbox[1], 1)

        if is_destructive:
            behavior = "拆家"
            activity = "high"
            desc = f"检测到 {pet_name} 正在接触可能被啃咬的物品！"
            return behavior, pet_conf, activity, True, desc

        if area > 50000:
            # 画面中占比大 → 靠近镜头
            if aspect_ratio > 1.3:
                behavior = "站立/跳跃"
                activity = "medium"
            else:
                behavior = "躺卧/趴着"
                activity = "low"
        elif area > 20000:
            behavior = "走动"
            activity = "medium"
        else:
            behavior = "跑动/跑酷"
            activity = "high"

        desc = f"检测到 {pet_name}，{behavior}，置信度 {pet_conf:.0%}"
        return behavior, pet_conf, activity, is_destructive, desc

    def _bbox_overlaps(self, a: list, b: list, threshold: float = 0.2) -> bool:
        """检测两个 bounding box 是否有足够重叠"""
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)
        if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
            return False
        inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
        a_area = (ax2 - ax1) * (ay2 - ay1)
        return inter_area / a_area > threshold

    def _draw_annotations(self, frame: np.ndarray, detections: List[Detection], label: str) -> bytes:
        """在帧上绘制检测框和标签，返回 JPEG 字节"""
        COLORS = {
            "dog": (0, 165, 255),    # 橙色
            "cat": (255, 0, 255),    # 紫色
            "person": (0, 255, 0),   # 绿色
        }

        for det in detections:
            color = COLORS.get(det.class_name, (255, 255, 0))
            x1, y1, x2, y2 = det.bbox
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            text = f"{det.class_name} {det.confidence:.0%}"
            cv2.putText(frame, text, (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        # 行为标签
        if label and label != "no_pet_detected":
            cv2.putText(frame, f"Behavior: {label}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        # 拆家警告红色标记
        if any(d.class_name in ("dog", "cat") and d.class_id in self.CHEW_TARGETS
               for d in detections):
            cv2.putText(frame, "WARNING: DESTRUCTIVE", (10, frame.shape[0] - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        success, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        return buf.tobytes() if success else b""
