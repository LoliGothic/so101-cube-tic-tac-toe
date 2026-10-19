# Python 3.12 が標準の Ubuntu 24.04 + CUDA 12.8
FROM nvidia/cuda:12.8.1-base-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    python3 python3-venv python3-dev git ffmpeg tmux \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 仮想環境を作って PATH に通す
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# CUDA 12.8 版の PyTorch → LeRobot（学習用）
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cu128 \
 && pip install --no-cache-dir "lerobot[training]"

WORKDIR /work