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

import cv2
import numpy as np

logger = logging.getLogger("pet_translator.vision")


@dataclass
class Detection:
    """单次检测结果"""
    class_name: str       # "dog", "cat", "person"...
    confidence: float
    bbox: List[int]       # [x1, y1, x2, y2]
    class_id: Optional[int] = None
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
    skipped: bool = True                # 是否跳过（无运动）
    inference_ms: float = 0.0           # 推理耗时
    motion_detected: bool = False       # 是否检测到运动
    clip_used: bool = False             # 是否使用 CLIP
    clip_confidence: float = 0.0        # CLIP 置信度


# ========== CLIP 零样本行为分类器 (可选) ==========

# 行为描述提示词 (CLIP 零样本分类用)
BEHAVIOR_PROMPTS = {
    "dog": {
        "躺卧/睡觉": "a dog sleeping peacefully curled up",
        "坐着休息": "a dog sitting calmly and relaxed",
        "站立/眺望": "a dog standing still looking around",
        "走动": "a dog walking slowly across the room",
        "跑动/跑酷": "a dog running energetically and playing",
        "跳跃/扑腾": "a dog jumping up excitedly",
        "扒拉/啃咬": "a dog chewing on furniture or objects with its mouth",
        "玩耍": "a dog playing with a toy happily",
        "进食/喝水": "a dog eating food or drinking water",
        "舔舐/梳理": "a dog licking itself or grooming",
    },
    "cat": {
        "躺卧/睡觉": "a cat sleeping peacefully curled up in a ball",
        "坐着/舔毛": "a cat sitting calmly and grooming itself",
        "站立/眺望": "a cat standing still looking out a window",
        "走动": "a cat walking slowly and gracefully",
        "跑动/跑酷": "a cat running around energetically and playing",
        "跳跃": "a cat jumping up onto furniture",
        "抓挠/磨爪": "a cat scratching furniture or scratching post",
        "玩耍": "a cat playing with a toy or object",
        "进食/喝水": "a cat eating food or drinking water",
        "躲藏": "a cat hiding under furniture or in a small space",
    },
}

# 英文提示词 → 中文行为标签映射
BEHAVIOR_LABEL_MAP = {}
for species, prompts in BEHAVIOR_PROMPTS.items():
    for cn, en in prompts.items():
        BEHAVIOR_LABEL_MAP[en] = cn


class CLIPBehaviorClassifier:
    """
    CLIP 零样本行为分类器

    使用 HuggingFace transformers 库加载 CLIP 模型
    将裁剪后的宠物区域 + 行为描述文本 → 匹配最相似的行为

    特征:
    - 无需训练，零样本
    - 语义理解，不是简单启发式
    - 可自定义提示词描述任意行为
    """

    def __init__(self, model_name: str = "openai/clip-vit-base-patch32"):
        self.model_name = model_name
        self.model = None
        self.processor = None
        self._loaded = False
        self._load_error = None

    def _load(self):
        """延迟加载 CLIP 模型"""
        if self._loaded:
            return True
        if self._load_error:
            return False
        try:
            from transformers import CLIPModel, CLIPProcessor
            logger.info(f"加载 CLIP 模型: {self.model_name}...")
            self.model = CLIPModel.from_pretrained(self.model_name)
            self.processor = CLIPProcessor.from_pretrained(self.model_name)
            self._loaded = True
            logger.info("CLIP 模型加载成功")
            return True
        except Exception as e:
            self._load_error = str(e)
            logger.warning(f"CLIP 模型加载失败: {e}")
            return False

    def classify(self, image, species="dog"):
        """
        对裁剪后的宠物图像进行零样本行为分类
        """
        import time
        import numpy as np
        start = time.time()
        if not self._load():
            return "unknown", 0.0, 0.0

        try:
            prompts = list(BEHAVIOR_PROMPTS.get(species, BEHAVIOR_PROMPTS["dog"]).values())
            inputs = self.processor(text=prompts, images=image, return_tensors="pt", padding=True)
            outputs = self.model(**inputs)
            probs = outputs.logits_per_image.softmax(dim=1).detach().numpy()[0]
            best_idx = int(probs.argmax())
            confidence = float(probs[best_idx])
            en_prompt = prompts[best_idx]
            cn_label = BEHAVIOR_LABEL_MAP.get(en_prompt, "unknown")
            inference_ms = (time.time() - start) * 1000
            return cn_label, confidence, inference_ms
        except Exception as e:
            logger.warning(f"CLIP 分类失败: {e}")
            return "unknown", 0.0, 0.0


# ========== CLIP 零样本行为分类器 (可选) ==========

# 行为描述提示词 (CLIP 零样本分类用)
BEHAVIOR_PROMPTS = {
    "dog": {
        "躺卧/睡觉": "a dog sleeping peacefully curled up",
        "坐着休息": "a dog sitting calmly and relaxed",
        "站立/眺望": "a dog standing still looking around",
        "走动": "a dog walking slowly across the room",
        "跑动/跑酷": "a dog running energetically and playing",
        "跳跃/扑腾": "a dog jumping up excitedly",
        "扒拉/啃咬": "a dog chewing on furniture or objects with its mouth",
        "玩耍": "a dog playing with a toy happily",
        "进食/喝水": "a dog eating food or drinking water",
        "舔舐/梳理": "a dog licking itself or grooming",
    },
    "cat": {
        "躺卧/睡觉": "a cat sleeping peacefully curled up in a ball",
        "坐着/舔毛": "a cat sitting calmly and grooming itself",
        "站立/眺望": "a cat standing still looking out a window",
        "走动": "a cat walking slowly and gracefully",
        "跑动/跑酷": "a cat running around energetically and playing",
        "跳跃": "a cat jumping up onto furniture",
        "抓挠/磨爪": "a cat scratching furniture or scratching post",
        "玩耍": "a cat playing with a toy or object",
        "进食/喝水": "a cat eating food or drinking water",
        "躲藏": "a cat hiding under furniture or in a small space",
    },
}

# 英文提示词 → 中文行为标签映射
BEHAVIOR_LABEL_MAP = {}
for species, prompts in BEHAVIOR_PROMPTS.items():
    for cn, en in prompts.items():
        BEHAVIOR_LABEL_MAP[en] = cn


class CLIPBehaviorClassifier:
    """
    CLIP 零样本行为分类器

    使用 HuggingFace transformers 库加载 CLIP 模型
    将裁剪后的宠物区域 + 行为描述文本 → 匹配最相似的行为

    特征:
    - 无需训练，零样本
    - 语义理解，不是简单启发式
    - 可自定义提示词描述任意行为
    """

    def __init__(self, model_name: str = "openai/clip-vit-base-patch32"):
        self.model_name = model_name
        self.model = None
        self.processor = None
        self._loaded = False
        self._load_error = None

    def _load(self):
        """延迟加载 CLIP 模型"""
        if self._loaded:
            return True
        if self._load_error:
            return False
        try:
            from transformers import CLIPModel, CLIPProcessor
            logger.info(f"加载 CLIP 模型: {self.model_name}...")
            self.model = CLIPModel.from_pretrained(self.model_name)
            self.processor = CLIPProcessor.from_pretrained(self.model_name)
            self._loaded = True
            logger.info("CLIP 模型加载成功")
            return True
        except Exception as e:
            self._load_error = str(e)
            logger.warning(f"CLIP 模型加载失败: {e}")
            return False

    def classify(self, image, species="dog"):
        """
        对裁剪后的宠物图像进行零样本行为分类
        """
        import time
        import numpy as np
        start = time.time()
        if not self._load():
            return "unknown", 0.0, 0.0

        try:
            prompts = list(BEHAVIOR_PROMPTS.get(species, BEHAVIOR_PROMPTS["dog"]).values())
            inputs = self.processor(text=prompts, images=image, return_tensors="pt", padding=True)
            outputs = self.model(**inputs)
            probs = outputs.logits_per_image.softmax(dim=1).detach().numpy()[0]
            best_idx = int(probs.argmax())
            confidence = float(probs[best_idx])
            en_prompt = prompts[best_idx]
            cn_label = BEHAVIOR_LABEL_MAP.get(en_prompt, "unknown")
            inference_ms = (time.time() - start) * 1000
            return cn_label, confidence, inference_ms
        except Exception as e:
            logger.warning(f"CLIP 分类失败: {e}")
            return "unknown", 0.0, 0.0


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

    def __init__(self, model_size: str = "yolov8n.pt", conf_threshold: float = 0.5, use_clip: bool = False):
        self.model_size = model_size
        self.conf_threshold = conf_threshold
        self.use_clip = use_clip
        self.model = None
        self.clip_classifier = None
        self.motion_threshold = 0.02
        self._previous_frame = None
        self._tracker: Optional[Dict[int, List[Detection]]] = {}
        self._model_loaded = False
        self._clip_initialized = False
        # Lazy load: models load on first detect() call

    def _load_model(self):
        """加载 YOLOv8 模型"""
        try:
            from ultralytics import YOLO
            import os, threading, time
            cache_dir = os.path.expanduser("~/.cache/ultralytics")
            model_path = os.path.join(cache_dir, self.model_size)
            if not os.path.exists(model_path):
                # Check if model file exists in cache (without extension)
                base_name = os.path.splitext(self.model_size)[0]
                model_path = os.path.join(cache_dir, base_name + ".pt")
            if os.path.exists(model_path):
                self.model = YOLO(model_path)
                logger.info(f"✅ YOLOv8 模型加载成功: {self.model_size}")
                self._model_loaded = True
                return True
            # Model not cached, try to load (will trigger download)
            # Use a timeout to avoid hanging on blocked network
            result = {"model": None, "error": None}
            def _try_load():
                try:
                    m = YOLO(self.model_size)
                    result["model"] = m
                except Exception as e:
                    result["error"] = str(e)
            t = threading.Thread(target=_try_load, daemon=True)
            t.start()
            t.join(timeout=30)
            if t.is_alive():
                logger.warning("⚠️ YOLOv8 模型下载超时（网络不可用），视觉检测降级")
                self.model = None
                self._model_loaded = True  # Don't retry
                return False
            if result["error"]:
                raise Exception(result["error"])
            self.model = result["model"]
            logger.info(f"✅ YOLOv8 模型加载成功: {self.model_size}")
            self._model_loaded = True
            return True
        except ImportError:
            logger.warning("⚠️ 未安装 ultralytics，视觉检测不可用 (pip install ultralytics)")
            return False
        except Exception as e:
            logger.error(f"❌ YOLOv8 加载失败: {e}")
            self.model = None
            self._model_loaded = True  # Don't retry
            return False

    def _ensure_model(self):
        """确保模型已加载（懒加载）"""
        if not self._model_loaded and self.model is None:
            return self._load_model()
        return self.model is not None

    def _init_clip(self):
        """初始化 CLIP 分类器"""
        try:
            self.clip_classifier = CLIPBehaviorClassifier()
            loaded = self.clip_classifier._load()
            if loaded:
                logger.info("✅ CLIP 行为分类器就绪 (零样本)")
            else:
                logger.warning("⚠️ CLIP 不可用，降级为纯 YOLO 启发式分析")
                self.use_clip = False
        except Exception as e:
            logger.warning(f"⚠️ CLIP 初始化失败: {e}，降级为启发式分析")
            self.use_clip = False
        self._clip_initialized = True

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

        # 懒加载模型
        if not self._model_loaded:
            self._ensure_model()
        if self.use_clip and not self._clip_initialized:
            self._init_clip()

        if self.model is None:
            return VisualBehavior(timestamp=ts, description="模型未加载", skipped=False, inference_ms=0.0)

        # 1. 运动检测 (快速跳过无运动帧)
        motion_score = self._detect_motion(frame)
        has_motion = motion_score > self.motion_threshold if hasattr(self, "motion_threshold") else True

        if not has_motion:
            return VisualBehavior(
                timestamp=ts,
                skipped=True,
                motion_detected=False,
                inference_ms=0.0,
                description="无运动",
            )

        # 2. 推理
        yolo_start = time.time()
        results = self.model.predict(
            frame,
            conf=self.conf_threshold,
            verbose=False,
            classes=list(self.PET_CLASSES.keys()) + list(self.OBJECT_CLASSES.keys()),
        )
        yolo_ms = (time.time() - yolo_start) * 1000

        if not results:
            return VisualBehavior(timestamp=ts, motion_detected=True, skipped=False, inference_ms=yolo_ms)

        r = results[0]
        detections = self._parse_results(r)
        behavior, confidence, activity, is_destructive, desc = self._analyze_behavior(detections)

        # 3. CLIP 增强 (可选)
        clip_used = False
        clip_conf = 0.0
        if self.use_clip and self.clip_classifier and detections:
            pet_dets = [d for d in detections if d.class_name in ("dog", "cat")]
            if pet_dets:
                clip_start = time.time()
                try:
                    pet = max(pet_dets, key=lambda x: x.confidence)
                    x1, y1, x2, y2 = pet.bbox
                    pet_img = frame[y1:y2, x1:x2]
                    if pet_img.size > 0:
                        species = "dog" if pet.class_name == "dog" else "cat"
                        clip_behavior, clip_conf, _ = self.clip_classifier.classify(pet_img, species)
                        if clip_conf > 0.5:
                            behavior = clip_behavior
                            confidence = clip_conf
                            clip_used = True
                except Exception as e:
                    logger.warning(f"CLIP 分类失败: {e}")
                clip_ms = (time.time() - clip_start) * 1000
                yolo_ms += clip_ms

        # 4. 生成标注图
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
            motion_detected=True,
            skipped=False,
            inference_ms=yolo_ms,
            clip_used=clip_used,
            clip_confidence=clip_conf,
        )

    def _detect_motion(self, frame: np.ndarray) -> float:
        """帧差法运动检测"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (160, 120))
        if self._previous_frame is not None:
            diff = cv2.absdiff(gray, self._previous_frame)
            score = float(np.mean(diff)) / 255.0
        else:
            score = 0.0
        self._previous_frame = gray
        return score

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
