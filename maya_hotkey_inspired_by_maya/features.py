import bpy
import bmesh
import math
import time
import mathutils

from . import core as C


# ============================================================
# Transform Orientation / Micro Manipulator
# ============================================================

def get_current_transform_orientation(context):
    try:
        orientation = (
            context.scene
            .transform_orientation_slots[0]
            .type
        )
    except Exception:
        orientation = 'GLOBAL'

    if orientation not in C.MICRO_ORIENTATION_TYPES:
        return 'GLOBAL'

    return orientation


def set_transform_orientation(context, orientation):
    if orientation not in C.MICRO_ORIENTATION_TYPES:
        orientation = 'GLOBAL'

    try:
        context.scene.transform_orientation_slots[0].type = (
            orientation
        )
    except Exception as error:
        print(
            f"⚠️ Transform Orientationを設定できませんでした: "
            f"{error}"
        )
        return False

    C.tag_all_view3d_redraw()
    return True


_RUNTIME_PROPERTY_NAMES = (
    "maya_micro_manipulator_enabled",
    "maya_micro_manipulator_mode",
    "maya_micro_visibility_owned",
    "maya_micro_previous_show_gizmo",
    "maya_micro_previous_show_gizmo_tool",
    "maya_micro_previous_show_gizmo_context",
)


def restore_maya_micro_space_visibility():
    wm = getattr(
        bpy.context,
        "window_manager",
        None,
    )

    if wm is None:
        return

    try:
        owned = bool(
            wm.maya_micro_visibility_owned
        )
    except Exception:
        owned = False

    if not owned:
        return

    try:
        previous_show_gizmo = bool(
            wm.maya_micro_previous_show_gizmo
        )
    except Exception:
        previous_show_gizmo = True

    try:
        previous_show_gizmo_tool = bool(
            wm.maya_micro_previous_show_gizmo_tool
        )
    except Exception:
        previous_show_gizmo_tool = True

    try:
        previous_show_gizmo_context = bool(
            wm.maya_micro_previous_show_gizmo_context
        )
    except Exception:
        previous_show_gizmo_context = True

    for space in C.iter_view3d_spaces():
        try:
            space.show_gizmo = previous_show_gizmo
        except Exception:
            pass

        try:
            space.show_gizmo_tool = previous_show_gizmo_tool
        except Exception:
            pass

        try:
            space.show_gizmo_context = (
                previous_show_gizmo_context
            )
        except Exception:
            pass

    try:
        wm.maya_micro_visibility_owned = False
    except Exception:
        pass

    C.tag_all_view3d_redraw()


def apply_maya_micro_space_visibility(context, enabled):
    wm = getattr(
        context,
        "window_manager",
        None,
    )

    if wm is None:
        return

    if not enabled:
        restore_maya_micro_space_visibility()
        return

    try:
        owned = bool(
            wm.maya_micro_visibility_owned
        )
    except Exception:
        owned = False

    if not owned:
        source_space = getattr(
            context,
            "space_data",
            None,
        )

        if (
            source_space is None or
            getattr(
                source_space,
                "type",
                None,
            ) != 'VIEW_3D'
        ):
            source_space = C.find_any_view3d_space(
                context
            )

        if source_space is None:
            try:
                source_space = next(
                    iter(C.iter_view3d_spaces())
                )
            except Exception:
                source_space = None

        if source_space is not None:
            try:
                wm.maya_micro_previous_show_gizmo = bool(
                    source_space.show_gizmo
                )
            except Exception:
                wm.maya_micro_previous_show_gizmo = True

            try:
                wm.maya_micro_previous_show_gizmo_tool = bool(
                    source_space.show_gizmo_tool
                )
            except Exception:
                wm.maya_micro_previous_show_gizmo_tool = True

            try:
                wm.maya_micro_previous_show_gizmo_context = bool(
                    source_space.show_gizmo_context
                )
            except Exception:
                wm.maya_micro_previous_show_gizmo_context = True

        try:
            wm.maya_micro_visibility_owned = True
        except Exception:
            pass

    for space in C.iter_view3d_spaces():
        try:
            space.show_gizmo = True
        except Exception:
            pass

        # Blender標準のツールギズモを隠し、
        # Micro Manipulatorとの重複クリックを防ぐ。
        try:
            space.show_gizmo_tool = False
        except Exception:
            pass

        # カスタムのPersistent GizmoGroupを表示する。
        try:
            space.show_gizmo_context = True
        except Exception:
            pass

    C.tag_all_view3d_redraw()


def register_runtime_properties():
    restore_maya_micro_space_visibility()

    for property_name in _RUNTIME_PROPERTY_NAMES:
        if hasattr(
            bpy.types.WindowManager,
            property_name,
        ):
            try:
                delattr(
                    bpy.types.WindowManager,
                    property_name,
                )
            except Exception:
                pass

    bpy.types.WindowManager.maya_micro_manipulator_enabled = (
        bpy.props.BoolProperty(
            name="Micro Manipulator",
            description=(
                "約1/10の感度で動作する"
                "高精度マニピュレーター"
            ),
            default=False,
            options={'SKIP_SAVE'},
        )
    )

    bpy.types.WindowManager.maya_micro_visibility_owned = (
        bpy.props.BoolProperty(
            default=False,
            options={'HIDDEN', 'SKIP_SAVE'},
        )
    )

    bpy.types.WindowManager.maya_micro_previous_show_gizmo = (
        bpy.props.BoolProperty(
            default=True,
            options={'HIDDEN', 'SKIP_SAVE'},
        )
    )

    bpy.types.WindowManager.maya_micro_previous_show_gizmo_tool = (
        bpy.props.BoolProperty(
            default=True,
            options={'HIDDEN', 'SKIP_SAVE'},
        )
    )

    bpy.types.WindowManager.maya_micro_previous_show_gizmo_context = (
        bpy.props.BoolProperty(
            default=True,
            options={'HIDDEN', 'SKIP_SAVE'},
        )
    )


def unregister_runtime_properties():
    restore_maya_micro_space_visibility()

    for property_name in _RUNTIME_PROPERTY_NAMES:
        if hasattr(
            bpy.types.WindowManager,
            property_name,
        ):
            try:
                delattr(
                    bpy.types.WindowManager,
                    property_name,
                )
            except Exception:
                pass


def _micro_average_vectors(vectors):
    if not vectors:
        return None

    total = mathutils.Vector(
        (0.0, 0.0, 0.0)
    )

    for vector in vectors:
        total += vector

    return total / len(vectors)


def _micro_bounding_box_center(vectors):
    if not vectors:
        return None

    min_value = vectors[0].copy()
    max_value = vectors[0].copy()

    for vector in vectors[1:]:
        min_value.x = min(
            min_value.x,
            vector.x,
        )
        min_value.y = min(
            min_value.y,
            vector.y,
        )
        min_value.z = min(
            min_value.z,
            vector.z,
        )

        max_value.x = max(
            max_value.x,
            vector.x,
        )
        max_value.y = max(
            max_value.y,
            vector.y,
        )
        max_value.z = max(
            max_value.z,
            vector.z,
        )

    return (min_value + max_value) * 0.5


def _micro_edit_mesh_active_position(
    context,
    obj,
    bm,
):
    try:
        active = bm.select_history.active
    except Exception:
        active = None

    if active is None:
        return None

    local_position = None

    if isinstance(
        active,
        bmesh.types.BMVert,
    ):
        local_position = active.co.copy()

    elif isinstance(
        active,
        bmesh.types.BMEdge,
    ):
        local_position = (
            active.verts[0].co +
            active.verts[1].co
        ) * 0.5

    elif isinstance(
        active,
        bmesh.types.BMFace,
    ):
        local_position = (
            active.calc_center_median()
        )

    if local_position is None:
        return None

    try:
        return obj.matrix_world @ local_position
    except Exception:
        return None


def _micro_edit_mesh_positions(context, obj):
    if obj is None or obj.type != 'MESH':
        return [], None

    try:
        bm = bmesh.from_edit_mesh(obj.data)
    except Exception:
        return [], None

    positions = []

    try:
        for vertex in bm.verts:
            if vertex.select:
                positions.append(
                    obj.matrix_world @ vertex.co
                )
    except Exception:
        positions = []

    active_position = (
        _micro_edit_mesh_active_position(
            context,
            obj,
            bm,
        )
    )

    return positions, active_position


def _micro_pose_bone_world_matrix(
    context,
    pose_bone,
):
    obj = getattr(
        context,
        "active_object",
        None,
    )

    if obj is None or pose_bone is None:
        return None

    try:
        return obj.matrix_world @ pose_bone.matrix
    except Exception:
        return None


def _micro_pose_positions(context):
    positions = []

    try:
        selected_pose_bones = (
            context.selected_pose_bones or []
        )
    except Exception:
        selected_pose_bones = []

    for pose_bone in selected_pose_bones:
        matrix = _micro_pose_bone_world_matrix(
            context,
            pose_bone,
        )

        if matrix is not None:
            positions.append(
                matrix.translation.copy()
            )

    active_position = None

    try:
        active_pose_bone = (
            context.active_pose_bone
        )
    except Exception:
        active_pose_bone = None

    if active_pose_bone is not None:
        matrix = _micro_pose_bone_world_matrix(
            context,
            active_pose_bone,
        )

        if matrix is not None:
            active_position = (
                matrix.translation.copy()
            )

    return positions, active_position


def _micro_object_positions(context):
    try:
        selected_objects = list(
            context.selected_objects or []
        )
    except Exception:
        selected_objects = []

    origin_positions = []
    bounding_positions = []

    for obj in selected_objects:
        try:
            origin_positions.append(
                obj.matrix_world.translation.copy()
            )
        except Exception:
            pass

        try:
            for corner in obj.bound_box:
                bounding_positions.append(
                    obj.matrix_world @
                    mathutils.Vector(corner)
                )
        except Exception:
            pass

    active_position = None
    active_object = getattr(
        context,
        "active_object",
        None,
    )

    if active_object is not None:
        try:
            active_position = (
                active_object
                .matrix_world
                .translation
                .copy()
            )
        except Exception:
            pass

    return (
        origin_positions,
        bounding_positions,
        active_position,
    )


def get_micro_manipulator_pivot(context):
    try:
        pivot_mode = (
            context.scene
            .tool_settings
            .transform_pivot_point
        )
    except Exception:
        pivot_mode = 'MEDIAN_POINT'

    if pivot_mode == 'CURSOR':
        try:
            return (
                context.scene.cursor.location.copy()
            )
        except Exception:
            return mathutils.Vector(
                (0.0, 0.0, 0.0)
            )

    if context.mode == 'POSE':
        positions, active_position = (
            _micro_pose_positions(context)
        )

        if (
            pivot_mode == 'ACTIVE_ELEMENT' and
            active_position is not None
        ):
            return active_position

        if pivot_mode == 'BOUNDING_BOX_CENTER':
            center = _micro_bounding_box_center(
                positions
            )
        else:
            center = _micro_average_vectors(
                positions
            )

        if center is not None:
            return center

        if active_position is not None:
            return active_position

    if context.mode == 'EDIT_MESH':
        obj = getattr(
            context,
            "active_object",
            None,
        )

        positions, active_position = (
            _micro_edit_mesh_positions(
                context,
                obj,
            )
        )

        if (
            pivot_mode == 'ACTIVE_ELEMENT' and
            active_position is not None
        ):
            return active_position

        if pivot_mode == 'BOUNDING_BOX_CENTER':
            center = _micro_bounding_box_center(
                positions
            )
        else:
            center = _micro_average_vectors(
                positions
            )

        if center is not None:
            return center

        if active_position is not None:
            return active_position

    (
        origin_positions,
        bounding_positions,
        active_position,
    ) = _micro_object_positions(context)

    if (
        pivot_mode == 'ACTIVE_ELEMENT' and
        active_position is not None
    ):
        return active_position

    if pivot_mode == 'BOUNDING_BOX_CENTER':
        center = _micro_bounding_box_center(
            bounding_positions or
            origin_positions
        )
    else:
        center = _micro_average_vectors(
            origin_positions
        )

    if center is not None:
        return center

    if active_position is not None:
        return active_position

    active_object = getattr(
        context,
        "active_object",
        None,
    )

    if active_object is not None:
        try:
            return (
                active_object
                .matrix_world
                .translation
                .copy()
            )
        except Exception:
            pass

    return mathutils.Vector(
        (0.0, 0.0, 0.0)
    )


def _micro_active_transform_matrix(context):
    if context.mode == 'POSE':
        try:
            active_pose_bone = (
                context.active_pose_bone
            )
        except Exception:
            active_pose_bone = None

        matrix = _micro_pose_bone_world_matrix(
            context,
            active_pose_bone,
        )

        if matrix is not None:
            return matrix

    active_object = getattr(
        context,
        "active_object",
        None,
    )

    if active_object is not None:
        try:
            return (
                active_object.matrix_world.copy()
            )
        except Exception:
            pass

    return mathutils.Matrix.Identity(4)


def _micro_active_rotation_target(context):
    if context.mode == 'POSE':
        try:
            if context.active_pose_bone is not None:
                return context.active_pose_bone
        except Exception:
            pass

    return getattr(
        context,
        "active_object",
        None,
    )


def _micro_matrix_axes(matrix):
    try:
        matrix_3x3 = matrix.to_3x3()
    except Exception:
        matrix_3x3 = (
            mathutils.Matrix.Identity(3)
        )

    axes = []

    for index in range(3):
        try:
            axis = (
                matrix_3x3.col[index].copy()
            )
        except Exception:
            axis = mathutils.Vector(
                (0.0, 0.0, 0.0)
            )
            axis[index] = 1.0

        if axis.length_squared < 1e-12:
            axis = mathutils.Vector(
                (0.0, 0.0, 0.0)
            )
            axis[index] = 1.0
        else:
            axis.normalize()

        axes.append(axis)

    return axes


def _micro_gimbal_axes(context):
    final_matrix = (
        _micro_active_transform_matrix(context)
    )
    local_axes = _micro_matrix_axes(
        final_matrix
    )

    target = _micro_active_rotation_target(
        context
    )

    if target is None:
        return local_axes

    rotation_mode = getattr(
        target,
        "rotation_mode",
        'XYZ',
    )

    if rotation_mode in {
        'QUATERNION',
        'AXIS_ANGLE',
    }:
        return local_axes

    if rotation_mode not in {
        'XYZ',
        'XZY',
        'YXZ',
        'YZX',
        'ZXY',
        'ZYX',
    }:
        return local_axes

    try:
        euler = target.rotation_euler.copy()
        base_quaternion = euler.to_quaternion()
        final_quaternion = (
            final_matrix.to_quaternion()
        )

        parent_quaternion = (
            final_quaternion @
            base_quaternion.inverted()
        )
    except Exception:
        return local_axes

    axes = []
    epsilon = 1e-5

    for index in range(3):
        try:
            perturbed = euler.copy()
            perturbed[index] += epsilon

            perturbed_quaternion = (
                perturbed.to_quaternion()
            )

            delta = (
                perturbed_quaternion @
                base_quaternion.inverted()
            )

            axis = delta.axis.copy()

            if axis.length_squared < 1e-12:
                axis = mathutils.Vector(
                    (0.0, 0.0, 0.0)
                )
                axis[index] = 1.0

            axis = parent_quaternion @ axis

            if axis.length_squared < 1e-12:
                axis = local_axes[index]
            else:
                axis.normalize()

            axes.append(axis)

        except Exception:
            axes.append(
                local_axes[index]
            )

    return axes


def get_micro_manipulator_axes(
    context,
    orientation,
):
    if orientation == 'GLOBAL':
        return (
            mathutils.Vector(
                (1.0, 0.0, 0.0)
            ),
            mathutils.Vector(
                (0.0, 1.0, 0.0)
            ),
            mathutils.Vector(
                (0.0, 0.0, 1.0)
            ),
        )

    if orientation == 'GIMBAL':
        return tuple(
            _micro_gimbal_axes(context)
        )

    matrix = _micro_active_transform_matrix(
        context
    )

    return tuple(
        _micro_matrix_axes(matrix)
    )


def _micro_axis_matrix(origin, axis):
    axis = axis.copy()

    if axis.length_squared < 1e-12:
        axis = mathutils.Vector(
            (0.0, 0.0, 1.0)
        )
    else:
        axis.normalize()

    world_y = mathutils.Vector(
        (0.0, 1.0, 0.0)
    )

    if abs(axis.dot(world_y)) > 0.999:
        up_axis = 'X'
    else:
        up_axis = 'Y'

    try:
        quaternion = axis.to_track_quat(
            'Z',
            up_axis,
        )
        matrix = (
            quaternion
            .to_matrix()
            .to_4x4()
        )
    except Exception:
        matrix = mathutils.Matrix.Identity(4)

    matrix.translation = origin
    return matrix


def _micro_active_tool_idname(context):
    try:
        tool = (
            context.workspace.tools
            .from_space_view3d_mode(
                context.mode,
                create=False,
            )
        )

        if tool is not None:
            return tool.idname
    except Exception:
        pass

    return ""


def get_micro_manipulator_visible_mode(context):
    """常にW / E / Rの現在ツールに連動する（AUTO固定）。"""
    tool_idname = _micro_active_tool_idname(
        context
    )

    if tool_idname == 'builtin.rotate':
        return 'ROTATE'

    if tool_idname == 'builtin.scale':
        return 'SCALE'

    return 'MOVE'


class VIEW3D_OT_maya_set_transform_orientation(
    bpy.types.Operator
):
    bl_idname = (
        "view3d.maya_set_transform_orientation"
    )
    bl_label = "マニピュレーター方向を設定"
    bl_options = {'REGISTER'}

    orientation: bpy.props.EnumProperty(
        name="Transform Orientation",
        items=(
            (
                'GLOBAL',
                "Global",
                "ワールド座標に合わせる",
            ),
            (
                'LOCAL',
                "Local",
                "アクティブ対象のローカル座標に合わせる",
            ),
            (
                'GIMBAL',
                "Gimbal",
                "Euler回転軸に合わせる",
            ),
        ),
        default='GLOBAL',
    )

    def execute(self, context):
        if not set_transform_orientation(
            context,
            self.orientation,
        ):
            self.report(
                {'WARNING'},
                "Transform Orientationを変更できませんでした。",
            )
            return {'CANCELLED'}

        self.report(
            {'INFO'},
            f"Manipulator Orientation: "
            f"{self.orientation}",
        )
        return {'FINISHED'}


class VIEW3D_OT_maya_toggle_micro_manipulator(
    bpy.types.Operator
):
    bl_idname = (
        "view3d.maya_toggle_micro_manipulator"
    )
    bl_label = "Micro Manipulator切替"
    bl_options = {'REGISTER'}

    enable: bpy.props.BoolProperty(
        name="有効",
        default=True,
    )

    def execute(self, context):
        wm = context.window_manager

        wm.maya_micro_manipulator_enabled = (
            self.enable
        )

        apply_maya_micro_space_visibility(
            context,
            self.enable,
        )

        C.tag_all_view3d_redraw()

        if self.enable:
            self.report(
                {'INFO'},
                "Micro Manipulator: ON（約1/10感度）",
            )
        else:
            self.report(
                {'INFO'},
                "Micro Manipulator: OFF",
            )

        return {'FINISHED'}


def _interaction_mode_id(context_mode):
    """context.mode を Object / Edit / Pose の3分類へ変換する。"""
    if context_mode == 'POSE':
        return 'POSE'

    if context_mode.startswith('EDIT'):
        return 'EDIT'

    if context_mode == 'OBJECT':
        return 'OBJECT'

    return ''


class VIEW3D_OT_maya_set_interaction_mode(
    bpy.types.Operator
):
    bl_idname = (
        "view3d.maya_set_interaction_mode"
    )
    bl_label = "モード切替 (Maya)"
    bl_options = {'REGISTER', 'UNDO'}

    mode: bpy.props.EnumProperty(
        name="Mode",
        items=(
            (
                'OBJECT',
                "Object Mode",
                "オブジェクトモードに切り替える",
            ),
            (
                'EDIT',
                "Edit Mode",
                "編集モードに切り替える",
            ),
            (
                'POSE',
                "Pose Mode",
                "ポーズモードに切り替える",
            ),
        ),
        default='OBJECT',
    )

    def execute(self, context):
        active = getattr(
            context,
            "active_object",
            None,
        )

        if active is None:
            self.report(
                {'WARNING'},
                "アクティブオブジェクトがありません。",
            )
            return {'CANCELLED'}

        current = _interaction_mode_id(
            context.mode
        )

        if current == self.mode:
            self.report(
                {'INFO'},
                f"すでに {self.mode} モードです。",
            )
            return {'FINISHED'}

        if (
            self.mode == 'POSE' and
            active.type != 'ARMATURE'
        ):
            self.report(
                {'WARNING'},
                "Pose Modeはアーマチュアのみ使用できます。",
            )
            return {'CANCELLED'}

        try:
            bpy.ops.object.mode_set(
                mode=self.mode
            )
        except Exception as error:
            self.report(
                {'WARNING'},
                f"モードを切り替えられませんでした: "
                f"{error}",
            )
            return {'CANCELLED'}

        C.tag_all_view3d_redraw()

        self.report(
            {'INFO'},
            f"モード: {self.mode}",
        )
        return {'FINISHED'}


class VIEW3D_MT_maya_manipulator_menu(
    bpy.types.Menu
):
    bl_idname = (
        "VIEW3D_MT_maya_manipulator_menu"
    )
    bl_label = "Manipulator Settings"

    def draw(self, context):
        layout = self.layout

        orientation = (
            get_current_transform_orientation(
                context
            )
        )
        wm = context.window_manager

        layout.label(
            text="Manipulator Orientation",
            icon='ORIENTATION_GLOBAL',
        )

        for orientation_id, label in (
            ('GLOBAL', "Global"),
            ('LOCAL', "Local"),
            ('GIMBAL', "Gimbal"),
        ):
            icon = (
                'RADIOBUT_ON'
                if orientation == orientation_id
                else 'RADIOBUT_OFF'
            )

            operator = layout.operator(
                "view3d.maya_set_transform_orientation",
                text=label,
                icon=icon,
            )
            operator.orientation = (
                orientation_id
            )

        layout.separator()

        enabled = bool(
            getattr(
                wm,
                "maya_micro_manipulator_enabled",
                False,
            )
        )

        operator = layout.operator(
            "view3d.maya_toggle_micro_manipulator",
            text=(
                "Micro Manipulator: ON"
                if enabled
                else "Micro Manipulator: OFF"
            ),
            icon=(
                'CHECKBOX_HLT'
                if enabled
                else 'CHECKBOX_DEHLT'
            ),
        )
        operator.enable = not enabled

        layout.label(
            text="通常の約1/10の感度・W/E/R連動",
            icon='INFO',
        )

        layout.separator()

        layout.label(
            text="Interaction Mode",
            icon='OBJECT_DATAMODE',
        )

        current_mode = _interaction_mode_id(
            context.mode
        )

        for mode_id, label in (
            ('OBJECT', "Object Mode"),
            ('EDIT', "Edit Mode"),
            ('POSE', "Pose Mode"),
        ):
            icon = (
                'RADIOBUT_ON'
                if current_mode == mode_id
                else 'RADIOBUT_OFF'
            )

            operator = layout.operator(
                "view3d.maya_set_interaction_mode",
                text=label,
                icon=icon,
            )
            operator.mode = mode_id


class VIEW3D_GGT_maya_micro_manipulator(
    bpy.types.GizmoGroup
):
    bl_idname = (
        "VIEW3D_GGT_maya_micro_manipulator"
    )
    bl_label = "Maya Micro Manipulator"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'3D', 'PERSISTENT'}

    _AXIS_COLORS = (
        (0.95, 0.12, 0.12),
        (0.20, 0.85, 0.20),
        (0.18, 0.38, 1.00),
    )

    _GIZMO_DEFINITIONS = (
        (
            'MOVE',
            "GIZMO_GT_arrow_3d",
            "transform.translate",
            'CONE',
            0.8,
            1.0,
            2.5,
        ),
        (
            'ROTATE',
            "GIZMO_GT_dial_3d",
            "transform.rotate",
            None,
            0.65,
            1.15,
            3.0,
        ),
        (
            'SCALE',
            "GIZMO_GT_arrow_3d",
            "transform.resize",
            'BOX',
            0.8,
            1.0,
            2.5,
        ),
    )

    @classmethod
    def poll(cls, context):
        wm = getattr(
            context,
            "window_manager",
            None,
        )

        if wm is None:
            return False

        if not getattr(
            wm,
            "maya_micro_manipulator_enabled",
            False,
        ):
            return False

        active_object = getattr(
            context,
            "active_object",
            None,
        )

        if active_object is None:
            return False

        if context.mode == 'POSE':
            try:
                return bool(
                    context.selected_pose_bones
                )
            except Exception:
                return False

        if context.mode == 'EDIT_MESH':
            return True

        try:
            return bool(
                context.selected_objects
            )
        except Exception:
            return active_object is not None

    def _create_axis_gizmo(
        self,
        mode_name,
        gizmo_type,
        operator_name,
        draw_style,
        alpha,
        scale,
        line_width,
        axis_index,
        axis_constraint,
        color,
    ):
        gizmo = self.gizmos.new(
            gizmo_type
        )

        properties = gizmo.target_set_operator(
            operator_name
        )

        C.safe_setattr(
            properties,
            "constraint_axis",
            axis_constraint,
        )
        C.safe_setattr(
            properties,
            "orient_type",
            'GLOBAL',
        )
        C.safe_setattr(
            properties,
            "release_confirm",
            True,
        )
        C.safe_setattr(
            properties,
            "use_accurate",
            True,
        )

        if draw_style is not None:
            C.safe_setattr(
                gizmo,
                "draw_style",
                draw_style,
            )

        C.safe_setattr(
            gizmo,
            "use_draw_modal",
            True,
        )
        C.safe_setattr(
            gizmo,
            "use_draw_value",
            True,
        )
        C.safe_setattr(
            gizmo,
            "line_width",
            line_width,
        )

        gizmo.color = color
        gizmo.alpha = alpha
        gizmo.color_highlight = (
            1.0,
            1.0,
            0.2,
        )
        gizmo.alpha_highlight = 1.0
        gizmo.scale_basis = (
            C.MICRO_MANIPULATOR_GIZMO_SCALE
            * scale
        )

        self._gizmo_groups[mode_name].append(
            (
                gizmo,
                properties,
                axis_index,
            )
        )

    def setup(self, context):
        self._gizmo_groups = {
            'MOVE': [],
            'ROTATE': [],
            'SCALE': [],
        }

        for axis_index in range(3):
            axis_constraint = [
                False,
                False,
                False,
            ]
            axis_constraint[axis_index] = True
            axis_constraint = tuple(
                axis_constraint
            )

            color = self._AXIS_COLORS[
                axis_index
            ]

            for (
                mode_name,
                gizmo_type,
                operator_name,
                draw_style,
                alpha,
                scale,
                line_width,
            ) in self._GIZMO_DEFINITIONS:
                self._create_axis_gizmo(
                    mode_name,
                    gizmo_type,
                    operator_name,
                    draw_style,
                    alpha,
                    scale,
                    line_width,
                    axis_index,
                    axis_constraint,
                    color,
                )

        self._update_gizmos(context)

    def refresh(self, context):
        self._update_gizmos(context)

    def draw_prepare(self, context):
        self._update_gizmos(context)

    def _update_gizmos(self, context):
        apply_maya_micro_space_visibility(
            context,
            True,
        )

        orientation = (
            get_current_transform_orientation(
                context
            )
        )

        visible_mode = (
            get_micro_manipulator_visible_mode(
                context
            )
        )

        origin = get_micro_manipulator_pivot(
            context
        )

        axes = get_micro_manipulator_axes(
            context,
            orientation,
        )

        for (
            mode_name,
            gizmo_items,
        ) in self._gizmo_groups.items():
            is_visible = (
                mode_name == visible_mode
            )

            for (
                gizmo,
                operator_properties,
                axis_index,
            ) in gizmo_items:
                try:
                    gizmo.hide = not is_visible
                except Exception:
                    pass

                if not is_visible:
                    continue

                C.safe_setattr(
                    operator_properties,
                    "orient_type",
                    orientation,
                )
                C.safe_setattr(
                    operator_properties,
                    "use_accurate",
                    True,
                )
                C.safe_setattr(
                    operator_properties,
                    "release_confirm",
                    True,
                )

                try:
                    gizmo.matrix_basis = (
                        _micro_axis_matrix(
                            origin,
                            axes[axis_index],
                        )
                    )
                except Exception:
                    pass


# ============================================================
# Maya Space / Hotbox
# ============================================================

class VIEW3D_MT_maya_hotbox_pie(
    bpy.types.Menu
):
    bl_idname = "VIEW3D_MT_maya_hotbox_pie"
    bl_label = "Hotbox (Maya風)"

    def draw(self, context):
        pie = self.layout.menu_pie()
        is_pose = context.mode == 'POSE'

        if hasattr(
            bpy.types,
            "ANIM_OT_keyframe_insert_menu",
        ):
            pie.operator(
                "anim.keyframe_insert_menu",
                text="キー挿入...",
                icon='KEY_HLT',
            )
        else:
            pie.operator(
                "anim.keyframe_insert",
                text="キー挿入",
                icon='KEY_HLT',
            )

        pie.operator(
            "anim.keyframe_delete_v3d",
            text="キー削除",
            icon='KEY_DEHLT',
        )

        pie.operator(
            "wm.toolbar",
            text="すべてのツール",
            icon='TOOL_SETTINGS',
        )

        pie.operator(
            "screen.animation_play",
            text="再生 / 停止",
            icon='PLAY',
        )

        pie.menu(
            "VIEW3D_MT_maya_spawn_menu",
            text="オブジェクト作成",
            icon='ADD',
        )

        pie.menu(
            "VIEW3D_MT_maya_constraint_menu",
            text="コンストレイント",
            icon='CONSTRAINT',
        )

        if is_pose:
            pie.operator(
                "pose.transforms_clear",
                text="ポーズをリセット",
                icon='LOOP_BACK',
            )
        else:
            pie.operator(
                "object.posemode_toggle",
                text="Object / Pose 切替",
                icon='POSE_HLT',
            )

        pie.operator(
            "view3d.view_selected",
            text="選択にフォーカス",
            icon='ZOOM_SELECTED',
        )

        center = pie.column()

        gap = center.column()
        gap.separator()
        gap.scale_y = 7.0

        box = center.box().column()
        box.scale_y = 1.2

        box.menu(
            "VIEW3D_MT_maya_view_menu",
            text="ビュー切替",
            icon='VIEW_PERSPECTIVE',
        )


class VIEW3D_OT_maya_space(
    bpy.types.Operator
):
    bl_idname = "view3d.maya_space"
    bl_label = (
        "Maya Space "
        "(Tap: Quad View / Hold: Hotbox)"
    )
    bl_options = {'REGISTER'}

    _timer = None
    _start_time = 0.0
    _mouse_x = 0
    _mouse_y = 0

    def invoke(self, context, event):
        if (
            context.area is None or
            context.area.type != 'VIEW_3D'
        ):
            return {'PASS_THROUGH'}

        self._start_time = time.monotonic()

        self._mouse_x = getattr(
            event,
            "mouse_x",
            0,
        )
        self._mouse_y = getattr(
            event,
            "mouse_y",
            0,
        )

        (
            area,
            region,
            space,
            region_data,
        ) = C.find_view3d_area_region_under_mouse(
            context,
            self._mouse_x,
            self._mouse_y,
        )

        if area is None or region is None:
            return {'PASS_THROUGH'}

        wm = context.window_manager

        self._timer = wm.event_timer_add(
            0.02,
            window=context.window,
        )

        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _remove_timer(self, context):
        if self._timer is not None:
            context.window_manager.event_timer_remove(
                self._timer
            )
            self._timer = None

    def _update_mouse_from_event(self, event):
        if event.type == 'TIMER':
            return

        try:
            self._mouse_x = event.mouse_x
            self._mouse_y = event.mouse_y
        except Exception:
            pass

    def modal(self, context, event):
        self._update_mouse_from_event(
            event
        )

        if (
            event.type == 'SPACE' and
            event.value == 'RELEASE'
        ):
            self._remove_timer(context)

            elapsed = (
                time.monotonic() -
                self._start_time
            )

            if elapsed >= C.SPACE_HOLD_TIME:
                self._open_hotbox(context)
            else:
                self._toggle_quad_view(context)

            return {'FINISHED'}

        if (
            event.type == 'SPACE' and
            event.value == 'PRESS'
        ):
            return {'RUNNING_MODAL'}

        if event.type == 'TIMER':
            elapsed = (
                time.monotonic() -
                self._start_time
            )

            if elapsed >= C.SPACE_HOLD_TIME:
                self._remove_timer(context)
                self._open_hotbox(context)
                return {'FINISHED'}

        if event.type in {
            'ESC',
            'RIGHTMOUSE',
        }:
            self._remove_timer(context)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def _open_hotbox(self, context):
        (
            area,
            region,
            space,
            region_data,
        ) = C.find_view3d_area_region_under_mouse(
            context,
            self._mouse_x,
            self._mouse_y,
        )

        try:
            C.call_menu_pie_for_region(
                context,
                VIEW3D_MT_maya_hotbox_pie.bl_idname,
                area,
                region,
                space,
                region_data,
            )
        except Exception as error:
            self.report(
                {'WARNING'},
                f"Hotboxを開けませんでした: "
                f"{error}",
            )

    def _toggle_quad_view(self, context):
        (
            area,
            region,
            space,
            region_data,
        ) = C.find_view3d_area_region_under_mouse(
            context,
            self._mouse_x,
            self._mouse_y,
        )

        try:
            if (
                space is not None and
                C.is_view3d_quadview(space) and
                region_data is not None
            ):
                main_region_data = None

                try:
                    main_region_data = (
                        space.region_3d
                    )
                except Exception:
                    pass

                C.copy_region_view3d_state(
                    region_data,
                    main_region_data,
                )

            C.call_region_quadview_for_region(
                context,
                area,
                region,
                space,
                region_data,
            )

            try:
                if area is not None:
                    area.tag_redraw()
            except Exception:
                pass

        except Exception as error:
            self.report(
                {'WARNING'},
                f"ビュー切替に失敗しました: "
                f"{error}",
            )

    def cancel(self, context):
        self._remove_timer(context)


# ============================================================
# Alt+1
# ============================================================

class VIEW3D_OT_maya_toggle_controllers(
    bpy.types.Operator
):
    bl_idname = (
        "view3d.maya_toggle_controllers"
    )
    bl_label = (
        "コントローラー表示切替 "
        "(Maya Alt+1)"
    )
    bl_options = {'REGISTER'}

    def _find_space(self, context, event=None):
        space = None

        if event is not None:
            mouse_x = getattr(
                event,
                "mouse_x",
                None,
            )
            mouse_y = getattr(
                event,
                "mouse_y",
                None,
            )

            (
                _area,
                _region,
                space,
                _region_data,
            ) = C.find_view3d_area_region_under_mouse(
                context,
                mouse_x,
                mouse_y,
            )

        if (
            space is None or
            getattr(
                space,
                "type",
                None,
            ) != 'VIEW_3D'
        ):
            candidate = getattr(
                context,
                "space_data",
                None,
            )

            if (
                candidate is not None and
                getattr(
                    candidate,
                    "type",
                    None,
                ) == 'VIEW_3D'
            ):
                space = candidate
            else:
                space = None

        if space is None:
            space = C.find_any_view3d_space(
                context
            )

        return space

    def _toggle(self, context, space):
        if space is None:
            self.report(
                {'WARNING'},
                "3D Viewが見つかりませんでした。",
            )
            return {'CANCELLED'}

        try:
            overlay = space.overlay
        except Exception:
            self.report(
                {'WARNING'},
                "オーバーレイ設定を取得できませんでした。",
            )
            return {'CANCELLED'}

        show = not overlay.show_bones
        overlay.show_bones = show

        if C.ALT1_ALSO_TOGGLE_EMPTIES:
            try:
                space.show_object_viewport_empty = (
                    show
                )
            except Exception:
                pass

        try:
            for area in context.window.screen.areas:
                if (
                    area.type == 'VIEW_3D' and
                    area.spaces.active == space
                ):
                    area.tag_redraw()
        except Exception:
            pass

        self.report(
            {'INFO'},
            (
                "コントローラー: 表示"
                if show
                else "コントローラー: 非表示"
            ),
        )

        return {'FINISHED'}

    def invoke(self, context, event):
        return self._toggle(
            context,
            self._find_space(
                context,
                event,
            ),
        )

    def execute(self, context):
        return self._toggle(
            context,
            self._find_space(context),
        )


# ============================================================
# Alt+W / Alt+S
# ============================================================

class SCREEN_OT_maya_keyframe_jump(
    bpy.types.Operator
):
    bl_idname = "screen.maya_keyframe_jump"
    bl_label = (
        "キーフレームジャンプ "
        "(Maya Alt+W/S)"
    )
    bl_options = {'REGISTER'}

    next: bpy.props.BoolProperty(
        name="次のキーフレームへ",
        default=True,
    )

    @staticmethod
    def _collect_from_id(id_data, frames):
        animation_data = getattr(
            id_data,
            "animation_data",
            None,
        )

        if animation_data is None:
            return

        action = animation_data.action

        if action is None:
            return

        try:
            for fcurve in action.fcurves:
                for point in fcurve.keyframe_points:
                    frames.add(point.co.x)
        except Exception:
            pass

    def _collect_keyframes(self, context):
        frames = set()
        objects = set()

        try:
            objects.update(
                context.selected_objects or []
            )
        except Exception:
            pass

        try:
            if context.active_object is not None:
                objects.add(
                    context.active_object
                )
        except Exception:
            pass

        for obj in objects:
            self._collect_from_id(
                obj,
                frames,
            )

            data = getattr(
                obj,
                "data",
                None,
            )

            if data is not None:
                self._collect_from_id(
                    data,
                    frames,
                )

                shape_keys = getattr(
                    data,
                    "shape_keys",
                    None,
                )

                if shape_keys is not None:
                    self._collect_from_id(
                        shape_keys,
                        frames,
                    )

        return frames

    def execute(self, context):
        scene = context.scene
        frames = self._collect_keyframes(
            context
        )

        if not frames:
            try:
                return bpy.ops.screen.keyframe_jump(
                    next=self.next
                )
            except Exception:
                self.report(
                    {'INFO'},
                    "選択オブジェクトに"
                    "キーフレームがありません。",
                )
                return {'CANCELLED'}

        try:
            current = scene.frame_current_final
        except Exception:
            current = float(
                scene.frame_current
            )

        epsilon = 1e-4

        if self.next:
            candidates = [
                frame
                for frame in frames
                if frame > current + epsilon
            ]
            target = (
                min(candidates)
                if candidates
                else None
            )
        else:
            candidates = [
                frame
                for frame in frames
                if frame < current - epsilon
            ]
            target = (
                max(candidates)
                if candidates
                else None
            )

        if target is None:
            self.report(
                {'INFO'},
                "これ以上キーフレームがありません。",
            )
            return {'CANCELLED'}

        frame = int(
            math.floor(target)
        )
        subframe = target - frame

        try:
            scene.frame_set(
                frame,
                subframe=subframe,
            )
        except TypeError:
            scene.frame_set(frame)

        return {'FINISHED'}


# ============================================================
# Alt+* Transform / Keyframe Reset
# ============================================================

class OBJECT_OT_maya_reset_transforms(
    bpy.types.Operator
):
    bl_idname = (
        "object.maya_reset_transforms"
    )
    bl_label = (
        "トランスフォームを初期化 "
        "(Maya Alt+*)"
    )
    bl_options = {'REGISTER', 'UNDO'}

    _ANIM_EDITOR_AREA_TYPES = {
        'GRAPH_EDITOR',
        'DOPESHEET_EDITOR',
    }

    # --------------------------------------------------------
    # 選択キーフレームのデフォルト化
    # --------------------------------------------------------

    @staticmethod
    def _default_channel_value(
        data_path,
        array_index,
    ):
        """トランスフォーム系チャンネルのデフォルト値を返す。
        対象外のチャンネルは None を返す。
        pose.bones["..."].location のようなパスにも対応する。
        """
        if not data_path:
            return None

        if data_path.endswith(
            "rotation_quaternion"
        ):
            return (
                1.0
                if array_index == 0
                else 0.0
            )

        if data_path.endswith(
            "rotation_axis_angle"
        ):
            # デフォルト (0.0, 0.0, 1.0, 0.0)
            return (
                1.0
                if array_index == 2
                else 0.0
            )

        if data_path.endswith("scale"):
            # scale / delta_scale
            return 1.0

        if data_path.endswith("location"):
            # location / delta_location
            return 0.0

        if data_path.endswith(
            "rotation_euler"
        ):
            # rotation_euler / delta_rotation_euler
            return 0.0

        return None

    @staticmethod
    def _collect_anim_fcurves(context):
        try:
            fcurves = list(
                context.editable_fcurves or []
            )
        except Exception:
            fcurves = []

        if not fcurves:
            try:
                fcurves = list(
                    context.visible_fcurves or []
                )
            except Exception:
                fcurves = []

        if not fcurves:
            objects = set()

            try:
                objects.update(
                    context.selected_objects or []
                )
            except Exception:
                pass

            try:
                if context.active_object is not None:
                    objects.add(
                        context.active_object
                    )
            except Exception:
                pass

            for obj in objects:
                animation_data = getattr(
                    obj,
                    "animation_data",
                    None,
                )

                if (
                    animation_data is None or
                    animation_data.action is None
                ):
                    continue

                try:
                    fcurves.extend(
                        animation_data.action.fcurves
                    )
                except Exception:
                    pass

        return [
            fcurve
            for fcurve in fcurves
            if (
                not getattr(
                    fcurve,
                    "lock",
                    False,
                ) and
                not getattr(
                    fcurve,
                    "hide",
                    False,
                )
            )
        ]

    def _execute_selected_keyframe_reset(
        self,
        context,
    ):
        """選択中のキーフレームだけをデフォルト値に戻す。
        現在フレーム上のキーでも、選択されていなければ触らない。
        ハンドルは同じ差分で移動させ、カーブ形状を保つ。
        """
        key_count = 0
        curve_count = 0
        skipped_channel_count = 0

        for fcurve in self._collect_anim_fcurves(
            context
        ):
            try:
                selected_points = [
                    point
                    for point in fcurve.keyframe_points
                    if point.select_control_point
                ]
            except Exception:
                continue

            if not selected_points:
                continue

            default_value = (
                self._default_channel_value(
                    getattr(
                        fcurve,
                        "data_path",
                        "",
                    ),
                    getattr(
                        fcurve,
                        "array_index",
                        0,
                    ),
                )
            )

            if default_value is None:
                # トランスフォーム以外のチャンネルは対象外。
                skipped_channel_count += 1
                continue

            for point in selected_points:
                try:
                    delta = (
                        default_value -
                        point.co.y
                    )

                    point.co.y = default_value
                    point.handle_left.y += delta
                    point.handle_right.y += delta

                    key_count += 1
                except Exception:
                    pass

            try:
                fcurve.update()
            except Exception:
                pass

            curve_count += 1

        if key_count == 0:
            if skipped_channel_count > 0:
                self.report(
                    {'INFO'},
                    "選択キーフレームは"
                    "トランスフォーム系チャンネル"
                    "ではないため対象外です。",
                )
            else:
                self.report(
                    {'INFO'},
                    "デフォルト化できる"
                    "選択キーフレームがありません。",
                )

            return {'CANCELLED'}

        try:
            for area in context.window.screen.areas:
                if area.type in {
                    'VIEW_3D',
                    'DOPESHEET_EDITOR',
                    'GRAPH_EDITOR',
                    'NLA_EDITOR',
                }:
                    area.tag_redraw()
        except Exception:
            pass

        message = (
            f"{curve_count} 本のカーブで "
            f"{key_count} 個の選択キーフレームを"
            "デフォルト値に戻しました。"
        )

        if skipped_channel_count > 0:
            message += (
                f"（対象外チャンネル "
                f"{skipped_channel_count} 本はスキップ）"
            )

        self.report(
            {'INFO'},
            message,
        )
        return {'FINISHED'}

    # --------------------------------------------------------
    # 従来のトランスフォーム初期化
    # --------------------------------------------------------

    @staticmethod
    def _reset_transform_channels(
        target,
        include_delta=False,
    ):
        try:
            target.location = (
                0.0,
                0.0,
                0.0,
            )
        except Exception:
            pass

        try:
            target.rotation_euler = (
                0.0,
                0.0,
                0.0,
            )
        except Exception:
            pass

        try:
            target.rotation_quaternion = (
                1.0,
                0.0,
                0.0,
                0.0,
            )
        except Exception:
            pass

        try:
            target.rotation_axis_angle = (
                0.0,
                0.0,
                1.0,
                0.0,
            )
        except Exception:
            pass

        try:
            target.scale = (
                1.0,
                1.0,
                1.0,
            )
        except Exception:
            pass

        if not include_delta:
            return

        try:
            target.delta_location = (
                0.0,
                0.0,
                0.0,
            )
        except Exception:
            pass

        try:
            target.delta_rotation_euler = (
                0.0,
                0.0,
                0.0,
            )
        except Exception:
            pass

        try:
            target.delta_rotation_quaternion = (
                1.0,
                0.0,
                0.0,
                0.0,
            )
        except Exception:
            pass

        try:
            target.delta_scale = (
                1.0,
                1.0,
                1.0,
            )
        except Exception:
            pass

    @staticmethod
    def _autokey_enabled(context):
        try:
            return bool(
                context.scene
                .tool_settings
                .use_keyframe_insert_auto
            )
        except Exception:
            return False

    @staticmethod
    def _rotation_data_path(target):
        mode = getattr(
            target,
            "rotation_mode",
            'XYZ',
        )

        if mode == 'QUATERNION':
            return "rotation_quaternion"

        if mode == 'AXIS_ANGLE':
            return "rotation_axis_angle"

        return "rotation_euler"

    @classmethod
    def _insert_reset_keys(
        cls,
        context,
        target,
        include_delta=False,
    ):
        try:
            frame = (
                context.scene.frame_current
            )
        except Exception:
            frame = None

        options = set()

        try:
            if getattr(
                context.preferences.edit,
                "use_keyframe_insert_available",
                False,
            ):
                options.add(
                    'INSERTKEY_AVAILABLE'
                )
        except Exception:
            pass

        data_paths = [
            "location",
            cls._rotation_data_path(target),
            "scale",
        ]

        if include_delta:
            data_paths.append(
                "delta_location"
            )

            if getattr(
                target,
                "rotation_mode",
                'XYZ',
            ) == 'QUATERNION':
                data_paths.append(
                    "delta_rotation_quaternion"
                )
            else:
                data_paths.append(
                    "delta_rotation_euler"
                )

            data_paths.append(
                "delta_scale"
            )

        inserted = 0

        for data_path in data_paths:
            try:
                if (
                    frame is not None and
                    options
                ):
                    ok = target.keyframe_insert(
                        data_path,
                        frame=frame,
                        options=options,
                    )
                elif frame is not None:
                    ok = target.keyframe_insert(
                        data_path,
                        frame=frame,
                    )
                else:
                    ok = target.keyframe_insert(
                        data_path
                    )

                if ok:
                    inserted += 1

            except TypeError:
                try:
                    if frame is not None:
                        ok = target.keyframe_insert(
                            data_path,
                            frame=frame,
                        )
                    else:
                        ok = target.keyframe_insert(
                            data_path
                        )

                    if ok:
                        inserted += 1
                except Exception:
                    pass

            except Exception:
                pass

        return inserted

    def execute(self, context):
        # アニメーションエディター上で実行された場合は、
        # 「選択キーフレームのデフォルト化」モードで動作する。
        area_type = getattr(
            getattr(
                context,
                "area",
                None,
            ),
            "type",
            "",
        )

        if area_type in self._ANIM_EDITOR_AREA_TYPES:
            return (
                self._execute_selected_keyframe_reset(
                    context
                )
            )

        # 以下は従来動作（3D View等での現在値リセット）。
        reset_count = 0
        keyed_count = 0
        autokey = self._autokey_enabled(
            context
        )

        if context.mode == 'POSE':
            pose_bones = (
                context.selected_pose_bones or []
            )

            for pose_bone in pose_bones:
                self._reset_transform_channels(
                    pose_bone
                )
                reset_count += 1

                if autokey:
                    if self._insert_reset_keys(
                        context,
                        pose_bone,
                    ):
                        keyed_count += 1

            if reset_count == 0:
                self.report(
                    {'WARNING'},
                    "ボーンが選択されていません。",
                )
                return {'CANCELLED'}

            if autokey:
                self.report(
                    {'INFO'},
                    f"{reset_count} 本のボーンを初期姿勢に戻し、"
                    f"{keyed_count} 本にキーを挿入しました"
                    "（Auto Keying: ON）。",
                )
            else:
                self.report(
                    {'INFO'},
                    f"{reset_count} 本のボーンを初期姿勢に戻しました"
                    "（Auto Keying: OFF → "
                    "キーは保存されません）。",
                )

        else:
            selected = list(
                context.selected_objects or []
            )

            for obj in selected:
                self._reset_transform_channels(
                    obj,
                    include_delta=(
                        C.RESET_DELTA_TRANSFORMS
                    ),
                )
                reset_count += 1

                if autokey:
                    if self._insert_reset_keys(
                        context,
                        obj,
                        include_delta=(
                            C.RESET_DELTA_TRANSFORMS
                        ),
                    ):
                        keyed_count += 1

            if reset_count == 0:
                self.report(
                    {'WARNING'},
                    "オブジェクトが選択されていません。",
                )
                return {'CANCELLED'}

            if autokey:
                self.report(
                    {'INFO'},
                    f"{reset_count} 個のオブジェクトを"
                    "初期状態に戻し、"
                    f"{keyed_count} 個にキーを挿入しました"
                    "（Auto Keying: ON）。",
                )
            else:
                self.report(
                    {'INFO'},
                    f"{reset_count} 個のオブジェクトを"
                    "初期状態に戻しました"
                    "（Auto Keying: OFF → "
                    "キーは保存されません）。",
                )

        try:
            for area in context.window.screen.areas:
                if area.type in {
                    'VIEW_3D',
                    'DOPESHEET_EDITOR',
                    'GRAPH_EDITOR',
                    'NLA_EDITOR',
                }:
                    area.tag_redraw()
        except Exception:
            pass

        return {'FINISHED'}


# ============================================================
# Graph Editor Shift+MMB
# ============================================================

class GRAPH_OT_maya_slide_keys(
    bpy.types.Operator
):
    bl_idname = "graph.maya_slide_keys"
    bl_label = (
        "キーを軸ロック移動 "
        "(Maya Shift+MMB)"
    )
    bl_options = {
        'REGISTER',
        'UNDO',
        'BLOCKING',
    }

    @classmethod
    def poll(cls, context):
        return (
            context.area is not None and
            context.area.type == 'GRAPH_EDITOR' and
            context.region is not None and
            context.region.type == 'WINDOW'
        )

    @staticmethod
    def _collect_editable_fcurves(context):
        try:
            fcurves = list(
                context.editable_fcurves or []
            )
        except Exception:
            fcurves = []

        if not fcurves:
            try:
                fcurves = list(
                    context.visible_fcurves or []
                )
            except Exception:
                fcurves = []

        return [
            fcurve
            for fcurve in fcurves
            if (
                not getattr(
                    fcurve,
                    "lock",
                    False,
                ) and
                not getattr(
                    fcurve,
                    "hide",
                    False,
                )
            )
        ]

    def invoke(self, context, event):
        region = context.region
        self._targets = []

        for fcurve in (
            self._collect_editable_fcurves(
                context
            )
        ):
            originals = []

            try:
                for point in fcurve.keyframe_points:
                    if point.select_control_point:
                        originals.append((
                            (
                                point.co.x,
                                point.co.y,
                            ),
                            (
                                point.handle_left.x,
                                point.handle_left.y,
                            ),
                            (
                                point.handle_right.x,
                                point.handle_right.y,
                            ),
                        ))
            except Exception:
                continue

            if originals:
                self._targets.append(
                    (
                        fcurve,
                        originals,
                    )
                )

        if not self._targets:
            return {'PASS_THROUGH'}

        space = getattr(
            context,
            "space_data",
            None,
        )

        if getattr(
            space,
            "use_normalization",
            False,
        ):
            self.report(
                {'WARNING'},
                "正規化表示中のため、値の移動量が"
                "表示と一致しない場合があります。",
            )

        self._axis = None
        self._start_region = (
            event.mouse_region_x,
            event.mouse_region_y,
        )

        try:
            self._start_view = (
                region.view2d.region_to_view(
                    self._start_region[0],
                    self._start_region[1],
                )
            )
        except Exception:
            return {'PASS_THROUGH'}

        context.window_manager.modal_handler_add(
            self
        )

        self._set_header(
            context,
            0.0,
            0.0,
        )
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type in {
            'MOUSEMOVE',
            'INBETWEEN_MOUSEMOVE',
        }:
            self._update(
                context,
                event,
            )
            return {'RUNNING_MODAL'}

        if (
            event.type == 'MIDDLEMOUSE' and
            event.value == 'RELEASE'
        ):
            self._finish(context)
            return {'FINISHED'}

        if (
            event.type in {
                'ESC',
                'RIGHTMOUSE',
            } and
            event.value == 'PRESS'
        ):
            self._apply_delta(
                context,
                0.0,
                0.0,
            )
            self._finish(context)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def _update(self, context, event):
        region = context.region

        if region is None:
            return

        mouse_x = event.mouse_region_x
        mouse_y = event.mouse_region_y

        pixel_dx = (
            mouse_x -
            self._start_region[0]
        )
        pixel_dy = (
            mouse_y -
            self._start_region[1]
        )

        if self._axis is None:
            if max(
                abs(pixel_dx),
                abs(pixel_dy),
            ) < C.SLIDE_AXIS_LOCK_THRESHOLD_PX:
                return

            self._axis = (
                'FRAME'
                if abs(pixel_dx) >= abs(pixel_dy)
                else 'VALUE'
            )

        try:
            view = (
                region.view2d.region_to_view(
                    mouse_x,
                    mouse_y,
                )
            )
        except Exception:
            return

        delta_frame = (
            view[0] -
            self._start_view[0]
        )
        delta_value = (
            view[1] -
            self._start_view[1]
        )

        if self._axis == 'FRAME':
            delta_value = 0.0

            if (
                C.SLIDE_SNAP_FRAMES and
                not event.ctrl
            ):
                delta_frame = float(
                    round(delta_frame)
                )
        else:
            delta_frame = 0.0

        self._apply_delta(
            context,
            delta_frame,
            delta_value,
        )

        self._set_header(
            context,
            delta_frame,
            delta_value,
        )

    def _apply_delta(
        self,
        context,
        delta_frame,
        delta_value,
    ):
        for fcurve, originals in self._targets:
            try:
                selected = [
                    point
                    for point in fcurve.keyframe_points
                    if point.select_control_point
                ]
            except Exception:
                continue

            if len(selected) != len(originals):
                continue

            for point, (
                coordinate,
                handle_left,
                handle_right,
            ) in zip(
                selected,
                originals,
            ):
                try:
                    point.co = (
                        coordinate[0] + delta_frame,
                        coordinate[1] + delta_value,
                    )

                    point.handle_left = (
                        handle_left[0] + delta_frame,
                        handle_left[1] + delta_value,
                    )

                    point.handle_right = (
                        handle_right[0] + delta_frame,
                        handle_right[1] + delta_value,
                    )
                except Exception:
                    pass

            try:
                fcurve.update()
            except Exception:
                pass

        try:
            context.area.tag_redraw()
        except Exception:
            pass

    def _set_header(
        self,
        context,
        delta_frame,
        delta_value,
    ):
        try:
            if self._axis == 'FRAME':
                axis_label = "フレーム"
            elif self._axis == 'VALUE':
                axis_label = "値"
            else:
                axis_label = "方向で軸決定"

            context.area.header_text_set(
                f"キー移動 [{axis_label}]  "
                f"Frame {delta_frame:+.1f} / "
                f"Value {delta_value:+.3f}  "
                "(MMB離す: 確定 / ESC: キャンセル / "
                "Ctrl: スナップ解除)"
            )
        except Exception:
            pass

    def _finish(self, context):
        try:
            context.area.header_text_set(
                None
            )
        except Exception:
            pass

        try:
            context.area.tag_redraw()
        except Exception:
            pass


# ============================================================
# View Menu
# ============================================================

class VIEW3D_OT_maya_set_view(
    bpy.types.Operator
):
    bl_idname = "view3d.maya_set_view"
    bl_label = "ビュー切替 (Maya)"
    bl_options = {'REGISTER'}

    view_type: bpy.props.StringProperty(
        default='PERSP'
    )

    _ORTHO_ROTATIONS = {
        'FRONT': (
            0.7071068,
            0.7071068,
            0.0,
            0.0,
        ),
        'BACK': (
            0.0,
            0.0,
            0.7071068,
            0.7071068,
        ),
        'RIGHT': (
            0.5,
            0.5,
            0.5,
            0.5,
        ),
        'LEFT': (
            0.5,
            0.5,
            -0.5,
            -0.5,
        ),
        'TOP': (
            1.0,
            0.0,
            0.0,
            0.0,
        ),
        'BOTTOM': (
            0.0,
            1.0,
            0.0,
            0.0,
        ),
    }

    def execute(self, context):
        view_type = self.view_type
        rv3d = C.resolve_active_region_view3d(
            context
        )

        if view_type == 'PERSP':
            if rv3d is None:
                self.report(
                    {'WARNING'},
                    "3D Viewが見つかりませんでした。",
                )
                return {'CANCELLED'}

            try:
                rv3d.view_perspective = 'PERSP'
            except Exception:
                pass

            self.report(
                {'INFO'},
                "ビュー: Perspective",
            )
            return {'FINISHED'}

        if view_type == 'CAMERA_NEW':
            return self._create_camera_from_view(
                context,
                rv3d,
            )

        if view_type in self._ORTHO_ROTATIONS:
            try:
                result = bpy.ops.view3d.view_axis(
                    type=view_type
                )

                if 'FINISHED' in result:
                    self.report(
                        {'INFO'},
                        f"ビュー: {view_type}",
                    )
                    return {'FINISHED'}
            except Exception:
                pass

            if rv3d is not None:
                try:
                    rv3d.view_perspective = 'ORTHO'
                    rv3d.view_rotation = (
                        mathutils.Quaternion(
                            self._ORTHO_ROTATIONS[
                                view_type
                            ]
                        )
                    )

                    self.report(
                        {'INFO'},
                        f"ビュー: {view_type}",
                    )
                    return {'FINISHED'}
                except Exception:
                    pass

            self.report(
                {'WARNING'},
                "ビューを切り替えられませんでした。",
            )
            return {'CANCELLED'}

        return {'CANCELLED'}

    def _create_camera_from_view(
        self,
        context,
        rv3d,
    ):
        scene = context.scene

        camera_data = bpy.data.cameras.new(
            "MayaCamera"
        )
        camera_object = bpy.data.objects.new(
            "MayaCamera",
            camera_data,
        )

        collection = (
            getattr(
                context,
                "collection",
                None,
            ) or
            scene.collection
        )

        try:
            collection.objects.link(
                camera_object
            )
        except Exception:
            try:
                scene.collection.objects.link(
                    camera_object
                )
            except Exception:
                self.report(
                    {'WARNING'},
                    "カメラをシーンに追加できませんでした。",
                )
                return {'CANCELLED'}

        if rv3d is not None:
            try:
                camera_object.matrix_world = (
                    rv3d.view_matrix.inverted()
                )
            except Exception:
                pass

        try:
            scene.camera = camera_object
        except Exception:
            pass

        if rv3d is not None:
            try:
                rv3d.view_perspective = 'CAMERA'
            except Exception:
                pass

        self.report(
            {'INFO'},
            f"新規カメラ '{camera_object.name}' を作成し、"
            "その視点に入りました。",
        )
        return {'FINISHED'}


class VIEW3D_OT_maya_look_through_camera(
    bpy.types.Operator
):
    bl_idname = (
        "view3d.maya_look_through_camera"
    )
    bl_label = "カメラ視点へ切替 (Maya)"
    bl_options = {'REGISTER', 'UNDO'}

    camera_name: bpy.props.StringProperty(
        name="カメラ名",
        default="",
    )

    def execute(self, context):
        scene = context.scene
        camera_object = None

        try:
            camera_object = scene.objects.get(
                self.camera_name
            )
        except Exception:
            pass

        if camera_object is None:
            try:
                camera_object = bpy.data.objects.get(
                    self.camera_name
                )
            except Exception:
                pass

        if (
            camera_object is None or
            camera_object.type != 'CAMERA'
        ):
            self.report(
                {'WARNING'},
                f"カメラ '{self.camera_name}' が"
                "見つかりませんでした。",
            )
            return {'CANCELLED'}

        try:
            scene.camera = camera_object
        except Exception as error:
            self.report(
                {'WARNING'},
                f"シーンカメラを設定できませんでした: "
                f"{error}",
            )
            return {'CANCELLED'}

        rv3d = C.resolve_active_region_view3d(
            context
        )

        if rv3d is not None:
            try:
                rv3d.view_perspective = 'CAMERA'
            except Exception:
                pass
        else:
            self.report(
                {'WARNING'},
                "3D Viewが見つからないため、"
                "シーンカメラのみ変更しました。",
            )

        C.tag_all_view3d_redraw()

        self.report(
            {'INFO'},
            f"カメラ '{camera_object.name}' の"
            "視点に切り替えました。",
        )
        return {'FINISHED'}


class VIEW3D_MT_maya_view_menu(
    bpy.types.Menu
):
    bl_idname = "VIEW3D_MT_maya_view_menu"
    bl_label = "ビュー切替"

    def draw(self, context):
        layout = self.layout

        layout.operator(
            "view3d.maya_set_view",
            text="Perspective",
            icon='VIEW_PERSPECTIVE',
        ).view_type = 'PERSP'

        layout.separator()

        view_definitions = (
            (
                'FRONT',
                "Front",
                'AXIS_FRONT',
            ),
            (
                'BACK',
                "Back",
                'NONE',
            ),
            (
                'RIGHT',
                "Right",
                'AXIS_SIDE',
            ),
            (
                'LEFT',
                "Left",
                'NONE',
            ),
            (
                'TOP',
                "Top",
                'AXIS_TOP',
            ),
            (
                'BOTTOM',
                "Bottom",
                'NONE',
            ),
        )

        for (
            view_type,
            label,
            icon,
        ) in view_definitions:
            layout.operator(
                "view3d.maya_set_view",
                text=label,
                icon=icon,
            ).view_type = view_type

        try:
            cameras = [
                obj
                for obj in context.scene.objects
                if obj.type == 'CAMERA'
            ]
        except Exception:
            cameras = []

        if cameras:
            layout.separator()

            layout.label(
                text="シーンのカメラ:",
                icon='CAMERA_DATA',
            )

            active_camera = getattr(
                context.scene,
                "camera",
                None,
            )

            for camera_object in sorted(
                cameras,
                key=lambda item: (
                    item.name.lower()
                ),
            ):
                is_active = (
                    camera_object ==
                    active_camera
                )

                operator = layout.operator(
                    "view3d.maya_look_through_camera",
                    text=camera_object.name,
                    icon=(
                        'VIEW_CAMERA'
                        if is_active
                        else 'OUTLINER_OB_CAMERA'
                    ),
                )
                operator.camera_name = (
                    camera_object.name
                )

        layout.separator()

        layout.operator(
            "view3d.maya_set_view",
            text="New Camera（現在の視点）",
            icon='OUTLINER_OB_CAMERA',
        ).view_type = 'CAMERA_NEW'


# ============================================================
# Spawn Menu
# ============================================================

class VIEW3D_MT_maya_spawn_menu(
    bpy.types.Menu
):
    bl_idname = "VIEW3D_MT_maya_spawn_menu"
    bl_label = "オブジェクト作成"

    def draw(self, context):
        layout = self.layout

        mesh_definitions = (
            (
                "mesh.primitive_plane_add",
                "Plane",
                'MESH_PLANE',
            ),
            (
                "mesh.primitive_cube_add",
                "Cube",
                'MESH_CUBE',
            ),
            (
                "mesh.primitive_circle_add",
                "Circle",
                'MESH_CIRCLE',
            ),
            (
                "mesh.primitive_uv_sphere_add",
                "UV Sphere",
                'MESH_UVSPHERE',
            ),
            (
                "mesh.primitive_ico_sphere_add",
                "Ico Sphere",
                'MESH_ICOSPHERE',
            ),
            (
                "mesh.primitive_cylinder_add",
                "Cylinder",
                'MESH_CYLINDER',
            ),
            (
                "mesh.primitive_cone_add",
                "Cone",
                'MESH_CONE',
            ),
            (
                "mesh.primitive_torus_add",
                "Torus",
                'MESH_TORUS',
            ),
        )

        for operator, label, icon in mesh_definitions:
            layout.operator(
                operator,
                text=label,
                icon=icon,
            )

        layout.separator()

        object_definitions = (
            (
                "object.empty_add",
                "Empty",
                'EMPTY_DATA',
            ),
            (
                "object.armature_add",
                "Armature",
                'OUTLINER_OB_ARMATURE',
            ),
            (
                "object.camera_add",
                "Camera",
                'OUTLINER_OB_CAMERA',
            ),
            (
                "object.light_add",
                "Light",
                'OUTLINER_OB_LIGHT',
            ),
            (
                "object.text_add",
                "Text",
                'OUTLINER_OB_FONT',
            ),
        )

        for operator, label, icon in object_definitions:
            layout.operator(
                operator,
                text=label,
                icon=icon,
            )


# ============================================================
# Constraint Menu
# ============================================================

class OBJECT_OT_maya_add_constraint(
    bpy.types.Operator
):
    bl_idname = (
        "object.maya_add_constraint"
    )
    bl_label = (
        "コンストレイント追加 (Maya)"
    )
    bl_options = {'REGISTER', 'UNDO'}

    constraint_type: bpy.props.StringProperty(
        default='COPY_LOCATION'
    )

    def execute(self, context):
        active = context.active_object

        if active is None:
            self.report(
                {'WARNING'},
                "アクティブオブジェクトがありません。",
            )
            return {'CANCELLED'}

        targets = [
            obj
            for obj in (
                context.selected_objects or []
            )
            if obj != active
        ]

        try:
            constraint = active.constraints.new(
                type=self.constraint_type
            )
        except Exception as error:
            self.report(
                {'WARNING'},
                f"コンストレイントを追加できませんでした: "
                f"{error}",
            )
            return {'CANCELLED'}

        if targets:
            target = targets[-1]

            try:
                constraint.target = target
            except Exception:
                pass

            self.report(
                {'INFO'},
                f"{active.name} に {constraint.name} を追加"
                f"（ターゲット: {target.name}）",
            )
        else:
            self.report(
                {'INFO'},
                f"{active.name} に {constraint.name} を追加"
                "（ターゲット未設定）",
            )

        return {'FINISHED'}


class VIEW3D_MT_maya_constraint_menu(
    bpy.types.Menu
):
    bl_idname = (
        "VIEW3D_MT_maya_constraint_menu"
    )
    bl_label = "コンストレイント"

    def draw(self, context):
        layout = self.layout

        definitions = (
            (
                'CHILD_OF',
                "Parent（Child Of）",
                'CONSTRAINT',
            ),
            (
                'COPY_LOCATION',
                "Point（Copy Location）",
                'CON_LOCLIKE',
            ),
            (
                'COPY_ROTATION',
                "Orient（Copy Rotation）",
                'CON_ROTLIKE',
            ),
            (
                'COPY_SCALE',
                "Scale（Copy Scale）",
                'CON_SIZELIKE',
            ),
            (
                'TRACK_TO',
                "Aim（Track To）",
                'CON_TRACKTO',
            ),
            (
                'DAMPED_TRACK',
                "Aim（Damped Track）",
                'CON_TRACKTO',
            ),
        )

        for (
            constraint_type,
            label,
            icon,
        ) in definitions:
            operator = layout.operator(
                "object.maya_add_constraint",
                text=label,
                icon=icon,
            )
            operator.constraint_type = (
                constraint_type
            )

        layout.separator()

        layout.operator(
            "object.constraints_clear",
            text="すべてのコンストレイントを削除",
            icon='X',
        )


# ============================================================
# Class Registration
# ============================================================

# 旧バージョンで登録されていて現在は廃止されたクラス名。
LEGACY_CLASS_NAMES = (
    "VIEW3D_OT_maya_set_micro_manipulator_mode",
)


CLASSES = (
    VIEW3D_OT_maya_set_transform_orientation,
    VIEW3D_OT_maya_toggle_micro_manipulator,
    VIEW3D_OT_maya_set_interaction_mode,
    VIEW3D_MT_maya_manipulator_menu,
    VIEW3D_GGT_maya_micro_manipulator,

    VIEW3D_OT_maya_set_view,
    VIEW3D_OT_maya_look_through_camera,
    VIEW3D_MT_maya_view_menu,
    VIEW3D_MT_maya_spawn_menu,

    OBJECT_OT_maya_add_constraint,
    VIEW3D_MT_maya_constraint_menu,

    VIEW3D_MT_maya_hotbox_pie,
    VIEW3D_OT_maya_space,
    VIEW3D_OT_maya_toggle_controllers,

    SCREEN_OT_maya_keyframe_jump,
    OBJECT_OT_maya_reset_transforms,
    GRAPH_OT_maya_slide_keys,
)


def register_classes():
    # 廃止クラスの残骸を先に除去する。
    for class_name in LEGACY_CLASS_NAMES:
        existing = getattr(
            bpy.types,
            class_name,
            None,
        )

        if existing is not None:
            try:
                bpy.utils.unregister_class(
                    existing
                )
            except Exception:
                pass

    for cls in reversed(CLASSES):
        existing = getattr(
            bpy.types,
            cls.__name__,
            None,
        )

        if existing is not None:
            try:
                bpy.utils.unregister_class(
                    existing
                )
            except Exception:
                pass

    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister_classes():
    for cls in reversed(CLASSES):
        existing = getattr(
            bpy.types,
            cls.__name__,
            None,
        )

        if existing is not None:
            try:
                bpy.utils.unregister_class(
                    existing
                )
            except Exception:
                pass
