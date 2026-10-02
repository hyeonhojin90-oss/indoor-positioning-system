const fs = require('node:fs');
const path = require('node:path');
const { createRequire } = require('node:module');
const zlib = require('node:zlib');

const projectRoot = path.resolve(__dirname, '..');
const expoPackage = require.resolve('expo/package.json', { paths: [projectRoot] });
const expoCliPackage = createRequire(expoPackage).resolve('@expo/cli/package.json');
const expoRequire = createRequire(expoCliPackage);
const { toQR } = expoRequire('toqr');

const url = process.argv[2];
const outputPath = process.argv[3];
if (!url || !outputPath) {
  throw new Error('Usage: node generate-expo-qr.js <url> <output.svg>');
}

const qr = toQR(url);
const size = Math.sqrt(qr.byteLength) | 0;
const quietZone = 4;
const scale = 12;
const canvasSize = (size + quietZone * 2) * scale;
const cells = [];

for (let row = 0; row < size; row += 1) {
  for (let col = 0; col < size; col += 1) {
    // toqr uses 0 for a dark cell and 1 for a light cell.
    if (qr[row * size + col] === 0) {
      cells.push(`<rect x="${(col + quietZone) * scale}" y="${(row + quietZone) * scale}" width="${scale}" height="${scale}"/>`);
    }
  }
}

const svg = [
  '<?xml version="1.0" encoding="UTF-8"?>',
  `<svg xmlns="http://www.w3.org/2000/svg" width="${canvasSize}" height="${canvasSize}" viewBox="0 0 ${canvasSize} ${canvasSize}" shape-rendering="crispEdges">`,
  '<rect width="100%" height="100%" fill="white"/>',
  '<g fill="black">',
  ...cells,
  '</g>',
  '</svg>',
].join('\n');

function crc32(buffer) {
  let crc = 0xffffffff;
  for (const byte of buffer) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) {
      crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function pngChunk(type, data) {
  const typeBuffer = Buffer.from(type, 'ascii');
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length);
  const checksum = Buffer.alloc(4);
  checksum.writeUInt32BE(crc32(Buffer.concat([typeBuffer, data])));
  return Buffer.concat([length, typeBuffer, data, checksum]);
}

function makePng() {
  const header = Buffer.alloc(13);
  header.writeUInt32BE(canvasSize, 0);
  header.writeUInt32BE(canvasSize, 4);
  header[8] = 8;
  header[9] = 0;
  const rows = [];
  for (let y = 0; y < canvasSize; y += 1) {
    const row = Buffer.alloc(canvasSize + 1, 255);
    row[0] = 0;
    for (let x = 0; x < canvasSize; x += 1) {
      const qrRow = Math.floor(y / scale) - quietZone;
      const qrCol = Math.floor(x / scale) - quietZone;
      if (qrRow >= 0 && qrRow < size && qrCol >= 0 && qrCol < size && qr[qrRow * size + qrCol] === 0) {
        row[x + 1] = 0;
      }
    }
    rows.push(row);
  }
  return Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    pngChunk('IHDR', header),
    pngChunk('IDAT', zlib.deflateSync(Buffer.concat(rows))),
    pngChunk('IEND', Buffer.alloc(0)),
  ]);
}

const resolvedOutput = path.resolve(outputPath);
if (path.extname(resolvedOutput).toLowerCase() === '.png') {
  fs.writeFileSync(resolvedOutput, makePng());
} else {
  fs.writeFileSync(resolvedOutput, svg, 'utf8');
}
console.log(resolvedOutput);
