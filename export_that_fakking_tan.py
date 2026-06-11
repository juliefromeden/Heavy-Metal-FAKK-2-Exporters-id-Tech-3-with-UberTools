import struct
import os
import sys
import re
from PIL import Image

def convert_ftx(in_filepath, out_filepath):
    """Converts FTX to PNG with strict alpha channel removal (to avoid invisible walls/swords)"""
    try:
        with open(in_filepath, 'rb') as f:
            header = f.read(12)
            if len(header) < 12: return False
            width, height, _ = struct.unpack('<3I', header)
            if width == 0 or height == 0 or width > 4096 or height > 4096: return False
            pixel_data = f.read()
            
            if len(pixel_data) >= width * height * 4:
                img = Image.frombytes("RGBA", (width, height), pixel_data, "raw", "RGBA")
                img = img.convert("RGB") # STRICTLY remove alpha (transparency)
            elif len(pixel_data) >= width * height * 3:
                img = Image.frombytes("RGB", (width, height), pixel_data, "raw", "RGB")
            else: return False
            
            img.save(out_filepath, "PNG")
            return True
    except Exception as e:
        print(f"   [!] Conversion error {in_filepath}: {e}")
        return False

def build_texture_index(base_dir):
    print(" > Indexing game base textures...")
    index = {}
    for root, _, files in os.walk(base_dir):
        for file in files:
            if file.lower().endswith('.ftx'):
                name = os.path.splitext(file)[0].lower()
                index[name] = os.path.join(root, file)
    return index

def parse_shaders(base_dir):
    """Smart analysis of .shader and .tik files to find hidden textures"""
    print(" > Smart shader analysis (Deep Parse)...")
    shader_map = {}
    for root, _, files in os.walk(base_dir):
        for file in files:
            ext = file.lower()
            filepath = os.path.join(root, file)
            
            if ext == '.tik':
                with open(filepath, 'r', errors='ignore') as f:
                    for line in f:
                        line = line.split('//')[0].strip().lower()
                        if line.startswith('surface '):
                            parts = line.split()
                            if len(parts) >= 4 and parts[2] == 'shader':
                                mat_name = parts[1]
                                tex_name = os.path.splitext(parts[3].split('/')[-1].split('\\')[-1])[0]
                                shader_map[mat_name] = tex_name
                                shader_map[os.path.basename(mat_name)] = tex_name
                                
            elif ext in ['.shader', '.txt']:
                with open(filepath, 'r', errors='ignore') as f:
                    text = f.read()
                    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
                    current_shader = None
                    bracket_level = 0
                    
                    for line in text.splitlines():
                        line = line.split('//')[0].strip().lower()
                        if not line: continue
                        
                        open_b = line.count('{')
                        close_b = line.count('}')
                        
                        if bracket_level == 0 and open_b > 0:
                            name_part = line.split('{')[0].strip()
                            if name_part: current_shader = name_part.split()[0]
                        elif bracket_level == 0 and not open_b and not close_b:
                            current_shader = line.split()[0]
                            
                        bracket_level += open_b
                        
                        if current_shader and bracket_level > 0:
                            if line.startswith('map ') or line.startswith('clampmap ') or line.startswith('qer_editorimage ') or line.startswith('animmap '):
                                parts = line.replace('"', '').split()
                                tex_path = ""
                                if line.startswith('animmap ') and len(parts) >= 3:
                                    tex_path = parts[2] 
                                elif len(parts) >= 2:
                                    tex_path = parts[1]
                                    
                                if tex_path and tex_path not in ['$lightmap', '$whiteimage']:
                                    tex_name = os.path.splitext(os.path.basename(tex_path))[0]
                                    shader_map[current_shader] = tex_name
                                    shader_map[os.path.basename(current_shader)] = tex_name
                                    
                        bracket_level -= close_b
                        if bracket_level <= 0:
                            current_shader = None
                            bracket_level = 0
    return shader_map

def resolve_texture(mat_name, tex_index, shader_map):
    mat_lower = mat_name.lower()
    if mat_lower in shader_map and shader_map[mat_lower] in tex_index: return shader_map[mat_lower], tex_index[shader_map[mat_lower]]
    base_name = mat_lower.split('/')[-1].split('\\')[-1]
    if base_name in shader_map and shader_map[base_name] in tex_index: return shader_map[base_name], tex_index[shader_map[base_name]]
    if base_name in tex_index: return base_name, tex_index[base_name]
    parts = base_name.split('_')
    while len(parts) > 1:
        parts.pop()
        fuzzy = "_".join(parts)
        if fuzzy in tex_index: return fuzzy, tex_index[fuzzy]
    for tex in tex_index:
        if len(tex) >= 4 and (tex in base_name or base_name in tex): return tex, tex_index[tex]
    return None, None


def export_tan_to_obj(filepath, tex_index, shader_map):
    model_name = os.path.splitext(os.path.basename(filepath))[0]
    print(f"\n--- EXPORTING: {model_name}.tan ---")
    
    # Create folder hierarchy
    export_dir = os.path.join(os.path.dirname(filepath), f"{model_name}_export")
    tex_dir = os.path.join(export_dir, "textures")
    os.makedirs(export_dir, exist_ok=True)
    os.makedirs(tex_dir, exist_ok=True)
    
    with open(filepath, 'rb') as f:
        f.seek(80)
        num_surfaces = struct.unpack('<I', f.read(4))[0]
        
        f.seek(100)
        ofs_frames = struct.unpack('<I', f.read(4))[0] 
        f.seek(104)
        ofs_surfaces = struct.unpack('<I', f.read(4))[0] 
        
        f.seek(ofs_frames)
        frame_data = struct.unpack('<17f', f.read(68))
        
        scale_x, scale_y, scale_z = frame_data[6], frame_data[7], frame_data[8]
        offset_x, offset_y, offset_z = frame_data[9], frame_data[10], frame_data[11]

        global_verts = []
        global_uvs =[]
        global_tris = {} # {mat_name: [tris]}
        used_materials = set()
        
        vert_offset = 1 
        current_surf_ofs = ofs_surfaces
        
        for i in range(num_surfaces):
            f.seek(current_surf_ofs)
            header_data = f.read(104)
            
            orig_mat_name = header_data[4:68].decode('ascii', errors='ignore').strip('\x00')
            if not orig_mat_name:
                orig_mat_name = f"Mesh_{i}"
                
            clean_mat_name = orig_mat_name.replace('/', '_').replace('\\', '_')
            used_materials.add((orig_mat_name, clean_mat_name))
            if clean_mat_name not in global_tris:
                global_tris[clean_mat_name] =[]
            
            num_verts = struct.unpack('<I', header_data[72:76])[0]
            num_tris = struct.unpack('<I', header_data[80:84])[0]
            
            ofs_tris = struct.unpack('<I', header_data[84:88])[0]
            ofs_uvs = struct.unpack('<I', header_data[92:96])[0]    
            ofs_verts = struct.unpack('<I', header_data[96:100])[0]  
            ofs_end = struct.unpack('<I', header_data[100:104])[0] 
            
            f.seek(current_surf_ofs + ofs_verts)
            for _ in range(num_verts):
                px, py, pz, pnorm = struct.unpack('<4H', f.read(8))
                vx = ((px - 32768) * scale_x) + offset_x
                vy = ((py - 32768) * scale_y) + offset_y
                vz = ((pz - 32768) * scale_z) + offset_z
                global_verts.append((vx, vy, vz))
            
            f.seek(current_surf_ofs + ofs_uvs)
            for _ in range(num_verts):
                u, v = struct.unpack('<2f', f.read(8))
                global_uvs.append((u, 1.0 - v)) 
                
            f.seek(current_surf_ofs + ofs_tris)
            for _ in range(num_tris):
                i1, i2, i3 = struct.unpack('<3I', f.read(12))
                global_tris[clean_mat_name].append((i1 + vert_offset, i2 + vert_offset, i3 + vert_offset))
            
            vert_offset += num_verts
            current_surf_ofs += ofs_end

    # --- EXPORT TEXTURES AND MTL ---
    print("   -> Preparing materials and textures...")
    mtl_path = os.path.join(export_dir, f"{model_name}.mtl")
    with open(mtl_path, 'w') as mtl:
        mtl.write("# EXPORT THAT FAKK - TAN MTL\n\n")
        
        for orig_mat, clean_mat in used_materials:
            mtl.write(f"newmtl {clean_mat}\n")
            mtl.write("Kd 1.0 1.0 1.0\n")
            
            tex_name, tex_path = resolve_texture(orig_mat, tex_index, shader_map)
            
            if tex_name and tex_path:
                png_name = f"{tex_name}.png"
                out_png = os.path.join(tex_dir, png_name)
                if not os.path.exists(out_png):
                    convert_ftx(tex_path, out_png)
                mtl.write(f"map_Kd textures/{png_name}\n\n")
            else:
                mtl.write("\n")

    # --- EXPORT OBJ ---
    obj_path = os.path.join(export_dir, f"{model_name}.obj")
    with open(obj_path, 'w') as out:
        out.write("# EXPORT THAT FAKK - Heavy Metal FAKK 2 Exporter\n")
        out.write(f"mtllib {model_name}.mtl\n\n")
        
        for v in global_verts:
            out.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
        for uv in global_uvs:
            out.write(f"vt {uv[0]:.6f} {uv[1]:.6f}\n")
            
        for mat_name, tris in global_tris.items():
            if not tris: continue
            out.write(f"\ng {mat_name}\n")
            out.write(f"usemtl {mat_name}\n")
            for t in tris:
                out.write(f"f {t[0]}/{t[0]} {t[2]}/{t[2]} {t[1]}/{t[1]}\n")
                
    print(f" [SUCCESS] -> Saved to {export_dir}")


def process_paths(paths):
    tan_files =[]
    for path in paths:
        if os.path.isfile(path) and path.lower().endswith('.tan'):
            tan_files.append(path)
        elif os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                for file in files:
                    if file.lower().endswith('.tan'):
                        tan_files.append(os.path.join(root, file))
    
    if not tan_files:
        print("No .tan files found!")
        input("Press Enter to exit...")
        return

    print(f"--- FOUND {len(tan_files)} .TAN FILES ---")
    
    # 1. Ask for the textures folder
    base_dir = input("\nEnter the full path to the game base (pak0) for auto-texture search\n(or press Enter to skip textures): ").strip()
    
    # 2. Index once for the entire batch of models
    tex_index, shader_map = {}, {}
    if base_dir and os.path.isdir(base_dir):
        tex_index = build_texture_index(base_dir)
        shader_map = parse_shaders(base_dir)
    elif base_dir:
        print("[ERROR] The specified base folder does not exist! Textures will not be linked.")

    # 3. Export all files
    for file in tan_files:
        try:
            export_tan_to_obj(file, tex_index, shader_map)
        except Exception as e:
            print(f" [ERROR] Failed to export {file}: {e}")
    
    print("\n--- ALL DONE! ---")
    input("Press Enter to exit...")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        process_paths(sys.argv[1:])
    else:
        print("Drag & Drop .tan files or folders directly onto this script!")
        input("Press Enter to exit...")