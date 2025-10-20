bl_info = {
    "name": "Compound Creator",
    "author": "Tim Bonzon",
    "version": (1.3, 1.3),
    "blender": (2, 80, 0),
    "location": "View3d > Toolbar",
    "description": "Adds a chemical compound from CML file",
    "warning": "",
    "doc_url": "",
    "category": "Add Mesh",
}

import bpy
import math
import bmesh
import mathutils
from mathutils import Vector
# ImportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ImportHelper
from bpy.types import GPencilFrame
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator

class CreatorPanel(bpy.types.Panel):
    bl_label = "Atom Animator"
    bl_idname = "PT_CompoundPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Atom Animator'
    
    def draw (self, context):
        layout = self.layout
        
        row = layout.row()
        row.label(text="Add Compound", icon='OUTLINER_OB_POINTCLOUD')
        row = layout.row()
        row.operator("import_cml.compound_data",icon='OUTLINER_DATA_POINTCLOUD')
        row = layout.row()
        
        layout.prop(context.scene, "lone_pair")
        row= layout.row()
        layout.prop(context.scene, "lone_pair_selected")
 
def showLonePairs(self, context):
    should_render = self.lone_pair
    for obj in bpy.data.objects:
        if obj.name.startswith("lonepair_"):
            obj.hide_render = not should_render
            obj.hide_viewport = not should_render
            obj.hide_select = not should_render

def showSelectedLonePairs(self, context):
    should_render = self.lone_pair_selected
    
    selected_objects = context.selected_objects
    
    for parent in selected_objects:
        for child in parent.children: 
            if child.name.startswith("lonepair_"):
                child.hide_viewport = not should_render
                child.hide_render = not should_render
                child.hide_select = not should_render
       
def findCollection (collection):
    for col in bpy.data.collections:
            if col.name == collection:
                    return True
    return False


def addBlackMaterial():
    mat = bpy.data.materials.get("Black")
    
    if mat is None:
        mat = bpy.data.materials.new(name="Black") 
        
    mat.diffuse_color = (0, 0, 0, 1)
    mat.specular_intensity = 0  
    mat.roughness = 1
    
    return mat
    
def addWhiteMaterial():
    mat = bpy.data.materials.get("White")
    
    if mat is None:
        mat = bpy.data.materials.new(name="White") 
        
    mat.diffuse_color = (1, 1, 1, 1)
    mat.specular_intensity = 0  
    mat.roughness = 1
    
    return mat

def makeHalo(name, radius=1.0, segments=32, location=(0,0,0)):
    mesh = bpy.data.meshes.new("Halo")
    obj = bpy.data.objects.new(name, mesh)
    
    bm = bmesh.new()

    center = bm.verts.new(Vector(location))

    verts = []
    for i in range (segments):
        angle = 2  * math.pi * i/ segments
        x = location[0] + radius * math.cos(angle)
        y = location[1] + radius * math.sin(angle)
        z = location[2]
        v = bm.verts.new((x,y,z))
        
        verts.append(v)

    bm.verts.ensure_lookup_table()

    for i in range(segments):
        v1 = verts[i]
        v2 = verts[(i+1) % segments]
        bm.faces.new([center, v1, v2])

    bm.to_mesh(mesh)
    bm.free()

    bpy.context.collection.objects.link(obj)
    

def addAtom(x,y,atom,id, hydrogens=0):
    
    #grabbing the right collection
    if findCollection (atom) == False:
        atom_collection = bpy.data.collections.new(atom)
        bpy.context.scene.collection.children.link(atom_collection)
    else:
        atom_collection = bpy.data.collections[atom]

    #grabbing the master collection
    
    master_collection = bpy.context.scene.collection
    
    #adding the text
    
    t = bpy.data.curves.new(name=id, type="FONT")
    t.offset_x = -0.015
    t.offset_y = -0.015
    t.size = 0.5
    t.materials.append(addBlackMaterial())
    t.align_x = "CENTER"
    t.align_y = "CENTER"
    t_o = bpy.data.objects.new(id, t)
    t_o.location = [x, y, 0]
    if hydrogens > 1:
        atom = atom + "H"
        h = bpy.data.curves.new(name=atom, type="FONT")
        h.body = str(hydrogens)
        h.materials.append(addBlackMaterial())
        h.size = 0.3
        h.offset_x = 0.35
        h.offset_y = -0.25
        h_o = bpy.data.objects.new(id+"_sub", h)
        h_o.parent = t_o
        h_o.location = [0, 0, 0]
        atom_collection.objects.link(h_o)

    t.body = atom
    bpy.context.scene.collection.objects.link(t_o)
    
    
    #Setting the atom text    

    # bpy.ops.font.delete(type='PREVIOUS_WORD')
    # bpy.ops.font.text_insert(text=atom)
    # bpy.ops.object.mode_set(mode='OBJECT', toggle=True)
    # bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='MEDIAN')
    
    # #assigning a black material
    
    text = bpy.context.active_object
    
    #adding in the atom halo
    
    makeHalo(id+str(x)+"_Halo",radius=0.25, segments=32, location=(0, 0, -0.05)) 
    #bpy.ops.mesh.primitive_circle_add(radius=0.25, fill_type='NGON', enter_editmode=False, align='WORLD', location=(0,0,-0.05), scale=(1, 1, 1))
    halo = bpy.data.objects[id+str(x)+"_Halo"]
    atom_collection.objects.link(halo)
    master_collection.objects.unlink(halo)
    halo.parent = t_o
    #@halo.name = id + "_halo"
    
    #assigning a white material to halo
    
    halo.data.materials.append(addWhiteMaterial())
    
    #Adding an empty to act as a handle
    
    #handle = bpy.ops.object.empty_add(type='SPHERE', align='WORLD', location=(x, 0, y + 4), scale=(1, 1, 1))
    
    #adding the object to the atom collection
    
    atom_collection.objects.link(t_o)
    master_collection.objects.unlink(t_o)

    
    #text.parent = handle
    
    print("Added atom " + id)

def draw_line(gp_frame, p0 : tuple, p1 : tuple):
    gp_stroke = gp_frame.strokes.new()
    gp_stroke.display_mode = '3DSPACE'
    
    gp_stroke.points.add(count=2)
    gp_stroke.points[0].co = p0
    gp_stroke.points[1].co = p1 
    return gp_stroke

def addBond(atom1, atom2, name, order):
    
     #grabbing the master collection
    
    master_collection = bpy.context.scene.collection
    
    #finding bond collection
    
    col_name = "bonds"
    
    if findCollection (col_name) == False:
        bond_collection = bpy.data.collections.new(col_name)
        bpy.context.scene.collection.children.link(bond_collection)
    else:
        bond_collection = bpy.data.collections[col_name]
    
    #Creating Armature and bond plane
    
    bondName = atom1+ "_" + atom2 + "_" + name[0]
    planeName = name + "_bondPlane"
    bpy.ops.object.armature_add(enter_editmode=True, align='WORLD', location=(0, 0, 0), scale=(1, 1, 1))
    armature = bpy.context.active_object
    armature.name = bondName
    bpy.ops.armature.select_all(action='SELECT')
    bpy.ops.armature.duplicate_move(ARMATURE_OT_duplicate={"do_flip_names":False}, TRANSFORM_OT_translate={"value":(1, 0, 0), "orient_type":'GLOBAL', "orient_matrix":((1, 0, 0), (0, 1, 0), (0, 0, 1)), "orient_matrix_type":'GLOBAL', "constraint_axis":(True, False, False), "mirror":False, "use_proportional_edit":False, "proportional_edit_falloff":'SMOOTH', "proportional_size":1, "use_proportional_connected":False, "use_proportional_projected":False, "snap":False, "snap_elements":{'INCREMENT'}, "use_snap_project":False, "snap_target":'CLOSEST', "use_snap_self":True, "use_snap_edit":True, "use_snap_nonedit":True, "use_snap_selectable":False, "snap_point":(0, 0, 0), "snap_align":False, "snap_normal":(0, 0, 0), "gpencil_strokes":False, "cursor_transform":False, "texture_space":False, "remove_on_cancel":False, "view2d_edge_pan":False, "release_confirm":False, "use_accurate":False, "use_automerge_and_split":False})
    bpy.ops.object.editmode_toggle()
    bpy.ops.object.gpencil_add(location=(0, 0, 0), type='EMPTY')
    bpy.context.active_object.name = planeName
    bondStroke = bpy.context.scene.objects[planeName]
    gpencil_layer = bondStroke.data.layers.new(name, set_active=True)
    gpencil_layer.location[2] = -0.1
    frame = gpencil_layer.frames.new(0)
    #armature.object.data.location += 0.1a
    
    #Handling higher order bonds by drawing them off center
    if order <= 1: 
        draw_line(frame, (0,0,0),(1,0,0))
    else:
        for x in range(-1, order - 1):
            draw_line(frame, (0,0,(x*0.17)+0.15),(1,0,(x*0.17)+0.15))
            
    gpencil_layer.line_change = 50 
    bondPlane = bpy.data.objects[planeName]
    bondArma = bpy.data.objects[bondName]
    bpy.ops.object.select_all(action='DESELECT')
    bondArma.select_set(True)
    bondPlane.select_set(True)
    bpy.context.view_layer.objects.active = bondArma
    bpy.context.object.data.display_type = 'WIRE'

    #Assigning bond plane to armature
    
    bpy.ops.object.parent_set(type='ARMATURE_AUTO', keep_transform=True)
    
    #Adding the armature constraints to the atoms
    
    bpy.ops.object.posemode_toggle()
    
    #Only two bones are needed so we grab them here
    
    bpy.ops.pose.select_all(action='DESELECT')
    bone1 = bpy.data.objects[bondName].pose.bones["Bone"].bone
    bone2 = bpy.data.objects[bondName].pose.bones["Bone.001"].bone
    
    #First, the constraint is applied to bone1
    
    bpy.context.view_layer.objects[bondName].data.bones.active = bone1
    bone1.select = True
    bpy.ops.pose.constraint_add(type='COPY_LOCATION')
   # bpy.ops.pose.bones["Bone"].constraints["Copy Location"].use_offset = True
    bpy.context.object.pose.bones["Bone"].constraints["Copy Location"].target = bpy.data.objects[atom1]
    bpy.ops.pose.constraint_add(type='TRACK_TO')
#    bpy.context.object.pose.bones["Bone"].constraints["Track To"].target = bpy.data.objects[bondName]
#    bpy.context.object.pose.bones["Bone"].constraints["Track To"].subtarget = "Bone.001"
#    bpy.data.objects[bondName].pose.bones["Bone"].constraints["Copy Location"].use_offset = True

    #The constraint is then applied to the second bone
    
    bpy.ops.pose.select_all(action='DESELECT')
    bpy.context.view_layer.objects[bondName].data.bones.active = bone2
    bone2.select = True
    bpy.ops.pose.constraint_add(type='COPY_LOCATION')
    #bpy.ops.pose.bones["Bone.001"].constraints["Copy Location"].use_offset = True
    bpy.context.object.pose.bones["Bone.001"].constraints["Copy Location"].target = bpy.data.objects[atom2]
    bpy.ops.pose.constraint_add(type='TRACK_TO')
#    bpy.context.object.pose.bones["Bone.001"].constraints["Track To"].target = bpy.data.objects[bondName]
#    bpy.context.object.pose.bones["Bone.001"].constraints["Track To"].subtarget = "Bone"
#    bpy.data.objects[bondName].pose.bones["Bone.001"].constraints["Copy Location"].use_offset = True
    #We then exit out of pose mode to run the process again if needed
    
    bpy.ops.object.posemode_toggle()
    
def read_cml_file(context, filepath, use_some_setting):
    print("reading file...")
    f = open(filepath, 'r', encoding='utf-8')
    fname_tmp = f.name
    fname_tmp1 = fname_tmp.split("\\",-1)
    fname = fname_tmp1[2]
    data = f.readline()
    
    while data != "</molecule>\n" :
         print(f"current line ={data}")
         if "bond atomRefs2=" in data:
             
             #First, find the atoms involved in the bond
             
             atom1_tmp = data.split("atomRefs2=\"", 1)
             atom1_tmp2 = atom1_tmp[1].split()
             atom1 = atom1_tmp2[0] + fname
             
             atom2_tmp = data.split("\" i", 1)
             atom2_tmp2 = atom2_tmp[0].split()
             atom2_tmp3 = atom1_tmp2[1].split("\"",1)
             atom2 = atom2_tmp3[0] + fname
             
             #Second, find the name of the bond
             
             bname_tmp = data.split("id=\"",1)
             bname_tmp2 = bname_tmp[1].split("\"",1)
             bname = bname_tmp2[0]
             
             #Third, find the bond order
             
             order_tmp = data.split("order=\"",1)
             order_tmp2 = order_tmp[1].split("\"/",1)
             order = order_tmp2[0]
             
             print("bonds at " + atom1 + " " + atom2 + " name " + bname + " order " + order)
             addBond(atom1, atom2, bname, int(order))
             
         if "atom elementType" in data:
             atom = data[19]
             id_tmp = data.split("id=\"", 1)
             id_tmp2 = id_tmp[1].split("\"",1)
             id = id_tmp2[0]
             count = 0
             	                    
             if "hydrogenCount" in data:
                 count_tmp = data.split("hydrogenCount=\"", 1)
                 count = int(count_tmp[1][0])
                 print(f"count={count}")
            
             x_tmp = data.split("x2=\"",1)
             x_tmp2 = x_tmp[1].split("\"", 1)
             x_pos = x_tmp2[0]
             x_pos = (float(x_pos) * 0.5) - 5

             y_tmp = data.split("y2=\"",1)
             y_tmp2 = y_tmp[1].split("\"", 1)
             y_pos = y_tmp2[0]
             y_pos = float(y_pos) * 0.5
             addAtom(x_pos, y_pos,atom,id+fname, count)
             print(x_pos, " ,", y_pos)
             
         data = f.readline()
    f.close()
    # would normally load the data here
    print(data)

    return {'FINISHED'}

class ImportCML(Operator, ImportHelper):
    """This appears in the tooltip of the operator and in the generated docs"""
    bl_idname = "import_cml.compound_data"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Import CML File"

    # ImportHelper mixin class uses this
    filename_ext = ".cml"

    filter_glob: StringProperty(
        default="*.cml",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    # List of operator properties, the attributes will be assigned
    # to the class instance from the operator settings before calling.
    use_setting: BoolProperty(
        name="Example Boolean",
        description="Example Tooltip",
        default=True,
    )

    type: EnumProperty(
        name="Example Enum",
        description="Choose between two items",
        items=(
            ('OPT_A', "First Option", "Description one"),
            ('OPT_B', "Second Option", "Description two"),
        ),
        default='OPT_A',
    )

    def execute(self, context):
         return read_cml_file(context, self.filepath, self.use_setting)


# Only needed if you want to add into a dynamic menu
def menu_func_import(self, context):
    
    self.layout.operator(ImportCML.bl_idname, text="Text Import Operator")

# Register and add to the "file selector" menu (required to use F3 search "Text Import Operator" for quick access)
def register():
        
    bpy.types.Scene.lone_pair = bpy.props.BoolProperty(
        name="Show Lone Pairs",
        description="Toggle lone pairs",
        default=False,
        update=showLonePairs
    )
    bpy.types.Scene.lone_pair_selected = bpy.props.BoolProperty(
        name="Show Selected Lone Pairs",
        description="Toggle lone pairs on selected atoms",
        default=False,
        update=showSelectedLonePairs
    )
    
    bpy.utils.register_class(CreatorPanel)
    bpy.utils.register_class(ImportCML)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.utils.unregister_class(CreatorPanel)
    bpy.utils.unregister_class(ImportCML)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    
    del bpy.types.Scene.lone_pair
    del bpy.types.Scene.lone_pair_selected


if __name__ == "__main__":
    register()

