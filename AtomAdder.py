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
import random
import mathutils
from mathutils import Vector
# ImportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ImportHelper
from bpy.types import GPencilFrame
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator

class CreateArrow(bpy.types.Operator):
    bl_idname = "object.generate_arrow"
    bl_label = "Generate Arrow"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute (self, context):
        arrow_collection = context.scene.collection
        
#        if not arrow_collection:
#            arrow_collection = bpy.data.collections.new("arrows")
#            
#        if not arrow_collection.name not in context.scene.collection.children:
#            context.scene.collection.children.link((bpy.data.collections["arrows"]))
                
        selected_objects = context.selected_objects
        
        if len (selected_objects) != 2:
            self.report({'ERROR'}, "Please select exactly 2 objects.")
            return {'CANCELLED'}
        
        obj1, obj2 = selected_objects
        
        p0 = obj1.location
        p2 = obj2.location
        
        mid = (p0 + p2) / 2
        
        direction = (p2 - p0).normalized()
        up = Vector((0, 0, 1))
        up_head = Vector((0,1,0))
        if direction.cross(up).length < 1e-3:
            up = mathutils.Vector((1, 0, 0))
            
        right = direction.cross(up).normalized()
        p1 = mid + right * 0.5
        
        gpencil_name = "CurvedArrow_GPencil" + str(random.randint(1, 500))
        
        gp_data=bpy.data.grease_pencils.new(gpencil_name)
        gp_object = bpy.data.objects.new(gpencil_name, gp_data)
        mat = addBlackMaterial()
        mat.use_nodes = True
        fill_node = mat.node_tree.nodes.get("Fill")
        if fill_node:
            fill_node.inputs[0].default_value = (0, 0, 0, 1)
        #mat.grease_pencil = True
        gp_data.materials.append(mat)
        arrow_collection.objects.link(gp_object)
        
        layer = gp_data.layers.new(name="ArrowLayer", set_active=True)
        frame = layer.frames.new(context.scene.frame_current)
        
        stroke = frame.strokes.new()
        stroke.display_mode = '3DSPACE'
        stroke.line_width = 30
        num_points = 64
        stroke.points.add(count=num_points)
        
        def bezier_point(p0, p1, p2, t):
            return (1-t)**2 * p0 + 2 * (1-t)*t*p1 + t**2 * p2
        
        for i in range(num_points):
            t = i / (num_points - 1)
            stroke.points[i].co = bezier_point(p0, p1, p2, t)
            
        p_end = stroke.points[-1].co
        p_before = stroke.points[-2].co
        tangent = (p_end - p_before).normalized()
        
        angle_rad = math.radians(30)
        rot_axis = tangent.cross(up_head)
        if rot_axis < 1e-6:
            rot_axis = mathutils.Vector((1,0,0))
        rot_axis.normalize()
        
        rot_mat1 = mathutils.Matrix.Rotation(math.pi - angle_rad, 4, rot_axis)
        rot_mat2 = mathutils.Matrix.Rotation(math.pi + angle_rad, 4, rot_axis)
    
        dir1 = tangent.copy()
        dir2 = tangent.copy()
        dir1.rotate(rot_mat1)
        dir2.rotate(rot_mat2)
        
        head_len = 0.2
        num_lines = 100
        v0 = p_end
        v1 = p_end + dir1 * head_len
        v2 = p_end + dir2 * head_len

        for i in range(num_lines + 1):
            t = i / num_lines
            # Linearly interpolate between v1 and v2
            start = v1.lerp(v2, t)
            end = v0.lerp(start, 0)  # Bring it toward the tip (optional)

            hatch = frame.strokes.new()
            hatch.display_mode = '3DSPACE'
            hatch.line_width = 30
            hatch.material_index = 0
            hatch.points.add(count=2)
            hatch.points[0].co = start
            hatch.points[1].co = end
            
        #This is for if the head is not filled in. 
#        arrow_head_stroke = frame.strokes.new()
#        arrow_head_stroke.display_mode = '3DSPACE'
#        arrow_head_stroke.line_width = 20
#        #arrow_head_stroke.cyclic = True  # This closes the triangle

#        arrow_head_stroke.points.add(count=4)
#        arrow_head_stroke.points[0].co = p_end
#        arrow_head_stroke.points[1].co = p_end + dir1 * head_len
#        arrow_head_stroke.points[2].co = p_end + dir2 * head_len
#        arrow_head_stroke.points[3].co = p_end
        
        
        #Adding modifiers to draw them in and out
        draw_mod = gp_object.grease_pencil_modifiers.new(name="Arrow_DrawIn", type='GP_BUILD')
        draw_mod.mode = 'SEQUENTIAL'
        draw_mod.transition = 'GROW'
        draw_mod.show_viewport = False
        draw_mod.length = 10 

        # Add "Vanish" build modifier
        vanish_mod = gp_object.grease_pencil_modifiers.new(name="Arrow_Vanish", type='GP_BUILD')
        vanish_mod.mode = 'SEQUENTIAL'
        vanish_mod.transition = 'FADE'
        vanish_mod.start_delay = 10  # Delay after first build
        vanish_mod.length = 10  # Duration in frames
        
        self.report({"INFO"}, "Arrow created")
        return {"FINISHED"}
        

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
        
        row = layout.row()
        layout.label(text="Generate arrow")
        layout.operator("object.generate_arrow", icon="ACTION")
        

 
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
#    mat = bpy.data.materials.get("Black")
#    
#    if mat is None:
#        mat = bpy.data.materials.new(name="Black") 
#        
#    mat.diffuse_color = (0, 0, 0, 1)
#    mat.specular_intensity = 0  
#    mat.roughness = 1
#    
#    return mat

    mat = bpy.data.materials.get("Black")
        
    if mat is None:
        mat = bpy.data.materials.new(name="Black")
        mat.use_nodes = True
        
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        
        # Clear existing nodes
        nodes.clear()

        # Create nodes
        output_node = nodes.new(type="ShaderNodeOutputMaterial")
        output_node.location = (300, 0)

        emission_node = nodes.new(type="ShaderNodeEmission")
        emission_node.location = (0, 0)
        emission_node.inputs["Color"].default_value = (0, 0, 0, 1)  # Black RGBA
        emission_node.inputs["Strength"].default_value = 1.0  # Optional: set strength

        # Link nodes
        links.new(emission_node.outputs["Emission"], output_node.inputs["Surface"])

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
        
        #First, adding the actual letter
        h_text = bpy.data.curves.new(name=atom, type="FONT")
        h_text.size = 0.5
        h_text.align_x = "LEFT"
        h_text.align_y = "CENTER"
        h_text.offset_x = 0.175
        h_text.offset_y = -0.015
        h_text.body = "H"
        h_text.materials.append(addBlackMaterial())
        h_text_o = bpy.data.objects.new(id+"_H", h_text)
        h_text_o.location = [0, 0, 0]
        h_text_o.parent = t_o
        atom_collection.objects.link(h_text_o)
        
        #Now, handling subscripts
        h = bpy.data.curves.new(name=atom, type="FONT")
        h.body = str(hydrogens)
        h.materials.append(addBlackMaterial())
        h.size = 0.3
        h.offset_x = 0.52
        h.offset_y = -0.25
        t.offset_x = -0.215
        t.offset_y = -0.015
        t.align_x = "LEFT"
        h_o = bpy.data.objects.new(id+"_sub", h)
        h_o.parent = t_o
        h_o.location = [0, 0, 0]
        atom_collection.objects.link(h_o)

    t.body = atom
    bpy.context.scene.collection.objects.link(t_o)
    
    
    #Setting the atom text    
    
    text = bpy.context.active_object
    
    #adding in the atom halo
    
    makeHalo(id+str(x)+"_Halo",radius=0.25, segments=32, location=(0, 0, -0.05)) 
    halo = bpy.data.objects[id+str(x)+"_Halo"]
    atom_collection.objects.link(halo)
    master_collection.objects.unlink(halo)
    halo.parent = t_o
    
    #assigning a white material to halo
    
    halo.data.materials.append(addWhiteMaterial())
    
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

def getBondNumber(atom, id):
    num_bonds = 0
    for obj in bpy.data.objects:
        if id in obj.name:
            num_bonds = num_bonds + 1
    
    return num_bonds

def handleLonePairs(atom, id):
#    if findCollection (atom) == False:
#        bond_collection = bpy.data.collections.new(col_name)
#        bpy.context.scene.collection.children.link(bond_collection)
#    else:
#        bond_collection = bpy.data.collections[col_name]
#    
#    num_bonds = getBondNumber(atom)
#    num_lone_pairs = 0
#    
#    if num_bonds == 0:
#        num_lone_pairs = 4
#    if num_bonds == 1:
#        num_lone_pairs = 3
#    if num_bonds == 2:
#        num_lone_pairs = 2
#    if num_bonds == 3:
#        num_lone_pairs = 1
#    if num_bonds == 4:
#        num_lone_pairs = 0
#        
#    lone_pairs_data = bpy.data.grease_pencils.new("lonepairGP_"+id)
#    gpencil_layer = lone_pairs_data.layers.new(name, set_active=True)
#    frame = gpencil_layer.frames.new(0)
#        
#    lone_pairs = bpy.data.objects.new("lonepair_"+id, lone_pairs_data)
#    
#    if num_lone_pairs == 1:
        
        
    #OK so if there is only one bond, I need the lone pairs
    #to find the atom it's parented to and track to it.
    #I need three lone pairs opposite the bond
    
    #OK so for two bonds, I need it to find the atoms
    #opposite the lone pairs, add a gpencil object for each
    #and then do the track to thing again (up is Z and track
    #axis is -Y). Set the influence to 0.75 too. 
    
    #For three bonds, I think just pick a bond and do this
    
    #All of this also needs to handle bond order ok this is 
    #getting harder
    
    #AND atom types (N, C, S even, O)
        
    return
        

def addBond(atom1, atom2, name, order):
    
     #grabbing the master collection
    
    master_collection = bpy.context.scene.collection
    
    #finding bond collection
    
    col_name = "bonds"
    
    bond_collection = None
    
    if findCollection (col_name) == False:
        bond_collection = bpy.data.collections.new(col_name)
        bpy.context.scene.collection.children.link(bond_collection)
    else:
        bond_collection = bpy.data.collections[col_name]
    
    #Creating Armature and bond plane
    
    bondName = atom1+ "_" + atom2 + "_" + name[0]
    planeName = name + "_bondPlane"
    a_data = bpy.data.armatures.new(bondName+"_data")
    a_data.display_type = 'WIRE'
    armature = bpy.data.objects.new(bondName, a_data)
    bond_collection.objects.link(armature)
    bpy.context.view_layer.objects.active = armature
    bpy.context.view_layer.objects.active.select_set(True)
    
    bpy.context.view_layer.update()
    bpy.ops.object.editmode_toggle()
    edit_bones = armature.data.edit_bones
    bone = edit_bones.new('Bone')
    bone.head = Vector((0,0,0))
    bone.tail = Vector((0,1,0))
    
    dup_bone = edit_bones.new('Bone.001')
    dup_bone.head = bone.head + Vector((1,0,0))
    dup_bone.tail = bone.tail + Vector((1,0,0))
    
    bpy.ops.object.editmode_toggle()
    
    gp_data = bpy.data.grease_pencils.new(planeName + "_data")
    gp_object = bpy.data.objects.new(planeName, gp_data)
    bond_collection.objects.link(gp_object)
    
    gpencil_layer = gp_data.layers.new(name, set_active=True)
    gpencil_layer.location[2] = -0.1
    frame = gpencil_layer.frames.new(0)
    
    #Handling higher order bonds by drawing them off center
    if order <= 1: 
        draw_line(frame, (0,0,0),(1,0,0))
    else:
        if order == 2:
            draw_line(frame, (0,0,-0.1),(1,0,-0.1))
            draw_line(frame, (0,0,0.1),(1,0,0.1))
        if order ==3:
            draw_line(frame, (0,0,-0.15),(1,0,-0.15))
            draw_line(frame, (0,0,0),(1,0,0))
            draw_line(frame, (0,0,0.15),(1,0,0.15))
            
    gpencil_layer.line_change = 50 
    bondPlane = bpy.data.objects[planeName]
    bondArma = bpy.data.objects[bondName]
    
    #Assigning bond plane to armature
    #I know this uses operators but this is 
    #The cleanest way I've found since it doesn't require custom
    #Weights. It's actualy less code.
    
    bpy.ops.object.select_all(action='DESELECT')
    bondArma.select_set(True)
    bondPlane.select_set(True)
    bpy.ops.object.parent_set(type='ARMATURE_AUTO', keep_transform=True)
    
    #Adding the armature constraints to the atoms
    #Only two bones are needed so we grab them here
    
    bone1 = bpy.data.objects[bondName].pose.bones["Bone"]
    bone2 = bpy.data.objects[bondName].pose.bones["Bone.001"]
    
    #First, the constraint is applied to bone1
    copy_location1 = bone1.constraints.new(type="COPY_LOCATION")
    copy_location1.target = bpy.data.objects[atom1]
    #bpy.ops.pose.constraint_add(type='TRACK_TO')
    track_to1 =  bone1.constraints.new(type="TRACK_TO")
    track_to1.target = bpy.data.objects[atom2]
    track_to1.up_axis = "UP_X"
    track_to1.track_axis = "TRACK_NEGATIVE_Y"

    #The constraint is then applied to the second bone
  
    copy_location2 = bone2.constraints.new(type="COPY_LOCATION")
    copy_location2.target = bpy.data.objects[atom2]
    #bpy.ops.pose.constraint_add(type='TRACK_TO')
    track_to2 =  bone2.constraints.new(type="TRACK_TO")
    track_to2.target = bpy.data.objects[atom1]
    track_to2.up_axis = "UP_X"
    track_to2.track_axis = "TRACK_Y"
    
    
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
#   
    bpy.utils.register_class(CreateArrow) 
    bpy.utils.register_class(CreatorPanel)
    bpy.utils.register_class(ImportCML)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

#    for cls in classes:
#        bpy.utils.register_class(cls)


def unregister():
    bpy.utils.unregister_class(CreateArrow) 
    bpy.utils.unregister_class(CreatorPanel)
    bpy.utils.unregister_class(ImportCML)

    for cls in classes:
        bpy.utils.unregister_class(cls)

    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    
    del bpy.types.Scene.lone_pair
    del bpy.types.Scene.lone_pair_selected


if __name__ == "__main__":
    register()

