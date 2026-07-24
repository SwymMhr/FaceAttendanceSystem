# app/services/liveness_service.py
# Lightweight OpenCV-based anti-spoofing detector.
# 5 checks: specular highlights, edge sharpness, color anomaly, reflection patterns, texture.

import cv2
import numpy as np


class AntiSpoofingDetector:
    """
    Lightweight anti-spoofing detector using OpenCV.
    Designed for real-time performance with minimal false positives.
    """

    def __init__(self, config=None):
        self.config = {
            "specular_threshold": 0.005,
            "specular_intensity": 215,
            "edge_sharpness_max": 45,
            "color_blue_shift_max": 1.05,
            "reflection_variance_min": 50,
            "texture_laplacian_min": 80.0,
            "min_checks_to_fail": 2,
            "enabled": True,
        }
        if config:
            self.config.update(config)

    # ── individual checks ────────────────────────────────────────────────

    def detect_specular_highlights(self, face_bgr):
        hsv = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2HSV)
        v = hsv[:, :, 2]
        t = self.config["specular_intensity"]
        bright_ratio = float(np.sum(v > t)) / v.size
        _, mask = cv2.threshold(v, t, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        regions = sum(1 for c in contours if cv2.contourArea(c) > 20)
        spoof = bright_ratio > self.config["specular_threshold"] or regions >= 3
        return spoof, bright_ratio, {"bright_ratio": bright_ratio, "bright_regions": regions}

    def detect_edge_sharpness(self, face_gray):
        lap = cv2.Laplacian(face_gray, cv2.CV_64F)
        score = float(np.abs(lap).mean())
        return score > self.config["edge_sharpness_max"], score, {"edge_mean": score}

    def detect_color_anomaly(self, face_bgr):
        b, g, r = cv2.split(face_bgr)
        bm, gm, rm = float(np.mean(b)), float(np.mean(g)), float(np.mean(r))
        blue_ratio = bm / ((rm + gm) / 2 + 1e-6)
        total = b.size
        clipped = (
            (np.sum(b < 10) + np.sum(g < 10) + np.sum(r < 10))
            + (np.sum(b > 250) + np.sum(g > 250) + np.sum(r > 250))
        ) / (3 * total)
        spoof = blue_ratio > self.config["color_blue_shift_max"] or clipped > 0.08
        return spoof, blue_ratio, {"blue_ratio": blue_ratio, "clipping_ratio": clipped}

    def detect_reflection_pattern(self, face_gray):
        h, w = face_gray.shape
        regions = []
        for i in range(3):
            for j in range(3):
                y1, y2 = i * h // 3, (i + 1) * h // 3
                x1, x2 = j * w // 3, (j + 1) * w // 3
                regions.append(float(np.mean(face_gray[y1:y2, x1:x2])))
        var = float(np.var(regions))
        return var < self.config["reflection_variance_min"], var, {"region_variance": var}

    def detect_texture_analysis(self, face_gray):
        resized = cv2.resize(face_gray, (100, 100))
        val = float(cv2.Laplacian(resized, cv2.CV_64F).var())
        return val < self.config["texture_laplacian_min"], val, {"texture_val": val}

    # ── main entry point ─────────────────────────────────────────────────

    def check_liveness(self, face_bgr):
        if not self.config["enabled"]:
            return self._result(True, 1.0, "none", {})

        if face_bgr.shape[0] < 50 or face_bgr.shape[1] < 50:
            return self._result(True, 0.5, "unknown", {})

        gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
        failed = []
        scores = {}

        for name, fn, args in [
            ("specular",    self.detect_specular_highlights, (face_bgr,)),
            ("sharpness",   self.detect_edge_sharpness,      (gray,)),
            ("color",       self.detect_color_anomaly,       (face_bgr,)),
            ("reflection",  self.detect_reflection_pattern,  (gray,)),
            ("texture",     self.detect_texture_analysis,    (gray,)),
        ]:
            spoof, score, _ = fn(*args)
            scores[name] = score
            if spoof:
                failed.append(name)

        is_live = len(failed) < self.config["min_checks_to_fail"]
        confidence = (5 - len(failed)) / 5
        spoof_type = "none"
        if not is_live:
            if "specular" in failed or "color" in failed:
                spoof_type = "screen"
            elif "reflection" in failed or "texture" in failed:
                spoof_type = "print"
            else:
                spoof_type = "unknown"
        return self._result(is_live, confidence, spoof_type, scores, failed)

    @staticmethod
    def _result(is_live, confidence, spoof_type, scores, failed=None):
        return {
            "is_live": is_live,
            "confidence": confidence,
            "spoof_type": spoof_type,
            "scores": scores,
            "failed": failed or [],
        }


detector = AntiSpoofingDetector()


def check_liveness(face_bgr):
    return detector.check_liveness(face_bgr)
