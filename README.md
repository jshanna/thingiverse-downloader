# Thingiverse Downloader

A Streamlit application that allows you to download, organize, browse, and visualize 3D model packages from Thingiverse.

## Features

### Downloading
- Input a single Thingiverse URL or batch of URLs
- Automatically download the associated ZIP package(s)
- Organize models into customizable categories
- Extract contents with progress tracking

### Browsing & Visualization
- Browse your downloaded models by category
- Search models by name, ID, or description
- View detailed model information including thumbnails and README files
- High-quality 3D model visualization with customizable appearance
- File browser to explore all files in a model package

### User Interface
- Clean, modern interface with intuitive navigation
- Easy-to-use sidebar navigation buttons
- Responsive layout that works on various screen sizes

## Installation

### Standard Installation

1. Clone this repository
2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

### Docker Installation

Alternatively, you can run the application using Docker:

1. Make sure you have Docker and Docker Compose installed
2. Build and start the container:

```bash
docker-compose up -d
```

3. The application will be available at http://localhost
4. To stop the container:

```bash
docker-compose down
```

## Usage

### Running Locally

1. Run the Streamlit app:

```bash
streamlit run app.py
```

### Running with Docker

1. Simply access http://localhost in your browser after starting the container
2. Downloaded models will be stored in the ./downloads directory on your host machine

2. Use the navigation buttons in the sidebar to switch between:
   - **Downloader**: Download new models from Thingiverse
   - **Browser**: Browse and view your downloaded models

### Downloading Models
1. Enter a valid Thingiverse URL (e.g., https://www.thingiverse.com/thing:12345)
2. Select a category to organize your models
3. Click "Download and Extract"
4. After download completes, navigate to the Browser tab to view your model

### Viewing Models
1. In the Browser tab, select a category or search for a model
2. Click on a model to view its details
3. Use the tabs to see the description, files, or 3D model viewer
4. In the 3D model viewer, customize the appearance with color and opacity controls

## Requirements

- Python 3.7+
- Streamlit
- Requests
- NumPy
- Plotly
- Trimesh
- PyMeshLab
- And other dependencies in requirements.txt

## Technical Notes

- The application uses a direct download approach from Thingiverse
- Models are organized in a category-based file structure
- 3D rendering uses Trimesh and Plotly for high-quality visualization
- The code follows modern Python practices with type hints and modular structure
