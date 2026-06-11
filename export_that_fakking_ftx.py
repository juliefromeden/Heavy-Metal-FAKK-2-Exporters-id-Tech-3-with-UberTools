import struct
import os
import sys
from PIL import Image

def convert_ftx_to_png(filepath):
    try:
        with open(filepath, 'rb') as f:
            # Read header (12 bytes)
            header = f.read(12)
            if len(header) < 12:
                return
            
            width, height, alpha_flag = struct.unpack('<3I', header)
            
            if width == 0 or height == 0 or width > 4096 or height > 4096:
                print(f" [!] Skipping {os.path.basename(filepath)}: incorrect size {width}x{height}")
                return

            # Read pixel data
            pixel_data = f.read()
            
            # In FAKK2, the channel order is RGBA (Red, Green, Blue, Alpha)
            # If there is enough data for 32 bits (standard for characters)
            if len(pixel_data) >= width * height * 4:
                # Read as pure RGBA
                img = Image.frombytes("RGBA", (width, height), pixel_data, "raw", "RGBA")
            # If the file is 24 bits
            elif len(pixel_data) >= width * height * 3:
                img = Image.frombytes("RGB", (width, height), pixel_data, "raw", "RGB")
            else:
                print(f" [!] Skipping {os.path.basename(filepath)}: insufficient data")
                return

            out_name = os.path.splitext(filepath)[0] + ".png"
            img.save(out_name, "PNG")
            print(f" [SUCCESS] -> {os.path.basename(out_name)}")
            
    except Exception as e:
        print(f" [ERROR] Failed to convert {filepath}: {e}")

def process_paths(paths):
    files_to_process = []
    for path in paths:
        if os.path.isfile(path) and path.lower().endswith('.ftx'):
            files_to_process.append(path)
        elif os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                for file in files:
                    if file.lower().endswith('.ftx'):
                        files_to_process.append(os.path.join(root, file))
    
    if not files_to_process:
        print("No .ftx files found!")
        return

    print(f"--- CONVERTING {len(files_to_process)} TEXTURES ---")
    for file in files_to_process:
        convert_ftx_to_png(file)
    print("\n--- DONE! ---")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        process_paths(sys.argv[1:])
    else:
        print("Drag & Drop .ftx files or folders directly onto this script!")
    
    input("\nPress Enter to exit...")