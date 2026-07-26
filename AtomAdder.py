bl_info = {
    "name": "Atom Animator",
    "author": "Tim Bonzon",
    "version": (1.4, 1.4),
    "blender": (3, 5, 0),
    "location": "View3d > Toolbar",
    "description": "Adds a chemical compound from CML file",
    "warning": "",
    "doc_url": "",
    "category": "Add Mesh",
}

#TODO: Add the ability to make charges [DONE]
#TODO: Make bond constraints its own slider [DONE]
#TODO: Add animatable visibility [DONE]
#TODO: Handle aromatic bond drawing [DONE]

import bpy
import math
import bmesh
import random
import mathutils
from mathutils import Vector
from pathlib import Path
import xml.etree.ElementTree as ET
from bpy.props import IntProperty, PointerProperty, FloatProperty
# ImportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator


#NOTE: Current bond naming scheme:  "[atom1]_[atom2]_[BondID][ORDER]"
class BondInfluenceProperty (bpy.types.PropertyGroup):
    influence : FloatProperty(name="Bond Influence",
                    description="Controls the bonding constraint between atoms",
                    default=1.0,
                    min=0,
                    max=1.0,
                    subtype="FACTOR")

class BondInfluence (bpy.types.Operator):
    bl_idname = "object.handle_bondinfluence"
    bl_label = "Set Influence"
    bl_options = {'REGISTER', 'UNDO'}

    def execute (self, context):
        influence = bpy.context.scene.bond_influence_property.influence

        frame = context.scene.frame_current

        #This is to get the selected objects in order

        selected_objects = list(context.selected_objects)
        active = context.view_layer.objects.active

        if len (selected_objects) != 2:
            self.report({'ERROR'}, "Please select exactly 2 atoms.")
            return {'CANCELLED'}
        
        if active in selected_objects:
            selected_objects.remove(active)
            selected_objects.append(active)

        atom2 = selected_objects[0].name
        atom1 = selected_objects[1].name

        print(f"Atom1: {atom1} Atom2 {atom2}")

        bond = None

        for obj in bpy.data.objects:
            if atom1 in obj.name and atom2 in obj.name and obj.type == "ARMATURE":
                bond = obj.name

        if bond == None:
            self.report({'ERROR'}, "No bond between atoms. Create a bond first.")
            return {'CANCELLED'}
        else:
            print(f"Bond between {atom1} and {atom2} is {bond}")
        
        #Finding the bones

        bone1 = bpy.data.objects[bond].pose.bones["Bone"]
        bone2 = bpy.data.objects[bond].pose.bones["Bone.001"]

        #Updating constraints
        found_bone = False
        for constraint in bone1.constraints:
            if found_bone == False:
                if atom1 in constraint.name:
                    found_bone = True
            
            #So the bond doesn't fly off to the world origin
            #Plot twist! We don't actually change the bond constraint, 
            #just the self constratint
            if "Self" in constraint.name and found_bone == True:
                constraint.influence = 1 - influence
                constraint.keyframe_insert(data_path="influence", frame=frame)

        #Maybe we're not using that bone. Checking bone2    
        if found_bone == False:
            for constraint in bone2.constraints:
                if atom1 in constraint.name:
                    found_bone = True

                if "Self" in constraint.name and found_bone == True:
                    constraint.influence = 1 - influence
                    constraint.keyframe_insert(data_path="influence", frame=frame)

        return {"FINISHED"}

class ChargeChoice(bpy.types.PropertyGroup):
    charge : StringProperty(name="Charge", 
                            description="Charge to add. Can be fractional, negative, or positive",
                            default="+1"
    )

class AddCharge (bpy.types.Operator):
    bl_idname = "object.add_charge"
    bl_label = "Add Charge"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        frame = context.scene.frame_current

        selected_objects = context.selected_objects

        if len(selected_objects) == 0:
            self.report({'ERROR'}, 'Select at least one atom')
            return {'CANCELLED'}
        
        charge = context.scene.charge_choice_data.charge

        tmp = "_charge_"+charge


        for object in selected_objects:
            doesnotexist = True

            #Disabling all other charges:
            for child in object.children:
                if tmp in child.name:
                    doesnotexist = False
                    break

                if "_charge_" in child.name and tmp not in child.name:
                    child.hide_render = True
                    child.hide_viewport = True
                    child.keyframe_insert(data_path="hide_render", frame=frame)
                    child.keyframe_insert(data_path="hide_viewport", frame=frame)

            if doesnotexist:
                #Create a text object
                t = bpy.data.curves.new(name=object.name+"_chargedata_"+charge, type="FONT")
                t.offset_x = 0.385
                t.offset_y = 0.185
                t.size = 0.5
                t.materials.append(addBlackMaterial())
                t.align_x = "CENTER"
                t.align_y = "CENTER"
                t.size = 0.25
                t.body = charge
                atom_collection = object.users_collection[0]

                #add to collection
                t_o = bpy.data.objects.new(object.name+"_charge_"+charge, t)
                #t_o.location = [object.location.x, object.location.y, 0]
                #keyframe it appearing
                prev = frame - 1
                # bpy.context.scene.frame_set(prev)
                t_o.hide_render = True
                t_o.hide_viewport = True
                t_o.keyframe_insert(data_path="hide_render", frame=prev)
                t_o.keyframe_insert(data_path="hide_viewport", frame=prev)
                t_o.parent = object
                t_o.hide_render = False
                t_o.hide_viewport = False
                t_o.keyframe_insert(data_path="hide_render", frame=frame)
                t_o.keyframe_insert(data_path="hide_viewport", frame=frame)
                atom_collection.objects.link(t_o)



        return {'FINISHED'}

class BondOrder (bpy.types.PropertyGroup):
    order : IntProperty(
        name = "Bond Order",
        description="Bond order for newly created bonds. (1-3)",
        default=1, min=1, max=3
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
    
def find_bond_between(atom1, atom2):
    """Find the armature whose constraints target both atom objects."""
    for candidate in bpy.data.objects:
        if candidate.type != 'ARMATURE' or candidate.pose is None:
            continue

        targets = {
            constraint.target
            for bone in candidate.pose.bones
            for constraint in bone.constraints
            if getattr(constraint, "target", None) is not None
        }
        if atom1 in targets and atom2 in targets:
            return candidate

    # Support older bonds that do not have the expected constraints.
    return next((
        candidate for candidate in bpy.data.objects
        if candidate.type == 'ARMATURE'
        and atom1.name in candidate.name
        and atom2.name in candidate.name
    ), None)


def find_bond_grease_pencil(bond):
    """Return the Grease Pencil plane parented beneath a bond armature."""
    return next((
        child for child in bond.children_recursive
        if child.type == 'GPENCIL' and "_bondPlane" in child.name_full
    ), None)


def get_bond_order(bond):
    """Read the bond order from the final character of its name."""
    try:
        return int(bond.name[-1])
    except ValueError:
        return None


def get_point_weights(grease_pencil, stroke, point_index):
    """Collect all vertex-group weights assigned to a Grease Pencil point."""
    weights = {}
    for vertex_group in grease_pencil.vertex_groups:
        try:
            weights[vertex_group.index] = stroke.points.weight_get(
                vertex_group_index=vertex_group.index,
                point_index=point_index,
            )
        except RuntimeError:
            pass
    return weights


def add_weighted_stroke(grease_pencil, gp_frame, source_stroke):
    """Duplicate a stroke's point properties and armature weights."""
    source_data = [
        (
            point.co.copy(),
            point.pressure,
            point.strength,
            get_point_weights(grease_pencil, source_stroke, point_index),
        )
        for point_index, point in enumerate(source_stroke.points)
    ]

    new_stroke = gp_frame.strokes.new()
    new_stroke.display_mode = source_stroke.display_mode
    new_stroke.line_width = source_stroke.line_width
    new_stroke.material_index = source_stroke.material_index
    new_stroke.use_cyclic = source_stroke.use_cyclic
    new_stroke.points.add(count=len(source_data))

    for point_offset, (new_point, point_data) in enumerate(zip(
        new_stroke.points, source_data
    )):
        co, pressure, strength, weights = point_data
        new_point.co = co
        new_point.pressure = pressure
        new_point.strength = strength

        for group_index, weight in weights.items():
            new_stroke.points.weight_set(
                vertex_group_index=group_index,
                point_index=point_offset,
                weight=weight,
            )

    return new_stroke


def set_stroke_count(grease_pencil, gp_frame, count):
    """Resize a bond drawing while preserving weights on added strokes."""
    while len(gp_frame.strokes) < count:
        add_weighted_stroke(grease_pencil, gp_frame, gp_frame.strokes[0])

    while len(gp_frame.strokes) > count:
        gp_frame.strokes.remove(gp_frame.strokes[-1])


def position_bond_strokes(gp_frame, order):
    """Place the bond lines symmetrically around the bond center."""
    offsets = {
        1: (0.0,),
        2: (-0.1, 0.1),
        3: (-0.15, 0.0, 0.15),
    }[order]

    for stroke, offset in zip(gp_frame.strokes, offsets):
        for point in stroke.points:
            point.co = Vector((
                point.co.x,
                point.co.y,
                offset,
            ))


def get_or_create_gp_frame(layer, frame_number):
    """Return the frame at frame_number, copying the held frame if needed."""
    current_frame = next((
        gp_frame for gp_frame in layer.frames
        if gp_frame.frame_number == frame_number
    ), None)
    if current_frame is not None:
        return current_frame

    previous_frames = [
        gp_frame for gp_frame in layer.frames
        if gp_frame.frame_number < frame_number
    ]
    if previous_frames:
        source_frame = max(previous_frames, key=lambda item: item.frame_number)
    elif layer.frames:
        source_frame = min(layer.frames, key=lambda item: item.frame_number)
    else:
        return None

    current_frame = layer.frames.copy(source_frame)
    current_frame.frame_number = frame_number
    return current_frame


def set_bond_drawing_order(bond, grease_pencil, frame_number, order):
    """Set one bond's drawing order, returning an error message on failure."""
    current_order = get_bond_order(bond)
    if current_order is None:
        return f"Could not read bond order from {bond.name}"

    active_layer = grease_pencil.data.layers.active
    if active_layer is None:
        return f"{grease_pencil.name} has no active layer"

    current_frame = get_or_create_gp_frame(active_layer, frame_number)
    if current_frame is None:
        return f"{grease_pencil.name} has no Grease Pencil frame to copy"

    if not current_frame.strokes:
        return f"{grease_pencil.name} has no stroke to copy"

    set_stroke_count(grease_pencil, current_frame, order)
    position_bond_strokes(current_frame, order)

    if current_order != order:
        bond.name = bond.name[:-1] + str(order)

    grease_pencil.data.update_tag()
    return None


class SetBond(bpy.types.Operator):
    bl_idname = "object.set_bond"
    bl_label = "Set Bond"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selected_objects = context.selected_objects
        if len(selected_objects) < 2:
            self.report({'ERROR'}, "Select at least two atoms")
            return {'CANCELLED'}

        order = context.scene.bond_order.order
        frame_number = context.scene.frame_current
        bonds_set = 0

        for i in range(0, len(selected_objects) - 1, 2):
            atom1 = selected_objects[i]
            atom2 = selected_objects[i + 1]
            bond = find_bond_between(atom1, atom2)

            if bond is None:
                self.report(
                    {'WARNING'},
                    f"No bond found between {atom1.name} and {atom2.name}"
                )
                continue

            grease_pencil = find_bond_grease_pencil(bond)
            if grease_pencil is None:
                self.report({'WARNING'}, f"No Grease Pencil found for {bond.name}")
                continue

            error = set_bond_drawing_order(
                bond, grease_pencil, frame_number, order
            )
            if error is not None:
                self.report({'WARNING'}, error)
                continue

            bonds_set += 1

        return {'FINISHED'} if bonds_set else {'CANCELLED'}


def flip_aromatic_drawing(bond, grease_pencil, frame_number):
    """Move an aromatic inner stroke to the opposite side on local Z."""
    if get_bond_order(bond) != 2:
        return f"{bond.name} is not a double aromatic bond"

    active_layer = grease_pencil.data.layers.active
    if active_layer is None:
        return f"{grease_pencil.name} has no active layer"

    current_frame = get_or_create_gp_frame(active_layer, frame_number)
    if current_frame is None:
        return f"{grease_pencil.name} has no Grease Pencil frame to copy"

    if len(current_frame.strokes) != 2:
        return f"{grease_pencil.name} does not have two aromatic strokes"

    inner_stroke = current_frame.strokes[1]
    for inner_point in inner_stroke.points:
        inner_point.co.z = -inner_point.co.z

    grease_pencil.data.update_tag()
    return None


class FlipAromatic(bpy.types.Operator):
    bl_idname = "object.flip_aromatic"
    bl_label = "Flip Aromatic"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selected_objects = context.selected_objects
        if len(selected_objects) < 2:
            self.report({'ERROR'}, "Select at least two atoms")
            return {'CANCELLED'}

        frame_number = context.scene.frame_current
        bonds_flipped = 0

        for i in range(0, len(selected_objects) - 1, 2):
            atom1 = selected_objects[i]
            atom2 = selected_objects[i + 1]
            bond = find_bond_between(atom1, atom2)

            if bond is None:
                self.report(
                    {'WARNING'},
                    f"No bond found between {atom1.name} and {atom2.name}"
                )
                continue

            grease_pencil = find_bond_grease_pencil(bond)
            if grease_pencil is None:
                self.report({'WARNING'}, f"No Grease Pencil found for {bond.name}")
                continue

            error = flip_aromatic_drawing(
                bond, grease_pencil, frame_number
            )
            if error is not None:
                self.report({'WARNING'}, error)
                continue

            bonds_flipped += 1

        return {'FINISHED'} if bonds_flipped else {'CANCELLED'}


class ToggleVisibility(bpy.types.Operator):
    bl_idname = "object.disable_atom"
    bl_label = "Toggle Visibility"
    
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        frame = context.scene.frame_current
        current_val = context.selected_objects[0].hide_render
        new_val = not current_val

        for obj in context.selected_objects:

            obj.hide_render = new_val
            if obj.hide_render:
                obj.display_type = 'WIRE'
            else:
                obj.display_type = 'SOLID'
            for child in obj.children:
                child.hide_render = new_val
                child.keyframe_insert(data_path="hide_render",
                                      frame=frame)
                
                if child.hide_render:
                    child.display_type = 'WIRE'
                else:
                    child.display_type = 'SOLID'
                
            obj.keyframe_insert(data_path="hide_render", frame=frame)

        return {"FINISHED"}

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
            else:
                num_lone_pairs = 1
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

class AtomChoice (bpy.types.PropertyGroup):
    atom_choice =  bpy.props.EnumProperty(
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
        layout.label(text="Reactivity")
        layout.operator("object.generate_arrow", icon="TRACKING_REFINE_FORWARDS")
        
        row = layout.row()
        layout.label(text="Bonding")
        props = context.scene.bond_order
        layout.prop(props, "order")
        layout.operator("object.generate_bond", icon="ACTION")
        layout.operator("object.set_bond", icon="GREASEPENCIL")
        layout.operator("object.flip_aromatic", icon="ARROW_LEFTRIGHT")
        row=layout.row()
        props = context.scene.bond_influence_property
        layout.prop(props, "influence")
        layout.operator("object.handle_bondinfluence", icon="AUTOMERGE_ON")

        row = layout.row()
        layout.label(text="Lone Pairs and Charges")
        layout.operator("object.toggle_lonepairs",icon="ACTION")
        row = layout.row()
        props = context.scene.charge_choice_data
        layout.prop(props, "charge")
        layout.operator("object.add_charge",icon="FORCE_CHARGE")

        row = layout.row()
        layout.label(text="Manual Atom Generation")
        layout.prop(context.scene, "atom_choice")
        row = layout.row()
        layout.operator("object.create_atom",icon="ACTION")

        row = layout.row()
        layout.label(text="Animation Settings")
        layout.operator("object.disable_atom",icon="HIDE_OFF")
        
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

def addBond(
    atom1,
    atom2,
    name,
    order,
    thickness=50,
    aromatic=False,
    aromatic_inner_offsets=((0, -0.2, -0.15), (0, 0.2, -0.15)),
):
    is_debug = atom1 == "a31reactants_2"
    if is_debug:
        print(f"Adding bond for {atom1} and {atom2}")
    if aromatic:
        print(f"Drawing aromatic bond {name}: {atom1} to {atom2} (order {order})")

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
    if is_debug:
        print(f"Adding bond for {atom1} and {atom2} made bond object")
    
    gpencil_layer = gp_data.layers.new(name, set_active=True)
    gpencil_layer.location[2] = -0.1
    frame = gpencil_layer.frames.new(bpy.context.scene.frame_current)
    if is_debug:
        print(f"Adding bond for {atom1} and {atom2} made new frame")
    if order <= 1:
        draw_line(frame, (0, 0, 0), (1, 0, 0))
    else:
        # Separate higher-order bonds along the drawing plane's Z axis.
        if order == 2:
            if aromatic:
                draw_line(frame, (0, 0, 0), (1, 0, 0))
            else:
                draw_line(frame, (0, 0, -0.1), (1, 0, -0.1))
                draw_line(frame, (0, 0, 0.1), (1, 0, 0.1))
        else:
            draw_line(frame, (0, 0, -0.15), (1, 0, -0.15))
            draw_line(frame, (0, 0, 0), (1, 0, 0))
            draw_line(frame, (0, 0, 0.15), (1, 0, 0.15))
    
    if is_debug:
        print(f"Adding bond for {atom1} and {atom2} drew line")
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

    if aromatic and order == 2:
        # Duplicate the auto-weighted outer stroke so both aromatic lines deform
        # identically, then offset each duplicate point independently.
        inner_stroke = add_weighted_stroke(gp_object, frame, frame.strokes[0])
        if len(aromatic_inner_offsets) != len(inner_stroke.points):
            raise ValueError(
                "aromatic_inner_offsets must contain one Vector3 per stroke point"
            )
        for point, offset in zip(inner_stroke.points, aromatic_inner_offsets):
            point.co += Vector(offset)
    
    if is_debug:
        print(f"Adding bond for {atom1} and {atom2} parented bond plane")
    #Adding the armature constraints to the atoms
    #Only two bones are needed so we grab them here
    
    bone1 = bpy.data.objects[bondName].pose.bones["Bone"]
    bone2 = bpy.data.objects[bondName].pose.bones["Bone.001"]
    
    #First, the constraint is applied to bone1
    copy_location1 = bone1.constraints.new(type="COPY_LOCATION")
    copy_location1.name = "Bond to " + atom1
    copy_location1.target = bpy.data.objects[atom1]
    
    #Adding another zero-influence constraint for animating bonding
    exists = False
    for constraint in bone1.constraints:
        if "Self" in constraint.name:
            exists = True
        
    if exists == False:
        self_location1 = bone1.constraints.new(type="COPY_LOCATION")
        self_location1.name = "Self"
        self_location1.target = bpy.data.objects[atom2]
        self_location1.influence = 0

    #bpy.ops.pose.constraint_add(type='TRACK_TO')
    track_to1 =  bone1.constraints.new(type="TRACK_TO")
    track_to1.target = bpy.data.objects[atom2]
    track_to1.up_axis = "UP_X"
    track_to1.track_axis = "TRACK_NEGATIVE_Y"

    #The constraint is then applied to the second bone
  
    copy_location2 = bone2.constraints.new(type="COPY_LOCATION")
    copy_location2.name = "Bond to " + atom2
    copy_location2.target = bpy.data.objects[atom2]

    #Adding another zero-influence constraint for animating bonding
    exists = False
    for constraint in bone2.constraints:
        if "Self" in constraint.name:
            exists = True
        
    if exists == False:
        self_location2 = bone2.constraints.new(type="COPY_LOCATION")
        self_location2.name = "Self"
        self_location2.target = bpy.data.objects[atom1]
        self_location2.influence = 0
    #bpy.ops.pose.constraint_add(type='TRACK_TO')
    track_to2 =  bone2.constraints.new(type="TRACK_TO")
    track_to2.target = bpy.data.objects[atom1]
    track_to2.up_axis = "UP_X"
    track_to2.track_axis = "TRACK_Y"
    print(f"Added bond {atom1} to {atom2}")

def get_bond(line):
    #First, find the atoms involved in the bond
    atom1_tmp = line.split("atomRefs2=\"", 1)
    atom1_tmp2 = atom1_tmp[1].split()
    atom1 = atom1_tmp2[0]
    
    atom2_tmp = line.split("\" i", 1)
    atom2_tmp2 = atom2_tmp[0].split()
    atom2_tmp3 = atom1_tmp2[1].split("\"",1)
    atom2 = atom2_tmp3[0]
    
    #Second, find the name of the bond
    
    bname_tmp = line.split("id=\"",1)
    bname_tmp2 = bname_tmp[1].split("\"",1)
    bname = bname_tmp2[0]
    
    #Third, find the bond order
    
    order_tmp = line.split("order=\"",1)
    order_tmp2 = order_tmp[1].split("\"/",1)
    order = order_tmp2[0]

    return (atom1, atom2, order)

#Have it read the lines in a CML file and determine
#What atoms are aromatic. Aromatic atoms are cycles. 
#I believe an undirected graph needs to be built.
#Have it return a list of bonds that are aromatic.
def get_aromaticatoms(cml_file):
    bond_atoms = [get_bond(line) for line in cml_file]
    if len(bond_atoms) < 3:
        return []

    graph = {}
    for edge_id, (atom1, atom2, _) in enumerate(bond_atoms):
        graph.setdefault(atom1, []).append((atom2, edge_id))
        graph.setdefault(atom2, []).append((atom1, edge_id))

    discovery = {}
    low = {}
    bridges = set()
    time = 0

    def find_bridges(atom, parent_edge=-1):
        nonlocal time
        discovery[atom] = low[atom] = time
        time += 1

        for neighbor, edge_id in graph[atom]:
            if edge_id == parent_edge:
                continue
            if neighbor not in discovery:
                find_bridges(neighbor, edge_id)
                low[atom] = min(low[atom], low[neighbor])
                if low[neighbor] > discovery[atom]:
                    bridges.add(edge_id)
            else:
                low[atom] = min(low[atom], discovery[neighbor])

    for atom in graph:
        if atom not in discovery:
            find_bridges(atom)

    return [bond for edge_id, bond in enumerate(bond_atoms)
            if edge_id not in bridges]



    #get atom 3
    #check if atom 3 bond to atom 1
    #if yes, return atoms 1-3
    #if no, continue
    #if no atoms, return empty

def read_cml_file(context, filepath):
    #grabbing line thickness
    line_thickness = bpy.context.scene.line_thickness_data.line_thickness

    print("reading file...") 
    file = Path(filepath)   
    fname = str(file.stem)
    lines = []
    isChemSketch = False
    with open (filepath, 'r', encoding='utf8') as f :
        lines = f.readlines()
        for line in lines:
            if "convention=\"ACD/ChemSketch\"" in line:
                print("ChemSketch detected")
                isChemSketch = True
                break
    
    #ChemSketch CMLs have to be handled differently
    if isChemSketch:
        lines.clear()
        root = ET.parse(filepath)

        atoms = root.findall("atomArray/atom")
        bonds = root.findall("bondArray/bond")

        for atom in atoms:
            id = atom.attrib["id"]

            x_pos = float(atom.find("float[@builtin='x2']").text)
            y_pos = float(atom.find("float[@builtin='y2']").text)

            element = atom.find("string[@builtin='elementType']").text

            addAtom(x_pos, y_pos,element,id+fname, 0)

        for bond in bonds:
            id = bond.attrib["id"]

            atoms_ = bond.findall('string')
            atom_1 = atoms_[1].text + fname
            atom_2 = atoms_[0].text + fname

            order = int(atoms_[2].text)

            if order > 3:
                order = 1

            addBond(atom_1, atom_2, id, int(order), thickness=line_thickness)
    else:
        #Not the best way to handle XMLs, but convention-free
        #seems to be best handled as a simple text file
        bond_lines = []
        atom_lines = []
        for data in lines:
            if "bond atomRefs2=" in data:
                bond_lines.append(data)
            if "atom elementType" in data:
                atom_lines.append(data)
        
        for data in atom_lines:
            #Really not a good way to do this. 
            atom_tmp1 = data.split("elementType=\"")
            atom = atom_tmp1[1].split("\"")[0]
            id_tmp = data.split("id=\"", 1)
            id_tmp2 = id_tmp[1].split("\"",1)
            id = id_tmp2[0]
            
            if "hydrogenCount" in data:
                print("Hydrogens need to be handled")
            
            x_tmp = data.split("x2=\"",1)
            x_tmp2 = x_tmp[1].split("\" ", 1)
            x_pos = x_tmp2[0]
            x_pos = (float(x_pos) * 0.5) - 5

            y_tmp = data.split("y2=\"",1)
            y_tmp2 = y_tmp[1].split("\"", 1)
            y_pos = y_tmp2[0]
            y_pos = float(y_pos) * 0.5
            addAtom(x_pos, y_pos,atom,id+fname)
            print(x_pos, " ,", y_pos)

        # CML commonly represents aromatic rings as alternating bond orders.
        aromatic_bonds = {
            frozenset((atom1, atom2))
            for atom1, atom2, _ in get_aromaticatoms(bond_lines)
        }
        print(f"Detected {len(aromatic_bonds)} bonds in aromatic cycles")

        aromatic_bond_index = 0
        for data in bond_lines:
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
            aromatic = (order.upper() == "A" or
                        frozenset((atom1_tmp2[0], atom2_tmp3[0])) in aromatic_bonds)
            print(f"CML bond {bname}: raw order={order!r}, aromatic={aromatic}")
            if aromatic:
                # Alternate the visible bond order around aromatic systems.
                order = 2 if aromatic_bond_index % 2 == 0 else 1
                aromatic_bond_index += 1
            
            print(f"bonds at {atom1} {atom2} name {bname} order {order}")
            addBond(atom1, atom2, bname, int(order), aromatic=aromatic)



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

classes = (
    ChargeChoice,
    AddCharge,
    BondInfluence,
    AtomChoice,
    MakeAtom,
    CreateArrow,
    CreatorPanel,
    ImportCML,
    MakeBond,
    BondOrder,
    LineThickness,
    ToggleLonePairs,
    ToggleVisibility,
    BondInfluenceProperty,
    SetBond,
    FlipAromatic
)

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

    for class_ in classes:
            bpy.utils.register_class(class_)
    bpy.types.Scene.bond_order = PointerProperty(type=BondOrder)
    bpy.types.Scene.line_thickness_data = PointerProperty(type=LineThickness)
    bpy.types.Scene.charge_choice_data = PointerProperty(type=ChargeChoice)
    bpy.types.Scene.bond_influence_property = PointerProperty(type=BondInfluenceProperty)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

    del bpy.types.Scene.atom_choice
    del bpy.types.Scene.bond_order
    del bpy.types.Scene.line_thickness_data
    del bpy.types.Scene.charge_choice_data
    del bpy.types.Scene.bond_influence_property

    for class_ in reversed(classes):
        bpy.utils.unregister_class(class_)

if __name__ == "__main__":
    register()

