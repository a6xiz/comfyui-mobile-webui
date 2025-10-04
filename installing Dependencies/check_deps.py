import sys
import importlib.util

def check_package(package_name, import_name=None):
    """Check if a package is installed"""
    if import_name is None:
        import_name = package_name
    
    spec = importlib.util.find_spec(import_name)
    if spec is not None:
        try:
            module = importlib.import_module(import_name)
            version = "unknown"
            if hasattr(module, "__version__"):
                version = module.__version__
            elif hasattr(module, "VERSION"):
                version = module.VERSION
            return True, version
        except ImportError:
            return False, None
    return False, None

def main():
    print("=" * 60)
    print("ComfyUI Mobile API - Dependency Checker")
    print("=" * 60)
    print(f"Python version: {sys.version.split()[0]}")
    print(f"Python executable: {sys.executable}")
    print("=" * 60)
    print()
    
    # List of required packages (package_name, import_name)
    packages = [
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("requests", "requests"),
        ("pydantic", "pydantic"),
        ("pillow", "PIL"),  # Pillow imports as PIL
    ]
    
    installed = []
    missing = []
    
    print("Checking dependencies...\n")
    
    for package_name, import_name in packages:
        is_installed, version = check_package(package_name, import_name)
        
        if is_installed:
            status = "✓ INSTALLED"
            color = ""
            version_str = f" (v{version})" if version != "unknown" else ""
            print(f"{status:15} {package_name}{version_str}")
            installed.append(package_name)
        else:
            status = "✗ MISSING"
            print(f"{status:15} {package_name}")
            missing.append(package_name)
    
    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Installed: {len(installed)}/{len(packages)}")
    print(f"Missing:   {len(missing)}/{len(packages)}")
    print()
    
    if missing:
        print("Missing packages:")
        for pkg in missing:
            print(f"  - {pkg}")
        print()
        print("To install missing packages, run:")
        print(f"  pip install {' '.join(missing)}")
        print()
        print("Or run the install_dependencies.py script")
    else:
        print("✓ All required dependencies are installed!")
        print()
        print("You're ready to run the ComfyUI Mobile API.")
        print()
        print("Remember to:")
        print("  1. Start ComfyUI first (usually on port 8188)")
        print("  2. Update COMFYUI_OUTPUT_DIR path in the script")
        print("  3. Run: python comfyui-api-fixed.py")
    
    print()
    print("Press Enter to exit...")
    input()

if __name__ == "__main__":
    main()
