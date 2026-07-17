"""
audio_classifier/classifier.py
基于 YAMNet (预训练 AudioSet 模型) 的宠物声音分类
支持: dog bark, cat meow, cat purr, dog howl, dog whine...
"""
import logging
import threading
from typing import Optional

import numpy as np

logger = logging.getLogger("pet_translator.classifier")


class AudioClassifier:
    """
    宠物声音分类器

    使用 YAMNet 模型推理 (TF Lite / ONNX Runtime)
    输出: (动物类型, 具体行为, 置信度)
    """

    # 宠物声音映射表 (YAMNet 521类中宠物相关标签)
    PET_SOUND_MAP = {
        "dog bark":            ("狗", "吠叫", 0.9),
        "dog howl":            ("狗", "嚎叫", 0.85),
        "dog whine":           ("狗", "呜咽", 0.8),
        "dog pant":            ("狗", "喘气", 0.75),
        "cat meow":            ("猫", "喵叫", 0.9),
        "cat purr":            ("猫", "呼噜", 0.9),
        "cat hiss":            ("猫", "嘶嘶", 0.85),
        "cat growl":           ("猫", "低吼", 0.8),
        "cat caterwaul":       ("猫", "嚎叫", 0.75),
    }

    # 高优先级警报声 (需要立即通知主人)
    ALERT_SOUNDS = {"dog whine", "cat caterwaul", "cat growl", "cat hiss"}

    def __init__(self, model_path: str = "models/yamnet.tflite"):
        self.model_path = model_path
        self.interpreter = None
        self._model_lock = threading.Lock()
        self._load_model()

    def _load_model(self):
        """懒加载 TFLite 模型"""
        try:
            import tensorflow as tf
            self.interpreter = tf.lite.Interpreter(model_path=self.model_path)
            self.interpreter.allocate_tensors()
            logger.info("✅ YAMNet 模型加载成功")
        except ImportError:
            logger.warning("⚠️ 未安装 tensorflow，使用模拟模式 (mock)")
            self.interpreter = None
        except Exception as e:
            logger.warning(f"⚠️ 模型加载失败: {e}，使用模拟模式")
            self.interpreter = None

    def classify(self, audio_array: np.ndarray, sample_rate: int = 16000) -> dict:
        """
        分类音频
        audio_array: float32 音频波形, 范围 [-1, 1], 长度 ~1s
        返回: {
            "animal": "狗" | "猫" | None,
            "behavior": "吠叫" | "喵叫" | ...,
            "confidence": 0.95,
            "is_pet_sound": True/False,
            "is_alert": True/False,
            "raw_predictions": [...]
        }
        """
        if self.interpreter is None:
            return self._mock_classify(audio_array)

        with self._model_lock:
            input_details = self.interpreter.get_input_details()
            output_details = self.interpreter.get_output_details()

            # 预处理: 计算梅尔频谱图
            spectrogram = self._compute_mel_spectrogram(audio_array, sample_rate)
            self.interpreter.set_tensor(input_details[0]["index"], spectrogram)
            self.interpreter.invoke()
            scores = self.interpreter.get_tensor(output_details[0]["index"])[0]

        return self._post_process(scores)

    def _compute_mel_spectrogram(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """计算梅尔频谱图 (YAMNet 输入格式)"""
        try:
            import librosa
            S = librosa.feature.melspectrogram(
                y=audio, sr=sr, n_mels=64, fmin=80, fmax=7600
            )
            S_db = librosa.power_to_db(S, ref=np.max)
            return S_db.T.astype(np.float32)[np.newaxis, ...]
        except ImportError:
            # 无 librosa 时返回随机特征
            return np.random.randn(1, 96, 64, 1).astype(np.float32)

    def _post_process(self, scores: np.ndarray) -> dict:
        """将模型输出解析为宠物行为标签"""
        # YAMNet 521 类中宠物相关类别索引
        pet_classes = {
            0: "dog bark", 1: "dog howl", 2: "dog whine",
            3: "cat meow", 4: "cat purr", 5: "cat hiss",
            6: "cat growl", 7: "cat caterwaul",
        }
        pet_scores = {name: float(scores[idx]) for idx, name in pet_classes.items()}
        best_label = max(pet_scores, key=pet_scores.get)
        confidence = pet_scores[best_label]

        mapped = self.PET_SOUND_MAP.get(best_label, (None, best_label, confidence))
        animal, behavior, _ = mapped

        return {
            "animal": animal,
            "behavior": behavior,
            "confidence": round(confidence, 3),
            "is_pet_sound": animal is not None,
            "is_alert": best_label in self.ALERT_SOUNDS,
            "raw_predictions": pet_scores,
        }

    def _mock_classify(self, audio: np.ndarray) -> dict:
        """无模型时的模拟模式，用于演示和测试"""
        energy = float(np.sqrt(np.mean(audio ** 2)))
        is_alert = energy > 0.3
        return {
            "animal": "狗" if energy > 0.25 else ("猫" if energy > 0.1 else None),
            "behavior": "吠叫" if energy > 0.3 else "喵叫",
            "confidence": min(round(energy, 2), 0.99),
            "is_pet_sound": energy > 0.1,
            "is_alert": is_alert,
            "raw_predictions": {"mock_energy": energy},
        }
