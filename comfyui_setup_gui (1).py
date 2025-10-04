import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
import shutil

def select_batch_file():
    """Open file dialog to select run_nvidia_gpu.bat"""
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    
    print("\n" + "="*60)
    print("ComfyUI Mobile API - Setup Wizard")
    print("="*60)
    print("\nPlease select the 'run_nvidia_gpu.bat' file from your ComfyUI folder...")
    
    file_path = filedialog.askopenfilename(
        title="Select run_nvidia_gpu.bat from ComfyUI folder",
        filetypes=[("Batch files", "*.bat"), ("All files", "*.*")],
        initialdir="C:\\"
    )
    
    root.destroy()
    
    if not file_path:
        print("\nNo file selected. Setup cancelled.")
        input("\nPress Enter to exit...")
        return None
    
    return Path(file_path)

def find_output_folder(comfyui_root):
    """Locate the output folder within ComfyUI directory"""
    print(f"\nSearching for output folder in: {comfyui_root}")
    
    possible_paths = [
        comfyui_root / "output",
        comfyui_root / "ComfyUI" / "output",
        comfyui_root / "comfyui" / "output",
    ]
    
    for path in possible_paths:
        if path.exists() and path.is_dir():
            print(f"Found output folder: {path}")
            return path
    
    # If not found, try to find any folder named 'output'
    print("Searching subdirectories for 'output' folder...")
    for item in comfyui_root.rglob("output"):
        if item.is_dir():
            print(f"Found output folder: {item}")
            return item
    
    print("Warning: Output folder not found, will create default path")
    return comfyui_root / "ComfyUI" / "output"

def generate_configured_script(comfyui_root, output_dir):
    """Generate a new API script with configured paths"""
    
    script_content = f'''import asyncio
import json
import requests
import uuid
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import uvicorn
from typing import Optional, List
import glob
from PIL import Image
from PIL.ExifTags import TAGS
import base64
from io import BytesIO

app = FastAPI(title="ComfyUI Mobile API")

# Configuration - Auto-configured by setup script
COMFYUI_HOST = "127.0.0.1"
COMFYUI_PORT = 8188
OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

# ComfyUI Output Directory - Auto-detected
COMFYUI_OUTPUT_DIR = Path(r"{output_dir}")

class GenerateRequest(BaseModel):
    prompt: str
    negative_prompt: Optional[str] = ""
    width: int = 1408
    height: int = 1408
    steps: int = 10
    cfg_scale: float = 1.0
    sampler: str = "lcm"
    scheduler: str = "beta"
    model: str = "mopMixtureOfPerverts_v31.safetensors"
    clip_skip: int = -2
    seed: int = -1

def extract_metadata_from_image(image_path):
    """Extract ComfyUI metadata from image - improved version"""
    try:
        with Image.open(image_path) as img:
            # Try PNG text chunks first (ComfyUI's preferred method)
            if hasattr(img, 'text') and img.text:
                # Check for prompt in text chunks
                if 'prompt' in img.text:
                    try:
                        prompt_data = json.loads(img.text['prompt'])
                        return extract_from_prompt_json(prompt_data)
                    except:
                        pass
                
                # Check for workflow
                if 'workflow' in img.text:
                    try:
                        workflow_data = json.loads(img.text['workflow'])
                        return extract_from_workflow_json(workflow_data)
                    except:
                        pass
                
                # Check for A1111 style parameters
                if 'parameters' in img.text:
                    return parse_a1111_parameters(img.text['parameters'])
            
            # Try EXIF as fallback
            exif = img.getexif()
            if exif:
                for tag_id, value in exif.items():
                    tag_name = TAGS.get(tag_id, tag_id)
                    if tag_name == 'UserComment' and value:
                        try:
                            if isinstance(value, bytes):
                                value = value.decode('utf-8', errors='ignore')
                            return json.loads(value)
                        except:
                            pass
                            
    except Exception as e:
        print(f"Error extracting metadata from {{image_path}}: {{e}}")
    
    return None

def extract_from_prompt_json(prompt_data):
    """Extract settings from ComfyUI prompt JSON (most reliable method)"""
    try:
        settings = {{}}
        
        # prompt_data is a dict with node IDs as keys
        for node_id, node_data in prompt_data.items():
            class_type = node_data.get('class_type', '')
            inputs = node_data.get('inputs', {{}})
            
            # Extract text prompts
            if class_type == 'CLIPTextEncode':
                text = inputs.get('text', '')
                if text:
                    if not settings.get('prompt'):
                        settings['prompt'] = text
                    elif not settings.get('negative_prompt'):
                        settings['negative_prompt'] = text
            
            # Extract KSampler settings
            elif class_type == 'KSampler' or class_type == 'KSamplerAdvanced':
                settings['steps'] = inputs.get('steps', 20)
                settings['cfg_scale'] = inputs.get('cfg', 7.0)
                settings['sampler'] = inputs.get('sampler_name', 'euler')
                settings['scheduler'] = inputs.get('scheduler', 'normal')
                settings['seed'] = inputs.get('seed', -1)
            
            # Extract image dimensions
            elif class_type == 'EmptyLatentImage':
                settings['width'] = inputs.get('width', 512)
                settings['height'] = inputs.get('height', 512)
            
            # Extract model
            elif class_type == 'CheckpointLoaderSimple':
                settings['model'] = inputs.get('ckpt_name', '')
            
            # Extract CLIP skip
            elif class_type == 'CLIPSetLastLayer':
                settings['clip_skip'] = inputs.get('stop_at_clip_layer', -1)
        
        return settings if settings else None
        
    except Exception as e:
        print(f"Error extracting from prompt JSON: {{e}}")
        return None

def extract_from_workflow_json(workflow_data):
    """Extract settings from ComfyUI workflow JSON (fallback method)"""
    try:
        settings = {{}}
        
        for node_id, node in workflow_data.items():
            node_type = node.get('class_type', '')
            
            # Get widgets_values which contains the actual values
            widgets = node.get('widgets_values', [])
            inputs = node.get('inputs', {{}})
            
            if node_type == 'CLIPTextEncode':
                # Text is usually in widgets_values[0] or inputs
                text = None
                if widgets and len(widgets) > 0:
                    text = widgets[0]
                elif isinstance(inputs, dict) and 'text' in inputs:
                    text = inputs['text']
                
                if text:
                    if not settings.get('prompt'):
                        settings['prompt'] = text
                    else:
                        settings['negative_prompt'] = text
            
            elif node_type in ['KSampler', 'KSamplerAdvanced']:
                if isinstance(inputs, dict):
                    settings['seed'] = inputs.get('seed', -1)
                    settings['steps'] = inputs.get('steps', 20)
                    settings['cfg_scale'] = inputs.get('cfg', 7.0)
                    settings['sampler'] = inputs.get('sampler_name', 'euler')
                    settings['scheduler'] = inputs.get('scheduler', 'normal')
            
            elif node_type == 'EmptyLatentImage':
                if isinstance(inputs, dict):
                    settings['width'] = inputs.get('width', 512)
                    settings['height'] = inputs.get('height', 512)
                elif widgets and len(widgets) >= 2:
                    settings['width'] = widgets[0]
                    settings['height'] = widgets[1]
            
            elif node_type == 'CheckpointLoaderSimple':
                if isinstance(inputs, dict):
                    settings['model'] = inputs.get('ckpt_name', '')
                elif widgets and len(widgets) > 0:
                    settings['model'] = widgets[0]
            
            elif node_type == 'CLIPSetLastLayer':
                if isinstance(inputs, dict):
                    settings['clip_skip'] = inputs.get('stop_at_clip_layer', -1)
                elif widgets and len(widgets) > 0:
                    settings['clip_skip'] = widgets[0]
        
        return settings if settings else None
        
    except Exception as e:
        print(f"Error extracting from workflow JSON: {{e}}")
        return None

def parse_a1111_parameters(params_str):
    """Parse Automatic1111 style parameters string"""
    try:
        settings = {{}}
        lines = params_str.split('\\n')
        
        # First line is the positive prompt
        if lines:
            settings['prompt'] = lines[0].strip()
        
        # Look for negative prompt
        for line in lines:
            if line.startswith('Negative prompt:'):
                settings['negative_prompt'] = line.replace('Negative prompt:', '').strip()
        
        # Parse parameter line (usually last line with "Steps: X, Sampler: Y, ...")
        for line in lines:
            if 'Steps:' in line or 'steps:' in line.lower():
                # Split by comma and parse each parameter
                parts = [p.strip() for p in line.split(',')]
                for part in parts:
                    if ':' not in part:
                        continue
                    
                    key, value = part.split(':', 1)
                    key = key.strip().lower()
                    value = value.strip()
                    
                    if key == 'steps':
                        settings['steps'] = int(value)
                    elif 'cfg' in key:
                        settings['cfg_scale'] = float(value)
                    elif key == 'sampler':
                        settings['sampler'] = value
                    elif key == 'scheduler':
                        settings['scheduler'] = value
                    elif key == 'size':
                        if 'x' in value:
                            w, h = value.split('x')
                            settings['width'] = int(w.strip())
                            settings['height'] = int(h.strip())
                    elif key == 'seed':
                        settings['seed'] = int(value)
                    elif key == 'model':
                        settings['model'] = value
                    elif 'clip skip' in key:
                        settings['clip_skip'] = int(value)
        
        return settings if settings else None
        
    except Exception as e:
        print(f"Error parsing A1111 parameters: {{e}}")
        return None

def create_workflow(params: GenerateRequest):
    seed = params.seed if params.seed != -1 else int.from_bytes(os.urandom(4), 'big')
    
    workflow = {{
        "6": {{
            "inputs": {{
                "text": params.prompt,
                "clip": ["11", 1]
            }},
            "class_type": "CLIPTextEncode",
            "_meta": {{"title": "CLIP Text Encode (Prompt)"}}
        }},
        "7": {{
            "inputs": {{
                "text": params.negative_prompt,
                "clip": ["11", 1]
            }},
            "class_type": "CLIPTextEncode",
            "_meta": {{"title": "CLIP Text Encode (Negative)"}}
        }},
        "8": {{
            "inputs": {{
                "samples": ["13", 0],
                "vae": ["11", 2]
            }},
            "class_type": "VAEDecode",
            "_meta": {{"title": "VAE Decode"}}
        }},
        "9": {{
            "inputs": {{
                "filename_prefix": "ComfyUI",
                "images": ["8", 0]
            }},
            "class_type": "SaveImage",
            "_meta": {{"title": "Save Image"}}
        }},
        "11": {{
            "inputs": {{
                "ckpt_name": params.model
            }},
            "class_type": "CheckpointLoaderSimple",
            "_meta": {{"title": "Load Checkpoint"}}
        }},
        "13": {{
            "inputs": {{
                "seed": seed,
                "steps": params.steps,
                "cfg": params.cfg_scale,
                "sampler_name": params.sampler,
                "scheduler": params.scheduler,
                "denoise": 1,
                "model": ["11", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["27", 0]
            }},
            "class_type": "KSampler",
            "_meta": {{"title": "KSampler"}}
        }},
        "27": {{
            "inputs": {{
                "width": params.width,
                "height": params.height,
                "batch_size": 1
            }},
            "class_type": "EmptyLatentImage",
            "_meta": {{"title": "Empty Latent Image"}}
        }}
    }}
    return workflow

@app.get("/", response_class=HTMLResponse)
async def get_mobile_ui():
    html_content = \'\'\'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ComfyUI Mobile</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #1a1a1a; color: #fff; padding: 10px; min-height: 100vh;
        }}
        .container {{ max-width: 500px; margin: 0 auto; }}
        .header {{ text-align: center; margin-bottom: 20px; }}
        .header-buttons {{ display: flex; gap: 10px; margin-top: 10px; justify-content: center; }}
        .header-btn {{ 
            background: #333; border: 1px solid #555; color: #fff;
            padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 14px;
        }}
        .header-btn.active {{ background: #007AFF; border-color: #007AFF; }}
        
        .tab-content {{ display: none; }}
        .tab-content.active {{ display: block; }}
        
        .form-group {{ margin-bottom: 15px; }}
        label {{ display: block; margin-bottom: 5px; color: #ccc; font-size: 14px; }}
        input, textarea, select, button {{ 
            width: 100%; padding: 12px; border: 1px solid #444;
            background: #2a2a2a; color: #fff; border-radius: 8px;
            font-size: 16px; -webkit-appearance: none;
        }}
        textarea {{ resize: vertical; min-height: 80px; font-family: inherit; }}
        .row {{ display: flex; gap: 10px; }}
        .col {{ flex: 1; }}
        .btn {{ 
            background: #007AFF; border: none; color: white;
            padding: 15px; font-weight: bold; cursor: pointer;
            margin-top: 10px; border-radius: 8px;
        }}
        .btn:hover {{ background: #005ecb; }}
        .btn:disabled {{ background: #555; cursor: not-allowed; }}
        .progress {{ 
            width: 100%; height: 6px; background: #333;
            border-radius: 3px; margin: 10px 0; overflow: hidden;
        }}
        .progress-bar {{ 
            height: 100%; background: linear-gradient(90deg, #007AFF, #00D4FF);
            width: 0%; transition: width 0.3s ease;
        }}
        .result {{ 
            margin-top: 20px; text-align: center;
            border: 2px dashed #444; border-radius: 12px;
            padding: 20px; min-height: 150px;
        }}
        .result img {{ 
            max-width: 100%; height: auto; border-radius: 12px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.6);
        }}
        .status {{ 
            padding: 12px; background: #2a2a2a; border-radius: 8px;
            margin: 10px 0; text-align: center; font-size: 14px;
        }}
        .loading {{ opacity: 0.7; pointer-events: none; }}
        .range-container {{ display: flex; align-items: center; gap: 10px; }}
        .range-value {{ 
            background: #333; padding: 8px 12px; border-radius: 6px;
            min-width: 60px; text-align: center; font-size: 14px;
        }}
        input[type="range"] {{
            flex: 1; padding: 0; height: 8px; border-radius: 4px;
            background: #333; outline: none;
        }}
        input[type="range"]::-webkit-slider-thumb {{
            -webkit-appearance: none; width: 20px; height: 20px;
            border-radius: 50%; background: #007AFF; cursor: pointer;
        }}
        .preset-btn {{ 
            background: #333; border: 1px solid #555; color: #fff;
            padding: 8px 12px; margin: 2px; border-radius: 6px;
            font-size: 12px; cursor: pointer;
        }}
        .preset-btn.active {{ background: #007AFF; border-color: #007AFF; }}
        .presets {{ display: flex; flex-wrap: wrap; gap: 5px; margin-top: 8px; }}
        
        .gallery-grid {{ 
            display: grid; grid-template-columns: repeat(2, 1fr);
            gap: 10px; margin: 20px 0;
        }}
        .gallery-item {{ 
            position: relative; border-radius: 8px; overflow: hidden;
            background: #2a2a2a; cursor: pointer; transition: transform 0.2s;
        }}
        .gallery-item:hover {{ transform: scale(1.02); }}
        .gallery-item img {{ 
            width: 100%; height: 150px; object-fit: cover;
            display: block;
        }}
        .gallery-item .info {{ 
            position: absolute; bottom: 0; left: 0; right: 0;
            background: linear-gradient(transparent, rgba(0,0,0,0.8));
            padding: 20px 8px 8px; font-size: 10px; color: #ccc;
        }}
        .gallery-loading {{ 
            text-align: center; padding: 20px; color: #666;
        }}
        .gallery-controls {{ 
            display: flex; justify-content: center; gap: 10px; margin: 10px 0;
        }}
        .load-more-btn {{ 
            background: #333; border: 1px solid #555; color: #fff;
            padding: 10px 20px; border-radius: 6px; cursor: pointer;
        }}
        
        .modal {{ 
            display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.9); z-index: 1000; align-items: center; justify-content: center;
        }}
        .modal.active {{ display: flex; }}
        .modal-content {{ 
            background: #2a2a2a; border-radius: 12px; padding: 20px;
            max-width: 90%; max-height: 90%; overflow-y: auto; position: relative;
        }}
        .modal-close {{ 
            position: absolute; top: 10px; right: 15px; 
            background: none; border: none; color: #fff; font-size: 24px; cursor: pointer;
        }}
        .modal img {{ 
            max-width: 100%; height: auto; border-radius: 8px; margin-bottom: 15px;
        }}
        .modal-actions {{ 
            display: flex; gap: 10px; justify-content: center;
        }}
        .modal-btn {{ 
            background: #007AFF; border: none; color: white;
            padding: 10px 20px; border-radius: 6px; cursor: pointer;
        }}
        .modal-btn.secondary {{ background: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>ComfyUI Mobile</h1>
            <div id="connectionStatus" class="status">Connecting...</div>
            <div class="header-buttons">
                <button class="header-btn active" onclick="showTab('generate')">Generate</button>
                <button class="header-btn" onclick="showTab('gallery')">Gallery</button>
            </div>
        </div>
        
        <div id="generate-tab" class="tab-content active">
            <div class="result" id="result">
                <p>Generated images will appear here</p>
            </div>
            
            <div class="progress" id="progress" style="display: none;">
                <div class="progress-bar" id="progressBar"></div>
            </div>
            
            <div class="status" id="status" style="display: none;"></div>
            
            <button type="submit" class="btn" id="generateBtn" onclick="generateImage()">Generate Image</button>
            
            <form id="generateForm">
                <div class="form-group">
                    <label>Model</label>
                    <select id="model">
                        <option value="">Loading models...</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label>Prompt</label>
                    <textarea id="prompt" placeholder="beautiful landscape, detailed, 4k">beautiful landscape, detailed, 4k</textarea>
                </div>
                
                <div class="form-group">
                    <label>Negative Prompt</label>
                    <textarea id="negativePrompt" placeholder="low quality, blurry...">low quality, grain, boring view, boring pose</textarea>
                </div>
                
                <div class="form-group">
                    <label>Image Size</label>
                    <div class="presets">
                        <button type="button" class="preset-btn" data-size="512,512">512x512</button>
                        <button type="button" class="preset-btn" data-size="768,768">768x768</button>
                        <button type="button" class="preset-btn active" data-size="1024,1024">1024x1024</button>
                        <button type="button" class="preset-btn" data-size="1408,1408">1408x1408</button>
                    </div>
                    <div class="row" style="margin-top: 10px;">
                        <div class="col">
                            <input type="number" id="width" value="1024" min="128" max="2048" step="64">
                        </div>
                        <div class="col">
                            <input type="number" id="height" value="1024" min="128" max="2048" step="64">
                        </div>
                    </div>
                </div>
                
                <div class="form-group">
                    <label>Steps: <span id="stepsValue">10</span></label>
                    <div class="range-container">
                        <input type="range" id="steps" min="1" max="50" value="10">
                        <div class="range-value" id="stepsDisplay">10</div>
                    </div>
                </div>
                
                <div class="form-group">
                    <label>CFG Scale: <span id="cfgValue">1.0</span></label>
                    <div class="range-container">
                        <input type="range" id="cfgScale" min="1" max="20" step="0.1" value="1.0">
                        <div class="range-value" id="cfgDisplay">1.0</div>
                    </div>
                </div>
                
                <div class="row">
                    <div class="col">
                        <label>Sampler</label>
                        <select id="sampler">
                            <option value="lcm" selected>LCM</option>
                            <option value="euler">Euler</option>
                            <option value="euler_ancestral">Euler Ancestral</option>
                            <option value="dpmpp_2m">DPM++ 2M</option>
                            <option value="dpmpp_2m_karras">DPM++ 2M Karras</option>
                        </select>
                    </div>
                    <div class="col">
                        <label>Scheduler</label>
                        <select id="scheduler">
                            <option value="beta" selected>Beta</option>
                            <option value="karras">Karras</option>
                            <option value="exponential">Exponential</option>
                            <option value="normal">Normal</option>
                        </select>
                    </div>
                </div>
                
                <div class="form-group">
                    <label>CLIP Skip: <span id="clipSkipValue">-2</span></label>
                    <div class="range-container">
                        <input type="range" id="clipSkip" min="-5" max="-1" value="-2">
                        <div class="range-value" id="clipSkipDisplay">-2</div>
                    </div>
                </div>
            </form>
        </div>
        
        <div id="gallery-tab" class="tab-content">
            <div class="gallery-controls">
                <button class="load-more-btn" onclick="loadImages()">Refresh Gallery</button>
            </div>
            <div id="galleryGrid" class="gallery-grid">
                <div class="gallery-loading">Loading images...</div>
            </div>
            <div class="gallery-controls">
                <button class="load-more-btn" id="loadMoreBtn" onclick="loadMoreImages()" style="display: none;">Load More</button>
            </div>
        </div>
    </div>

    <div id="imageModal" class="modal">
        <div class="modal-content">
            <button class="modal-close" onclick="closeModal()">&times;</button>
            <img id="modalImage" src="" alt="Selected image">
            <div class="modal-actions">
                <button class="modal-btn" onclick="useImageSettings()">Use Settings</button>
                <button class="modal-btn secondary" onclick="closeModal()">Cancel</button>
            </div>
            <div id="modalInfo" style="margin-top: 15px; font-size: 12px; color: #ccc;"></div>
        </div>
    </div>

    <script>
        let currentTab = 'generate';
        let galleryImages = [];
        let galleryOffset = 0;
        let selectedImageData = null;
        
        function showTab(tab) {{
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.header-btn').forEach(b => b.classList.remove('active'));
            
            document.getElementById(tab + '-tab').classList.add('active');
            event.target.classList.add('active');
            currentTab = tab;
            
            if (tab === 'gallery' && galleryImages.length === 0) {{
                loadImages();
            }}
        }}
        
        const form = document.getElementById('generateForm');
        const btn = document.getElementById('generateBtn');
        const progress = document.getElementById('progress');
        const progressBar = document.getElementById('progressBar');
        const status = document.getElementById('status');
        const result = document.getElementById('result');
        const connectionStatus = document.getElementById('connectionStatus');
        
        const steps = document.getElementById('steps');
        const stepsDisplay = document.getElementById('stepsDisplay');
        const cfgScale = document.getElementById('cfgScale');
        const cfgDisplay = document.getElementById('cfgDisplay');
        const clipSkip = document.getElementById('clipSkip');
        const clipSkipDisplay = document.getElementById('clipSkipDisplay');
        
        steps.oninput = () => stepsDisplay.textContent = steps.value;
        cfgScale.oninput = () => cfgDisplay.textContent = cfgScale.value;
        clipSkip.oninput = () => clipSkipDisplay.textContent = clipSkip.value;
        
        document.querySelectorAll('.preset-btn').forEach(btn => {{
            btn.addEventListener('click', () => {{
                document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const [w, h] = btn.dataset.size.split(',');
                document.getElementById('width').value = w;
                document.getElementById('height').value = h;
            }});
        }});
        
        async function loadModels() {{
            try {{
                const response = await fetch('/api/models');
                const models = await response.json();
                const modelSelect = document.getElementById('model');
                
                const currentSelection = modelSelect.value;
                
                modelSelect.innerHTML = '';
                models.forEach(model => {{
                    const option = document.createElement('option');
                    option.value = model;
                    option.textContent = model;
                    modelSelect.appendChild(option);
                }});
                
                if (currentSelection && models.includes(currentSelection)) {{
                    modelSelect.value = currentSelection;
                }} else {{
                    const defaultModel = models.find(m => m.includes('mopMixtureOfPerverts'));
                    if (defaultModel) modelSelect.value = defaultModel;
                }}
                
                connectionStatus.textContent = 'Connected to ComfyUI';
                connectionStatus.style.background = '#1a4d1a';
            }} catch (error) {{
                connectionStatus.textContent = 'ComfyUI disconnected';
                connectionStatus.style.background = '#4d1a1a';
            }}
        }}
        
        async function generateImage() {{
            const data = {{
                prompt: document.getElementById('prompt').value,
                negative_prompt: document.getElementById('negativePrompt').value,
                width: parseInt(document.getElementById('width').value),
                height: parseInt(document.getElementById('height').value),
                steps: parseInt(document.getElementById('steps').value),
                cfg_scale: parseFloat(document.getElementById('cfgScale').value),
                sampler: document.getElementById('sampler').value,
                scheduler: document.getElementById('scheduler').value,
                model: document.getElementById('model').value,
                clip_skip: parseInt(document.getElementById('clipSkip').value),
                seed: -1
            }};
            
            btn.disabled = true;
            btn.textContent = 'Generating...';
            form.classList.add('loading');
            progress.style.display = 'block';
            status.style.display = 'block';
            status.textContent = 'Starting generation...';
            
            try {{
                const response = await fetch('/api/generate', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify(data)
                }});
                
                const jobData = await response.json();
                
                if (response.ok) {{
                    pollProgress(jobData.job_id);
                }} else {{
                    throw new Error(jobData.detail || 'Generation failed');
                }}
            }} catch (error) {{
                status.textContent = 'Error: ' + error.message;
                resetForm();
            }}
        }}
        
        async function pollProgress(jobId) {{
            const maxAttempts = 300;
            let attempts = 0;
            let smoothProgress = 0;
            
            const poll = async () => {{
                try {{
                    const response = await fetch(`/api/status/${{jobId}}`);
                    const data = await response.json();
                    
                    if (data.status === 'completed') {{
                        progressBar.style.width = '100%';
                        status.textContent = 'Generation complete!';
                        result.innerHTML = `<img src="/api/image/${{jobId}}" alt="Generated image" onclick="window.open(this.src)">`;
                        resetForm();
                        if (currentTab === 'gallery') {{
                            setTimeout(() => loadImages(), 1000);
                        }}
                    }} else if (data.status === 'failed') {{
                        throw new Error(data.error || 'Generation failed');
                    }} else if (data.status === 'processing') {{
                        let targetProgress = data.progress || 50;
                        
                        if (smoothProgress < targetProgress) {{
                            smoothProgress = Math.min(targetProgress, smoothProgress + 2);
                        }}
                        
                        progressBar.style.width = smoothProgress + '%';
                        
                        let statusText = 'Processing';
                        if (data.elapsed_time) {{
                            statusText += ` (${{data.elapsed_time}}s)`;
                        }}
                        statusText += ` ${{smoothProgress}}%`;
                        status.textContent = statusText;
                        
                        if (attempts < maxAttempts) {{
                            setTimeout(poll, 500);
                            attempts++;
                        }} else {{
                            throw new Error('Generation timeout');
                        }}
                    }} else if (data.status === 'queued') {{
                        smoothProgress = 5;
                        progressBar.style.width = '5%';
                        let statusText = 'Waiting in queue';
                        if (data.queue_position) {{
                            statusText += ` (Position: ${{data.queue_position}})`;
                        }}
                        status.textContent = statusText;
                        
                        if (attempts < maxAttempts) {{
                            setTimeout(poll, 1000);
                            attempts++;
                        }} else {{
                            throw new Error('Generation timeout');
                        }}
                    }} else {{
                        smoothProgress = Math.min(95, smoothProgress + 1);
                        progressBar.style.width = smoothProgress + '%';
                        status.textContent = `Processing... ${{smoothProgress}}%`;
                        
                        if (attempts < maxAttempts) {{
                            setTimeout(poll, 1000);
                            attempts++;
                        }} else {{
                            throw new Error('Generation timeout');
                        }}
                    }}
                }} catch (error) {{
                    status.textContent = 'Error: ' + error.message;
                    resetForm();
                }}
            }};
            
            poll();
        }}
        
        function resetForm() {{
            btn.disabled = false;
            btn.textContent = 'Generate Image';
            form.classList.remove('loading');
            setTimeout(() => {{
                progress.style.display = 'none';
                status.style.display = 'none';
            }}, 3000);
        }}
        
        async function loadImages(reset = true) {{
            if (reset) {{
                galleryOffset = 0;
                galleryImages = [];
            }}
            
            try {{
                const response = await fetch(`/api/gallery?offset=${{galleryOffset}}&limit=20`);
                const data = await response.json();
                
                if (reset) {{
                    galleryImages = data.images;
                }} else {{
                    galleryImages = [...galleryImages, ...data.images];
                }}
                
                renderGallery();
                
                document.getElementById('loadMoreBtn').style.display = 
                    data.has_more ? 'block' : 'none';
                galleryOffset += data.images.length;
                
            }} catch (error) {{
                document.getElementById('galleryGrid').innerHTML = 
                    '<div class="gallery-loading">Error loading gallery</div>';
            }}
        }}
        
        function loadMoreImages() {{
            loadImages(false);
        }}
        
        function renderGallery() {{
            const grid = document.getElementById('galleryGrid');
            
            if (galleryImages.length === 0) {{
                grid.innerHTML = '<div class="gallery-loading">No images found</div>';
                return;
            }}
            
            grid.innerHTML = galleryImages.map((img, index) => `
                <div class="gallery-item" onclick="selectImage(${{index}})">
                    <img src="/api/gallery/thumb/${{img.filename}}" alt="Generated image" loading="lazy">
                    <div class="info">
                        ${{img.date}} ${{img.size}}
                    </div>
                </div>
            `).join('');
        }}
        
        function selectImage(index) {{
            selectedImageData = galleryImages[index];
            const modal = document.getElementById('imageModal');
            const modalImage = document.getElementById('modalImage');
            const modalInfo = document.getElementById('modalInfo');
            
            modalImage.src = `/api/gallery/full/${{selectedImageData.filename}}`;
            
            let infoHtml = `<strong>File:</strong> ${{selectedImageData.filename}}<br>`;
            infoHtml += `<strong>Size:</strong> ${{selectedImageData.size}}<br>`;
            infoHtml += `<strong>Date:</strong> ${{selectedImageData.date}}<br>`;
            
            if (selectedImageData.settings) {{
                infoHtml += '<br><strong>Settings:</strong><br>';
                const settings = selectedImageData.settings;
                if (settings.prompt) infoHtml += `<strong>Prompt:</strong> ${{settings.prompt}}<br>`;
                if (settings.negative_prompt) infoHtml += `<strong>Negative:</strong> ${{settings.negative_prompt}}<br>`;
                if (settings.steps) infoHtml += `<strong>Steps:</strong> ${{settings.steps}}<br>`;
                if (settings.cfg_scale) infoHtml += `<strong>CFG:</strong> ${{settings.cfg_scale}}<br>`;
                if (settings.sampler) infoHtml += `<strong>Sampler:</strong> ${{settings.sampler}}<br>`;
                if (settings.model) infoHtml += `<strong>Model:</strong> ${{settings.model}}<br>`;
                if (settings.seed && settings.seed !== -1) infoHtml += `<strong>Seed:</strong> ${{settings.seed}}<br>`;
            }}
            
            modalInfo.innerHTML = infoHtml;
            modal.classList.add('active');
        }}
        
        function closeModal() {{
            document.getElementById('imageModal').classList.remove('active');
        }}
        
        function useImageSettings() {{
            if (!selectedImageData || !selectedImageData.settings) {{
                alert('No settings available for this image');
                return;
            }}
            
            const settings = selectedImageData.settings;
            
            if (settings.prompt) document.getElementById('prompt').value = settings.prompt;
            if (settings.negative_prompt) document.getElementById('negativePrompt').value = settings.negative_prompt;
            if (settings.width) document.getElementById('width').value = settings.width;
            if (settings.height) document.getElementById('height').value = settings.height;
            if (settings.steps) {{
                document.getElementById('steps').value = settings.steps;
                document.getElementById('stepsDisplay').textContent = settings.steps;
            }}
            if (settings.cfg_scale) {{
                document.getElementById('cfgScale').value = settings.cfg_scale;
                document.getElementById('cfgDisplay').textContent = settings.cfg_scale;
            }}
            if (settings.sampler) document.getElementById('sampler').value = settings.sampler;
            if (settings.scheduler) document.getElementById('scheduler').value = settings.scheduler;
            if (settings.model) document.getElementById('model').value = settings.model;
            if (settings.clip_skip) {{
                document.getElementById('clipSkip').value = settings.clip_skip;
                document.getElementById('clipSkipDisplay').textContent = settings.clip_skip;
            }}
            
            if (settings.width && settings.height) {{
                document.querySelectorAll('.preset-btn').forEach(btn => {{
                    btn.classList.remove('active');
                    const [w, h] = btn.dataset.size.split(',');
                    if (w == settings.width && h == settings.height) {{
                        btn.classList.add('active');
                    }}
                }});
            }}
            
            closeModal();
            showTab('generate');
            window.scrollTo(0, 0);
        }}
        
        loadModels();
        setInterval(loadModels, 30000);
        
        document.addEventListener('keydown', (e) => {{
            if (e.key === 'Escape') closeModal();
        }});
    </script>
</body>
</html>
    \'\'\'
    return HTMLResponse(content=html_content)

jobs = {{}}

@app.get("/api/models")
async def get_models():
    try:
        response = requests.get(f"http://{{COMFYUI_HOST}}:{{COMFYUI_PORT}}/object_info", timeout=10)
        if response.status_code == 200:
            object_info = response.json()
            checkpoints = []
            if "CheckpointLoaderSimple" in object_info:
                checkpoint_info = object_info["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"]
                if isinstance(checkpoint_info, list) and len(checkpoint_info) > 0:
                    checkpoints = checkpoint_info[0]
            return checkpoints
        else:
            return ["mopMixtureOfPerverts_v31.safetensors"]
    except Exception as e:
        return ["mopMixtureOfPerverts_v31.safetensors"]

@app.get("/api/gallery")
async def get_gallery(offset: int = 0, limit: int = 20):
    try:
        image_paths = []
        
        if COMFYUI_OUTPUT_DIR.exists():
            for ext in ['*.png', '*.jpg', '*.jpeg', '*.webp']:
                found_images = list(COMFYUI_OUTPUT_DIR.glob(ext))
                image_paths.extend(found_images)
        
        if OUTPUT_DIR.exists():
            for ext in ['*.png', '*.jpg', '*.jpeg', '*.webp']:
                local_images = list(OUTPUT_DIR.glob(ext))
                image_paths.extend(local_images)
        
        image_paths.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        total = len(image_paths)
        paginated_paths = image_paths[offset:offset + limit]
        
        images = []
        for path in paginated_paths:
            try:
                stat = path.stat()
                settings = extract_metadata_from_image(path)
                
                images.append({{
                    "filename": path.name,
                    "path": str(path),
                    "size": f"{{stat.st_size // 1024}}KB",
                    "date": stat.st_mtime,
                    "settings": settings
                }})
            except Exception as e:
                continue
        
        for img in images:
            try:
                from datetime import datetime
                img["date"] = datetime.fromtimestamp(img["date"]).strftime("%m/%d %H:%M")
            except:
                img["date"] = "Unknown"
        
        return {{
            "images": images,
            "total": total,
            "has_more": offset + limit < total
        }}
        
    except Exception as e:
        return {{"images": [], "total": 0, "has_more": False}}

@app.get("/api/gallery/thumb/{{filename}}")
async def get_thumbnail(filename: str):
    return await get_gallery_image(filename, thumbnail=True)

@app.get("/api/gallery/full/{{filename}}")
async def get_full_image(filename: str):
    return await get_gallery_image(filename, thumbnail=False)

async def get_gallery_image(filename: str, thumbnail: bool = False):
    try:
        possible_paths = [
            COMFYUI_OUTPUT_DIR / filename,
            OUTPUT_DIR / filename,
        ]
        
        image_path = None
        for path in possible_paths:
            if path.exists():
                image_path = path
                break
        
        if not image_path:
            raise HTTPException(status_code=404, detail="Image not found")
        
        if thumbnail:
            try:
                with Image.open(image_path) as img:
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    
                    img.thumbnail((300, 300), Image.Resampling.LANCZOS)
                    
                    img_buffer = BytesIO()
                    img.save(img_buffer, format='JPEG', quality=85)
                    img_buffer.seek(0)
                    
                    return Response(
                        content=img_buffer.getvalue(),
                        media_type="image/jpeg"
                    )
            except Exception as e:
                pass
        
        return FileResponse(
            image_path,
            media_type="image/png" if image_path.suffix.lower() == '.png' else "image/jpeg"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error serving image: {{str(e)}}")

@app.post("/api/generate")
async def generate_image(request: GenerateRequest):
    job_id = str(uuid.uuid4())
    
    try:
        workflow = create_workflow(request)
        
        response = requests.post(
            f"http://{{COMFYUI_HOST}}:{{COMFYUI_PORT}}/prompt",
            json={{"prompt": workflow}},
            timeout=30
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"ComfyUI error: {{response.text}}")
        
        comfy_response = response.json()
        
        jobs[job_id] = {{
            "status": "processing",
            "comfy_prompt_id": comfy_response["prompt_id"],
            "params": request.dict()
        }}
        
        return {{"job_id": job_id, "message": "Generation started"}}
        
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=500, detail="ComfyUI connection timeout")
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=500, detail="Cannot connect to ComfyUI - is it running?")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/status/{{job_id}}")
async def get_job_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    
    try:
        prompt_id = job["comfy_prompt_id"]
        
        history_response = requests.get(f"http://{{COMFYUI_HOST}}:{{COMFYUI_PORT}}/history/{{prompt_id}}", timeout=10)
        
        if history_response.status_code == 200:
            history = history_response.json()
            
            if prompt_id in history:
                history_entry = history[prompt_id]
                outputs = history_entry.get("outputs", {{}})
                
                if history_entry.get("status", {{}}).get("status_str") == "error":
                    job["status"] = "failed"
                    return {{"status": "failed", "error": "Generation failed in ComfyUI"}}
                
                for node_id, output in outputs.items():
                    if "images" in output:
                        image_info = output["images"][0]
                        job["status"] = "completed"
                        job["output_image"] = image_info
                        return {{"status": "completed", "progress": 100}}
        
        queue_response = requests.get(f"http://{{COMFYUI_HOST}}:{{COMFYUI_PORT}}/queue", timeout=10)
        if queue_response.status_code == 200:
            queue_data = queue_response.json()
            
            for item in queue_data.get("queue_running", []):
                if len(item) > 1 and item[1] == prompt_id:
                    if "start_time" not in job:
                        job["start_time"] = __import__('time').time()
                    
                    elapsed = __import__('time').time() - job["start_time"]
                    expected_steps = job.get("params", {{}}).get("steps", 10)
                    estimated_total_time = expected_steps * 1.0
                    
                    if elapsed < estimated_total_time:
                        progress = int((elapsed / estimated_total_time) * 95)
                    else:
                        progress = 95
                    
                    return {{
                        "status": "processing",
                        "progress": max(15, progress),
                        "elapsed_time": int(elapsed)
                    }}
            
            for idx, item in enumerate(queue_data.get("queue_pending", [])):
                if len(item) > 1 and item[1] == prompt_id:
                    return {{
                        "status": "queued",
                        "progress": 5,
                        "queue_position": idx + 1
                    }}
        
        job["status"] = "failed"
        return {{"status": "failed", "error": "Job not found in ComfyUI queue"}}
        
    except Exception as e:
        job["status"] = "failed"
        return {{"status": "failed", "error": str(e)}}

@app.get("/api/image/{{job_id}}")
async def get_image(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    
    if job["status"] != "completed" or "output_image" not in job:
        raise HTTPException(status_code=404, detail="Image not ready")
    
    image_info = job["output_image"]
    
    try:
        image_path = f"http://{{COMFYUI_HOST}}:{{COMFYUI_PORT}}/view"
        params = {{
            "filename": image_info["filename"],
            "subfolder": image_info.get("subfolder", ""),
            "type": image_info.get("type", "output")
        }}
        
        image_response = requests.get(image_path, params=params, timeout=30)
        
        if image_response.status_code == 200:
            return Response(
                content=image_response.content,
                media_type="image/png",
                headers={{"Content-Disposition": f"inline; filename={{image_info['filename']}}"}}
            )
        else:
            raise HTTPException(status_code=404, detail="Image not found in ComfyUI")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get image: {{str(e)}}")

@app.get("/api/health")
async def health_check():
    try:
        response = requests.get(f"http://{{COMFYUI_HOST}}:{{COMFYUI_PORT}}/system_stats", timeout=5)
        if response.status_code == 200:
            return {{"status": "healthy", "comfyui": "connected"}}
        else:
            return {{"status": "degraded", "comfyui": "disconnected"}}
    except:
        return {{"status": "unhealthy", "comfyui": "unreachable"}}

if __name__ == "__main__":
    print(f"Starting ComfyUI Mobile API...")
    print(f"ComfyUI connection: {{COMFYUI_HOST}}:{{COMFYUI_PORT}}")
    print(f"Web UI: http://0.0.0.0:8080")
    print(f"Mobile access: http://[your-pc-ip]:8080")
    print(f"Gallery path: {{COMFYUI_OUTPUT_DIR}}")
    print(f"Make sure ComfyUI is running!")
    
    uvicorn.run(app, host="0.0.0.0", port=8080)
'''
    
    return script_content

def main():
    # Step 1: Select batch file
    batch_file_path = select_batch_file()
    
    if not batch_file_path:
        return
    
    # Step 2: Get ComfyUI root directory
    comfyui_root = batch_file_path.parent
    print(f"\nComfyUI root directory: {comfyui_root}")
    
    # Step 3: Find output folder
    output_dir = find_output_folder(comfyui_root)
    
    if not output_dir.exists():
        print(f"\nCreating output directory: {output_dir}")
        output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Output directory: {output_dir}")
    
    # Step 4: Generate configured script
    print("\nGenerating configured API script...")
    script_content = generate_configured_script(comfyui_root, output_dir)
    
    # Step 5: Save script to ComfyUI folder
    output_script_path = comfyui_root / "comfyui_mobile_api.py"
    
    try:
        with open(output_script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        print(f"\n{'='*60}")
        print("SUCCESS!")
        print(f"{'='*60}")
        print(f"\nConfigured script saved to:")
        print(f"  {output_script_path}")
        print(f"\nDetected paths:")
        print(f"  ComfyUI Root: {comfyui_root}")
        print(f"  Output Folder: {output_dir}")
        print(f"\nTo run the API:")
        print(f"  1. Make sure ComfyUI is running (run_nvidia_gpu.bat)")
        print(f"  2. Open a new command prompt")
        print(f"  3. Navigate to: {comfyui_root}")
        print(f"  4. Run: python comfyui_mobile_api.py")
        print(f"  5. Access from browser: http://localhost:8080")
        print(f"  6. Access from phone: http://[your-pc-ip]:8080")
        print(f"\n{'='*60}")
        
    except Exception as e:
        print(f"\nError saving script: {e}")
        return
    
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        input("\nPress Enter to exit...")