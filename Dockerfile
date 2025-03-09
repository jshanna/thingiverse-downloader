FROM python:3.9-alpine

WORKDIR /app

# Install system dependencies for Trimesh and PyMeshLab
RUN apk add --no-cache \
    build-base \
    mesa-gl \
    libgomp \
    libc6-compat \
    libstdc++ \
    mesa-dri-gallium \
    freetype-dev \
    && ln -s /usr/lib/libgfortran.so.5 /usr/lib/libgfortran.so.3

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create the downloads directory
RUN mkdir -p /app/downloads

# Environment variables for OpenGL rendering in container
ENV PYTHONUNBUFFERED=1 \
    DISPLAY=:99 \
    MESA_GL_VERSION_OVERRIDE=3.3

# Expose the Streamlit port
EXPOSE 8501

# Command to run the application
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
