"""
Tiny binary-glTF (.glb) builder used only to create demo 3D models (a toothbrush, a toothpaste
tube and a gift box) so the 3D viewer works before the owner uploads real scans/renders.

Real product models should be exported from Blender / a 3D scanning app as .glb.
"""

import json
import math
import struct

ARRAY_BUFFER, ELEMENT_ARRAY_BUFFER, FLOAT, USHORT = 34962, 34963, 5126, 5123


def _hex(c, a=1.0):
    c = c.lstrip("#")
    # glTF colours are linear; convert from sRGB so they look right.
    def lin(v):
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return [lin(int(c[i:i + 2], 16)) for i in (0, 2, 4)] + [a]


def box(center, size):
    cx, cy, cz = center
    hx, hy, hz = (s / 2 for s in size)
    faces = [  # normal, 4 corners (counter-clockwise seen from outside)
        ((1, 0, 0), [(hx, -hy, hz), (hx, -hy, -hz), (hx, hy, -hz), (hx, hy, hz)]),
        ((-1, 0, 0), [(-hx, -hy, -hz), (-hx, -hy, hz), (-hx, hy, hz), (-hx, hy, -hz)]),
        ((0, 1, 0), [(-hx, hy, hz), (hx, hy, hz), (hx, hy, -hz), (-hx, hy, -hz)]),
        ((0, -1, 0), [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, -hy, hz), (-hx, -hy, hz)]),
        ((0, 0, 1), [(-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)]),
        ((0, 0, -1), [(hx, -hy, -hz), (-hx, -hy, -hz), (-hx, hy, -hz), (hx, hy, -hz)]),
    ]
    pos, nrm, idx = [], [], []
    for n, corners in faces:
        base = len(pos)
        for x, y, z in corners:
            pos.append((cx + x, cy + y, cz + z))
            nrm.append(n)
        idx += [base, base + 1, base + 2, base, base + 2, base + 3]
    return pos, nrm, idx


def cylinder(center, radius, height, segments=32):
    cx, cy, cz = center
    h = height / 2
    pos, nrm, idx = [], [], []
    for i in range(segments + 1):  # side
        a = 2 * math.pi * i / segments
        x, z = math.cos(a), math.sin(a)
        pos += [(cx + radius * x, cy - h, cz + radius * z), (cx + radius * x, cy + h, cz + radius * z)]
        nrm += [(x, 0, z), (x, 0, z)]
    for i in range(segments):
        a, b, c, d = 2 * i, 2 * i + 1, 2 * i + 2, 2 * i + 3
        idx += [a, b, d, a, d, c]
    for y, ny in ((h, 1), (-h, -1)):  # caps
        centre = len(pos)
        pos.append((cx, cy + y, cz))
        nrm.append((0, ny, 0))
        for i in range(segments + 1):
            a = 2 * math.pi * i / segments
            pos.append((cx + radius * math.cos(a), cy + y, cz + radius * math.sin(a)))
            nrm.append((0, ny, 0))
        for i in range(segments):
            p, q = centre + 1 + i, centre + 2 + i
            idx += [centre, q, p] if ny > 0 else [centre, p, q]
    return pos, nrm, idx


def build_glb(parts, name="Paalvi demo"):
    """parts: list of (geometry_tuple, hex_colour, roughness, metallic)."""
    bin_data = bytearray()
    buffer_views, accessors, materials, primitives = [], [], [], []

    def add_view(data, target):
        while len(bin_data) % 4:
            bin_data.append(0)
        buffer_views.append({"buffer": 0, "byteOffset": len(bin_data), "byteLength": len(data), "target": target})
        bin_data.extend(data)
        return len(buffer_views) - 1

    for (pos, nrm, idx), colour, rough, metal in parts:
        flat_p = [c for p in pos for c in p]
        flat_n = [c for n in nrm for c in n]
        vp = add_view(struct.pack(f"<{len(flat_p)}f", *flat_p), ARRAY_BUFFER)
        vn = add_view(struct.pack(f"<{len(flat_n)}f", *flat_n), ARRAY_BUFFER)
        vi = add_view(struct.pack(f"<{len(idx)}H", *idx), ELEMENT_ARRAY_BUFFER)
        mins = [min(p[i] for p in pos) for i in range(3)]
        maxs = [max(p[i] for p in pos) for i in range(3)]
        accessors += [
            {"bufferView": vp, "componentType": FLOAT, "count": len(pos), "type": "VEC3", "min": mins, "max": maxs},
            {"bufferView": vn, "componentType": FLOAT, "count": len(nrm), "type": "VEC3"},
            {"bufferView": vi, "componentType": USHORT, "count": len(idx), "type": "SCALAR"},
        ]
        a = len(accessors) - 3
        materials.append({"pbrMetallicRoughness": {"baseColorFactor": _hex(colour), "metallicFactor": metal, "roughnessFactor": rough}})
        primitives.append({"attributes": {"POSITION": a, "NORMAL": a + 1}, "indices": a + 2, "material": len(materials) - 1})

    while len(bin_data) % 4:
        bin_data.append(0)
    gltf = {
        "asset": {"version": "2.0", "generator": "paalvi-demo"},
        "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0, "name": name}],
        "meshes": [{"name": name, "primitives": primitives}], "materials": materials,
        "accessors": accessors, "bufferViews": buffer_views, "buffers": [{"byteLength": len(bin_data)}],
    }
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    total = 12 + 8 + len(js) + 8 + len(bin_data)
    return (struct.pack("<4sII", b"glTF", 2, total) + struct.pack("<I4s", len(js), b"JSON") + js
            + struct.pack("<I4s", len(bin_data), b"BIN\x00") + bytes(bin_data))


def toothbrush(handle="#C4A070", bristles="#2A2D31"):
    return build_glb([
        (box((0, 0.30, 0), (0.07, 0.56, 0.045)), handle, 0.65, 0.0),
        (box((0, 0.62, 0), (0.05, 0.10, 0.035)), handle, 0.65, 0.0),
        (box((0, 0.73, 0), (0.075, 0.13, 0.04)), handle, 0.65, 0.0),
        (box((0, 0.73, 0.045), (0.06, 0.11, 0.05)), bristles, 0.9, 0.0),
        (box((0, 0.12, 0.024), (0.03, 0.10, 0.004)), "#F8F7F4", 0.4, 0.0),
    ], "Bamboo toothbrush")


def tube(band="#8FC9B9"):
    return build_glb([
        (cylinder((0, 0.33, 0), 0.11, 0.46), "#FBFAF7", 0.35, 0.0),
        (cylinder((0, 0.30, 0), 0.112, 0.10), band, 0.4, 0.0),
        (cylinder((0, 0.07, 0), 0.06, 0.08), "#1E2227", 0.5, 0.1),
        (box((0, 0.58, 0), (0.24, 0.05, 0.03)), "#F1EFEA", 0.4, 0.0),
    ], "Toothpaste tube")


def gift_box(colour="#EADCD5", ribbon="#BFA77A"):
    return build_glb([
        (box((0, 0.17, 0), (0.5, 0.34, 0.36)), colour, 0.6, 0.0),
        (box((0, 0.36, 0), (0.53, 0.06, 0.39)), colour, 0.55, 0.0),
        (box((0, 0.20, 0), (0.07, 0.42, 0.395)), ribbon, 0.3, 0.6),
        (box((0, 0.20, 0), (0.535, 0.42, 0.07)), ribbon, 0.3, 0.6),
    ], "Gift box")
