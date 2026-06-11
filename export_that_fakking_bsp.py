import struct
import os
import sys
import json
import re
from PIL import Image

# Filter out technical materials
SKIP_MATERIALS = ['nodraw', 'clip', 'trigger', 'caulk', 'hint', 'system', 'fog', 'skip', 'areaportal']

def convert_ftx(in_filepath, out_filepath):
    try:
        with open(in_filepath, 'rb') as f:
            header = f.read(12)
            if len(header) < 12: return False
            width, height, _ = struct.unpack('<3I', header)
            if width == 0 or height == 0 or width > 4096 or height > 4096: return False
            pixel_data = f.read()
            
            if len(pixel_data) >= width * height * 4:
                img = Image.frombytes("RGBA", (width, height), pixel_data, "raw", "RGBA")
                # TRANSPARENT WALLS FIX: 
                # Strictly remove Alpha channel, as in FAKK2 it's often used for Specular
                img = img.convert("RGB")
            elif len(pixel_data) >= width * height * 3:
                img = Image.frombytes("RGB", (width, height), pixel_data, "raw", "RGB")
            else: return False
            
            img.save(out_filepath, "PNG")
            return True
    except Exception as e:
        print(f"   [!] Conversion error {in_filepath}: {e}")
        return False

def build_texture_index(base_dir):
    print(" > Indexing textures...")
    index = {}
    for root, _, files in os.walk(base_dir):
        for file in files:
            if file.lower().endswith('.ftx'):
                name = os.path.splitext(file)[0].lower()
                index[name] = os.path.join(root, file)
    return index

def parse_shaders(base_dir):
    """Deep parser of .shader, .txt, and .tik files for hidden textures"""
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
    """Perfect texture matching algorithm"""
    mat_lower = mat_name.lower()
    
    # 1. Search in shaders
    if mat_lower in shader_map and shader_map[mat_lower] in tex_index:
        return shader_map[mat_lower], tex_index[shader_map[mat_lower]]
        
    base_name = mat_lower.split('/')[-1].split('\\')[-1]
    if base_name in shader_map and shader_map[base_name] in tex_index:
        return shader_map[base_name], tex_index[shader_map[base_name]]
        
    # 2. Direct match
    if base_name in tex_index:
        return base_name, tex_index[base_name]

    # 3. FIX: Strip digits and garbage at the end (bloodclaw2 -> bloodclaw)
    clean_base = re.sub(r'[\d_]+$', '', base_name)
    if clean_base and clean_base in tex_index:
        return clean_base, tex_index[clean_base]
        
    # 4. Strip suffixes by underscore
    parts = base_name.split('_')
    while len(parts) > 1:
        parts.pop()
        fuzzy_name = "_".join(parts)
        if fuzzy_name in tex_index:
            return fuzzy_name, tex_index[fuzzy_name]
            
    # 5. FIX: Search for the LONGEST match inside the name, not the first one
    best_match = None
    for tex in tex_index:
        if len(tex) >= 4 and (tex in base_name or base_name in tex):
            if best_match is None or len(tex) > len(best_match):
                best_match = tex
                
    if best_match:
        return best_match, tex_index[best_match]
            
    return None, None

def tessellate_patch(c_points, p_width, p_height, lod=5):
    patch_verts =[]
    patch_faces =[]
    
    def get_pt(gx, gy): return c_points[gy * p_width + gx]
    def bez(p0, p1, p2, t):
        omt = 1.0 - t
        return omt*omt*p0 + 2*t*omt*p1 + t*t*p2
        
    for py in range(0, p_height - 1, 2):
        for px in range(0, p_width - 1, 2):
            grid = [
                [get_pt(px, py),   get_pt(px+1, py),   get_pt(px+2, py)],
                [get_pt(px, py+1), get_pt(px+1, py+1), get_pt(px+2, py+1)],
                [get_pt(px, py+2), get_pt(px+1, py+2), get_pt(px+2, py+2)]
            ]
            
            base_idx = len(patch_verts)
            for iy in range(lod + 1):
                v_t = iy / float(lod)
                for ix in range(lod + 1):
                    u_t = ix / float(lod)
                    
                    row_pts = []
                    for row in grid:
                        pt =[]
                        for i in range(5):
                            pt.append(bez(row[0][i], row[1][i], row[2][i], u_t))
                        row_pts.append(pt)
                        
                    final_pt =[]
                    for i in range(5):
                        final_pt.append(bez(row_pts[0][i], row_pts[1][i], row_pts[2][i], v_t))
                    patch_verts.append(final_pt)
            
            for iy in range(lod):
                for ix in range(lod):
                    idx0 = base_idx + (iy * (lod + 1)) + ix
                    idx1 = base_idx + (iy * (lod + 1)) + ix + 1
                    idx2 = base_idx + ((iy + 1) * (lod + 1)) + ix
                    idx3 = base_idx + ((iy + 1) * (lod + 1)) + ix + 1
                    patch_faces.extend([(idx0, idx2, idx1), (idx1, idx2, idx3)])
                    
    return patch_verts, patch_faces

def process_bsp(filepath, base_dir):
    print(f"\n--- READING MAP: {os.path.basename(filepath)} ---")
    
    tex_index = build_texture_index(base_dir)
    shader_map = parse_shaders(base_dir)
    
    map_name = os.path.splitext(os.path.basename(filepath))[0]
    export_dir = os.path.join(os.path.dirname(filepath), f"{map_name}_export")
    tex_dir = os.path.join(export_dir, "textures")
    
    os.makedirs(export_dir, exist_ok=True)
    os.makedirs(tex_dir, exist_ok=True)
    
    with open(filepath, 'rb') as f:
        magic, version, _ = struct.unpack("<4sII", f.read(12))
        if magic != b'FAKK': return

        lump_headers = [struct.unpack("<II", f.read(8)) for _ in range(20)]

        # Entities Lump
        for offset, size in lump_headers:
            if size > 0:
                f.seek(offset)
                data = f.read(min(size, 256))
                if b'worldspawn' in data:
                    f.seek(offset)
                    entities_text = f.read(size).decode('latin-1', errors='ignore')
                    
                    entities =[]
                    current_ent = {}
                    for line in entities_text.splitlines():
                        line = line.strip()
                        if line == '{': current_ent = {}
                        elif line == '}': 
                            if current_ent: entities.append(current_ent)
                        elif line.startswith('"'):
                            parts = line.split('" "')
                            if len(parts) == 2:
                                current_ent[parts[0].strip('"')] = parts[1].strip('"')
                    
                    with open(os.path.join(export_dir, f"{map_name}_entities.json"), 'w', encoding='utf-8') as ef:
                        json.dump(entities, ef, indent=4, ensure_ascii=False)
                    break

        f.seek(lump_headers[0][0])
        shaders = [f.read(76)[:64].split(b'\0')[0].decode('ascii', errors='ignore') for _ in range(lump_headers[0][1] // 76)]

        f.seek(lump_headers[3][0])
        surfaces = [struct.unpack("<12I 3f 9f II f", f.read(108)) for _ in range(lump_headers[3][1] // 108)]

        f.seek(lump_headers[4][0])
        verts = [struct.unpack("<3f 2f 2f 3f 4B", f.read(44)) for _ in range(lump_headers[4][1] // 44)]

        f.seek(lump_headers[5][0])
        indexes = [struct.unpack("<I", f.read(4))[0] for _ in range(lump_headers[5][1] // 4)]

    obj_verts, obj_uvs = [],[]
    mat_faces = {}
    bsp_v_to_obj_v = {}

    def get_obj_v(bsp_idx, bsp_v):
        if bsp_idx not in bsp_v_to_obj_v:
            obj_verts.append((bsp_v[0], bsp_v[1], bsp_v[2]))
            obj_uvs.append((bsp_v[3], bsp_v[4]))
            bsp_v_to_obj_v[bsp_idx] = len(obj_verts)
        return bsp_v_to_obj_v[bsp_idx]

    print(" > Generating High-Poly geometry...")
    used_materials = set()

    for surf in surfaces:
        tex_idx, _, stype, v_start, v_count, i_start, i_count = surf[:7]
        mat_name = shaders[tex_idx]

        if any(skip in mat_name.lower() for skip in SKIP_MATERIALS):
            continue

        clean_mat_name = mat_name.replace('/', '_').replace('\\', '_')
        if clean_mat_name not in mat_faces: mat_faces[clean_mat_name] =[]
        used_materials.add((mat_name, clean_mat_name))

        if stype in [1, 3, 5]:
            for i in range(0, i_count, 3):
                idx1, idx2, idx3 = v_start + indexes[i_start + i], v_start + indexes[i_start + i + 2], v_start + indexes[i_start + i + 1]
                mat_faces[clean_mat_name].append((get_obj_v(idx1, verts[idx1]), get_obj_v(idx2, verts[idx2]), get_obj_v(idx3, verts[idx3])))
                
        elif stype == 2:
            p_width, p_height = surf[24], surf[25]
            if p_width < 3 or p_height < 3: continue
            
            c_points = [(verts[v_start + (y * p_width) + x][0], verts[v_start + (y * p_width) + x][1], verts[v_start + (y * p_width) + x][2], verts[v_start + (y * p_width) + x][3], verts[v_start + (y * p_width) + x][4]) for y in range(p_height) for x in range(p_width)]
            
            p_verts, p_faces = tessellate_patch(c_points, p_width, p_height, lod=5)
            
            for face in p_faces:
                for idx in face:
                    obj_verts.append((p_verts[idx][0], p_verts[idx][1], p_verts[idx][2]))
                    obj_uvs.append((p_verts[idx][3], p_verts[idx][4]))
                v3_idx = len(obj_verts)
                mat_faces[clean_mat_name].append((v3_idx - 2, v3_idx - 1, v3_idx))

    print(" > Converting textures and building .MTL...")
    mtl_path = os.path.join(export_dir, f"{map_name}.mtl")
    with open(mtl_path, 'w') as mtl:
        mtl.write("# EXPORT THAT FAKK - BSP MTL\n\n")
        for orig_mat, clean_mat in used_materials:
            mtl.write(f"newmtl {clean_mat}\nKd 1.0 1.0 1.0\n")
            
            tex_name, tex_path = resolve_texture(orig_mat, tex_index, shader_map)
            if tex_name and tex_path:
                png_name = f"{tex_name}.png"
                out_png = os.path.join(tex_dir, png_name)
                if not os.path.exists(out_png):
                    convert_ftx(tex_path, out_png)
                mtl.write(f"map_Kd textures/{png_name}\n\n")
            else:
                mtl.write("\n")

    print(f" > Saving 3D model to {map_name}.obj...")
    with open(os.path.join(export_dir, f"{map_name}.obj"), 'w') as obj:
        obj.write(f"mtllib {map_name}.mtl\n\n")
        for v in obj_verts: obj.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
        for uv in obj_uvs: obj.write(f"vt {uv[0]:.6f} {1.0 - uv[1]:.6f}\n")
        for mat_name, faces in mat_faces.items():
            if not faces: continue
            obj.write(f"\ng {mat_name}\nusemtl {mat_name}\n")
            for f in faces: obj.write(f"f {f[0]}/{f[0]} {f[1]}/{f[1]} {f[2]}/{f[2]}\n")

    print("\n[SUCCESS] Map, textures, and script objects list successfully exported!")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        process_bsp(sys.argv[1], input("Enter the full path to the game's main folder: ").strip())
    else:
        print("Drag & Drop the .bsp file directly onto this script!")
    input("\nPress Enter to exit...")