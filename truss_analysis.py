"""
Linear static analysis of a symmetric 2D parallel-chord truss using OpenSeesPy.

Units: N, m, Pa internally; kN and mm for printed results.
This is an educational linear-elastic analysis, not a code-compliance check.
"""

import openseespy.opensees as ops
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Circle
from pathlib import Path
import numpy as np


# ============================================================
# 1. MODEL PARAMETERS
# ============================================================

HEIGHT = 1.5                 # Truss height (m)
PANEL_WIDTH = 2.0            # Panel width (m)
LOAD = 30e3                  # Downward load at B, C and D (N)
E = 200e9                    # Young's modulus (Pa), assumed steel
AREA = 1.0e-3                # Uniform member area (m^2)
EQUILIBRIUM_TOL = 1e-6       # Force residual tolerance (N)

# ============================================================
# 2. NODES AND LABELS
# ============================================================

nodes = {
    1: (0.0, 0.0),                   # A
    2: (PANEL_WIDTH, 0.0),           # B
    3: (2 * PANEL_WIDTH, 0.0),       # C
    4: (3 * PANEL_WIDTH, 0.0),       # D
    5: (4 * PANEL_WIDTH, 0.0),       # E
    6: (0.0, HEIGHT),                # F
    7: (PANEL_WIDTH, HEIGHT),        # G
    8: (2 * PANEL_WIDTH, HEIGHT),    # H
    9: (3 * PANEL_WIDTH, HEIGHT),    # I
    10: (4 * PANEL_WIDTH, HEIGHT),   # J
}

node_names = {
    1: "A", 2: "B", 3: "C", 4: "D", 5: "E",
    6: "F", 7: "G", 8: "H", 9: "I", 10: "J",
}

# ============================================================
# 3. MEMBER CONNECTIVITY
# ============================================================

bottom_chord = [(1, 2), (2, 3), (3, 4), (4, 5)]
top_chord = [(6, 7), (7, 8), (8, 9), (9, 10)]
verticals = [(1, 6), (2, 7), (3, 8), (4, 9), (5, 10)]
diagonals = [(6, 2), (7, 3), (10, 4), (9, 3)]

members = bottom_chord + top_chord + verticals + diagonals

assert len(nodes) == 10
assert len(members) == 17

# ============================================================
# 4. BUILD THE OPENSEES MODEL
# ============================================================

ops.wipe()
ops.model("basic", "-ndm", 2, "-ndf", 2)

for tag, (x, y) in nodes.items():
    ops.node(tag, x, y)

# A: pinned support; E: roller support (vertical restraint only)
ops.fix(1, 1, 1)
ops.fix(5, 0, 1)

ops.uniaxialMaterial("Elastic", 1, E)

for element_tag, (i, j) in enumerate(members, start=1):
    ops.element("Truss", element_tag, i, j, AREA, 1)

# ============================================================
# 5. APPLY LOADS
# ============================================================

loaded_nodes = (2, 3, 4)

ops.timeSeries("Linear", 1)
ops.pattern("Plain", 1, 1)

for node_tag in loaded_nodes:
    ops.load(node_tag, 0.0, -LOAD)

# ============================================================
# 6. LINEAR STATIC ANALYSIS
# ============================================================

ops.constraints("Plain")
ops.numberer("RCM")
ops.system("BandGeneral")
ops.algorithm("Linear")
ops.integrator("LoadControl", 1.0)
ops.analysis("Static")

analysis_status = ops.analyze(1)
if analysis_status != 0:
    ops.wipe()
    raise RuntimeError(
        "OpenSeesPy analysis failed. Check the model, restraints, "
        "member connectivity, and installed OpenSeesPy version."
    )

# ============================================================
# 7. SUPPORT REACTIONS
# ============================================================

ops.reactions()

reactions = {
    tag: (ops.nodeReaction(tag, 1), ops.nodeReaction(tag, 2))
    for tag in (1, 5)
}

print("\nSUPPORT REACTIONS")
print("-" * 55)
for tag, (rx, ry) in reactions.items():
    print(
        f"Node {node_names[tag]}: "
        f"Rx = {rx / 1000:10.4f} kN, "
        f"Ry = {ry / 1000:10.4f} kN"
    )

# ============================================================
# 8. NODAL DISPLACEMENTS
# ============================================================

print("\nNODAL DISPLACEMENTS")
print("-" * 55)
for tag in nodes:
    ux = ops.nodeDisp(tag, 1) * 1000.0
    uy = ops.nodeDisp(tag, 2) * 1000.0
    print(
        f"Node {node_names[tag]}: "
        f"Ux = {ux:10.5f} mm, Uy = {uy:10.5f} mm"
    )

# ============================================================
# 9. MEMBER AXIAL FORCES
# ============================================================

print("\nMEMBER AXIAL FORCES")
print("-" * 65)
print("Sign convention: tension positive; compression negative.")

member_forces = {}
for element_tag, (i, j) in enumerate(members, start=1):
    response = ops.eleResponse(element_tag, "axialForce")
    if response is None or len(response) == 0:
        raise RuntimeError(
            f"Could not retrieve axial force for element {element_tag}."
        )

    force_n = float(response[0])
    member_forces[element_tag] = force_n

    if force_n > 1e-6:
        nature = "Tension"
    elif force_n < -1e-6:
        nature = "Compression"
    else:
        nature = "Zero"

    print(
        f"Element {element_tag:02d} ({node_names[i]}-{node_names[j]}): "
        f"N = {force_n / 1000:10.4f} kN ({nature})"
    )

# ============================================================
# 10. GLOBAL EQUILIBRIUM CHECK
# ============================================================

applied_fx = 0.0
applied_fy = -len(loaded_nodes) * LOAD
reaction_fx = sum(value[0] for value in reactions.values())
reaction_fy = sum(value[1] for value in reactions.values())

residual_x = applied_fx + reaction_fx
residual_y = applied_fy + reaction_fy

print("\nGLOBAL FORCE EQUILIBRIUM")
print("-" * 55)
print(f"Horizontal residual: {residual_x / 1000:.8f} kN")
print(f"Vertical residual:   {residual_y / 1000:.8f} kN")

if max(abs(residual_x), abs(residual_y)) > EQUILIBRIUM_TOL:
    raise RuntimeError(
        "Global equilibrium check failed: force residual exceeds tolerance."
    )
print("Equilibrium check: PASSED")

# ============================================================
# 11. STRUCTURAL SCHEMATIC
# ============================================================

fig, ax = plt.subplots(figsize=(12, 5.5))

# Members, grouped by type for a clearer drawing
for group, color, linewidth in (
    (bottom_chord, "#263746", 2.2),
    (top_chord, "#263746", 2.2),
    (verticals, "#64748b", 1.8),
    (diagonals, "#0f766e", 2.0),
):
    for i, j in group:
        xi, yi = nodes[i]
        xj, yj = nodes[j]
        ax.plot(
            [xi, xj], [yi, yj],
            color=color, linewidth=linewidth, zorder=2,
            solid_capstyle="round"
        )

# Nodes and labels
for tag, (x, y) in nodes.items():
    ax.add_patch(Circle((x, y), radius=0.055, facecolor="white",
                        edgecolor="#17202a", linewidth=1.3, zorder=5))
    label_offset = 0.16 if tag <= 5 else 0.16
    ax.text(x, y + label_offset, node_names[tag], ha="center",
            va="bottom", fontsize=10, fontweight="bold", zorder=6)

# Applied downward loads: arrows start at the loaded joints and point down
for tag in loaded_nodes:
    x, y = nodes[tag]
    ax.annotate(
        "",
        xy=(x, y - 0.62),
        xytext=(x, y - 0.04),
        arrowprops=dict(arrowstyle="-|>", color="#c0392b", lw=2.0,
                        mutation_scale=14),
        zorder=4,
    )
    ax.text(x + 0.12, y - 0.43, f"{LOAD / 1000:g} kN",
            color="#c0392b", fontsize=9, ha="left", va="center")

# Pinned support at A
xa, ya = nodes[1]
ax.add_patch(Polygon(
    [(xa, ya - 0.08), (xa - 0.22, ya - 0.38), (xa + 0.22, ya - 0.38)],
    closed=True, facecolor="#dbeafe", edgecolor="#334155",
    linewidth=1.2, zorder=3
))
ax.plot([xa - 0.30, xa + 0.30], [ya - 0.42, ya - 0.42],
        color="#334155", linewidth=1.4, zorder=3)
ax.text(xa, ya - 0.52, "Pinned", ha="center", va="top", fontsize=9)

# Roller support at E
xe, ye = nodes[5]
ax.add_patch(Polygon(
    [(xe, ye - 0.08), (xe - 0.22, ye - 0.35), (xe + 0.22, ye - 0.35)],
    closed=True, facecolor="#dbeafe", edgecolor="#334155",
    linewidth=1.2, zorder=3
))
for dx in (-0.13, 0.13):
    ax.add_patch(Circle((xe + dx, ye - 0.40), radius=0.045,
                        facecolor="white", edgecolor="#334155",
                        linewidth=1.0, zorder=3))
ax.plot([xe - 0.30, xe + 0.30], [ye - 0.48, ye - 0.48],
        color="#334155", linewidth=1.4, zorder=3)
ax.text(xe, ye - 0.57, "Roller", ha="center", va="top", fontsize=9)

ax.set_title(
    "Symmetric 2D Parallel-Chord Truss — Geometry and Loading",
    fontsize=13, fontweight="bold", pad=14
)
ax.set_xlabel("x (m)")
ax.set_ylabel("y (m)")
ax.set_xlim(-0.75, 8.75)
ax.set_ylim(-1.15, 2.05)
ax.set_aspect("equal", adjustable="box")
ax.grid(True, linestyle="--", linewidth=0.6, alpha=0.35)
fig.tight_layout()

output_image = Path(__file__).resolve().with_name("truss_schema.png")
fig.savefig(output_image, dpi=300, bbox_inches="tight")
print(f"\nSchematic saved to: {output_image}")

plt.show()
ops.wipe()

# ============================================================
# 12. AXIAL FORCE DIAGRAM WITH MEMBER FORCE LABELS
# ============================================================

fig, ax = plt.subplots(figsize=(14, 7))

# Colors for axial force classification
COLOR_TENSION = "#D62728"       # Red: tension
COLOR_COMPRESSION = "#1565C0"   # Blue: compression
COLOR_ZERO = "#555555"          # Gray: approximately zero

# Draw members and annotate their axial forces
for element_tag, (i, j) in enumerate(members, start=1):

    xi, yi = nodes[i]
    xj, yj = nodes[j]

    # Axial force in kN
    force_kn = member_forces[element_tag] / 1000.0

    # Determine force nature and color
    if force_kn > 1e-6:
        color = COLOR_TENSION
    elif force_kn < -1e-6:
        color = COLOR_COMPRESSION
    else:
        color = COLOR_ZERO

    # Draw member
    ax.plot(
        [xi, xj],
        [yi, yj],
        color=color,
        linewidth=2.2,
        zorder=2
    )

    # Midpoint of member
    xm = (xi + xj) / 2.0
    ym = (yi + yj) / 2.0

    # Small perpendicular offset to improve label readability
    dx = xj - xi
    dy = yj - yi
    length = np.hypot(dx, dy)

    nx = -dy / length
    ny = dx / length

    offset = 0.13
    label_x = xm + offset * nx
    label_y = ym + offset * ny

    # Force label
    ax.text(
        label_x,
        label_y,
        f"{force_kn:+.2f} kN",
        fontsize=8.5,
        color=color,
        ha="center",
        va="center",
        fontweight="bold",
        bbox=dict(
            facecolor="white",
            edgecolor=color,
            boxstyle="round,pad=0.20",
            linewidth=0.7,
            alpha=0.95
        ),
        zorder=4
    )

# Draw nodes and their names
for tag, (x, y) in nodes.items():
    ax.scatter(
        x, y,
        s=28,
        color="black",
        zorder=5
    )

    ax.annotate(
        node_names[tag],
        (x, y),
        xytext=(0, 9),
        textcoords="offset points",
        ha="center",
        fontsize=9,
        fontweight="bold"
    )

# Plot title and axes
ax.set_title(
    "Axial Forces in Truss Members",
    fontsize=14,
    fontweight="bold",
    pad=15
)

ax.set_xlabel("x (m)")
ax.set_ylabel("y (m)")

ax.set_aspect("equal", adjustable="box")
ax.grid(True, linestyle="--", alpha=0.3)

# Legend
from matplotlib.lines import Line2D

legend_elements = [
    Line2D([0], [0], color=COLOR_TENSION, lw=2.5,
           label="Tension (+)"),
    Line2D([0], [0], color=COLOR_COMPRESSION, lw=2.5,
           label="Compression (-)"),
    Line2D([0], [0], color=COLOR_ZERO, lw=2.5,
           label="Approximately zero")
]

ax.legend(handles=legend_elements, loc="upper right")

# Leave room around the structure and labels
ax.set_xlim(-0.8, 8.8)
ax.set_ylim(-0.7, 2.1)

fig.tight_layout()

# Save image in the same directory as this Python file
output_path = Path(__file__).resolve().parent / "truss_axial_forces.png"

fig.savefig(
    output_path,
    dpi=300,
    bbox_inches="tight",
    facecolor="white"
)

print(f"\nAxial force figure saved to: {output_path}")

plt.show()