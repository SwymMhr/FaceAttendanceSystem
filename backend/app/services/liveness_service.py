# app/services/liveness_service.py
# CNN-based anti-spoofing using Silent-Face-Anti-Spoofing pretrained models.
# Uses MiniFASNetV2/V1SE ensemble for liveness classification.

import os
import cv2
import numpy as np
import torch
import torch.nn.functional as F
from collections import OrderedDict
from torch.nn import (
    Linear, Conv2d, BatchNorm1d, BatchNorm2d, PReLU, ReLU, Sigmoid,
    AdaptiveAvgPool2d, Sequential, Module,
)

# ══════════════════════════════════════════════════════════════════════════
# MiniFASNet architecture (from Silent-Face-Anti-Spoofing)
# ══════════════════════════════════════════════════════════════════════════

class Flatten(Module):
    def forward(self, input):
        return input.view(input.size(0), -1)

class Conv_block(Module):
    def __init__(self, in_c, out_c, kernel=(1,1), stride=(1,1), padding=(0,0), groups=1):
        super(Conv_block, self).__init__()
        self.conv = Conv2d(in_c, out_c, kernel_size=kernel, groups=groups,
                           stride=stride, padding=padding, bias=False)
        self.bn = BatchNorm2d(out_c)
        self.prelu = PReLU(out_c)
    def forward(self, x):
        return self.prelu(self.bn(self.conv(x)))

class Linear_block(Module):
    def __init__(self, in_c, out_c, kernel=(1,1), stride=(1,1), padding=(0,0), groups=1):
        super(Linear_block, self).__init__()
        self.conv = Conv2d(in_c, out_channels=out_c, kernel_size=kernel,
                           groups=groups, stride=stride, padding=padding, bias=False)
        self.bn = BatchNorm2d(out_c)
    def forward(self, x):
        return self.bn(self.conv(x))

class Depth_Wise(Module):
    def __init__(self, c1, c2, c3, residual=False, kernel=(3,3), stride=(2,2), padding=(1,1), groups=1):
        super(Depth_Wise, self).__init__()
        c1_in, c1_out = c1
        c2_in, c2_out = c2
        c3_in, c3_out = c3
        self.conv = Conv_block(c1_in, c1_out, kernel=(1,1), padding=(0,0), stride=(1,1))
        self.conv_dw = Conv_block(c2_in, c2_out, groups=c2_in, kernel=kernel, padding=padding, stride=stride)
        self.project = Linear_block(c3_in, c3_out, kernel=(1,1), padding=(0,0), stride=(1,1))
        self.residual = residual
    def forward(self, x):
        short_cut = x if self.residual else None
        x = self.project(self.conv_dw(self.conv(x)))
        return short_cut + x if self.residual else x

class Residual(Module):
    def __init__(self, c1, c2, c3, num_block, groups, kernel=(3,3), stride=(1,1), padding=(1,1)):
        super(Residual, self).__init__()
        modules = []
        for i in range(num_block):
            modules.append(Depth_Wise(c1[i], c2[i], c3[i], residual=True,
                kernel=kernel, padding=padding, stride=stride, groups=groups))
        self.model = Sequential(*modules)
    def forward(self, x):
        return self.model(x)

class SEModule(Module):
    def __init__(self, channels, reduction):
        super(SEModule, self).__init__()
        self.avg_pool = AdaptiveAvgPool2d(1)
        self.fc1 = Conv2d(channels, channels // reduction, kernel_size=1, padding=0, bias=False)
        self.bn1 = BatchNorm2d(channels // reduction)
        self.relu = ReLU(inplace=True)
        self.fc2 = Conv2d(channels // reduction, channels, kernel_size=1, padding=0, bias=False)
        self.bn2 = BatchNorm2d(channels)
        self.sigmoid = Sigmoid()
    def forward(self, x):
        module_input = x
        x = self.avg_pool(x)
        x = self.relu(self.bn1(self.fc1(x)))
        x = self.sigmoid(self.bn2(self.fc2(x)))
        return module_input * x

class Depth_Wise_SE(Module):
    def __init__(self, c1, c2, c3, residual=False, kernel=(3,3), stride=(2,2), padding=(1,1), groups=1, se_reduct=8):
        super(Depth_Wise_SE, self).__init__()
        c1_in, c1_out = c1
        c2_in, c2_out = c2
        c3_in, c3_out = c3
        self.conv = Conv_block(c1_in, c1_out, kernel=(1,1), padding=(0,0), stride=(1,1))
        self.conv_dw = Conv_block(c2_in, c2_out, groups=c2_in, kernel=kernel, padding=padding, stride=stride)
        self.project = Linear_block(c3_in, c3_out, kernel=(1,1), padding=(0,0), stride=(1,1))
        self.residual = residual
        self.se_module = SEModule(c3_out, se_reduct)
    def forward(self, x):
        short_cut = x if self.residual else None
        x = self.project(self.conv_dw(self.conv(x)))
        if self.residual:
            x = self.se_module(x)
            return short_cut + x
        return x

class ResidualSE(Module):
    def __init__(self, c1, c2, c3, num_block, groups, kernel=(3,3), stride=(1,1), padding=(1,1), se_reduct=4):
        super(ResidualSE, self).__init__()
        modules = []
        for i in range(num_block):
            if i == num_block - 1:
                modules.append(Depth_Wise_SE(c1[i], c2[i], c3[i], residual=True,
                    kernel=kernel, padding=padding, stride=stride, groups=groups, se_reduct=se_reduct))
            else:
                modules.append(Depth_Wise(c1[i], c2[i], c3[i], residual=True,
                    kernel=kernel, padding=padding, stride=stride, groups=groups))
        self.model = Sequential(*modules)
    def forward(self, x):
        return self.model(x)

class MiniFASNet(Module):
    def __init__(self, keep, embedding_size, conv6_kernel=(7,7), drop_p=0.0, num_classes=3, img_channel=3):
        super(MiniFASNet, self).__init__()
        self.embedding_size = embedding_size
        self.conv1 = Conv_block(img_channel, keep[0], kernel=(3,3), stride=(2,2), padding=(1,1))
        self.conv2_dw = Conv_block(keep[0], keep[1], kernel=(3,3), stride=(1,1), padding=(1,1), groups=keep[1])
        self.conv_23 = Depth_Wise(
            (keep[1], keep[2]), (keep[2], keep[3]), (keep[3], keep[4]),
            kernel=(3,3), stride=(2,2), padding=(1,1), groups=keep[3])
        c1 = [(keep[4], keep[5]), (keep[7], keep[8]), (keep[10], keep[11]), (keep[13], keep[14])]
        c2 = [(keep[5], keep[6]), (keep[8], keep[9]), (keep[11], keep[12]), (keep[14], keep[15])]
        c3 = [(keep[6], keep[7]), (keep[9], keep[10]), (keep[12], keep[13]), (keep[15], keep[16])]
        self.conv_3 = Residual(c1, c2, c3, num_block=4, groups=keep[4], kernel=(3,3), stride=(1,1), padding=(1,1))
        self.conv_34 = Depth_Wise(
            (keep[16], keep[17]), (keep[17], keep[18]), (keep[18], keep[19]),
            kernel=(3,3), stride=(2,2), padding=(1,1), groups=keep[19])
        c1 = [(keep[19], keep[20]), (keep[22], keep[23]), (keep[25], keep[26]), (keep[28], keep[29]),
              (keep[31], keep[32]), (keep[34], keep[35])]
        c2 = [(keep[20], keep[21]), (keep[23], keep[24]), (keep[26], keep[27]), (keep[29], keep[30]),
              (keep[32], keep[33]), (keep[35], keep[36])]
        c3 = [(keep[21], keep[22]), (keep[24], keep[25]), (keep[27], keep[28]), (keep[30], keep[31]),
              (keep[33], keep[34]), (keep[36], keep[37])]
        self.conv_4 = Residual(c1, c2, c3, num_block=6, groups=keep[19], kernel=(3,3), stride=(1,1), padding=(1,1))
        self.conv_45 = Depth_Wise(
            (keep[37], keep[38]), (keep[38], keep[39]), (keep[39], keep[40]),
            kernel=(3,3), stride=(2,2), padding=(1,1), groups=keep[40])
        c1 = [(keep[40], keep[41]), (keep[43], keep[44])]
        c2 = [(keep[41], keep[42]), (keep[44], keep[45])]
        c3 = [(keep[42], keep[43]), (keep[45], keep[46])]
        self.conv_5 = Residual(c1, c2, c3, num_block=2, groups=keep[40], kernel=(3,3), stride=(1,1), padding=(1,1))
        self.conv_6_sep = Conv_block(keep[46], keep[47], kernel=(1,1), stride=(1,1), padding=(0,0))
        self.conv_6_dw = Linear_block(keep[47], keep[48], groups=keep[48], kernel=conv6_kernel, stride=(1,1), padding=(0,0))
        self.conv_6_flatten = Flatten()
        self.linear = Linear(512, embedding_size, bias=False)
        self.bn = BatchNorm1d(embedding_size)
        self.drop = torch.nn.Dropout(p=drop_p)
        self.prob = Linear(embedding_size, num_classes, bias=False)
    def forward(self, x):
        out = self.conv1(x)
        out = self.conv2_dw(out)
        out = self.conv_23(out)
        out = self.conv_3(out)
        out = self.conv_34(out)
        out = self.conv_4(out)
        out = self.conv_45(out)
        out = self.conv_5(out)
        out = self.conv_6_sep(out)
        out = self.conv_6_dw(out)
        out = self.conv_6_flatten(out)
        if self.embedding_size != 512:
            out = self.linear(out)
        out = self.bn(out)
        out = self.drop(out)
        out = self.prob(out)
        return out

class MiniFASNetSE(MiniFASNet):
    def __init__(self, keep, embedding_size, conv6_kernel=(7,7), drop_p=0.75, num_classes=3, img_channel=3):
        super(MiniFASNetSE, self).__init__(keep=keep, embedding_size=embedding_size,
            conv6_kernel=conv6_kernel, drop_p=drop_p, num_classes=num_classes, img_channel=img_channel)
        c1 = [(keep[4], keep[5]), (keep[7], keep[8]), (keep[10], keep[11]), (keep[13], keep[14])]
        c2 = [(keep[5], keep[6]), (keep[8], keep[9]), (keep[11], keep[12]), (keep[14], keep[15])]
        c3 = [(keep[6], keep[7]), (keep[9], keep[10]), (keep[12], keep[13]), (keep[15], keep[16])]
        self.conv_3 = ResidualSE(c1, c2, c3, num_block=4, groups=keep[4], kernel=(3,3), stride=(1,1), padding=(1,1))
        c1 = [(keep[19], keep[20]), (keep[22], keep[23]), (keep[25], keep[26]), (keep[28], keep[29]),
              (keep[31], keep[32]), (keep[34], keep[35])]
        c2 = [(keep[20], keep[21]), (keep[23], keep[24]), (keep[26], keep[27]), (keep[29], keep[30]),
              (keep[32], keep[33]), (keep[35], keep[36])]
        c3 = [(keep[21], keep[22]), (keep[24], keep[25]), (keep[27], keep[28]), (keep[30], keep[31]),
              (keep[33], keep[34]), (keep[36], keep[37])]
        self.conv_4 = ResidualSE(c1, c2, c3, num_block=6, groups=keep[19], kernel=(3,3), stride=(1,1), padding=(1,1))
        c1 = [(keep[40], keep[41]), (keep[43], keep[44])]
        c2 = [(keep[41], keep[42]), (keep[44], keep[45])]
        c3 = [(keep[42], keep[43]), (keep[45], keep[46])]
        self.conv_5 = ResidualSE(c1, c2, c3, num_block=2, groups=keep[40], kernel=(3,3), stride=(1,1), padding=(1,1))

keep_dict = {
    '1.8M': [32, 32, 103, 103, 64, 13, 13, 64, 26, 26,
             64, 13, 13, 64, 52, 52, 64, 231, 231, 128,
             154, 154, 128, 52, 52, 128, 26, 26, 128, 52,
             52, 128, 26, 26, 128, 26, 26, 128, 308, 308,
             128, 26, 26, 128, 26, 26, 128, 512, 512],
    '1.8M_': [32, 32, 103, 103, 64, 13, 13, 64, 13, 13, 64, 13,
              13, 64, 13, 13, 64, 231, 231, 128, 231, 231, 128, 52,
              52, 128, 26, 26, 128, 77, 77, 128, 26, 26, 128, 26, 26,
              128, 308, 308, 128, 26, 26, 128, 26, 26, 128, 512, 512],
}
MODEL_MAPPING = {
    'MiniFASNetV1': lambda kw: MiniFASNet(keep_dict['1.8M'], **kw),
    'MiniFASNetV2': lambda kw: MiniFASNet(keep_dict['1.8M_'], **kw),
    'MiniFASNetV1SE': lambda kw: MiniFASNetSE(keep_dict['1.8M'], **kw),
    'MiniFASNetV2SE': lambda kw: MiniFASNetSE(keep_dict['1.8M_'], **kw),
}

def _get_kernel(h, w):
    return ((h + 15) // 16, (w + 15) // 16)

def _parse_model_name(model_name):
    info = model_name.split('_')[0:-1]
    h_input, w_input = info[-1].split('x')
    model_type = model_name.split('.pth')[0].split('_')[-1]
    scale = None if info[0] == "org" else float(info[0])
    return int(h_input), int(w_input), model_type, scale

# ══════════════════════════════════════════════════════════════════════════
# CropImage
# ══════════════════════════════════════════════════════════════════════════

class CropImage:
    @staticmethod
    def _get_new_box(src_w, src_h, bbox, scale):
        x, y, box_w, box_h = bbox
        scale = min((src_h - 1) / box_h, min((src_w - 1) / box_w, scale))
        new_width = box_w * scale
        new_height = box_h * scale
        center_x, center_y = box_w / 2 + x, box_h / 2 + y
        left_top_x = center_x - new_width / 2
        left_top_y = center_y - new_height / 2
        right_bottom_x = center_x + new_width / 2
        right_bottom_y = center_y + new_height / 2
        if left_top_x < 0:
            right_bottom_x -= left_top_x
            left_top_x = 0
        if left_top_y < 0:
            right_bottom_y -= left_top_y
            left_top_y = 0
        if right_bottom_x > src_w - 1:
            left_top_x -= right_bottom_x - src_w + 1
            right_bottom_x = src_w - 1
        if right_bottom_y > src_h - 1:
            left_top_y -= right_bottom_y - src_h + 1
            right_bottom_y = src_h - 1
        return (int(left_top_x), int(left_top_y), int(right_bottom_x), int(right_bottom_y))

    def crop(self, org_img, bbox, scale, out_w, out_h, crop=True):
        if not crop:
            return cv2.resize(org_img, (out_w, out_h))
        src_h, src_w, _ = np.shape(org_img)
        ltx, lty, rbx, rby = self._get_new_box(src_w, src_h, bbox, scale)
        img = org_img[lty:rby + 1, ltx:rbx + 1]
        return cv2.resize(img, (out_w, out_h))


# ══════════════════════════════════════════════════════════════════════════
# CNN Liveness Detector (singleton)
# ══════════════════════════════════════════════════════════════════════════

class CNNLivenessDetector:
    def __init__(self, model_dir=None, device=None):
        if model_dir is None:
            model_dir = os.path.join(os.path.dirname(__file__), "anti_spoof_models")
        self.model_dir = model_dir
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.image_cropper = CropImage()
        self.models = []
        self._load_models()

    def _load_models(self):
        for fname in os.listdir(self.model_dir):
            if not fname.endswith(".pth"):
                continue
            h_input, w_input, model_type, scale = _parse_model_name(fname)
            kernel = _get_kernel(h_input, w_input)
            if model_type not in MODEL_MAPPING:
                continue
            model = MODEL_MAPPING[model_type]({
                "embedding_size": 128, "conv6_kernel": kernel,
                "num_classes": 3, "drop_p": 0.0,
            })
            state_dict = torch.load(os.path.join(self.model_dir, fname),
                                     map_location=self.device, weights_only=True)
            new_state_dict = OrderedDict()
            for key, value in state_dict.items():
                nk = key[7:] if key.startswith('module.') else key
                nk = nk.replace('.se_fc1.', '.se_module.fc1.')
                nk = nk.replace('.se_bn1.', '.se_module.bn1.')
                nk = nk.replace('.se_fc2.', '.se_module.fc2.')
                nk = nk.replace('.se_bn2.', '.se_module.bn2.')
                new_state_dict[nk] = value
            model.load_state_dict(new_state_dict, strict=False)
            model.to(self.device)
            model.eval()
            self.models.append({"model": model, "h": h_input, "w": w_input, "scale": scale})

    def check_liveness(self, frame, face_bbox):
        prediction = np.zeros((1, 3))
        for m in self.models:
            param = {
                "org_img": frame, "bbox": face_bbox, "scale": m["scale"],
                "out_w": m["w"], "out_h": m["h"], "crop": True,
            }
            if m["scale"] is None:
                param["crop"] = False
            img = self.image_cropper.crop(**param)
            tensor = torch.from_numpy(img).float().permute(2, 0, 1).unsqueeze(0)
            tensor = tensor.to(self.device)
            with torch.no_grad():
                out = m["model"](tensor)
                prob = F.softmax(out, dim=1).cpu().numpy()
            prediction += prob

        real_score = float(prediction[0][1]) / 2.0
        is_live = real_score > 0.5

        return {
            "is_live": is_live,
            "confidence": round(real_score if is_live else (1.0 - real_score), 4),
            "spoof_type": "none" if is_live else "cnn_detected",
            "scores": {
                "raw_spoof": float(prediction[0][0]),
                "raw_real": float(prediction[0][1]),
                "raw_unknown": float(prediction[0][2]),
            },
        }


# ── Singleton ────────────────────────────────────────────────────────────

_detector = None

def get_detector(model_dir=None):
    global _detector
    if _detector is None:
        _detector = CNNLivenessDetector(model_dir)
    return _detector


def check_liveness(frame, face_bbox):
    """Check liveness of a face in the frame.

    Args:
        frame: BGR image (full frame from webcam/CCTV)
        face_bbox: (x, y, w, h) as detected by YOLO

    Returns:
        dict with 'is_live', 'confidence', 'spoof_type', 'scores'
    """
    return get_detector().check_liveness(frame, face_bbox)
