<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { applyBpsPatch, crc32, formatHex32, sha256Hex, type BpsApplyResult } from './bps'

const PATCH_FILE = 'narutorpg3_chs_v36.bps'
const EXPECTED_SOURCE_SIZE = 67108864
const EXPECTED_TARGET_SIZE = 61997716
const EXPECTED_SOURCE_SHA256 = 'A4D5B1A8AE88899A5CD62791FAF9CA102AA9FBEC768E3C5AFB0AB2EE8C1D1E2C'
const EXPECTED_TARGET_SHA256 = 'B29FEA1B5B7BBD5E2010BD5AF1262676B6B71CB1D6E126847BECCB9A71954BB9'
const PATCH_SHA256 = 'B2EC1D6803866CB6FCB716419B43DBA156807E6C9EEAFE8206DD35DE86E94347'

const version = import.meta.env.VITE_VERSION ?? 'v36'
const patchBytes = ref<Uint8Array | null>(null)
const patchLoadError = ref<string | null>(null)
const loadingPatch = ref(true)
const selectedFile = ref<File | null>(null)
const patching = ref(false)
const patchError = ref<string | null>(null)
const lastResult = ref<BpsApplyResult | null>(null)
const lastOutputSha256 = ref<string | null>(null)

const patchReady = computed(() => patchBytes.value !== null && patchLoadError.value === null)

onMounted(async () => {
  try {
    const base = import.meta.env.BASE_URL
    const prefix = base.endsWith('/') ? base : `${base}/`
    const response = await fetch(`${prefix}${PATCH_FILE}`)
    if (!response.ok) {
      throw new Error(`加载 BPS 补丁失败：HTTP ${response.status}`)
    }
    patchBytes.value = new Uint8Array(await response.arrayBuffer())
  } catch (error) {
    patchLoadError.value = error instanceof Error ? error.message : String(error)
  } finally {
    loadingPatch.value = false
  }
})

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  selectedFile.value = input.files?.[0] ?? null
  patchError.value = null
  lastResult.value = null
  lastOutputSha256.value = null
}

function downloadBytes(bytes: Uint8Array, filename: string) {
  const blob = new Blob([bytes], { type: 'application/octet-stream' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

async function runPatch() {
  if (!patchBytes.value || !selectedFile.value) return

  patching.value = true
  patchError.value = null
  lastResult.value = null
  lastOutputSha256.value = null

  try {
    const source = new Uint8Array(await selectedFile.value.arrayBuffer())
    if (source.length !== EXPECTED_SOURCE_SIZE) {
      throw new Error(`原版 ROM 大小不正确：实际 ${source.length}，期望 ${EXPECTED_SOURCE_SIZE}`)
    }

    const sourceSha256 = await sha256Hex(source)
    if (sourceSha256 !== EXPECTED_SOURCE_SHA256) {
      throw new Error(`原版 ROM SHA256 不匹配：${sourceSha256}`)
    }

    const result = applyBpsPatch(source, patchBytes.value)
    const outputSha256 = await sha256Hex(result.target)
    if (outputSha256 !== EXPECTED_TARGET_SHA256) {
      throw new Error(`补丁后 ROM SHA256 不匹配：${outputSha256}`)
    }

    lastResult.value = result
    lastOutputSha256.value = outputSha256
    downloadBytes(result.target, 'narutorpg3_chs_v36.nds')
  } catch (error) {
    patchError.value = error instanceof Error ? error.message : String(error)
  } finally {
    patching.value = false
  }
}
</script>

<template>
  <main class="min-h-screen bg-zinc-950 text-zinc-100 flex items-center justify-center px-5 py-8">
    <section class="w-full max-w-xl rounded-3xl border border-zinc-800 bg-zinc-900/90 shadow-2xl shadow-black/40 overflow-hidden">
      <div class="border-b border-zinc-800 bg-gradient-to-br from-orange-500/20 via-zinc-900 to-zinc-900 px-7 py-6">
        <p class="text-xs tracking-[0.35em] text-orange-300 uppercase mb-3">Naruto RPG3 CHS</p>
        <h1 class="text-2xl sm:text-3xl font-bold flex items-center gap-3">
          <span class="i-mdi-nintendo-game-boy text-orange-300 text-3xl" />
          火影忍者 RPG3 汉化补丁
        </h1>
        <p class="mt-3 text-sm leading-6 text-zinc-400">
          选择原版 NDS ROM，在浏览器内读取 BPS 补丁并生成汉化版。文件只在本地处理，不会上传。
        </p>
      </div>

      <div class="px-7 py-6">
        <div class="grid gap-3 text-sm mb-6">
          <div class="flex justify-between gap-4 rounded-xl bg-zinc-950/60 border border-zinc-800 px-4 py-3">
            <span class="text-zinc-500">补丁版本</span>
            <span class="font-mono text-orange-200">{{ version }}</span>
          </div>
          <div class="flex justify-between gap-4 rounded-xl bg-zinc-950/60 border border-zinc-800 px-4 py-3">
            <span class="text-zinc-500">BPS SHA256</span>
            <span class="font-mono text-right text-xs text-zinc-300 break-all">{{ PATCH_SHA256 }}</span>
          </div>
        </div>

        <div v-if="loadingPatch" class="rounded-xl border border-zinc-800 bg-zinc-950/60 px-4 py-5 text-zinc-400 flex items-center gap-3">
          <span class="i-svg-spinners-90-ring-with-bg text-orange-300" />
          正在加载 BPS 补丁...
        </div>

        <div v-else-if="patchLoadError" class="rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-4 text-red-200 text-sm">
          {{ patchLoadError }}
        </div>

        <template v-else>
          <div class="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-emerald-200 text-sm mb-5 flex items-center gap-2">
            <span class="i-mdi-check-circle" />
            BPS 已加载，大小 {{ patchBytes?.length.toLocaleString() }} bytes
          </div>

          <label class="block mb-4">
            <span class="block text-sm text-zinc-400 mb-2">选择原版 ROM 文件（.nds）</span>
            <input
              type="file"
              accept=".nds,.bin,application/octet-stream"
              class="block w-full text-sm text-zinc-400 file:mr-4 file:rounded-xl file:border-0 file:bg-orange-400/20 file:px-4 file:py-3 file:font-medium file:text-orange-200 hover:file:bg-orange-400/30 file:cursor-pointer cursor-pointer"
              @change="onFileChange"
            >
          </label>

          <div v-if="selectedFile" class="rounded-xl bg-zinc-950/60 border border-zinc-800 px-4 py-3 text-sm text-zinc-300 mb-5">
            <div class="flex items-center gap-2">
              <span class="i-mdi-file-check text-emerald-300" />
              <span class="truncate">{{ selectedFile.name }}</span>
            </div>
            <div class="mt-2 text-xs text-zinc-500">
              文件大小：{{ selectedFile.size.toLocaleString() }} bytes，选择后会先校验原版 SHA256。
            </div>
          </div>

          <button
            type="button"
            :disabled="!patchReady || !selectedFile || patching"
            class="w-full rounded-2xl bg-orange-400 px-5 py-4 font-bold text-zinc-950 transition hover:bg-orange-300 disabled:bg-zinc-700 disabled:text-zinc-400 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            @click="runPatch"
          >
            <span v-if="patching" class="i-svg-spinners-90-ring-with-bg" />
            <span v-else class="i-mdi-download" />
            {{ patching ? '正在打补丁...' : '生成汉化 ROM 并下载' }}
          </button>

          <div v-if="patchError" class="mt-5 rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-4 text-red-200 text-sm">
            {{ patchError }}
          </div>

          <div v-if="lastResult && lastOutputSha256" class="mt-5 rounded-xl border border-zinc-800 bg-zinc-950/60 px-4 py-4 text-xs text-zinc-400 space-y-2">
            <p class="text-emerald-300 text-sm flex items-center gap-2">
              <span class="i-mdi-check-decagram" />
              校验通过，已开始下载。
            </p>
            <p>Source CRC32: {{ formatHex32(lastResult.sourceCrc32) }}</p>
            <p>Target CRC32: {{ formatHex32(lastResult.targetCrc32) }}</p>
            <p>Output SHA256: <span class="break-all">{{ lastOutputSha256 }}</span></p>
          </div>
        </template>
      </div>
    </section>
  </main>
</template>
