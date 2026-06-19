# app/services/model_service.py
# This is the most important backend file.
# It loads your trained PyTorch model and exposes two functions:
#   - get_embedding(pil_image)  → returns a 128-dim numpy vector
#   - compare_embedding(vec_a, vec_b) → returns cosine similarity score

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from torchvision import models, transforms
from PIL import Image

from app.core.config import settings


# ── 1. Rebuild the EXACT same model class you used in Colab ──────────────────
#    This must match your notebook 1-to-1 so the saved weights load correctly.

class FaceModel(nn.Module):
    def __init__(self, base):
        super().__init__()
        self.base = base
        self.fc = nn.Sequential(
            nn.Linear(1280, 256),
            nn.ReLU(),
            nn.Linear(256, 128)
        )

    def forward(self, x):
        x = self.base(x)
        x = self.fc(x)
        return F.normalize(x, dim=1)   # L2-normalised 128-dim vector


# ── 2. Preprocessing transform (same as training) ────────────────────────────
#    Your notebook used Resize(160,160) + ToTensor() — no normalisation.

_transform = transforms.Compose([
    transforms.Resize((160, 160)),
    transforms.ToTensor(),
])


# ── 3. Load the model ONCE when the server starts ────────────────────────────
#    Loading is slow (~1-2 s); we do it at import time so every API request
#    reuses the already-loaded model.

def _load_model() -> FaceModel:
    base = models.mobilenet_v2(weights=None)   # no pretrained weights
    base.classifier = nn.Identity()

    model = FaceModel(base)
    model.load_state_dict(
        torch.load(settings.MODEL_PATH, map_location="cpu")
    )
    model.eval()   # switch to inference mode (disables dropout etc.)
    print(f"[ModelService] Model loaded from {settings.MODEL_PATH}")
    return model

_model: FaceModel = _load_model()    # module-level singleton


# ── 4. Public API ─────────────────────────────────────────────────────────────

def get_embedding(pil_image: Image.Image) -> np.ndarray:
    """
    Given a PIL Image (RGB), return a 128-dim L2-normalised embedding
    as a numpy float32 array.
    """
    tensor = _transform(pil_image.convert("RGB")).unsqueeze(0)  # shape: [1, 3, 160, 160]
    with torch.no_grad():
        emb = _model(tensor)                                     # shape: [1, 128]
    return emb.squeeze(0).numpy()                                # shape: [128]


def embedding_to_str(vector: np.ndarray) -> str:
    """Convert a numpy array to a comma-separated string for DB storage."""
    return ",".join(f"{v:.8f}" for v in vector.tolist())


def str_to_embedding(text: str) -> np.ndarray:
    """Convert comma-separated string back to numpy array."""
    return np.array([float(v) for v in text.split(",")], dtype=np.float32)


def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """
    Compute cosine similarity between two embedding vectors.
    Both are already L2-normalised so: similarity = dot product.
    Returns a value between -1.0 and 1.0 (higher = more similar).
    """
    return float(np.dot(vec_a, vec_b))