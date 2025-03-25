import os
import glob
import cv2
import numpy as np
import torch
import matplotlib.cm as cm

from depth_anything_v2.dpt import DepthAnythingV2

# 🧩 설정 값 직접 정의
video_path = "short_video.mp4"  # ← 비디오 경로
input_size = 518
outdir = "object_depth"
encoder = "vits"
pred_only = False
grayscale = False

# 🧠 디바이스 설정
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# 모델 구성
model_configs = {
    'vits': {'encoder': 'vits', 'features': 64, 'out_channels': [48, 96, 192, 384]},
    'vitb': {'encoder': 'vitb', 'features': 128, 'out_channels': [96, 192, 384, 768]},
    'vitl': {'encoder': 'vitl', 'features': 256, 'out_channels': [256, 512, 1024, 1024]},
    'vitg': {'encoder': 'vitg', 'features': 384, 'out_channels': [1536, 1536, 1536, 1536]}
}

# 모델 로딩
depth_anything = DepthAnythingV2(**model_configs[encoder])
depth_anything.load_state_dict(torch.load(f"object_depth\Depth-Anything-V2\checkpoints\depth_anything_v2_vits.pth", map_location=DEVICE))
depth_anything = depth_anything.to(DEVICE).eval()

# 입력 영상 리스트 구성
if os.path.isfile(video_path):
    filenames = [video_path]
else:
    filenames = glob.glob(os.path.join(video_path, "**/*"), recursive=True)

# 출력 디렉토리 생성
os.makedirs(outdir, exist_ok=True)

margin_width = 50
cmap = cm.get_cmap("Spectral_r")

# 처리 시작
for k, filename in enumerate(filenames):
    print(f"Processing {k + 1}/{len(filenames)}: {filename}")

    raw_video = cv2.VideoCapture(filename)
    frame_width = int(raw_video.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(raw_video.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_rate = int(raw_video.get(cv2.CAP_PROP_FPS))

    output_width = frame_width if pred_only else frame_width * 2 + margin_width
    output_path = os.path.join(outdir, os.path.splitext(os.path.basename(filename))[0] + ".mp4")

    out = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*"mp4v"), frame_rate, (output_width, frame_height))

    frame_total = int(raw_video.get(cv2.CAP_PROP_FRAME_COUNT))  # 전체 프레임 수
    frame_index = 0

    while raw_video.isOpened():
        ret, raw_frame = raw_video.read()
        if not ret:
            break

        # 진행률 계산
        frame_index += 1
        percent = (frame_index / frame_total) * 100
        bar_len = 30
        filled_len = int(bar_len * frame_index // frame_total)
        bar = "#" * filled_len + "-" * (bar_len - filled_len)
        print(f"\r[{percent:5.1f}%] [{bar}] Frame {frame_index}/{frame_total}", end="")

        # 추론
        depth = depth_anything.infer_image(raw_frame, input_size)
        depth = (depth - depth.min()) / (depth.max() - depth.min()) * 255.0
        depth = depth.astype(np.uint8)

        if grayscale:
            depth = np.repeat(depth[..., np.newaxis], 3, axis=-1)
        else:
            depth = (cmap(depth)[:, :, :3] * 255).astype(np.uint8)[..., ::-1]

        if pred_only:
            out.write(depth)
        else:
            gap = np.ones((frame_height, margin_width, 3), dtype=np.uint8) * 255
            combined = cv2.hconcat([raw_frame, gap, depth])
            out.write(combined)

    raw_video.release()
    out.release()

print("완료! 결과 저장 경로:", outdir)
