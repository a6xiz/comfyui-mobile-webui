import subprocess
import sys

def install_package(package):
    """Install a package using pip"""
    try:
        print(f"Installing {package}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"✓ {package} installed successfully\n")
        return True
    except subprocess.CalledProcessError:
        print(f"✗ Failed to install {package}\n")
        return False

def main():
    print("=" * 50)
    print("ComfyUI Mobile API - Dependency Installer")
    print("=" * 50)
    print()
    
    # List of required packages
    packages = [
        "fastapi",
        "uvicorn",
        "requests",
        "pydantic",
        "pillow"
    ]
    
    # Track installation results
    successful = []
    failed = []
    
    # Install each package
    for package in packages:
        if install_package(package):
            successful.append(package)
        else:
            failed.append(package)
    
    # Summary
    print("=" * 50)
    print("Installation Summary")
    print("=" * 50)
    print(f"Successfully installed: {len(successful)}/{len(packages)}")
    if successful:
        print("  ✓ " + "\n  ✓ ".join(successful))
    
    if failed:
        print(f"\nFailed to install: {len(failed)}")
        print("  ✗ " + "\n  ✗ ".join(failed))
        print("\nTry running this script as administrator or with sudo")
    else:
        print("\n✓ All dependencies installed successfully!")
        print("\nYou can now run the ComfyUI Mobile API script.")
    
    print("\nPress Enter to exit...")
    input()

if __name__ == "__main__":
    main()
