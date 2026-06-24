# app/services/crop_utils.py
def crop_with_margin(frame, box, margin_ratio=0.25):
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    mx, my = int(w * margin_ratio), int(h * margin_ratio)

    H, W = frame.shape[:2]
    x1 = max(0, x1 - mx)
    y1 = max(0, y1 - my)
    x2 = min(W, x2 + mx)
    y2 = min(H, y2 + my)

    return frame[y1:y2, x1:x2]