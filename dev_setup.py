#!/usr/bin/env python3
"""Setup script for How CLI Tool development installation"""

import os
import sys
import subprocess
import shutil
from pathlib import Path


def run_command(cmd, description):
    """Run a shell command and handle errors"""
    print(f"📦 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e.stderr}")
        return False


def setup_development_environment():
    """Set up development environment"""
    print("🚀 Setting up How CLI development environment...")
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        sys.exit(1)
    
    print(f"✅ Python {sys.version.split()[0]} detected")
    
    # Create virtual environment if it doesn't exist
    venv_path = Path(".venv")
    if not venv_path.exists():
        if not run_command("python -m venv .venv", "Creating virtual environment"):
            sys.exit(1)
    else:
        print("✅ Virtual environment already exists")
    
    # Activate virtual environment and install dependencies
    if os.name == 'nt':  # Windows
        activate_cmd = ".venv\\Scripts\\activate"
        pip_cmd = ".venv\\Scripts\\pip"
    else:  # Unix/macOS
        activate_cmd = "source .venv/bin/activate"
        pip_cmd = ".venv/bin/pip"
    
    # Install requirements
    if not run_command(f"{pip_cmd} install --upgrade pip", "Upgrading pip"):
        sys.exit(1)
    
    if not run_command(f"{pip_cmd} install -r requirements.txt", "Installing dependencies"):
        sys.exit(1)
    
    # Install development dependencies
    dev_deps = [
        "black>=23.0.0",
        "isort>=5.12.0", 
        "flake8>=6.0.0",
        "mypy>=1.5.0"
    ]
    
    for dep in dev_deps:
        run_command(f"{pip_cmd} install {dep}", f"Installing {dep}")
    
    # Create shell completion directory
    completion_dir = Path("completions")
    if completion_dir.exists():
        print("✅ Shell completions available")
        print("   To enable shell completion, run:")
        print("   Bash: source completions/how_completion.bash")
        print("   Zsh:  source completions/how_completion.zsh") 
        print("   Fish: source completions/how_completion.fish")
    
    # Create symlink for global access (optional)
    home_bin = Path.home() / "bin"
    if home_bin.exists():
        how_link = home_bin / "how"
        how_script = Path.cwd() / "how.py"
        
        if not how_link.exists():
            try:
                how_link.symlink_to(how_script)
                print(f"✅ Created symlink: {how_link} -> {how_script}")
                print("   You can now run 'how' from anywhere!")
            except Exception as e:
                print(f"⚠️  Could not create symlink: {e}")
    
    print("\n🎉 Setup complete!")
    print("\n📖 Quick start:")
    print(f"   {activate_cmd}")
    print("   python how.py version")
    print("   python how.py config-init")
    print("   python how.py to 'list files'")
    
    print("\n🔐 Security setup:")
    print("   Set HOW_API_KEY environment variable, or")
    print("   Run 'python how.py to' and enter API key when prompted")


def run_tests():
    """Run the test suite"""
    print("🧪 Running tests...")
    
    if os.name == 'nt':
        python_cmd = ".venv\\Scripts\\python"
    else:
        python_cmd = ".venv/bin/python"
    
    if not run_command(f"{python_cmd} -m pytest tests/ -v", "Running test suite"):
        print("❌ Some tests failed")
        return False
    
    print("✅ All tests passed!")
    return True


def build_package():
    """Build the package for distribution"""
    print("📦 Building package...")
    
    if os.name == 'nt':
        python_cmd = ".venv\\Scripts\\python"
    else:
        python_cmd = ".venv/bin/python"
    
    # Install build tools
    run_command(f"{python_cmd} -m pip install build twine", "Installing build tools")
    
    # Clean previous builds
    for path in ["build", "dist", "*.egg-info"]:
        if Path(path).exists():
            shutil.rmtree(path, ignore_errors=True)
    
    # Build package
    if not run_command(f"{python_cmd} -m build", "Building package"):
        return False
    
    print("✅ Package built successfully!")
    print("   Check the 'dist/' directory for built packages")
    return True


def main():
    """Main setup function"""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "test":
            run_tests()
        elif command == "build":
            build_package()
        elif command == "dev":
            setup_development_environment()
        elif command == "clean":
            print("🧹 Cleaning up...")
            for path in [".venv", "build", "dist", "*.egg-info", "__pycache__", ".pytest_cache"]:
                if Path(path).exists():
                    shutil.rmtree(path, ignore_errors=True)
                    print(f"   Removed {path}")
            print("✅ Cleanup complete!")
        else:
            print(f"Unknown command: {command}")
            print("Available commands: dev, test, build, clean")
    else:
        setup_development_environment()


if __name__ == "__main__":
    main()
