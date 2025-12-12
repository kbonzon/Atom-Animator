bl_info = {
    "name": "Compound Creator",
    "author": "Tim Bonzon",
    "version": (1.4, 1.4),
    "blender": (3, 50, 0),
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
from pathlib import Path
from bpy.props import IntProperty, PointerProperty
# ImportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ImportHelper
from bpy.types import GPencilFrame
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator

class BondOrder (bpy.types.PropertyGroup):
    order : IntProperty(
        name = "Bond Order",
        description="Bond order for newly created bonds. (1-3)",
        default=1, min = 1, soft_max=3
    )

class LineThickness (bpy.types.PropertyGroup):
    line_thickness : IntProperty(
        name = "Line Thickness",
        description="Thickness of bonds",
        default=50
    )

class MakeBond(bpy.types.Operator):
    bl_idname = "object.generate_bond"
    bl_label = "Generate Bond"
    bl_options = {'REGISTER', 'UNDO'}

    def execute (self, context):
        
        selected_objects = context.selected_objects

        if len(selected_objects) != 2:
            self.report({'ERROR'}, "Select two atoms")
            return {'CANCELLED'}

        atom1 = selected_objects[0].name
        atom2 = selected_objects[1].name

        bond_name = atom1 + "_" + atom2 +"_new"

        order = context.scene.bond_order.order

        addBond(atom1, atom2, bond_name, order)

        return {'FINISHED'}

class CreateArrow(bpy.types.Operator):
    bl_idname = "object.generate_arrow"
    bl_label = "Generate Arrow"
    bl_options = {'REGISTER', 'UNDO'}

    def bezier_point(self, p0, p1, p2, t):
        return (1-t)**2 * p0 + 2 * (1-t)*t*p1 + t**2 * p2

    def execute (self, context):
        thickness = context.scene.line_thickness_data.line_thickness
        arrow_collection = context.scene.collection
                    
        selected_objects = list(context.selected_objects)
        active = context.view_layer.objects.active

        if len (selected_objects) != 2:
            self.report({'ERROR'}, "Please select exactly 2 objects.")
            return {'CANCELLED'}
        
        if active in selected_objects:
            selected_objects.remove(active)
            selected_objects.append(active)

        obj1, obj2 = selected_objects
        
        p0 = obj1.location
        p2 = obj2.location

        start_offset = 13
        end_offset = 13

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
        #mat.grease_pencil = True
        gp_data.materials.append(mat)
        arrow_collection.objects.link(gp_object)
        
        layer = gp_data.layers.new(name="ArrowLayer", set_active=True)
        frame = layer.frames.new(context.scene.frame_current)
        stroke = frame.strokes.new()
        stroke.display_mode = '3DSPACE'
        stroke.line_width = thickness
        num_points = 64
        
        pts = [self.bezier_point(p0, p1, p2, i /(num_points - 2)) for i in range(num_points)]

        start_i = min(start_offset, num_points - 2)
        end_i = max(num_points - 1 - end_offset, start_i + 1)

        trimmed = pts[start_i:end_i+1]

        stroke.points.add(count=len(trimmed))

        for j, co in enumerate(trimmed):
            stroke.points[j].co = co
        
        # for i in range(num_points):
        #     t = i / (num_points - 1)
        #     stroke.points[i].co = self.bezier_point(p0, p1, p2, t)
            
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
 
#This operator has a lot of duplicated code
#partly because I have no other ideas on
#how to handling lonepairs for double bonds
#and for atoms other than O and N
class ToggleLonePairs(bpy.types.Operator):
    bl_idname = "object.toggle_lonepairs"
    bl_label = "Toggle Lonepairs"
    bl_options = {'REGISTER', 'UNDO'}

    should_render = False

    # def getNumHydrogens(self, atom, context):
    #     hydrogens = 0
    #     for child in atom.children:
    #         if "_H" in child.name and "_Halo" not in child.name:
    #             hydrogens = 1
    #         if "_sub" in child.name:
    #             hydrogens = int(child.data.body)

    #     return hydrogens

    def getBondNumber(self, atom, context):
        num_bonds = 0
        order = 0
        for obj in bpy.data.collections['bonds'].objects:
            if atom in obj.name and len(obj.children) > 0:
                #Accounting for bond order
                tmp = obj.name.split("_")

                order = int(tmp[2][1])

                num_bonds = num_bonds + order

                print(obj.name)
               
        #Accounting for hydrogens
        hydrogens = 0
        for child in bpy.context.scene.objects[atom].children:
            if "_H" in child.name and "_Halo" not in child.name:
                hydrogens = 1
            if "_sub" in child.name:
                hydrogens = int(child.data.body)

        num_bonds = num_bonds + hydrogens
        print(f"atom {atom} has {num_bonds} with order {order} and hydrogens {hydrogens}")
        return num_bonds

    def getBondedAtoms(self, atom):
        bonded_atoms = []
        for obj in bpy.data.collections['bonds'].objects:
            if atom in obj.name:
                #To grab the bonded atoms
                #First, split the names
                tmp = [p for p in obj.name.split("_") if p != atom] 
                bonded_atoms.append(tmp)

        #cleaned_up = list(set(bonded_atoms))
        return bonded_atoms

    def toggleVisibility(self, child, should_render):
        should_render = child.hide_viewport
        
        should_render = not should_render

        child.hide_viewport = should_render
        child.hide_render = should_render
        child.hide_select = should_render

        if child.children:
            for grand_child in child.children:
                grand_child.hide_viewport = should_render
                grand_child.hide_render = should_render
                grand_child.hide_select = should_render

    def handleLonePairs(self, obj, atom_collection, context, atoms_with_lone_pairs, thickness=40):
        obj_lps = atoms_with_lone_pairs
        num_bonds = 0
        num_bonds = self.getBondNumber(obj.name, context)
        num_lone_pairs = 0
        print(f"bonds {num_bonds} and lonepairs {obj_lps} for {obj.name}")
        # atom_object = bpy.data.objects[atom]

        if obj.users_collection:
            atom_collection = obj.users_collection[0]

        atom_type = atom_collection.name

        if num_bonds == 0:
            num_lone_pairs = 4
        if num_bonds == 1:
            num_lone_pairs = 3
        if num_bonds == 2:
            if atom_type == 'C':
                num_lone_pairs = 1
            if atom_type == 'O':
                num_lone_pairs = 2
        if num_bonds == 3:
            num_lone_pairs = 1
        if num_bonds == 4:
            num_lone_pairs = 0

        atom = obj.name
        bonded_atoms = self.getBondedAtoms(atom)
        bonded_atoms_objects = []

        #This is a really janky way to do this I know
        #I need to refactor this eventually

        try:
            for bonded_atom in bonded_atoms:
                for atom1 in bonded_atom:
                    for obj1 in bpy.context.scene.objects:
                        if atom1 == obj1.name:
                            bonded_atoms_objects.append(obj1)
            
            lone_pair_objects = []

            const_target=bonded_atoms_objects[0]
        except IndexError:
            self.report({"INFO"}, "No bonded heavy atoms detected. Bonded atoms are likely hydrogens")
        #Looks like I need to handle lone pairs
        #separately based on the bonding
        
        #Basically, I'm only going to handle lone
        #pairs for oxygen and nitrogen. 
        if atom_type != 'C':

            #This is an incredibly verbose way to do
            #this but I have very specific things that
            #need to be drawn for each scenario
            if num_lone_pairs == 3:
                    
                    #Create the lone pair object
                    lone_pairs_data = bpy.data.grease_pencils.new("lonepairGP_"+atom)
                    gpencil_layer = lone_pairs_data.layers.new(name="LP", set_active=True)
                    frame = gpencil_layer.frames.new(context.scene.frame_current)
                    lone_pairs = bpy.data.objects.new("lonepair_"+atom, lone_pairs_data)
                    lone_pairs.parent = obj
                    mat = addBlackMaterial()
                    lone_pairs_data.materials.append(mat)
                    atom_collection.objects.link(lone_pairs)

                    #draw the lone pairs
                    #Top Pair
                    stroke = frame.strokes.new()
                    stroke.display_mode = '3DSPACE'
                    stroke.line_width = thickness 
                    stroke.points.add(count=1)
                    stroke.points[0].co = Vector((-0.07,0,0.25))
                    stroke = frame.strokes.new()
                    stroke.display_mode = '3DSPACE'
                    stroke.line_width = thickness 
                    stroke.points.add(count=1)
                    stroke.points[0].co = Vector((0.07,0,0.25))

                    #Left Pair
                    stroke = frame.strokes.new()
                    stroke.display_mode = '3DSPACE'
                    stroke.line_width = thickness 
                    stroke.points.add(count=1)
                    stroke.points[0].co = Vector((0.25,0,0.07))
                    stroke = frame.strokes.new()
                    stroke.display_mode = '3DSPACE'
                    stroke.line_width = thickness 
                    stroke.points.add(count=1)
                    stroke.points[0].co = Vector((0.25,0,-0.07))

                    #Right Pair
                    stroke = frame.strokes.new()
                    stroke.display_mode = '3DSPACE'
                    stroke.line_width = thickness 
                    stroke.points.add(count=1)
                    stroke.points[0].co = Vector((-0.25,0,0.07))
                    stroke = frame.strokes.new()
                    stroke.display_mode = '3DSPACE'
                    stroke.line_width = thickness 
                    stroke.points.add(count=1)
                    stroke.points[0].co = Vector((-0.25,0,-0.07))

                    constraint = lone_pairs.constraints.new(type="TRACK_TO")
                    constraint.target = const_target

                    #Creating the charge symbol
                    charge_data = bpy.data.grease_pencils.new("chargeGP_"+atom)
                    charge_layer = charge_data.layers.new(name="lonepair_charge", set_active=True)
                    charge_frame = charge_layer.frames.new(context.scene.frame_current)
                    charge = bpy.data.objects.new("lonepair_charge_"+atom, charge_data)
                    charge.parent = obj
                    charge.data.materials.append(mat)
                    atom_collection.objects.link(charge)
                    charge_stroke = charge_frame.strokes.new()
                    charge_stroke.display_mode = '3DSPACE'
                    charge_stroke.line_width = thickness 
                    charge_stroke.points.add(count=2)
                    charge_stroke.points[0].co = Vector((0.25,0.12,0))
                    charge_stroke.points[1].co = Vector((0.35,0.12,0))

                    charge_constraint = charge.constraints.new(type="TRACK_TO")
                    charge_constraint.target = const_target
                    charge_constraint.track_axis = "TRACK_Y"
                    charge_constraint.up_axis = "UP_Y"
            elif num_lone_pairs == 2:
                #Handling bond orders
                if len(bonded_atoms_objects) > 1:
                    for i in range (0, num_lone_pairs):
                        lone_pairs_data = bpy.data.grease_pencils.new("lonepairGP_"+str(i)+"_"+atom)
                        gpencil_layer = lone_pairs_data.layers.new(name="LP", set_active=True)
                        frame = gpencil_layer.frames.new(context.scene.frame_current)
                        lone_pairs = bpy.data.objects.new("lonepair_"+str(i)+"_"+atom, lone_pairs_data)
                        lone_pairs.parent = obj
                        mat = addBlackMaterial()
                        lone_pairs_data.materials.append(mat)
                        atom_collection.objects.link(lone_pairs)

                        stroke = frame.strokes.new()
                        stroke.display_mode = '3DSPACE'
                        stroke.line_width = thickness 
                        stroke.points.add(count=1)

                        #For some reason, only the Z
                        #works with the constraint as up
                        stroke.points[0].co = Vector((-0.07,0,0.25))

                        stroke = frame.strokes.new()
                        stroke.display_mode = '3DSPACE'
                        stroke.line_width = thickness 
                        stroke.points.add(count=1)
                        stroke.points[0].co = Vector((0.07,0,0.25))

                        lone_pair_objects.append(lone_pairs)

                        const_target=bonded_atoms_objects[i]
                        constraint = lone_pairs.constraints.new(type="TRACK_TO")
                        constraint.target = const_target
                else:
                        lone_pairs_data = bpy.data.grease_pencils.new("lonepairGP_"+atom)
                        gpencil_layer = lone_pairs_data.layers.new(name="LP", set_active=True)
                        frame = gpencil_layer.frames.new(context.scene.frame_current)
                        lone_pairs = bpy.data.objects.new("lonepair_"+atom, lone_pairs_data)
                        lone_pairs.parent = obj
                        mat = addBlackMaterial()
                        lone_pairs_data.materials.append(mat)
                        atom_collection.objects.link(lone_pairs)

                        stroke = frame.strokes.new()
                        stroke.display_mode = '3DSPACE'
                        stroke.line_width = thickness 
                        stroke.points.add(count=1)
                        stroke.points[0].co = Vector((-0.2,0,0.15))
                        stroke = frame.strokes.new()
                        stroke.line_width = thickness 
                        stroke.points.add(count=1)
                        stroke.points[0].co = Vector((-0.25,0,0))
                        stroke = frame.strokes.new()
                        stroke.display_mode = '3DSPACE'
                        stroke.line_width = thickness 
                        stroke.points.add(count=1)
                        stroke.points[0].co = Vector((0.2,0,0.15))
                        stroke = frame.strokes.new()
                        stroke.line_width = thickness 
                        stroke.points.add(count=1)
                        stroke.points[0].co = Vector((0.25,0,0))

                        #Incase the bonded atoms are hydrogens    
                        try:
                            const_target=bonded_atoms_objects[0]
                            constraint = lone_pairs.constraints.new(type="TRACK_TO")
                            constraint.target = const_target

                        except IndexError:
                            lone_pairs.rotation_mode = 'XYZ'

                            lone_pairs.rotation_euler = (math.radians(90), 0 ,math.radians(-90))

                        # constraint.track_axis = "TRACK_Y"
                        # constraint.up_axis = "UP_Y"
            elif num_lone_pairs == 1:
                lone_pairs_data = bpy.data.grease_pencils.new("lonepairGP_"+atom)
                gpencil_layer = lone_pairs_data.layers.new(name="LP", set_active=True)
                frame = gpencil_layer.frames.new(context.scene.frame_current)
                lone_pairs = bpy.data.objects.new("lonepair_"+atom, lone_pairs_data)
                lone_pairs.parent = obj
                mat = addBlackMaterial()
                lone_pairs_data.materials.append(mat)
                atom_collection.objects.link(lone_pairs)

                stroke = frame.strokes.new()
                stroke.display_mode = '3DSPACE'
                stroke.line_width = thickness 
                stroke.points.add(count=1)

                #For some reason, only the Z
                #works with the constraint as up
                stroke.points[0].co = Vector((-0.07,0,0.25))

                stroke = frame.strokes.new()
                stroke.display_mode = '3DSPACE'
                stroke.line_width = thickness 
                stroke.points.add(count=1)
                stroke.points[0].co = Vector((0.07,0,0.25))

                constraint = lone_pairs.constraints.new(type="TRACK_TO")
                constraint.target = const_target

                print(f"Bonded atoms {bonded_atoms_objects}")

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
            

    def execute (self, context):
        selected_objects = context.selected_objects
        line_thickness = context.scene.line_thickness_data.line_thickness

        if len(selected_objects) == 0:
            self.report({'ERROR'}, 'Please select at least one atom.')
            return {'CANCELLED'}

        #self.showSelectedLonePairs(selected_objects, True, context)

        should_render = self.should_render

        for obj in selected_objects:
            obj_lps = 0
            for child in obj.children: 
                if child.name.startswith("lonepair_"):
                    obj_lps = obj_lps + 1

                    self.toggleVisibility(child, should_render)       

                print(f"Should render is {should_render}")
                
            #If lone pairs have not been generated
            if obj_lps == 0:
                self.handleLonePairs(obj, context.scene.collection, context, obj_lps, thickness=line_thickness)


                


        return {'FINISHED'}

class MakeAtom (bpy.types.Operator):
    bl_idname = "object.create_atom"
    bl_label = "Insert Atom"

    def execute(self, context):
        cursor = bpy.context.scene.cursor.location

        atom_choice = context.scene.atom_choice

        match atom_choice:
            case 'C':
                addAtom(x=cursor.x, y=cursor.y, atom='C', id=f"C_{random.randint(0,30)}", hydrogens=4)
            case 'O':
                addAtom(x=cursor.x, y=cursor.y, atom='O', id=f"O_{random.randint(0,30)}", hydrogens=2)
            case 'N':
                addAtom(x=cursor.x, y=cursor.y, atom='N', id=f"N_{random.randint(0,30)}", hydrogens=0)
            case 'H':
                addAtom(x=cursor.x, y=cursor.y, atom='H', id=f"H_{random.randint(0,30)}", hydrogens=0)
            case 'S':
                addAtom(x=cursor.x, y=cursor.y, atom='S', id=f"S_{random.randint(0,30)}", hydrogens=0)
        return {'FINISHED'}

class CreatorPanel(bpy.types.Panel):
    bl_label = "Atom Animator"
    bl_idname = "VIEW3D_PT_CompoundPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    #bl_context = 'scene'
    bl_category = 'Atom Animator'
    
    def draw (self, context):
        layout = self.layout
        
        row = layout.row()
        props = context.scene.line_thickness_data
        layout.prop(props, 'line_thickness')
        row.label(text="Add Compound", icon='OUTLINER_OB_POINTCLOUD')
        row = layout.row()
        row.operator("import_cml.compound_data",icon='OUTLINER_DATA_POINTCLOUD')
        
        row = layout.row()
        layout.label(text="Generate arrow")
        layout.operator("object.generate_arrow", icon="ACTION")
        
        row = layout.row()
        layout.label(text="Bonding")
        props = context.scene.bond_order
        layout.prop(props, "order")
        layout.operator("object.generate_bond", icon="ACTION")

        row = layout.row()
        layout.label(text="Lone Pairs")
        layout.operator("object.toggle_lonepairs",icon="ACTION")

        row = layout.row()
        layout.label(text="Manual Atom Generation")
        layout.prop(context.scene, "atom_choice")
        row = layout.row()
        layout.operator("object.create_atom",icon="ACTION")
        
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

    #bpy.context.collection.objects.link(obj)

    return obj
    
def addAtom(x,y,atom,id, hydrogens=0):
    atom_collection = bpy.context.scene.collection
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
    if hydrogens > 0:
        
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
        if hydrogens > 1:
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
    #bpy.context.scene.collection.objects.link(t_o)
    
    
    #Setting the atom text    
    
    text = bpy.context.active_object
    
    #adding in the atom halo
    
    halo = makeHalo(id+str(x)+"_Halo",radius=0.25, segments=32, location=(0, 0, -0.05)) 

    #master_collection.objects.unlink(halo)
    
    #assigning a white material to halo
    
    halo.data.materials.append(addWhiteMaterial())
    
    #adding the object to the atom collection
    
    atom_collection.objects.link(t_o)
    atom_collection.objects.link(halo)
    halo.parent = t_o
    #master_collection.objects.unlink(t_o)

    
    #text.parent = handle
    
    print("Added atom " + id)

def draw_line(gp_frame, p0 : tuple, p1 : tuple):
    gp_stroke = gp_frame.strokes.new()
    gp_stroke.display_mode = '3DSPACE'
    
    gp_stroke.points.add(count=2)
    gp_stroke.points[0].co = p0
    gp_stroke.points[1].co = p1 
    return gp_stroke

def addBond(atom1, atom2, name, order, thickness=50):

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
    
    bondName = atom1+ "_" + atom2 + "_" + name[0] + str(order)
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
    gp_data.materials.append(addBlackMaterial())
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
            
    gpencil_layer.line_change = thickness
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
       
def read_cml_file(context, filepath):
    #grabbing line thickness
    line_thickness = bpy.context.scene.line_thickness_data.line_thickness

    print("reading file...") 
    file = Path(filepath)   
    fname = str(file.stem)
    with open (filepath, 'r', encoding='utf8') as f :
        #  fname_tmp = f.resolve()
        #  fname_tmp1 = fname_tmp.split("\\",-1)
         for data in f:
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
                bname = bname_tmp2[0]+"_"+fname
                
                #Third, find the bond order
                
                order_tmp = data.split("order=\"",1)
                order_tmp2 = order_tmp[1].split("\"/",1)
                order = order_tmp2[0]
                
                print("bonds at " + atom1 + " " + atom2 + " name " + bname + " order " + order)
                addBond(atom1, atom2, bname, int(order), thickness=line_thickness)
                
            if "atom elementType" in data:
                atom = data[19]
                id_tmp = data.split("id=\"", 1)
                id_tmp2 = id_tmp[1].split("\"",1)
                id = id_tmp2[0]
                count = 0
                                        
                if "hydrogenCount" in data:
                    count_tmp = data.split("hydrogenCount=\"", 1)
                    count = int(count_tmp[1][0])
                    print(f"count={count} for atom {atom} with id {id}")
                
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
    # would normally load the data here

    return {'FINISHED'}

class ImportCML(Operator, ImportHelper):
    """This appears in the tooltip of the operator and in the generated docs"""
    bl_idname = "import_cml.compound_data"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Import CML File"

    # ImportHelper mixin class uses this
    filename_ext = ".cml"
    # List of operator properties, the attributes will be assigned
    # to the class instance from the operator settings before calling.
    
    def execute(self, context):
         return read_cml_file(context, self.filepath)

# Only needed if you want to add into a dynamic menu
def menu_func_import(self, context):
    
    self.layout.operator(ImportCML.bl_idname, text="Text Import Operator")

# Register and add to the "file selector" menu (required to use F3 search "Text Import Operator" for quick access)
def register():

    bpy.types.Scene.atom_choice =  bpy.props.EnumProperty(
        name = "Atom",
        items = [
            ('C', 'Carbon', 'Insert Carbon Atom'),
            ('O', "Oxygen", 'Insert Oxygen'),
            ('N', 'Nitrogen', 'Insert Nitrogen'),
            ('H', 'Hydrogen', 'Insert Hydrogen'),
            ('S', 'Sulfur', 'Insert Sulfur'),
        ],
        default = 'C'
    )
    bpy.utils.register_class(MakeAtom)
    bpy.utils.register_class(CreateArrow) 
    bpy.utils.register_class(CreatorPanel)
    bpy.utils.register_class(ImportCML)
    bpy.utils.register_class(MakeBond)
    bpy.utils.register_class(BondOrder)
    bpy.utils.register_class(LineThickness)
    bpy.utils.register_class(ToggleLonePairs)
    bpy.types.Scene.bond_order = PointerProperty(type=BondOrder)
    bpy.types.Scene.line_thickness_data = PointerProperty(type=LineThickness)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.utils.unregister_class(MakeAtom)
    bpy.utils.unregister_class(CreateArrow) 
    bpy.utils.unregister_class(CreatorPanel)
    bpy.utils.unregister_class(ImportCML)
    bpy.utils.unregister_class(ToggleLonePairs)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    
    del bpy.types.Scene.lone_pair
    del bpy.types.Scene.lone_pair_selected
    del bpy.types.Scene.bond_order
    del bpy.types.Scene.atom_choice
    del bpy.types.Scene.line_thickness
    bpy.utils.unregister_class(MakeBond)
    bpy.utils.unregister_class(BondOrder)


if __name__ == "__main__":
    register()

