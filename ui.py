"""
Blendshape Mask Tool

Usage in Maya:
1. Copy the entire content of this file into the Maya Script Editor.
2. Change the value of ROOT_DIR to the absolute path of your project folder.
   Example (Windows): "C:/dna_calibration"
   Example (Linux/macOS): "/home/user/dna_calibration"
   Important: Use forward slashes `/` because Maya requires them in paths.
3. Place the required files inside ROOT_DIR:
   - Icons (PNG files) go in the `icons` folder:
       blendShapeEditor.png, IsolateSelected.png, 3dPaint.png
   - JSON data files go in the `data` folder:
       topology_vertex_map.json, expression_masks.json

Folder structure should look like this:
ROOT_DIR/
├─ icons/                # button icons
│   ├─ blendShapeEditor.png
│   ├─ IsolateSelected.png
│   └─ 3dPaint.png
├─ data/                 # JSON files
│   ├─ topology_vertex_map.json
│   └─ expression_masks.json
└─ blendshape_mask_tool.py  # this script
"""

import maya.cmds as cmds
import maya.api.OpenMaya as om
import maya.mel as mel
import json
import os

from PySide2 import QtWidgets, QtCore, QtGui
from shiboken2 import wrapInstance
import maya.OpenMayaUI as omui


ROOT_DIR = "C:/blendshape_mask_tool"
ICON_DIR = os.path.join(ROOT_DIR, "icons")
DATA_DIR = os.path.join(ROOT_DIR, "data")

ICON_SHAPE_EDITOR = os.path.join(ICON_DIR, "blendShapeEditor.png")
ICON_ISOLATE = os.path.join(ICON_DIR, "IsolateSelected.png")
ICON_PAINT = os.path.join(ICON_DIR, "3dPaint.png")

VERTEX_MAP_PATH = os.path.join(DATA_DIR, "topology_vertex_map.json")
MASK_DATA_PATH  = os.path.join(DATA_DIR, "expression_masks.json")

# === Global State ===
MASK_DATA = {}
VERTEX_GROUPS = {}
VERTEX_TO_COLOR = {}
last_applied_base_mesh = None
region_selection_mode = False
current_region_mesh = None
blendshape_cycle_index = 0
paint_index = 0


def load_vertex_map(file_path):
    global VERTEX_GROUPS, VERTEX_TO_COLOR
    try:
        with open(file_path, "r") as f:
            data = json.load(f)

        VERTEX_GROUPS = {
            tuple(map(int, color.strip("()").split(","))): verts
            for color, verts in data.get("vertex_groups", {}).items()
        }

        VERTEX_TO_COLOR = {
            int(vid): tuple(map(int, color.strip("()").split(",")))
            for vid, color in data.get("vertex_to_color", {}).items()
        }

    except Exception as e:
        cmds.warning(f"Could not load topology vertex map: {e}")
        VERTEX_GROUPS = {}
        VERTEX_TO_COLOR = {}


def load_base_mask(json_path):
    global MASK_DATA
    try:
        with open(json_path) as f:
            MASK_DATA = json.load(f)
    except Exception as e:
        cmds.warning(f"Error loading mask file: {e}")
        MASK_DATA = {}


def get_mask_by_key(mask_key):
    if mask_key not in MASK_DATA:
        cmds.warning(f"Mask key '{mask_key}' not found in loaded data.")
        return None
    return MASK_DATA[mask_key]


def apply_blendshape_mask(target_mesh, base_mesh, mask):
    mask = [min(max(m, 0.0), 1.0) for m in mask]  # clamp 0–1
    vert_count = cmds.polyEvaluate(base_mesh, vertex=True)
    if len(mask) != vert_count:
        cmds.warning(f"Mask length ({len(mask)}) doesn't match vertex count ({vert_count}) of base mesh.")
        return

    blend_node = cmds.blendShape(target_mesh, base_mesh, name=f"{base_mesh}")[0]

    for i, weight in enumerate(mask):
        attr = f"{blend_node}.inputTarget[0].inputTargetGroup[0].targetWeights[{i}]"
        cmds.setAttr(attr, weight)

    cmds.inViewMessage(amg="<hl>Applied blendshape mask</hl>", pos='midCenterTop', fade=True)

    global last_applied_base_mesh

    clean_base = base_mesh.replace("_regionSelect", "")
    last_applied_base_mesh = clean_base


def get_vertex_adjacency(mesh):
    adjacency = {}
    num_verts = cmds.polyEvaluate(mesh, v=True)
    
    for i in range(num_verts):
        adjacency[i] = set()
    
    faces = cmds.polyEvaluate(mesh, f=True)
    
    for f in range(faces):
        verts_in_face = cmds.polyInfo(f"{mesh}.f[{f}]", faceToVertex=True)[0]
        verts = [int(v) for v in verts_in_face.split(':')[1].split()]
        for i, vi in enumerate(verts):
            for vj in verts:
                if vi != vj:
                    adjacency[vi].add(vj)
    
    adjacency = {k: list(v) for k, v in adjacency.items()}
    return adjacency


def smooth_mask(mask, adjacency, iterations=10, weight=0.5):
    new_mask = mask[:]
    for _ in range(iterations):
        temp_mask = new_mask[:]
        for i, neighbors in adjacency.items():
            neighbor_sum = sum(new_mask[j] * weight for j in neighbors)
            temp_mask[i] = (new_mask[i] + neighbor_sum) / (1 + weight * len(neighbors))
        new_mask = temp_mask
    return new_mask


def get_maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)


class BlendMaskTool(QtWidgets.QDialog):
    def __init__(self, parent=get_maya_main_window()):
        super(BlendMaskTool, self).__init__(parent)
        self.setWindowTitle("Blendshape Mask Tool")
        self.setMinimumWidth(350)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)

        # UI Elements
        self.target_field = QtWidgets.QLineEdit()
        self.base_field = QtWidgets.QLineEdit()
        self.apply_mask_btn = QtWidgets.QPushButton("Apply Mask from data")
        self.region_btn = QtWidgets.QPushButton("Create Region Selection Mesh")

        # self.spin_box = QtWidgets.QDoubleSpinBox()
        self.spin_box = QtWidgets.QSpinBox()
        self.spin_box.setRange(1, 30)      
        self.spin_box.setSingleStep(1)    # step size when clicking arrows
        # self.spin_box.setDecimals(1)    # number of decimal places to display
        self.spin_box.setValue(10)        # default value
                        
        self.smooth_label = QtWidgets.QLabel("Smooth iters:")
        self.smooth_label.hide()
        self.spin_box.hide()

        self.create_with_number_btn = QtWidgets.QPushButton("Create Region Mesh (with number)")

        self.isolate_btn = QtWidgets.QPushButton("Isolate Base Mesh")
        self.paint_btn = QtWidgets.QPushButton("Toggle BS Paint Tool")
        self.shape_btn = QtWidgets.QPushButton("Shape Editor")

        self._build_ui()
        self._connect_signals()

        # Load data
        load_vertex_map(VERTEX_MAP_PATH)
        load_base_mask(MASK_DATA_PATH)

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        layout.addWidget(QtWidgets.QLabel("Select meshes in order: 1) Target, 2) Base"))
        layout.addWidget(QtWidgets.QLabel("Target Mesh (1st selected):"))
        layout.addWidget(self.target_field)
        layout.addWidget(QtWidgets.QLabel("Base Mesh (2nd selected):"))
        layout.addWidget(self.base_field)
        layout.addWidget(self.apply_mask_btn)

        spin_layout = QtWidgets.QHBoxLayout()
        spin_layout.addWidget(self.smooth_label)
        spin_layout.addWidget(self.spin_box)
        spin_layout.addWidget(self.region_btn)
        layout.addLayout(spin_layout)

        btn_layout = QtWidgets.QHBoxLayout()
        self._setup_icon_button(self.isolate_btn, ICON_ISOLATE)
        self._setup_icon_button(self.paint_btn, ICON_PAINT)
        self._setup_icon_button(self.shape_btn, ICON_SHAPE_EDITOR)

        btn_layout.addWidget(self.isolate_btn)
        btn_layout.addWidget(self.paint_btn)
        btn_layout.addWidget(self.shape_btn)
        layout.addLayout(btn_layout)

    def _setup_icon_button(self, button, icon_path):
        button.setIcon(QtGui.QIcon(icon_path))
        button.setIconSize(QtCore.QSize(40, 40))
        button.setMinimumHeight(60)

    def _connect_signals(self):
        self.apply_mask_btn.clicked.connect(self.apply_mask_from_ui)
        self.region_btn.clicked.connect(self.toggle_region_selection)
        self.isolate_btn.clicked.connect(self.toggle_isolate_on_object)
        self.paint_btn.clicked.connect(self.toggle_blendshape_paint_tool)
        self.shape_btn.clicked.connect(lambda: cmds.ShapeEditor())

        # Selection watcher
        self.selection_timer = QtCore.QTimer()
        self.selection_timer.timeout.connect(self.on_selection_changed)
        self.selection_timer.start(500)  # 0.5 sec polling

    def on_selection_changed(self):
        if region_selection_mode:
            return  # Ignore updates while in region selection mode

        sel_objects = cmds.ls(selection=True, objectsOnly=True)
        # Ignore region selection mesh
        if sel_objects and all("_regionSelect" in obj for obj in sel_objects):
            return

        if not sel_objects:
            self.target_field.setText("")
            self.base_field.setText("")
            return

        if len(sel_objects) == 1:
            self.target_field.setText(sel_objects[0])
            self.base_field.setText("")
        else:
            self.target_field.setText(sel_objects[0])
            self.base_field.setText(sel_objects[1])

    def apply_mask_from_ui(self):
        target_mesh = self.target_field.text()
        base_mesh = self.base_field.text()
        mask_key = base_mesh.replace('_head_lod0_meshhead_grp', '')

        if not base_mesh or not target_mesh or not mask_key:
            cmds.warning("Missing Base, Target, or Mask Key.")
            return

        mask = get_mask_by_key(mask_key)
        if mask is None:
            return
        apply_blendshape_mask(target_mesh, base_mesh, mask)

    def toggle_region_selection(self):
        global region_selection_mode, current_region_mesh

        if not region_selection_mode:
            sel_mesh = self.create_region_selection_mesh()
            if not sel_mesh:
                return
            region_selection_mode = True
            current_region_mesh = sel_mesh

            # Disable other buttons
            self.isolate_btn.setEnabled(False)
            self.paint_btn.setEnabled(False)
            self.shape_btn.setEnabled(False)
            self.apply_mask_btn.setEnabled(False)

            # Change region button label
            self.region_btn.setText("Apply Region Mask")

            self.smooth_label.show()
            self.spin_box.show()

            cmds.inViewMessage(
                amg="<hl>Select vertices, then click again to apply region mask.</hl>",
                pos='midCenterTop', fade=True
            )

        else:
            self.apply_region_mask_from_selection()

            if current_region_mesh and cmds.objExists(current_region_mesh):
                cmds.delete(current_region_mesh)
            current_region_mesh = None
            region_selection_mode = False

            # Re-enable other buttons
            self.isolate_btn.setEnabled(True)
            self.paint_btn.setEnabled(True)
            self.shape_btn.setEnabled(True)
            self.apply_mask_btn.setEnabled(True)

            # Reset button label
            self.region_btn.setText("Create Region Selection Mesh")
            self.smooth_label.hide()
            self.spin_box.hide()

    def create_region_selection_mesh(self):
        base_mesh = self.base_field.text()
        if not base_mesh or not cmds.objExists(base_mesh):
            cmds.warning("Base mesh is not set or doesn't exist.")
            return

        sel_mesh = cmds.duplicate(base_mesh, name=base_mesh + "_regionSelect")[0]
        cmds.move(20.0, 0, 0, sel_mesh, relative=True)

        sel_dag = om.MSelectionList()
        sel_dag.add(sel_mesh)
        dag_path = sel_dag.getDagPath(0)
        mesh_fn = om.MFnMesh(dag_path)

        vertex_indices = list(VERTEX_TO_COLOR.keys())
        colors = [
            om.MColor((r / 255.0, g / 255.0, b / 255.0, 1.0))
            for r, g, b in VERTEX_TO_COLOR.values()
        ]
        mesh_fn.setVertexColors(colors, vertex_indices)
        cmds.setAttr(f"{sel_mesh}.displayColors", 1)

        cmds.selectMode(component=True)
        cmds.selectType(vertex=True)
        cmds.setToolTo('selectSuperContext')  # Force Select Tool
        
        cmds.inViewMessage(
            amg=f"<hl>Created & colored region selection mesh: {sel_mesh}</hl>",
            pos='midCenterTop', fade=True
        )
        return sel_mesh

    def apply_region_mask_from_selection(self):
        iters = self.spin_box.value()
        sel_vertices = cmds.ls(selection=True, flatten=True)
        if not sel_vertices:
            cmds.warning("Please select vertices.")
            return

        selected_ids = [int(v.split("[")[-1].split("]")[0]) for v in sel_vertices if "[" in v]
        region_group_verts = set()
        for vid in selected_ids:
            if vid in VERTEX_TO_COLOR:
                color = VERTEX_TO_COLOR[vid]
                region_group_verts.update(VERTEX_GROUPS.get(color, []))

        target_mesh = self.target_field.text()
        base_mesh = self.base_field.text()
        if not target_mesh or not base_mesh:
            cmds.warning("Target or Base mesh missing.")
            return

        if base_mesh.endswith("_regionSelect"):
            base_mesh = base_mesh.replace("_regionSelect", "")

        # mask_key = base_mesh.replace('_head_lod0_meshhead_grp', '')
        # Here, base_mesh and mask_key are the same
        mask_key = base_mesh
        base_mask = get_mask_by_key(mask_key)
        if base_mask is None:
            return
        
        adjacency = get_vertex_adjacency(base_mesh)
        final_mask = [1 if i in region_group_verts else bm for i, bm in enumerate(base_mask)]
        mask = smooth_mask(final_mask, adjacency, iterations=iters)

        apply_blendshape_mask(target_mesh, base_mesh, mask)

    def get_active_model_panel(self):
        # Get panel under cursor or currently active panel
        panel = cmds.getPanel(withFocus=True)
        if panel and cmds.getPanel(typeOf=panel) == "modelPanel":
            cam = cmds.modelEditor(panel, query=True, camera=True)
            # ignore default orthographic cameras
            if cam not in ['top', 'front', 'side']:
                return panel
        # fallback: pick first perspective panel
        for p in cmds.getPanel(type='modelPanel'):
            cam = cmds.modelEditor(p, query=True, camera=True)
            if cam not in ['top', 'front', 'side']:
                return p
        # fallback to any model panel
        panels = cmds.getPanel(type='modelPanel')
        return panels[0] if panels else None

    def toggle_isolate_on_object(self):
        global last_applied_base_mesh

        obj = last_applied_base_mesh
        if not obj or not cmds.objExists(obj):
            cmds.warning(f"Object '{obj}' does not exist or mask not applied yet.")
            return

        panel = self.get_active_model_panel()
        if not panel:
            cmds.warning("No valid model panel found.")
            return

        state = cmds.isolateSelect(panel, query=True, state=True)

        if state:
            cmds.isolateSelect(panel, state=False)
            cmds.inViewMessage(amg="<hl>Isolate OFF</hl>", pos='midCenterTop', fade=True)
        else:
            cmds.select(obj, replace=True)
            cmds.isolateSelect(panel, state=True)
            cmds.isolateSelect(panel, addSelected=True) 
            cmds.inViewMessage(amg=f"<hl>Isolated: {obj}</hl>", pos='midCenterTop', fade=True)

    def toggle_blendshape_paint_tool(self):
        global paint_index, last_applied_base_mesh

        base_mesh = last_applied_base_mesh
        if not base_mesh or not cmds.objExists(base_mesh):
            cmds.warning("No valid base mesh found. Apply a mask first.")
            return

        # Strip out regionSelect just in case
        if base_mesh.endswith("_regionSelect"):
            base_mesh = base_mesh.replace("_regionSelect", "")

        history = cmds.listHistory(base_mesh) or []
        blendshape_nodes = cmds.ls(history, type="blendShape")
        if not blendshape_nodes:
            cmds.warning(f"No blendShape node found on {base_mesh}.")
            return

        node = blendshape_nodes[paint_index]

        mel.eval(f'select -r {base_mesh}; artSetToolAndSelectAttr("artAttrCtx", "blendShape.{node}.paintTargetWeights");')
        mel.eval("toolPropertyWindow;")

        cmds.inViewMessage(
            amg=f"<hl>Paint BlendShape Tool: {node} ({paint_index+1}/{len(blendshape_nodes)})</hl>",
            pos='midCenterTop',
            fade=True
        )

        paint_index = (paint_index + 1) % len(blendshape_nodes)


def show_blend_mask_tool():
    global blend_mask_ui
    try:
        blend_mask_ui.close()
    except:
        pass
    blend_mask_ui = BlendMaskTool()
    blend_mask_ui.show()


# Launch
show_blend_mask_tool()
