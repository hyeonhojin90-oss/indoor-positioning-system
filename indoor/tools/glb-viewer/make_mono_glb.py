import json
import struct
import sys
from pathlib import Path


SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("assets/scan.glb")
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("assets/scan_mono.glb")

data = SRC.read_bytes()
magic, version, _ = struct.unpack_from("<4sII", data, 0)
if magic != b"glTF" or version != 2:
    raise SystemExit("not a GLB v2 file")

offset = 12
json_chunk = None
bin_chunk = None
while offset < len(data):
    chunk_length, chunk_type = struct.unpack_from("<I4s", data, offset)
    offset += 8
    chunk = data[offset : offset + chunk_length]
    offset += chunk_length
    if chunk_type == b"JSON":
        json_chunk = chunk
    elif chunk_type == b"BIN\x00":
        bin_chunk = chunk

gltf = json.loads(json_chunk.decode("utf-8"))

for material in gltf.get("materials", []):
    material.pop("emissiveTexture", None)
    material.pop("normalTexture", None)
    material.pop("occlusionTexture", None)
    material["emissiveFactor"] = [0, 0, 0]
    pbr = material.setdefault("pbrMetallicRoughness", {})
    pbr.pop("baseColorTexture", None)
    pbr.pop("metallicRoughnessTexture", None)
    pbr["baseColorFactor"] = [0.72, 0.76, 0.80, 1.0]
    pbr["metallicFactor"] = 0.0
    pbr["roughnessFactor"] = 0.95

json_bytes = json.dumps(gltf, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
json_bytes += b" " * ((4 - len(json_bytes) % 4) % 4)
bin_chunk += b"\x00" * ((4 - len(bin_chunk) % 4) % 4)

total_length = 12 + 8 + len(json_bytes) + 8 + len(bin_chunk)
out = bytearray()
out += struct.pack("<4sII", b"glTF", 2, total_length)
out += struct.pack("<I4s", len(json_bytes), b"JSON")
out += json_bytes
out += struct.pack("<I4s", len(bin_chunk), b"BIN\x00")
out += bin_chunk
OUT.write_bytes(out)
print(OUT, OUT.stat().st_size)
