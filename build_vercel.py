import os
import subprocess

def run():
    print("--- Vercel Build Script ---")

    # 1. Attempt to compile C++ engine
    cpp_source = "game/engine/main.cpp"
    cpp_output = "game/engine/main"

    print(f"Attempting to compile {cpp_source}...")
    try:
        # Check if g++ exists first
        subprocess.run(["g++", "--version"], capture_output=True, check=True)

        # Attempt compilation
        subprocess.run(
            ["g++", "-O2", "-std=c++17", "-o", cpp_output, cpp_source],
            check=True
        )
        # Ensure it's executable
        os.chmod(cpp_output, 0o755)
        print("C++ compilation successful.")
    except FileNotFoundError:
        print("NOTICE: g++ compiler not found. The application will use the built-in Python fallback engine.")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: C++ compilation failed (exit code {e.returncode}). Check game/engine/main.cpp for errors. Using Python fallback.")

    # 2. Setup public directory for Vercel
    os.makedirs("public", exist_ok=True)
    with open("public/placeholder.html", "w") as f:
        f.write("<!-- Managed by Vercel -->")

    print("Build script finished.")

if __name__ == "__main__":
    run()
