"""Minimal Blender add-on skeleton: operator + panel + scene property + preferences. Works as a legacy add-on (bl_info)
and as an extension (blender_manifest.toml, Blender 4.2+). Rename `threedpro_demo` / `THREEDPRO` everywhere.

Test headless:  python -c "import sys; sys.path.insert(0,'<parent dir>'); import bpy, addon_template as m; m.register(); bpy.ops.object.threedpro_add_crate(); m.unregister()"
"""
bl_info = {
    "name": "3Dpro demo",
    "author": "you",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > 3Dpro",
    "description": "Operator + panel skeleton",
    "category": "Object",
}

import bpy  # noqa: E402
import bmesh  # noqa: E402


class THREEDPRO_Props(bpy.types.PropertyGroup):
    crate_size: bpy.props.FloatVectorProperty(name="Size", default=(1.0, 1.0, 1.0), min=0.01, subtype="XYZ", unit="LENGTH")
    bevel: bpy.props.FloatProperty(name="Bevel", default=0.01, min=0.0, soft_max=0.1, unit="LENGTH")


class THREEDPRO_OT_add_crate(bpy.types.Operator):
    """Add a beveled box at the 3D cursor"""
    bl_idname = "object.threedpro_add_crate"      # becomes bpy.ops.object.threedpro_add_crate()
    bl_label = "Add Crate"
    bl_options = {"REGISTER", "UNDO"}             # UNDO makes it undoable and enables the redo panel

    size: bpy.props.FloatVectorProperty(name="Size", default=(1.0, 1.0, 1.0), min=0.01, subtype="XYZ", unit="LENGTH")

    @classmethod
    def poll(cls, context):                       # greys the button out when the operator cannot run
        return context.mode == "OBJECT" or context.mode is None

    def execute(self, context):
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=self.size, verts=bm.verts)
        me = bpy.data.meshes.new("Crate")
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new("Crate", me)
        ob.location = context.scene.cursor.location
        context.collection.objects.link(ob)
        for o in context.view_layer.objects:
            o.select_set(False)
        context.view_layer.objects.active = ob
        ob.select_set(True)
        bev = ob.modifiers.new("Bevel", "BEVEL")
        bev.width = context.scene.threedpro.bevel
        bev.segments = 3
        self.report({"INFO"}, f"Added {ob.name}")
        return {"FINISHED"}

    def invoke(self, context, event):             # pre-fill from scene settings, then run
        self.size = context.scene.threedpro.crate_size
        return self.execute(context)


class THREEDPRO_PT_panel(bpy.types.Panel):
    bl_label = "3Dpro"
    bl_idname = "THREEDPRO_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "3Dpro"

    def draw(self, context):
        p = context.scene.threedpro
        col = self.layout.column(align=True)
        col.prop(p, "crate_size")
        col.prop(p, "bevel")
        col.operator(THREEDPRO_OT_add_crate.bl_idname, icon="MESH_CUBE")


classes = (THREEDPRO_Props, THREEDPRO_OT_add_crate, THREEDPRO_PT_panel)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.threedpro = bpy.props.PointerProperty(type=THREEDPRO_Props)


def unregister():
    del bpy.types.Scene.threedpro
    for c in reversed(classes):
        bpy.utils.unregister_class(c)


if __name__ == "__main__":
    register()
