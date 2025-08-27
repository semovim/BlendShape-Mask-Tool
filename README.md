# Blendshape Mask Tool for Maya

A **Maya tool** for applying **blendshape masks** to character meshes using either **predefined JSON mask data** or **interactive region selection**.

Built for workflows with **MetaHuman for Maya** (Unreal Engine’s MetaHuman expression editing tool).

This tool helps prepare the **final blended mesh** that replaces the **expression node** inside the MetaHuman Expression Editor.

By blending a **scanned facial mesh** with the **original MetaHuman expression mesh**, artists can transfer the scan’s expressions onto only the **necessary facial regions** (defined via masks).

---

## ✨ Features

- Apply **pre-defined blendshape masks** from JSON data.
- Create **region selection meshes** with color-coded vertex groups.
- Apply region-based masks by selecting vertices directly in the Maya viewport.
- Smooth mask weights with customizable iterations.
- Quick access to Maya utilities:
    - **BlendShape Paint Tool**
    - **Isolate Base Mesh**
    - **Shape Editor**

---

## 📂 Folder Structure

```
ROOT_DIR/
├─ icons/                      # Button icons
│   ├─ blendShapeEditor.png
│   ├─ IsolateSelected.png
│   └─ 3dPaint.png
├─ data/                       # JSON files
│   ├─ topology_vertex_map.json
│   └─ expression_masks.json
└─ blendshape_mask_tool.py      # Main script

```

> ⚠️ Paths must use forward slashes / in Maya.
> 

---

## 🔧 Installation

1. Download or clone this repository.
2. Place the folder anywhere on your system.
3. Open `blendshape_mask_tool.py` and update the `ROOT_DIR` variable:
    
    ```python
    ROOT_DIR = "C:/blendshape_mask_tool"       # Windows
    
    ```
    
4. Ensure the **icons** and **data** subfolders exist inside your `ROOT_DIR`.

---

## ▶️ Usage

### Launching

1. Prepare your Maya scene:
    - Import or load your **base mesh** (MetaHuman expression mesh).
    - Import or load your **target mesh** (wrapped scan mesh).
2. Open **Maya Script Editor** → switch to the **Python tab**.
3. Copy and paste the full content of `blendshape_mask_tool.py`.
4. Run the script.
5. A UI window titled **"Blendshape Mask Tool"** will appear.

---

### Workflow

### 1. Apply Mask from Data

- Select meshes in order:
    1. **Target Mesh** → wrapped scan mesh.
    2. **Base Mesh** → MetaHuman expression mesh.
- Click **"Apply Mask from data"** to apply the pre-defined mask.

### 2. Region Selection

- Click **"Create Region Selection Mesh"**:
    - Duplicates the base mesh.
    - Applies vertex colors (region map based on metahuman topology texture).
- Select vertices in the viewport → click again to apply region mask.
- Adjust **Smooth Iterations** for blending mask weights.

### 3. Quick Tools

- **Isolate Base Mesh** → Focus only on the masked base mesh.
- **Toggle BS Paint Tool** → Open Maya’s BlendShape Paint Tool for manual tweaks.
- **Shape Editor** → Open Maya’s Shape Editor.

---

## 🧩 Data Files

- **topology_vertex_map.json**
    
    Defines vertex groups and their color IDs.
    
- **expression_masks.json**
    
    Defines base masks for each expression.
    

Both must be placed inside the `data/` folder.

---

## 📝 Notes

- Base mesh names must match the keys in `expression_masks.json`.
