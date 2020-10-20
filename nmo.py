bl_info = {
    "name": "Import NMO files",
    "author": "Half-asian",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "File > Import > NMO (.nmo)",
    "description": "Import Shadow of the Colossus models in NMO format",
    "warning": "",
    "wiki_url": "",
    "category": "Import-Export",
}

import bpy
import time
from random import random

from bpy_extras.io_utils import ImportHelper, ExportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator

IGNORE_MIX_SHADERS = True

class GeometryHeader:
    def __init__(self):
        self.surface = None
        self.strips = 0

def toAscii(hex_str):
    string = ""
    ascii_list = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', ':', ';', '<', '=', '>', '?', '@', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', '[', '', ']', '^', '_',  "'", 'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z']
    for i in range(0, len(hex_str), 2):
        try:
            current_character = int(hex_str[i:i+2], 16)
            string += ascii_list[current_character - 48]
        except Exception:
            print("unknown char")
    return string

def twos_complement(hexstr,bits):
    value = int(hexstr,16)
    if value & (1 << (bits-1)):
        value -= 1 << bits
    return value

def convert_to_float32(byte4):
    mantissa_bits = byte4[9:]
    byte4 = int(byte4, 2)
    sign = (byte4 >> 31) & 0x01
    exponent = (byte4 >> 23) & 0xff
    mantissa = 1
    for i in range(23):
        if mantissa_bits[i] == '1':
            mantissa += 2 ** (-(i + 1))
    if sign == 1:
        decimal = -1 * mantissa * (2 ** (exponent - 127))
    else:
        decimal = mantissa * (2 ** (exponent - 127))
    return decimal

def convert_hex_to_binary32(hex32):
    binary32 = '00000000000000000000000000000000' + str(bin(int(hex32, 16)))[2:]
    return binary32[-32:]

def convert_to_big_endian(little_endian):
    return little_endian[6:8] + little_endian[4:6] + little_endian[2:4] + little_endian[0:2]

def crossProduct(a, b):
    return ((a[1] * b[2] - a[2] * b[1], a[2]  * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]))

def retrieveTextures(content, pointer):
    textures = []
    current_texture = ""
    while True:
        if content[pointer] == 0:
            pointer += 1
            if content[pointer] == 0:
                textures.append(toAscii(current_texture))
                return textures
            else:
                textures.append(toAscii(current_texture))
                current_texture = ""
        else:
            current_texture += hex(content[pointer])[2:]
            pointer += 1            

def retrieveSurfaceNames(data, file_size):
    surfaces = []
    current_surface = ""
    pointer = file_size
    while data[pointer:pointer+4].hex() != "2e6e6d6f":
        pointer -= 1
    while data[pointer-2:pointer].hex() != "0000":
        pointer -= 1
    while True:
        if data[pointer] == 0:
            pointer += 1
            if data[pointer] == 0:
                surfaces.append(toAscii(current_surface))
                return surfaces
            else:
                surfaces.append(toAscii(current_surface))
                current_surface = ""
        else:
            current_surface += hex(data[pointer])[2:]
            pointer += 1
            
def exportSurfaces(content, file_size, textures, surfaces, object_name, nmo_object, filepath_folder, srf_location, srf_amount):
    #mtl_write = open(object_name + '.mtl', mode='w')
    #mtl_write.write('mtllib ' + object_name + '\n')
    
    new_surfaces = []
    
    surface_count = 0
    surface_to_mat = {}
    for pointer in range(srf_location, srf_location + 288 * srf_amount, 288):
        uv_map_count = int(convert_to_big_endian(content[pointer + 28:pointer + 32].hex()), 16)
        if IGNORE_MIX_SHADERS == True:
            mat_name = textures[int(convert_to_big_endian(content[pointer + 44:pointer + 48].hex()), 16)]
        else:
            if uv_map_count == 1:
                mat_name = textures[int(convert_to_big_endian(content[pointer + 44:pointer + 48].hex()), 16)]
            else:
                mat_name = "mix"
                for i in range(pointer, pointer + uv_map_count * 16, 16):
                    mat_name += " + " + textures[int(convert_to_big_endian(content[i + 44:i + 48].hex()), 16)]
        img = bpy.data.images.load(filepath_folder + "\\texture\\" + mat_name + ".png")
        if len(surfaces) == surface_count:
            print("Error, out of bounds surface")
            break
        if len(surfaces[surface_count]) == 0:
            print("Error, unnamed surface!")
            continue
        if surfaces[surface_count][0].lower() == 'z':
            if "z_" + mat_name not in new_surfaces:
                addImageMaterial("z_" + mat_name, nmo_object, img, True)
                new_surfaces.append("z_" + mat_name)
            surface_to_mat[surface_count] = new_surfaces.index("z_" + mat_name)
        else:
            if mat_name not in new_surfaces:
                addImageMaterial(mat_name, nmo_object, img, False)
                new_surfaces.append(mat_name)
            surface_to_mat[surface_count] = new_surfaces.index(mat_name)
        surface_count += 1
        pointer += 3
    return surface_to_mat

# def retrieveGeometryHeaders(content, file_size):
# 
#     geometry_headers = []
#     pointer = file_size
#     while content[pointer:pointer + 3].hex() != "4e4d4f":
#         pointer -= 1
#     pointer -= 32
#     while content[pointer - 32:pointer - 28].hex() != "00000000" and content[pointer - 32:pointer - 28].hex() != "02000000":
#         pointer -= 32
#         new_geo = GeometryHeader()
#         new_geo.surface = int(convert_to_big_endian(content[pointer + 8:pointer + 12].hex()), 16)
#         new_geo.strips = int(convert_to_big_endian(content[pointer + 24:pointer + 28].hex()), 16)
#         if new_geo.surface == 0 or new_geo.strips == 0: #Just in case
#             break
#         #print(hex(pointer), new_geo.surface, new_geo.strips)
#         geometry_headers.append(new_geo)
#     geometry_headers.reverse()
#     return geometry_headers
def getGeometryHeaders(content, pointer, amount):
    geometry_headers = []
    for i in range(pointer, pointer + amount * 32, 32):
        new_geo = GeometryHeader()
        new_geo.surface = int(convert_to_big_endian(content[i + 8:i + 12].hex()), 16)
        new_geo.strips = int(convert_to_big_endian(content[i + 24:i + 28].hex()), 16)
        geometry_headers.append(new_geo)
    return geometry_headers

def get_unstable_surfaces(content, file_size, srf_location, srf_count):
    unstable_surfaces = []
    for i in range(srf_location, srf_location + 288 * srf_count, 288):
        if content[i + 264] == 0x1:
            unstable_surfaces.append(1)
        else:
            unstable_surfaces.append(0)
        i += 1
    return unstable_surfaces

def exportVertexCoords(data, pointer, vertex_amount, list_vertices):
    first_3 = []
    #print(hex(pointer))
    
    for i in range(pointer, pointer + 12 * vertex_amount, 12):
        
        x_vertex = convert_to_float32(convert_hex_to_binary32(convert_to_big_endian(data[i:i+4].hex()))) * -1
        y_vertex = convert_to_float32(convert_hex_to_binary32(convert_to_big_endian(data[i+4:i+8].hex()))) 
        z_vertex = convert_to_float32(convert_hex_to_binary32(convert_to_big_endian(data[i+8:i+12].hex()))) * -1
        
        #print(x_vertex, y_vertex, z_vertex)
        
        #if x_vertex > 10000 or x_vertex < -10000 or y_vertex > 10000 or y_vertex < -10000 or z_vertex > 10000 or y_vertex < -10000:
            #return None
    
        list_vertices.append((x_vertex, z_vertex, y_vertex))
        if i <= pointer + 24:
            first_3.append((x_vertex, y_vertex, z_vertex))
    return first_3

def exportTexCoords(content, pointer, vertex_amount, list_uv):
    for i in range(pointer, pointer + 4 * vertex_amount, 4):
        x_vertex = twos_complement(convert_to_big_endian(content[i:i+2].hex()), 16) / 4096.0
        y_vertex = twos_complement(convert_to_big_endian(content[i+2:i+4].hex()), 16) / 4096.0

        list_uv.append((x_vertex, (1 - y_vertex)))

def exportVertexColors(content, pointer, vertex_amount, list_colors):
    for i in range(pointer, pointer + 4 * vertex_amount, 4):
        r = content[i]
        g = content[i + 1]
        b = content[i + 2]
        a = content[i + 3] / 128
        list_colors.append((r, g, b, a))

def addImageMaterial(name, obj, img, is_transparent):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    obj.data.materials.append(mat)
    nodes = mat.node_tree.nodes
    mat.blend_method = 'HASHED'

    nodes.clear()
    
    principled = nodes.new('ShaderNodeBsdfPrincipled')
    output = nodes.new('ShaderNodeOutputMaterial')
    #principled.inputs["Specular"].default_value = 0.0
    #principled.inputs["Roughness"].default_value = 1.0
    texture = nodes.new(type="ShaderNodeTexImage")
    texture.image = img
    #texture.extension = 'CLIP' #TODO: Set to clip if foliage
    links = mat.node_tree.links
    links.new(texture.outputs[0], principled.inputs[0])
    
    tex_mix = nodes.new('ShaderNodeMixShader')
    tex_trans = nodes.new('ShaderNodeBsdfTransparent')
    
    links.new(principled.outputs[0], tex_mix.inputs[2])
    links.new(tex_trans.outputs[0], tex_mix.inputs[1])
    links.new(texture.outputs[1], tex_mix.inputs[0])

    if is_transparent == True:
        #mat.blend_method = 'BLEND'
        transparent = nodes.new('ShaderNodeBsdfTransparent')
        color = nodes.new('ShaderNodeVertexColor')
        mix = nodes.new('ShaderNodeMixShader')
        links.new(color.outputs[1], mix.inputs[0])
        links.new(transparent.outputs[0], mix.inputs[1])
        links.new(tex_mix.outputs[0], mix.inputs[2])
        links.new(mix.outputs[0], output.inputs[0])
    else:
        links.new(tex_mix.outputs[0], output.inputs[0])

        
        #color = nodes["Vertex Color"]
        #mix = nodes["Mix Shader"]
        
    


def nmo_parser(context, filepath):
    #print("\nImporting NMO file...")
    
    #print(filepath)
    
    object_name = filepath.split('\\')[-1][:-4]
    
    filepath_folder = filepath[:len(filepath) - len(object_name) - 5]
    #print(filepath_folder)
    vert_counter = 0

    mesh = bpy.data.meshes.new(object_name)
    nmo_object = bpy.data.objects.new(object_name, mesh)
    #Read NMO file
    with open(filepath, mode='rb') as nmo_file:
        data = nmo_file.read()
        
        file_size = int(convert_to_big_endian(data[0x14:0x18].hex()), 16)
        
        print ("'"+filepath+"'" + " succesfully loaded!\n")

        
        rodata = 0
        while data[rodata:rodata+6].hex() != "726f64617461":
            rodata += 1
        
        nmo_header = 0
        while data[nmo_header:nmo_header+4].hex() != "4e4d4f00":
            nmo_header += 1
        offset = nmo_header - int(convert_to_big_endian(data[16: 20].hex()), 16)
    
        tex_amount = int(convert_to_big_endian(data[nmo_header + 68: nmo_header + 72].hex()), 16)
        tex_location = int(convert_to_big_endian(data[nmo_header + 64: nmo_header + 68].hex()), 16) + offset
        srf_amount = int(convert_to_big_endian(data[nmo_header + 84: nmo_header + 88].hex()), 16)
        srf_location = int(convert_to_big_endian(data[nmo_header + 80: nmo_header + 84].hex()), 16) + offset
        geo_amount = int(convert_to_big_endian(data[nmo_header + 100: nmo_header + 104].hex()), 16)
        geo_location = int(convert_to_big_endian(data[nmo_header + 96: nmo_header + 100].hex()), 16) + offset
        
        
        textures = retrieveTextures(data, rodata + 12)
        surfaces = retrieveSurfaceNames(data, file_size)
        surfaces = surfaces[tex_amount:]
        surface_to_mat = exportSurfaces(data, file_size, textures, surfaces, object_name, nmo_object, filepath_folder, srf_location, srf_amount)
        geometry_headers = getGeometryHeaders(data, geo_location, geo_amount)
        unstable_surfaces = get_unstable_surfaces(data, file_size, srf_location, srf_amount)
        
        
        list_vertices = []
        list_faces = []
        list_uv = []
        list_actual_uv = []
        list_vertex_colors = []
        list_actual_vertex_colors = []
        material_indexes = []
        vertex_entry_point = int(convert_to_big_endian(data[0xb4:0xb8].hex()), 16) + 32
        
        strip_mode = 1                                    
        
        current_geo = 0
        current_strip = 0
        
        for g in geometry_headers:
            for s in range(g.strips):
                first_3 = exportVertexCoords(data, vertex_entry_point + 4, data[vertex_entry_point + 2], list_vertices)
                           
                a = (first_3[1][0] - first_3[0][0], first_3[1][1] - first_3[0][1], -(first_3[1][2] - first_3[0][2]))                
                b = (first_3[2][0] - first_3[0][0], first_3[2][1] - first_3[0][1], -(first_3[2][2] - first_3[0][2]))
                
                #print(g.strips)
                if unstable_surfaces[g.surface] == 1:
                    n = crossProduct(a, b)
                    if n[1] > 0:
                        strip_mode = 0
                    else:
                        strip_mode = 1
                    if (data[vertex_entry_point + 2] == 4) :
                       strip_mode = 0
                    if (data[vertex_entry_point + 2] == 3):
                        strip_mode = 1
                
                tex_coord_location = vertex_entry_point + data[vertex_entry_point + 2] * 12 + 12
                
                if data[tex_coord_location - 5] == 109: #This is the normals of the object
                    tex_coord_location += data[vertex_entry_point + 2] * 8 + 4
                
                exportTexCoords(data, tex_coord_location, data[vertex_entry_point + 2], list_uv)
                
                color_location = vertex_entry_point
                while data[color_location + 3] != 110: # 04 XX XX 6E
                    color_location += 4
                
                exportVertexColors(data, color_location + 4, data[vertex_entry_point + 2], list_vertex_colors)
                
                for i in range(data[vertex_entry_point + 2] - 2):
                    if strip_mode == 0:
                        list_faces.append((vert_counter + i, vert_counter + 1 + i, vert_counter + 2 + i))
                        list_actual_uv.append(list_uv[vert_counter + i])
                        list_actual_uv.append(list_uv[vert_counter + i + 1])
                        list_actual_uv.append(list_uv[vert_counter + i + 2])
                        list_actual_vertex_colors.append(list_vertex_colors[vert_counter + i])
                        list_actual_vertex_colors.append(list_vertex_colors[vert_counter + i + 1])
                        list_actual_vertex_colors.append(list_vertex_colors[vert_counter + i + 2])
                        strip_mode = 1
                    else:
                        list_faces.append((vert_counter + 2 + i, vert_counter + 1 + i, vert_counter + i))
                        list_actual_uv.append(list_uv[vert_counter + i + 2])
                        list_actual_uv.append(list_uv[vert_counter + i + 1])
                        list_actual_uv.append(list_uv[vert_counter + i])
                        list_actual_vertex_colors.append(list_vertex_colors[vert_counter + i + 2])
                        list_actual_vertex_colors.append(list_vertex_colors[vert_counter + i + 1])
                        list_actual_vertex_colors.append(list_vertex_colors[vert_counter + i])
                        strip_mode = 0
                    material_indexes.append(surface_to_mat[g.surface])

                strip_mode = 1
                vert_counter += data[vertex_entry_point + 2]
                    
                    
                #We probably need these but it breaks some models and fixes others rip
                vertex_entry_point += 4 + 4 * data[vertex_entry_point + 2] * 3
                
                #IF the model crashes / has broken verts, replace top line with next 2 lines
                
                #while data[vertex_entry_point: vertex_entry_point + 4].hex() != "01000005":
                    #vertex_entry_point += 1
                
                while int(data[vertex_entry_point:vertex_entry_point + 2].hex(), 16) != 384 and data[vertex_entry_point + 4] != '6c':
                    if (vertex_entry_point + 8 < file_size):  
                        vertex_entry_point += 4
                    else:
                        break

        #for a in surface_to_mat:
           #print(a, surface_to_mat[a])
            #print(surfaces[a])

        mesh.from_pydata(list_vertices,[],list_faces)
        mesh.update(calc_edges=True)
        context.view_layer.active_layer_collection.collection.objects.link(nmo_object)
        
        
        uvlayer = nmo_object.data.uv_layers.new()
        
        uv_counter = 0
        
        for face in nmo_object.data.polygons:
            for vert_idx, loop_idx in zip(face.vertices, face.loop_indices):
                uvlayer.data[loop_idx].uv = (list_actual_uv[uv_counter]) # ie UV coord for each face with vert  me.vertices[vert_idx]
                uv_counter += 1

        vertex_colors = nmo_object.data.vertex_colors.new()
        
        for i in range(len(nmo_object.data.vertex_colors[0].data)):
            nmo_object.data.vertex_colors[0].data[i].color = list_actual_vertex_colors[i]
        
        for i in range(len(nmo_object.data.polygons)):
            nmo_object.data.polygons[i].material_index = material_indexes[i]
        print("\nNMO file successfully imported!\n")

    return {'FINISHED'}

class ImportNMO(Operator, ImportHelper):
    "Load a NMO file"
    bl_idname = "import_test.some_data"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Import NMO"

    # ImportHelper mixin class uses this
    filename_ext = ".nmo"

    filter_glob: StringProperty(
        default="*.nmo",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )
    def execute(self, context):
        quadrant_parts = ["m01", "m02", "m03", "p01", "p02", "p03"]
        nmo_file = self.filepath.split('\\')[-1]
        nmo_name = nmo_file.split('_')[0]
        
        is_quadrant = False

        for a in quadrant_parts:
            for b in quadrant_parts:
                #nmo_parser(context, self.filepath)
                try:
                    file_name = self.filepath[:len(self.filepath) - len(nmo_file)] + nmo_name + '_' + nmo_name + '_' + a + '_' + b + '_' + "lyr0.nmo"
                    nmo_parser(context, file_name)
                    is_quadrant = True
                except Exception:
                    continue
                    #print ("Couldn't find", file_name)
        if is_quadrant == False:
            nmo_parser(context, self.filepath)
        
        return {'FINISHED'}

# Only needed if you want to add into a dynamic menu
def menu_func_import(self, context):
    self.layout.operator(ImportNMO.bl_idname, text="NMO (.nmo)")
    
def register():
    bpy.utils.register_class(ImportNMO)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    bpy.utils.unregister_class(ImportNMO)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)


if __name__ == "__main__":
    register()
    bpy.ops.import_test.some_data('INVOKE_DEFAULT')




