FROM python:3.9-slim

WORKDIR /app

# Install system dependencies for Trimesh and PyMeshLab
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create the downloads directory
RUN mkdir -p /app/downloads

# Expose the Streamlit port
EXPOSE 8501

# Command to run the application
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
