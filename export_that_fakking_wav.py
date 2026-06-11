import os
import subprocess
import sys

def prepare_for_audacity(input_dir):
    ffmpeg_path = "ffmpeg.exe"
    
    wav_files =[]
    for root, _, files in os.walk(input_dir):
        for f in files:
            if f.lower().endswith('.wav') and "audacity_ready" not in root:
                wav_files.append(os.path.join(root, f))
                
    if not wav_files:
        print("No .wav files found!")
        return

    base_out_dir = os.path.join(input_dir, "audacity_ready")
    os.makedirs(base_out_dir, exist_ok=True)

    print(f"--- PREPARING {len(wav_files)} SOUNDS FOR AUDACITY ---")

    for in_path in wav_files:
        rel_path = os.path.relpath(in_path, input_dir)
        out_path = os.path.join(base_out_dir, rel_path)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        # No filters! Just repackaging to 16-bit so Audacity doesn't lag.
        cmd = [
            ffmpeg_path, "-y", "-i", in_path,
            "-c:a", "pcm_s16le", # Standard format for any editors
            out_path
        ]
        
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f" > Done: {rel_path}")

    print(f"\n[SUCCESS] Files are located in the {base_out_dir} folder. Now you can drag them into Audacity!")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        target = input("Drag the sounds folder here and press Enter: ").strip()
        
    if os.path.isdir(target):
        prepare_for_audacity(target)
    else:
        print("[ERROR] Folder not found!")
        
    input("\nPress Enter to exit...")