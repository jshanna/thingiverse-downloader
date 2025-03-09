"""Thingiverse Downloader - Download, organize, browse, and visualize 3D models from Thingiverse

This application provides a user-friendly interface for downloading 3D model packages from Thingiverse,
organizing them into categories, and browsing/visualizing the downloaded models with advanced 3D rendering.

Navigate between the downloader and browser pages using the sidebar navigation buttons. The downloader
allows single or batch downloads with category organization, while the browser provides searching,
filtering, and 3D visualization of downloaded models.

Key features:
- Download models from Thingiverse URLs (single or batch)
- Organize models into customizable categories
- Browse models by category with search functionality
- View detailed model information including thumbnails and README files
- High-quality 3D model visualization with customizable appearance

Author: Thingiverse Downloader Team
License: MIT
Version: 2.0.0
"""

import streamlit as st

import requests
import os
import re
import zipfile
import tempfile
import glob
import numpy as np
import plotly.graph_objects as go
from stl import mesh
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import trimesh
import pymeshlab
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple, Any

# Configuration settings for the application
@dataclass
class AppConfig:
    """Application configuration settings"""
    # Supported file extensions for 3D models
    model_extensions: List[str] = None
    # Supported file extensions for images
    image_extensions: List[str] = None
    # Default category name for uncategorized models
    default_category: str = "Uncategorized"
    
    def __post_init__(self):
        if self.model_extensions is None:
            self.model_extensions = [".stl", ".obj", ".3mf"]
        if self.image_extensions is None:
            self.image_extensions = [".png", ".jpg", ".jpeg"]

# Create a global config object
config = AppConfig()

def is_valid_thingiverse_url(url):
    """Check if the URL is a valid Thingiverse thing URL."""
    parsed_url = urlparse(url)
    return (parsed_url.netloc == 'www.thingiverse.com' or 
            parsed_url.netloc == 'thingiverse.com') and 'thing:' in parsed_url.path

def extract_thing_id(url):
    """Extract the thing ID from a Thingiverse URL."""
    match = re.search(r'thing:(\d+)', url)
    if match:
        return match.group(1)
    return None

def get_download_url(thing_id):
    """Get the download URL for a Thingiverse thing."""
    download_url = f"https://www.thingiverse.com/thing:{thing_id}/zip"
    return download_url

def download_and_extract(url, extract_path):
    """Download a ZIP file from URL and extract its contents."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_file:
        # Download the file
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        # Write to temporary file
        for chunk in response.iter_content(chunk_size=8192):
            temp_file.write(chunk)
        
        temp_file_path = temp_file.name
    
    # Extract the ZIP file
    try:
        with zipfile.ZipFile(temp_file_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
        os.unlink(temp_file_path)  # Delete the temporary file
        return True
    except zipfile.BadZipFile:
        os.unlink(temp_file_path)  # Delete the temporary file
        return False

def find_thumbnail(directory, thing_id):
    """Find the thumbnail image for a specific thing ID.
    
    Args:
        directory (str): The directory to search for thumbnails
        thing_id (str): The thing ID to help find specific thumbnails
        
    Returns:
        str or None: Path to the thumbnail image if found, None otherwise
    """
    # Define search strategies in order of preference
    search_strategies = [
        # Strategy 1: Check images directory first
        lambda: find_in_images_dir(directory),
        # Strategy 2: Look for files with _Thumbnail in the name
        lambda: find_first_match(directory, f"*_Thumbnail*.png"),
        # Strategy 3: Look for files with thing_id and Thumbnail
        lambda: find_first_match(directory, f"*{thing_id}*Thumbnail*.png"),
        # Strategy 4: Any PNG file as fallback
        lambda: find_first_match(directory, "*.png")
    ]
    
    # Try each strategy in order until we find a thumbnail
    for strategy in search_strategies:
        thumbnail = strategy()
        if thumbnail:
            return thumbnail
    
    return None

def find_in_images_dir(directory):
    """Find the first image in the 'images' subdirectory."""
    images_dir = os.path.join(directory, "images")
    if not os.path.exists(images_dir):
        return None
        
    image_files = []
    for ext in [".png", ".jpg", ".jpeg"]:
        image_files.extend(glob.glob(os.path.join(images_dir, f"*{ext}")))
    
    if image_files:
        image_files.sort()
        return image_files[0]
    
    return None

def find_first_match(directory, pattern):
    """Find the first file matching a glob pattern."""
    matches = glob.glob(os.path.join(directory, pattern))
    if matches:
        matches.sort()
        return matches[0]
    
    return None

def downloader_page(downloads_dir):
    st.title("Download Thingiverse Models")
    
    # Create tabs for single and batch downloads
    single_tab, batch_tab = st.tabs(["Single Download", "Batch Download"])
    
    with single_tab:
        st.write("Enter a Thingiverse URL to download and extract the 3D model files.")
        
        # Input for Thingiverse URL
        thingiverse_url = st.text_input("Thingiverse URL", 
                                     placeholder="https://www.thingiverse.com/thing:12345")
    
    with batch_tab:
        st.write("Enter multiple Thingiverse URLs (one per line) to download several models at once.")
        
        # Text area for multiple URLs
        batch_urls = st.text_area("Thingiverse URLs (one per line)", 
                                 placeholder="https://www.thingiverse.com/thing:12345\nhttps://www.thingiverse.com/thing:67890")
    
    # Common section for both tabs
    st.markdown("---")
    
    # Category selection
    # Get existing categories from the directory structure
    categories = ["Uncategorized"]  # Default category
    if os.path.exists(downloads_dir):
        for item in os.listdir(downloads_dir):
            item_path = os.path.join(downloads_dir, item)
            if os.path.isdir(item_path) and item != "Uncategorized":
                categories.append(item)
    
    # Add option to create a new category
    categories.append("+ Create new category")
    
    # Category dropdown
    st.write("**Select category for the download(s):**")
    selected_category = st.selectbox("Select category:", categories, label_visibility="collapsed")
    
    # If user selects to create a new category, show an input field
    new_category = None
    if selected_category == "+ Create new category":
        new_category = st.text_input("Enter new category name:")
        if new_category:
            selected_category = new_category
    
    # Common download button for both tabs
    if st.button("Download and Extract"):
        # Create extract directory if it doesn't exist
        os.makedirs(downloads_dir, exist_ok=True)
        
        # Create the category directory if it doesn't exist
        category_dir = os.path.join(downloads_dir, selected_category)
        os.makedirs(category_dir, exist_ok=True)
        
        # Determine which tab is active by checking inputs
        if batch_urls.strip():
            # Batch download mode
            urls = batch_urls.strip().split('\n')
            valid_urls = []
            
            # Validate all URLs first
            with st.expander("Validation Results", expanded=True):
                for url in urls:
                    if not url.strip():
                        continue
                        
                    if not is_valid_thingiverse_url(url):
                        st.error(f"Invalid URL: {url}")
                        continue
                        
                    thing_id = extract_thing_id(url)
                    if not thing_id:
                        st.error(f"Could not extract thing ID from URL: {url}")
                        continue
                        
                    valid_urls.append((url, thing_id))
                
                st.info(f"Found {len(valid_urls)} valid Thingiverse URLs to download.")
            
            if valid_urls:
                # Create a progress bar for overall progress
                overall_progress = st.progress(0, text="Overall progress...")
                
                # Download each valid URL
                for i, (url, thing_id) in enumerate(valid_urls):
                    # Create a specific directory for this model within the category
                    model_dir = os.path.join(category_dir, f"thing_{thing_id}")
                    os.makedirs(model_dir, exist_ok=True)
                    
                    # Get download URL
                    download_url = get_download_url(thing_id)
                    
                    # Update progress
                    progress_text = f"Downloading model {i+1}/{len(valid_urls)}: thing_{thing_id}..."
                    st.write(progress_text)
                    
                    try:
                        # Download and extract
                        download_and_extract(download_url, model_dir)
                        st.success(f"Successfully downloaded and extracted thing_{thing_id}.")
                    except Exception as e:
                        st.error(f"Error downloading thing_{thing_id}: {str(e)}")
                    
                    # Update overall progress
                    overall_progress.progress((i+1)/len(valid_urls), text=f"Overall progress: {i+1}/{len(valid_urls)} complete")
                
                st.success("Batch download complete!")
                
        else:
            # Single download mode
            if not thingiverse_url:
                st.error("Please enter a Thingiverse URL.")
                return
            
            if not is_valid_thingiverse_url(thingiverse_url):
                st.error("Please enter a valid Thingiverse URL (e.g., https://www.thingiverse.com/thing:12345).")
                return
            
            thing_id = extract_thing_id(thingiverse_url)
            if not thing_id:
                st.error("Could not extract thing ID from the URL.")
                return
        
        # Create a specific directory for this model within the category
        model_dir = os.path.join(category_dir, f"thing_{thing_id}")
        os.makedirs(model_dir, exist_ok=True)
        
        # Get download URL
        download_url = get_download_url(thing_id)
        
        # Create a progress bar
        progress_text = "Downloading model..."
        progress_bar = st.progress(0, text=progress_text)
        
        try:
            # Send a GET request to the download URL
            response = requests.get(download_url, stream=True)
            response.raise_for_status()  # Raise an exception for HTTP errors
            
            # Get the total file size if available
            total_size = int(response.headers.get('content-length', 0))
            
            # Generate a filename based on the thing ID
            zip_filename = os.path.join(model_dir, f"thing_{thing_id}.zip")
            
            # Download the file with progress updates
            downloaded_size = 0
            with open(zip_filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:  # Filter out keep-alive chunks
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # Update progress bar
                        if total_size > 0:
                            progress = min(downloaded_size / total_size, 1.0)
                            progress_bar.progress(progress, text=f"{progress_text} {downloaded_size / (1024 * 1024):.1f} MB")
            
            # Extract the ZIP file
            progress_bar.progress(1.0, text="Extracting files...")
            
            with zipfile.ZipFile(zip_filename, 'r') as zip_ref:
                zip_ref.extractall(model_dir)
            
            # Clean up the ZIP file
            os.remove(zip_filename)
            
            progress_bar.empty()
            
            # Display success message
            st.success(f"Files successfully downloaded and extracted to {model_dir}")
            
            # Add a simple message about where to find the model
            st.info(f"You can find your downloaded model in the Browser tab under the '{selected_category}' category.")
            
        except requests.exceptions.RequestException as e:
            progress_bar.empty()
            st.error(f"Failed to download: {str(e)}")
        except zipfile.BadZipFile:
            progress_bar.empty()
            st.error("Downloaded file is not a valid ZIP file")
        except Exception as e:
            progress_bar.empty()
            st.error(f"An error occurred: {str(e)}")

def find_readme(directory: str) -> Optional[str]:
    """Find README.txt or similar files in the directory.
    
    Args:
        directory (str): Directory to search for README files
        
    Returns:
        Optional[str]: Path to the README file if found, None otherwise
    """
    # Define common README file patterns (could be moved to config)
    readme_patterns = [
        "README.txt", "readme.txt", "ReadMe.txt", "Readme.txt",
        "README.md", "readme.md", "ReadMe.md", "Readme.md",
        "instructions.txt", "Instructions.txt",
        "description.txt", "Description.txt"
    ]
    
    # Strategy 1: Check root directory first (most common case)
    for pattern in readme_patterns:
        readme_path = os.path.join(directory, pattern)
        if os.path.exists(readme_path):
            return readme_path
    
    # Strategy 2: Search recursively in subdirectories
    # Create a lowercase lookup for more efficient comparison
    lowercase_patterns = [p.lower() for p in readme_patterns]
    
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower() in lowercase_patterns:
                return os.path.join(root, file)
    
    return None

def get_model_info(model_path: str, model_name: str) -> Dict[str, Any]:
    """Get comprehensive information about a 3D model.
    
    Args:
        model_path (str): Path to the model directory
        model_name (str): Name of the model (usually directory name)
        
    Returns:
        Dict[str, Any]: Dictionary containing model information including:
            - name: Model name
            - path: Path to model directory
            - thing_id: Thingiverse ID if available
            - thumbnail_path: Path to thumbnail if found
            - model_files: List of 3D model files (name, path) tuples
            - model_count: Number of 3D model files
            - readme_path: Path to README file if found
            - readme_content: Content of README file
    """
    # Extract thing ID from the directory name
    thing_id_match = re.search(r'(\d+)', model_name)
    thing_id = thing_id_match.group(1) if thing_id_match else None
    
    # Find thumbnail if available
    thumbnail_path = find_thumbnail(model_path, thing_id or "")
    
    # Find all 3D model files using global config
    model_files = find_model_files(model_path)
    
    # Get README content
    readme_path, readme_content = get_readme_content(model_path)
    
    # Build comprehensive model info dictionary
    return {
        "name": model_name,
        "path": model_path,
        "thing_id": thing_id,
        "thumbnail_path": thumbnail_path,
        "model_files": model_files,
        "model_count": len(model_files),
        "readme_path": readme_path,
        "readme_content": readme_content
    }

def find_model_files(directory: str) -> List[Tuple[str, str]]:
    """Find all 3D model files in a directory.
    
    Args:
        directory (str): Directory to search for model files
        
    Returns:
        List[Tuple[str, str]]: List of (relative_path, absolute_path) tuples for model files
    """
    model_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            file_ext = os.path.splitext(file)[1].lower()
            if file_ext in config.model_extensions:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, directory)
                model_files.append((rel_path, abs_path))
    return model_files

def get_readme_content(directory: str) -> Tuple[Optional[str], str]:
    """Get README file path and content.
    
    Args:
        directory (str): Directory to search for README file
        
    Returns:
        Tuple[Optional[str], str]: (readme_path, readme_content)
    """
    readme_path = find_readme(directory)
    readme_content = ""
    
    if readme_path:
        try:
            with open(readme_path, 'r', encoding='utf-8', errors='replace') as f:
                readme_content = f.read()
        except Exception as e:
            readme_content = f"Error reading README: {str(e)}"
    
    return readme_path, readme_content

def display_model_details(model_info):
    """Display detailed information for a model"""
    st.write(f"### {model_info['name']}")
    
    # Create columns for thumbnail and basic info
    col1, col2 = st.columns([1, 2])
    
    with col1:
        if model_info['thumbnail_path'] and os.path.exists(model_info['thumbnail_path']):
            st.image(model_info['thumbnail_path'], use_column_width=True)
        else:
            st.info("No preview image available")
    
    with col2:
        st.write(f"**Thing ID:** {model_info['thing_id'] if model_info['thing_id'] else 'Unknown'}")
        st.write(f"**3D Model Files:** {model_info['model_count']}")
        st.write(f"**Location:** {model_info['path']}")
    
    # Create tabs for file browser and 3D model viewer
    file_browser_tab, model_viewer_tab = st.tabs(["Files", "3D Model Viewer"])
    
    with file_browser_tab:
        # Display files in a more organized way
        st.write("#### Files:")
        for file in sorted(os.listdir(model_info['path'])):
            file_path = os.path.join(model_info['path'], file)
            if os.path.isdir(file_path):
                st.markdown(f"📁 **{file}/**")
                # List files in subdirectory
                subfiles = os.listdir(file_path)
                for subfile in sorted(subfiles):
                    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;📄 {subfile}")
            else:
                st.markdown(f"📄 {file}")
    
    with model_viewer_tab:
        if model_info['model_files']:
            # Let user select which 3D model to view
            selected_model = st.selectbox("Select 3D model file to view", 
                                       [name for name, _ in model_info['model_files']])
            
            # Get the full path of the selected model
            selected_model_path = next((path for name, path in model_info['model_files'] if name == selected_model), None)
            
            if selected_model_path:
                # Display file format
                file_ext = os.path.splitext(selected_model_path)[1].lower()
                st.write(f"File format: {file_ext[1:].upper()}")
                
                try:
                    # Load the 3D model file based on its format
                    if file_ext == '.stl':
                        # Use numpy-stl for STL files
                        your_mesh = mesh.Mesh.from_file(selected_model_path)
                    
                        # Get the vertices and faces for plotting
                        x = your_mesh.x.flatten()
                        y = your_mesh.y.flatten()
                        z = your_mesh.z.flatten()
                        
                        # Create a 3D mesh plot
                        fig = go.Figure(data=[
                            go.Mesh3d(
                                x=x,
                                y=y,
                                z=z,
                                color='lightblue',
                                opacity=0.8,
                            )
                        ])
                    else:  # .obj or .3mf
                        # Display a message about limited preview support
                        st.info(f"Preview for {file_ext[1:].upper()} files is currently only available for download. You can download the file to view it in your preferred 3D model viewer.")
                        # Skip the 3D visualization for non-STL files
                        fig = None
                    
                    # Only update and display the plot if fig is not None (for STL files)
                    if fig is not None:
                        # Update the layout for better visualization
                        fig.update_layout(
                            scene=dict(
                                xaxis=dict(showticklabels=False),
                                yaxis=dict(showticklabels=False),
                                zaxis=dict(showticklabels=False),
                            ),
                            margin=dict(l=0, r=0, b=0, t=0),
                            scene_camera=dict(
                                eye=dict(x=1.5, y=1.5, z=1.5)
                            ),
                            height=500,
                        )
                        
                        # Display the plot in Streamlit
                        st.plotly_chart(fig, use_container_width=True)
                    
                    # Add a download button for the 3D model file
                    with open(selected_model_path, "rb") as file:
                        st.download_button(
                            label=f"Download {file_ext[1:].upper()} file",
                            data=file,
                            file_name=os.path.basename(selected_model_path),
                            mime="application/octet-stream"
                        )
                except Exception as e:
                    st.error(f"Error loading 3D model file: {str(e)}")
        else:
            st.info("No 3D model files found in this model.")

def browser_page(downloads_dir, selected_model_name=None, selected_category=None):
    st.title("Model Browser")
    
    # Initialize session state variables if they don't exist
    if 'selected_model' not in st.session_state:
        st.session_state.selected_model = None
    
    # No special handling needed since we removed the View Model Details button
    
    # If a specific model name is provided, look for it in the specified category or all categories
    if selected_model_name:
        found = False
        
        # First, check if we have a selected category to look in
        if selected_category and os.path.exists(downloads_dir):
            category_path = os.path.join(downloads_dir, selected_category)
            if os.path.isdir(category_path):
                model_path = os.path.join(category_path, selected_model_name)
                if os.path.exists(model_path):
                    model_info = get_model_info(model_path, selected_model_name)
                    model_info['category'] = selected_category  # Add category to model info
                    st.session_state.selected_model = model_info
                    found = True
        
        # If not found and we have a category, show a specific error message
        if not found and selected_category:
            st.warning(f"Model '{selected_model_name}' not found in the '{selected_category}' category.")
            
        # If no category specified or not found in the specified category, check all categories
        if not found and os.path.exists(downloads_dir):
            for category in os.listdir(downloads_dir):
                category_path = os.path.join(downloads_dir, category)
                if os.path.isdir(category_path):
                    model_path = os.path.join(category_path, selected_model_name)
                    if os.path.exists(model_path):
                        model_info = get_model_info(model_path, selected_model_name)
                        model_info['category'] = category  # Add category to model info
                        st.session_state.selected_model = model_info
                        found = True
                        break
        
        # If still not found, show a general error message
        if not found and selected_model_name:
            st.warning(f"Model '{selected_model_name}' not found in any category.")
    
    # Check if the downloads directory has any subdirectories (categories)
    if os.path.exists(downloads_dir) and os.listdir(downloads_dir):
        # Get all subdirectories in the downloads directory (these are categories)
        categories = [d for d in os.listdir(downloads_dir) 
                     if os.path.isdir(os.path.join(downloads_dir, d))]
        
        if categories:
            # If a model is selected, show the detail view instead of the gallery
            if st.session_state.selected_model is not None:
                # Add a back button to return to the gallery
                if st.button("← Back to Gallery"):
                    st.session_state.selected_model = None
                    st.rerun()
                
                # Get the selected model info
                model = st.session_state.selected_model
                
                # Display the model details in a full-width view
                st.write(f"## {model['name']}")
                
                # Create columns for thumbnail and basic info
                col1, col2 = st.columns([1, 2])
                
                with col1:
                    if model['thumbnail_path'] and os.path.exists(model['thumbnail_path']):
                        st.image(model['thumbnail_path'], use_column_width=True)
                    else:
                        st.info("No preview image available")
                
                with col2:
                    st.write(f"**Thing ID:** {model['thing_id'] if model['thing_id'] else 'Unknown'}")
                    st.write(f"**3D Model Files:** {model['model_count']}")
                    
                    # Display the category if it exists
                    if 'category' in model:
                        st.write(f"**Category:** {model['category']}")
                        
                    st.write(f"**Location:** {model['path']}")
                
                # Create tabs for README, file browser and 3D model viewer
                readme_tab, file_browser_tab, model_viewer_tab = st.tabs(["Description", "Files", "3D Model Viewer"])
                
                with readme_tab:
                    if model['readme_content']:
                        # Display README content as markdown
                        st.markdown(model['readme_content'])
                        
                        # Show the path to the README file
                        if model['readme_path']:
                            st.caption(f"Source: {os.path.basename(model['readme_path'])}")
                    else:
                        st.info("No description or README file found for this model.")
                
                with file_browser_tab:
                    # Display files in a more organized way
                    st.write("#### Files:")
                    for file in sorted(os.listdir(model['path'])):
                        file_path = os.path.join(model['path'], file)
                        if os.path.isdir(file_path):
                            st.markdown(f"📁 **{file}/**")
                            # List files in subdirectory
                            subfiles = os.listdir(file_path)
                            for subfile in sorted(subfiles):
                                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;📄 {subfile}")
                        else:
                            st.markdown(f"📄 {file}")
                
                with model_viewer_tab:
                    if model['model_files']:
                        # Let user select which 3D model to view
                        selected_model = st.selectbox("Select 3D model file to view", 
                                                [name for name, _ in model['model_files']])
                        
                        # Get the full path of the selected model
                        selected_model_path = next((path for name, path in model['model_files'] if name == selected_model), None)
                        
                        if selected_model_path:
                            # Display file format
                            file_ext = os.path.splitext(selected_model_path)[1].lower()
                            st.write(f"File format: {file_ext[1:].upper()}")
                            
                            try:
                                # Load the 3D model file based on its format
                                if file_ext == '.stl':
                                    # Use trimesh for better STL rendering
                                    try:
                                        # Load the mesh with trimesh for better processing
                                        tm_mesh = trimesh.load(selected_model_path)
                                        
                                        # Center the model and normalize size
                                        tm_mesh.apply_translation(-tm_mesh.center_mass)
                                        # Normalize size for consistent display
                                        scale = 100.0 / max(tm_mesh.extents)
                                        tm_mesh.apply_scale(scale)
                                        
                                        # Get vertices and faces for plotting
                                        vertices = tm_mesh.vertices
                                        faces = tm_mesh.faces
                                        
                                        # Convert to x, y, z arrays for plotly
                                        i, j, k = faces[:, 0], faces[:, 1], faces[:, 2]
                                        x, y, z = vertices[:, 0], vertices[:, 1], vertices[:, 2]
                                        
                                        # Calculate normals for better lighting
                                        normals = tm_mesh.face_normals
                                        
                                        # Create improved 3D mesh with better visual settings
                                        fig = go.Figure(data=[
                                            go.Mesh3d(
                                                x=x, y=y, z=z,
                                                i=i, j=j, k=k,
                                                # Use nicer color and lighting
                                                intensity=z,  # Color based on z height for visual interest
                                                colorscale='Viridis',
                                                opacity=1.0,
                                                lighting=dict(
                                                    ambient=0.5,
                                                    diffuse=0.8,
                                                    roughness=0, 
                                                    specular=0.9,
                                                    fresnel=0.1
                                                ),
                                                lightposition=dict(x=100, y=100, z=100),
                                                # Smooth appearance
                                                flatshading=False
                                            )
                                        ])
                                        
                                        # Configure layout for better viewing experience
                                        fig.update_layout(
                                            scene=dict(
                                                aspectmode='data',
                                                xaxis=dict(visible=False),
                                                yaxis=dict(visible=False),
                                                zaxis=dict(visible=False),
                                                camera=dict(
                                                    eye=dict(x=1.5, y=1.5, z=1.5)
                                                )
                                            ),
                                            margin=dict(l=0, r=0, t=0, b=0)
                                        )
                                    except Exception as e:
                                        st.error(f"Error rendering the STL file: {str(e)}")
                                        # Fallback to the original implementation if trimesh fails
                                        your_mesh = mesh.Mesh.from_file(selected_model_path)
                                        x = your_mesh.x.flatten()
                                        y = your_mesh.y.flatten()
                                        z = your_mesh.z.flatten()
                                        
                                        fig = go.Figure(data=[
                                            go.Mesh3d(
                                                x=x, y=y, z=z,
                                                color='lightblue',
                                                opacity=0.8,
                                            )
                                        ])
                                else:  # .obj or .3mf
                                    # Display a message about simplified support for non-STL files
                                    st.info(f"Preview for {file_ext[1:].upper()} files is currently only available for download. You can download the file to view it in your preferred 3D model viewer.")
                                    
                                    # Skip 3D visualization for non-STL files to avoid errors with Scene objects
                                    fig = None
                                    
                                    # Add a download button for the model file
                                    with open(selected_model_path, "rb") as file:
                                        st.download_button(
                                            label=f"Download {file_ext[1:].upper()} file",
                                            data=file,
                                            file_name=os.path.basename(selected_model_path),
                                            mime="application/octet-stream"
                                        )
                                    # Return early since we're not showing a 3D visualization
                                    return
                                
                                # Update the layout for better visualization
                                fig.update_layout(
                                    scene=dict(
                                        xaxis=dict(showticklabels=False),
                                        yaxis=dict(showticklabels=False),
                                        zaxis=dict(showticklabels=False),
                                    ),
                                    margin=dict(l=0, r=0, b=0, t=0),
                                    scene_camera=dict(
                                        eye=dict(x=1.5, y=1.5, z=1.5)
                                    ),
                                    height=600,  # Taller plot for better visibility
                                )
                                
                                # Add user-friendly controls for customizing the model appearance
                                col1, col2 = st.columns([1, 1])
                                with col1:
                                    color_option = st.selectbox(
                                        "Color Style",
                                        ["Viridis", "Plasma", "Inferno", "Magma", "Cividis", "Rainbow", "Solid Blue", "Solid Green"]
                                    )
                                with col2:
                                    # Add a slider for opacity
                                    opacity = st.slider("Opacity", min_value=0.1, max_value=1.0, value=1.0, step=0.1)
                                
                                # Update figure based on user selections
                                if hasattr(fig.data[0], 'intensity') and "Solid" not in color_option:
                                    fig.data[0].colorscale = color_option.lower()
                                    fig.data[0].opacity = opacity
                                elif "Solid Blue" in color_option:
                                    fig.data[0].colorscale = None
                                    fig.data[0].intensity = None
                                    fig.data[0].color = 'royalblue'
                                    fig.data[0].opacity = opacity
                                elif "Solid Green" in color_option:
                                    fig.data[0].colorscale = None
                                    fig.data[0].intensity = None
                                    fig.data[0].color = 'mediumseagreen'
                                    fig.data[0].opacity = opacity
                                
                                # Display the plot in Streamlit with a good height for better visualization
                                st.plotly_chart(fig, use_container_width=True, height=600)
                                
                                # Add a download button for the 3D model file
                                with open(selected_model_path, "rb") as file:
                                    st.download_button(
                                        label=f"Download {file_ext[1:].upper()} file",
                                        data=file,
                                        file_name=os.path.basename(selected_model_path),
                                        mime="application/octet-stream"
                                    )
                            except Exception as e:
                                st.error(f"Error loading 3D model file: {str(e)}")
                    else:
                        st.info("No 3D model files found in this model.")
            else:
                # Show the gallery view
                st.write("### 3D Model Browser")
                
                # Add search functionality
                search_query = st.text_input("🔍 Search models by name, ID or description", "").lower()
                
                # For each category, display its models
                for category in sorted(categories):
                    category_path = os.path.join(downloads_dir, category)
                    
                    # Get all models in this category
                    model_dirs = [d for d in os.listdir(category_path) 
                                if os.path.isdir(os.path.join(category_path, d))]
                    
                    if model_dirs:
                        # Add separator between categories (except for the first one)
                        if category != sorted(categories)[0]:
                            st.markdown("---")
                            
                        # Create a header for each category with a bit of styling
                        st.markdown(f"<h3 style='color: #1E88E5;'>{category} <span style='font-size: 0.8em; color: #424242;'>({len(model_dirs)} models)</span></h3>", unsafe_allow_html=True)
                        
                        # Create a container for this category's models
                        with st.container():
                            # Collect model information for this category
                            category_models = []
                            for model_name in model_dirs:
                                model_path = os.path.join(category_path, model_name)
                                model_info = get_model_info(model_path, model_name)
                                # Add category to model info
                                model_info['category'] = category
                                
                                # Filter models based on search query if provided
                                if search_query:
                                    # Check if search query is in the model name, id, or readme content
                                    model_matches = False
                                    # Check name
                                    if search_query in model_info['name'].lower():
                                        model_matches = True
                                    # Check thing_id
                                    elif model_info['thing_id'] and search_query in model_info['thing_id'].lower():
                                        model_matches = True
                                    # Check readme content
                                    elif model_info['readme_content'] and search_query in model_info['readme_content'].lower():
                                        model_matches = True
                                    
                                    # Only add if it matches the search
                                    if model_matches:
                                        category_models.append(model_info)
                                else:
                                    # No search query, add all models
                                    category_models.append(model_info)
                            
                            # Display models in a grid layout
                            cols = st.columns(3)  # Create 3 columns for the gallery
                            
                            for i, model in enumerate(category_models):
                                with cols[i % 3]:
                                    # Create a card-like display for each model
                                    with st.container():
                                        # Show thumbnail if available, otherwise show placeholder
                                        if model['thumbnail_path'] and os.path.exists(model['thumbnail_path']):
                                            st.image(model['thumbnail_path'], use_column_width=True)
                                        else:
                                            # Display a placeholder for models without thumbnails
                                            st.markdown(
                                                """<div style='background-color: #f0f0f0; height: 150px; 
                                                display: flex; align-items: center; justify-content: center;'>
                                                <span style='color: #888; font-size: 24px;'>No Preview</span>
                                                </div>""", 
                                                unsafe_allow_html=True
                                            )
                                        
                                        # Display model name and basic info
                                        st.write(f"**{model['name']}**")
                                        st.write(f"3D Model Files: {model['model_count']}")
                                        st.write(f"Category: {model['category']}")
                                        
                                        # Add a button to view details
                                        if st.button(f"View Details", key=f"view_details_{category}_{i}"):
                                            st.session_state.selected_model = model
                                            st.rerun()
        else:
            st.info("No models found. Download a model to get started.")
    else:
        st.info("No models downloaded yet. Use the downloader to download a model.")

def main():
    # Create a directory for downloads if it doesn't exist
    project_dir = os.path.dirname(os.path.abspath(__file__))
    downloads_dir = os.path.join(project_dir, "downloads")
    os.makedirs(downloads_dir, exist_ok=True)
    
    # Get query parameters
    query_params = st.query_params
    
    # Set up the sidebar
    st.sidebar.title("Thingiverse Downloader")
    
    # Navigation section at the top of the sidebar
    st.sidebar.subheader("Navigation")
    
    # Navigation buttons
    col1, col2 = st.sidebar.columns(2)
    with col1:
        browser_btn = st.button("Browser", use_container_width=True)
    with col2:
        downloader_btn = st.button("Downloader", use_container_width=True)
        
    # Initialize session state for page if not exists
    if 'page' not in st.session_state:
        st.session_state.page = "Browser"  # Default page
        
    # Update page based on button clicks
    if browser_btn:
        st.session_state.page = "Browser"
    if downloader_btn:
        st.session_state.page = "Downloader"
        
    # Add a sidebar section for tools
    st.sidebar.markdown("---")
    st.sidebar.subheader("Tools")
    
    # Add backup/restore options
    with st.sidebar.expander("Backup & Restore"):
        st.write("Export or import your collection data.")
        
        col1, col2 = st.columns(2)
        with col1:
            # Export button
            if st.button("Export Collection"):
                try:
                    # Create a JSON export of the collection structure
                    export_data = {"categories": {}}
                    
                    if os.path.exists(downloads_dir):
                        for category in os.listdir(downloads_dir):
                            category_path = os.path.join(downloads_dir, category)
                            if os.path.isdir(category_path):
                                export_data["categories"][category] = []
                                
                                for model in os.listdir(category_path):
                                    model_path = os.path.join(category_path, model)
                                    if os.path.isdir(model_path):
                                        # Get model info
                                        model_info = get_model_info(model_path, model)
                                        export_data["categories"][category].append({
                                            "name": model,
                                            "thing_id": model_info.get("thing_id", ""),
                                            "model_count": model_info.get("model_count", 0),
                                            "path": model_path,
                                            "download_date": model_info.get("download_date", ""),
                                        })
                    
                    # Create a download link
                    import json
                    import base64
                    from datetime import datetime
                    
                    export_str = json.dumps(export_data, indent=2)
                    b64 = base64.b64encode(export_str.encode()).decode()
                    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"thingiverse_collection_{date_str}.json"
                    href = f'<a href="data:application/json;base64,{b64}" download="{filename}">Download Export File</a>'
                    st.markdown(href, unsafe_allow_html=True)
                    st.success("Export file ready for download!")
                except Exception as e:
                    st.error(f"Error exporting collection: {str(e)}")
                    
        with col2:
            # Import button
            uploaded_file = st.file_uploader("Import", type="json")
            if uploaded_file is not None:
                try:
                    import json
                    # Load and validate the file
                    import_data = json.loads(uploaded_file.read())
                    
                    if "categories" not in import_data:
                        st.error("Invalid import file format.")
                    else:
                        # Show summary of what will be imported
                        categories = import_data["categories"]
                        st.write(f"Found {len(categories)} categories with {sum(len(models) for models in categories.values())} models.")
                        
                        # Show restore button
                        if st.button("Restore from Backup"):
                            st.info("Restore functionality would go here in a production version.")
                            # Note: Actually restoring would involve copying files, which is complex and could be dangerous
                            # so we're just showing a placeholder for now
                except Exception as e:
                    st.error(f"Error importing file: {str(e)}")
    
    # Add a sidebar section for app information
    st.sidebar.markdown("---")
    st.sidebar.subheader("App Statistics")
    # Calculate app statistics if the downloads directory exists
    if os.path.exists(downloads_dir):
        # Count categories, models, and estimate storage
        categories = [d for d in os.listdir(downloads_dir) if os.path.isdir(os.path.join(downloads_dir, d))]
        model_count = 0
        total_size = 0
        for category in categories:
            category_path = os.path.join(downloads_dir, category)
            models = [d for d in os.listdir(category_path) if os.path.isdir(os.path.join(category_path, d))]
            model_count += len(models)
            
            # Calculate directory size
            for root, dirs, files in os.walk(category_path):
                for file in files:
                    try:
                        total_size += os.path.getsize(os.path.join(root, file))
                    except (FileNotFoundError, PermissionError):
                        pass
        
        # Display statistics
        st.sidebar.info(f"📊 **Statistics**\n\n"
                      f"Categories: {len(categories)}\n"
                      f"Models: {model_count}\n"
                      f"Storage used: {total_size / (1024*1024):.1f} MB")
    
    # Use session state for navigation - no more URL parameters
    if st.session_state.page == "Browser":
        browser_page(downloads_dir)
    else:  # Downloader
        downloader_page(downloads_dir)
    


if __name__ == "__main__":
    main()
