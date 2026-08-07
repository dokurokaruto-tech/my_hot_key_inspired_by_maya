"""Shared helpers for the Kenny's Animation Picker test suite (headless bpy 5.2)."""
import os
import struct
import zlib

BLENDER_VERSION_OK = (5, 2, 0)


def make_test_png(path, w=256, h=256):
    """Generate a simple test PNG (checkerboard + a colored center square)."""
    raw = bytearray()
    for y in range(h):
        raw.append(0)  # filter: none
        for x in range(w):
            if 64 <= x < 192 and 64 <= y < 192:
                r, g, b, a = 255, 200, 0, 255      # orange center
            elif (x // 32 + y // 32) % 2:
                r, g, b, a = 200, 200, 220, 255    # light checker
            else:
                r, g, b, a = 40, 40, 60, 255       # dark checker
            raw += bytes((r, g, b, a))

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
           + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)
    return path


def new_test_armature(name="TestRig"):
    """Create a test armature in pose mode and return the object."""
    import bpy
    bpy.ops.wm.read_factory_settings(use_empty=True)
    arm = bpy.data.armatures.new(name)
    obj = bpy.data.objects.new(name, arm)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bones = ["head", "neck", "spine",
             "arm_L", "arm_R", "forearm_L", "forearm_R",
             "leg.L", "leg.R", "foot.L", "foot.R",
             "hand_L.001", "hand_R.001",
             "earLeft", "earRight",
             "jaw", "tongue"]
    for i, n in enumerate(bones):
        eb = arm.edit_bones.new(n)
        eb.head = (0.0, 0.0, float(i))
        eb.tail = (0.0, 0.0, float(i) + 0.1)
        if i > 0:
            eb.parent = arm.edit_bones[bones[i - 1]]
    bpy.ops.object.mode_set(mode='POSE')
    return obj


def make_fake_context(state_owner=True):
    """Build a minimal fake bpy context for draw-callback tests."""
    import builtins

    class FakeSpace:
        kind = 'VIEW_3D'

    class FakeSpaces:
        active = FakeSpace()

    class FakeRegion:
        type = 'WINDOW'
        width = 1200
        height = 800
        x = 0
        y = 0

    class FakeArea:
        type = 'VIEW_3D'
        spaces = FakeSpaces()

        def tag_redraw(self):
            pass

    class FakeScreen:
        areas = [FakeArea()]

    class FakeContext:
        pass

    ctx = FakeContext()
    ctx.area = FakeArea()
    ctx.region = FakeRegion()
    ctx.space_data = FakeSpace()
    ctx.screen = FakeScreen()
    ctx.scene = None
    ctx.object = None
    ctx.mode = 'POSE'
    ctx.view_layer = None
    return ctx
