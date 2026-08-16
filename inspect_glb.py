import json
import pathlib
import struct
import zipfile

zip_path = pathlib.Path(r"C:\Users\20222967\Documents\카카오톡 받은 파일\2026. 8. 15.zip")
with zipfile.ZipFile(zip_path) as archive:
    name = archive.namelist()[0]
    data = archive.read(name)

magic, version, length = struct.unpack_from("<4sII", data, 0)
print("file", name, "bytes", len(data))
print("magic", magic.decode("ascii"), "version", version, "length", length)

offset = 12
gltf = None
chunks = []
while offset < len(data):
    chunk_length, chunk_type = struct.unpack_from("<I4s", data, offset)
    offset += 8
    chunk = data[offset : offset + chunk_length]
    offset += chunk_length
    chunks.append((chunk_type.decode("ascii"), chunk_length))
    if chunk_type == b"JSON":
        gltf = json.loads(chunk.decode("utf-8"))

print("chunks", chunks)
print("asset", gltf.get("asset"))
print(
    "counts",
    {
        "scenes": len(gltf.get("scenes", [])),
        "nodes": len(gltf.get("nodes", [])),
        "meshes": len(gltf.get("meshes", [])),
        "materials": len(gltf.get("materials", [])),
        "accessors": len(gltf.get("accessors", [])),
    },
)

mins = []
maxs = []
for accessor in gltf.get("accessors", []):
    if accessor.get("type") == "VEC3" and "min" in accessor and "max" in accessor:
        mins.append(accessor["min"])
        maxs.append(accessor["max"])

if mins:
    mn = [min(value[index] for value in mins) for index in range(3)]
    mx = [max(value[index] for value in maxs) for index in range(3)]
    print("bbox_min", mn)
    print("bbox_max", mx)
    print("bbox_size", [mx[index] - mn[index] for index in range(3)])
else:
    print("bbox", "not found")
