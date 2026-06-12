const BPS_MAGIC = 'BPS1'
const SOURCE_READ = 0
const TARGET_READ = 1
const SOURCE_COPY = 2
const TARGET_COPY = 3

export interface BpsApplyResult {
  target: Uint8Array
  metadata: string
  sourceSize: number
  targetSize: number
  sourceCrc32: number
  targetCrc32: number
  patchCrc32: number
}

class Cursor {
  offset = 0

  constructor(readonly data: Uint8Array) {}

  readByte(): number {
    if (this.offset >= this.data.length) {
      throw new Error('BPS 文件意外结束')
    }
    return this.data[this.offset++]!
  }

  readBytes(length: number): Uint8Array {
    const end = this.offset + length
    if (end > this.data.length) {
      throw new Error('BPS 文件意外结束')
    }
    const out = this.data.subarray(this.offset, end)
    this.offset = end
    return out
  }
}

const crcTable = new Uint32Array(256)
for (let i = 0; i < 256; i++) {
  let value = i
  for (let bit = 0; bit < 8; bit++) {
    value = value & 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1
  }
  crcTable[i] = value >>> 0
}

export function crc32(data: Uint8Array, start = 0, end = data.length): number {
  let value = 0xffffffff
  for (let i = start; i < end; i++) {
    value = crcTable[(value ^ data[i]!) & 0xff]! ^ (value >>> 8)
  }
  return (value ^ 0xffffffff) >>> 0
}

export async function sha256Hex(data: Uint8Array): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', data)
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, '0')).join('').toUpperCase()
}

function readU32LE(data: Uint8Array, offset: number): number {
  if (offset + 4 > data.length) {
    throw new Error('BPS CRC 字段不完整')
  }
  return (
    data[offset]! |
    (data[offset + 1]! << 8) |
    (data[offset + 2]! << 16) |
    (data[offset + 3]! << 24)
  ) >>> 0
}

function decodeNumber(cursor: Cursor): number {
  let value = 0
  let shift = 1

  while (true) {
    const byte = cursor.readByte()
    value += (byte & 0x7f) * shift
    if (byte & 0x80) return value
    shift <<= 7
    value += shift
  }
}

function decodeSignedOffset(cursor: Cursor): number {
  const encoded = decodeNumber(cursor)
  const value = encoded >>> 1
  return encoded & 1 ? -value : value
}

function assertCrc(label: string, actual: number, expected: number) {
  if (actual !== expected) {
    throw new Error(`${label} CRC32 不匹配：实际 ${toHex32(actual)}，期望 ${toHex32(expected)}`)
  }
}

function toHex32(value: number): string {
  return value.toString(16).toUpperCase().padStart(8, '0')
}

export function applyBpsPatch(source: Uint8Array, patch: Uint8Array): BpsApplyResult {
  if (patch.length < 16) {
    throw new Error('BPS 文件过小')
  }

  const magic = new TextDecoder().decode(patch.subarray(0, 4))
  if (magic !== BPS_MAGIC) {
    throw new Error('不是有效的 BPS1 补丁')
  }

  const expectedSourceCrc = readU32LE(patch, patch.length - 12)
  const expectedTargetCrc = readU32LE(patch, patch.length - 8)
  const expectedPatchCrc = readU32LE(patch, patch.length - 4)
  assertCrc('补丁', crc32(patch, 0, patch.length - 4), expectedPatchCrc)
  assertCrc('原版 ROM', crc32(source), expectedSourceCrc)

  const cursor = new Cursor(patch)
  cursor.offset = 4
  const sourceSize = decodeNumber(cursor)
  const targetSize = decodeNumber(cursor)
  const metadataSize = decodeNumber(cursor)
  const metadata = new TextDecoder().decode(cursor.readBytes(metadataSize))

  if (source.length !== sourceSize) {
    throw new Error(`原版 ROM 大小不匹配：实际 ${source.length}，期望 ${sourceSize}`)
  }

  const commandEnd = patch.length - 12
  const target = new Uint8Array(targetSize)
  let targetOffset = 0
  let sourceRelativeOffset = 0
  let targetRelativeOffset = 0

  while (cursor.offset < commandEnd) {
    const encoded = decodeNumber(cursor)
    const action = encoded & 3
    const length = (encoded >>> 2) + 1

    if (targetOffset + length > targetSize) {
      throw new Error('BPS 命令写入超过目标 ROM 大小')
    }

    if (action === SOURCE_READ) {
      const end = targetOffset + length
      if (end > source.length) {
        throw new Error('SourceRead 超出原版 ROM 大小')
      }
      target.set(source.subarray(targetOffset, end), targetOffset)
      targetOffset = end
    } else if (action === TARGET_READ) {
      if (cursor.offset + length > commandEnd) {
        throw new Error('TargetRead 超出 BPS 命令区')
      }
      target.set(patch.subarray(cursor.offset, cursor.offset + length), targetOffset)
      cursor.offset += length
      targetOffset += length
    } else if (action === SOURCE_COPY) {
      sourceRelativeOffset += decodeSignedOffset(cursor)
      const end = sourceRelativeOffset + length
      if (sourceRelativeOffset < 0 || end > source.length) {
        throw new Error('SourceCopy 超出原版 ROM 大小')
      }
      target.set(source.subarray(sourceRelativeOffset, end), targetOffset)
      sourceRelativeOffset = end
      targetOffset += length
    } else if (action === TARGET_COPY) {
      targetRelativeOffset += decodeSignedOffset(cursor)
      if (targetRelativeOffset < 0) {
        throw new Error('TargetCopy 起点无效')
      }
      for (let i = 0; i < length; i++) {
        if (targetRelativeOffset >= targetOffset) {
          throw new Error('TargetCopy 读取超过已生成目标数据')
        }
        target[targetOffset++] = target[targetRelativeOffset++]!
      }
    } else {
      throw new Error(`未知 BPS 动作：${action}`)
    }
  }

  if (cursor.offset !== commandEnd) {
    throw new Error('BPS 命令区解析位置异常')
  }

  assertCrc('目标 ROM', crc32(target), expectedTargetCrc)

  return {
    target,
    metadata,
    sourceSize,
    targetSize,
    sourceCrc32: expectedSourceCrc,
    targetCrc32: expectedTargetCrc,
    patchCrc32: expectedPatchCrc,
  }
}

export function formatHex32(value: number): string {
  return toHex32(value)
}
