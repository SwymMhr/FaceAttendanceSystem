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


# ── 1. Rebuild the EXACT same model class used in training ───────────────────
#    This must match the notebook's FaceEmbeddingModel 1-to-1 so the saved
#    weights load correctly. This is the MobileNetV2 + ArcFace model
#    (v6), not the old simpler test model.

class FaceModel(nn.Module):
    def __init__(self, embedding_dim: int = 128):
        super().__init__()
        backbone = models.mobilenet_v2(weights=None)
        backbone.classifier = nn.Identity()
        self.backbone = backbone
        self.embedding = nn.Sequential(
            nn.Linear(1280, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(512, embedding_dim),
        )

    def forward(self, x):
        x = self.backbone(x)
        x = self.embedding(x)
        return F.normalize(x, p=2, dim=1)   # L2-normalised embedding


# ── 2. Load the checkpoint ONCE when the server starts ───────────────────────
#    Loading is slow (~1-2 s); we do it at import time so every API request
#    reuses the already-loaded model.
#
#    The new checkpoint is a dict (not a raw state_dict) that also carries
#    the preprocessing config and the verification threshold computed during
#    training, so the backend doesn't have to guess those values separately.

def _load_checkpoint():
    checkpoint = torch.load(settings.MODEL_PATH, map_location="cpu")

    model = FaceModel(embedding_dim=checkpoint["embedding_dim"])
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()   # switch to inference mode (disables dropout etc.)

    print(f"[ModelService] Model loaded from {settings.MODEL_PATH}")
    print(f"[ModelService] embedding_dim={checkpoint['embedding_dim']}  "
          f"img_size={checkpoint['img_size']}  "
          f"verification_threshold={checkpoint['verification_threshold']:.4f}")

    return model, checkpoint


_model, _checkpoint = _load_checkpoint()    # module-level singletons

IMG_SIZE = _checkpoint["img_size"]
VERIFICATION_THRESHOLD = float(_checkpoint["verification_threshold"])
_NORMALIZE_MEAN = _checkpoint["normalize_mean"]
_NORMALIZE_STD = _checkpoint["normalize_std"]

# ── 3. Preprocessing transform (must match training exactly) ─────────────────
#    The new model was trained at 224x224 WITH ImageNet normalisation —
#    different from the old model's 160x160 / no-normalisation pipeline.

_transform = transforms.Compose([
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(mean=_NORMALIZE_MEAN, std=_NORMALIZE_STD),
])


# ── 4. Public API ─────────────────────────────────────────────────────────────

def get_embedding(pil_image: Image.Image) -> np.ndarray:
    """
    Given a PIL Image (RGB), return a 128-dim L2-normalised embedding
    as a numpy float32 array.
    """
    tensor = _transform(pil_image.convert("RGB")).unsqueeze(0)  # [1, 3, IMG_SIZE, IMG_SIZE]
    with torch.no_grad():
        emb = _model(tensor)                                     # [1, 128]
    return emb.squeeze(0).numpy().astype(np.float32)              # [128]


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