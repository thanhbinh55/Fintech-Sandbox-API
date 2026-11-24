FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download Gipformer 1.5 INT8 ONNX weights into the Docker image for instant startup
ENV STT_MODEL_DIR=/app/models/gipformer
ENV STT_USE_INT8=true
RUN python -c "from huggingface_hub import hf_hub_download; \
    [hf_hub_download('g-group-ai-lab/gipformer1.5-68M-rnnt', f, local_dir='/app/models/gipformer') \
    for f in ['tokens.txt', 'encoder.int8.onnx', 'decoder.int8.onnx', 'joiner.int8.onnx']]"

COPY app ./app
COPY static ./static

EXPOSE 7860

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
