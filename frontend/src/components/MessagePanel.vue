<script setup>
import { watch, nextTick, ref, computed } from 'vue'
import { useConversationsStore } from '@/stores/conversations'

const store = useConversationsStore()
const messagesEl = ref(null)

function chatKind(waId) {
  if (waId?.endsWith('@g.us')) return 'group'
  if (waId?.endsWith('@broadcast')) return 'broadcast'
  return 'direct'
}

const isGroup = computed(() => chatKind(store.selectedChat?.wa_chat_id) === 'group')

// The ID of the last message in the list — changes when a new message arrives
// or when the chat is first loaded. Does NOT change when older messages are prepended.
const lastMessageId = computed(() =>
  store.messages.length ? store.messages[store.messages.length - 1].id : null
)

watch(lastMessageId, async (newId) => {
  if (!newId || store.loadingOlderMessages) return
  await nextTick()
  scrollToBottom()
  // Second pass: handles images/media that affect height after initial render
  setTimeout(scrollToBottom, 150)
})

// Also scroll when switching chats (messages may already be loaded)
watch(() => store.selectedChatId, async () => {
  await nextTick()
  scrollToBottom()
})

function scrollToBottom() {
  if (messagesEl.value) {
    messagesEl.value.scrollTop = messagesEl.value.scrollHeight
  }
}

async function onScroll() {
  const el = messagesEl.value
  if (!el || store.loadingOlderMessages || !store.hasMoreMessages) return
  if (el.scrollTop < 80) {
    const prevHeight = el.scrollHeight
    await store.loadOlderMessages()
    await nextTick()
    el.scrollTop = el.scrollHeight - prevHeight
  }
}

function formatTime(dt) {
  if (!dt) return ''
  return new Date(dt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function formatDateLabel(dt) {
  const d = new Date(dt)
  const now = new Date()
  const yesterday = new Date(now)
  yesterday.setDate(now.getDate() - 1)
  if (d.toDateString() === now.toDateString()) return 'Today'
  if (d.toDateString() === yesterday.toDateString()) return 'Yesterday'
  return d.toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
}

function isNewDay(messages, index) {
  if (index === 0) return true
  return new Date(messages[index - 1].message_time).toDateString() !==
         new Date(messages[index].message_time).toDateString()
}

function mimeLabel(mime) {
  if (!mime) return ''
  if (mime.includes('pdf')) return 'PDF'
  if (mime.includes('word') || mime.includes('docx')) return 'Word'
  if (mime.includes('sheet') || mime.includes('xlsx') || mime.includes('csv')) return 'Spreadsheet'
  if (mime.includes('zip') || mime.includes('rar')) return 'Archive'
  const ext = mime.split('/')[1]?.split(';')[0]?.toUpperCase()
  return ext || mime
}

function mediaSrc(url) {
  if (!url) return null
  // url from worker is /media/{sessionId}/{file} — proxy it through /worker-media
  return url.replace(/^\/media\//, '/worker-media/')
}

const senderColors = [
  'text-purple-600','text-blue-600','text-green-600','text-yellow-600',
  'text-pink-600','text-indigo-600','text-teal-600','text-orange-600',
]
function senderColor(name) {
  return senderColors[(name || '').charCodeAt(0) % senderColors.length]
}

// Lightbox
const lightbox = ref(null) // { src, type: 'image'|'video' }

function openLightbox(src, type = 'image') {
  lightbox.value = { src, type }
}
function closeLightbox() {
  lightbox.value = null
}

function onLightboxKey(e) {
  if (e.key === 'Escape') closeLightbox()
}

watch(lightbox, (val) => {
  if (val) window.addEventListener('keydown', onLightboxKey)
  else window.removeEventListener('keydown', onLightboxKey)
})
</script>

<template>
  <div class="flex flex-col overflow-hidden bg-[#efeae2] flex-1 min-w-0 h-full">

    <!-- Empty state -->
    <div v-if="!store.selectedChatId" class="flex-1 flex items-center justify-center bg-[#f0f2f5]">
      <div class="text-center text-gray-400 select-none">
        <div class="w-20 h-20 bg-gray-200 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg class="w-10 h-10 text-gray-400" fill="currentColor" viewBox="0 0 24 24">
            <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z"/>
          </svg>
        </div>
        <p class="text-lg font-light text-gray-600">ChatLens</p>
        <p class="text-sm mt-1 text-gray-400">Select a conversation to view messages</p>
      </div>
    </div>

    <template v-else>
      <!-- Chat header -->
      <div class="bg-[#f0f2f5] border-b border-gray-200 px-4 py-2.5 flex items-center gap-3 shrink-0 shadow-sm">
        <!-- Avatar -->
        <div class="w-10 h-10 rounded-full bg-gray-400 flex items-center justify-center text-white font-semibold shrink-0">
          <svg v-if="isGroup" class="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
            <path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/>
          </svg>
          <span v-else>{{ (store.selectedChat?.display_name || '?')[0].toUpperCase() }}</span>
        </div>

        <!-- Info -->
        <div class="flex-1 min-w-0">
          <p class="font-medium text-gray-900 text-sm truncate">{{ store.selectedChat?.display_name }}</p>
          <p class="text-xs text-gray-500">
            {{ isGroup ? 'Group' : 'Direct message' }} ·
            {{ store.selectedChat?.message_count }} messages
          </p>
        </div>

        <!-- Message count badge -->
        <div class="shrink-0 text-xs text-gray-400 bg-white rounded-full px-2 py-1 border border-gray-200">
          {{ store.messages.length }} loaded
        </div>
      </div>

      <!-- Messages -->
      <div
        ref="messagesEl"
        class="flex-1 overflow-y-auto px-4 py-3"
        style="background-image: url('data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2240%22 height=%2240%22><rect width=%2240%22 height=%2240%22 fill=%22%23e5ddd5%22/></svg>')"
        @scroll.passive="onScroll"
      >
        <!-- Load-older spinner -->
        <div v-if="store.loadingOlderMessages" class="flex justify-center py-3">
          <span class="text-xs text-gray-500 bg-white px-3 py-1 rounded-full shadow-sm">Loading older messages…</span>
        </div>
        <!-- Load-older indicator when more exist but not loading yet -->
        <div v-else-if="store.hasMoreMessages" class="flex justify-center py-2">
          <span class="text-xs text-gray-400">Scroll up to load older messages</span>
        </div>

        <div v-if="store.loadingMessages" class="flex justify-center py-12">
          <span class="text-sm text-gray-500 bg-white px-4 py-1.5 rounded-full shadow-sm">Loading messages...</span>
        </div>

        <div v-else-if="store.messages.length === 0" class="flex justify-center py-12">
          <span class="text-sm text-gray-500 bg-white px-4 py-1.5 rounded-full shadow-sm">No messages yet</span>
        </div>

        <template v-else>
          <template v-for="(msg, i) in store.messages" :key="msg.id">

            <!-- Date separator -->
            <div v-if="isNewDay(store.messages, i)" class="flex justify-center my-3">
              <span class="bg-white text-gray-500 text-xs px-3 py-1 rounded-full shadow-sm">
                {{ formatDateLabel(msg.message_time) }}
              </span>
            </div>

            <!-- Message -->
            <div :class="['flex mb-1', msg.direction === 'outbound' ? 'justify-end' : 'justify-start']">
              <div
                :class="[
                  'relative max-w-xs lg:max-w-md xl:max-w-lg px-3 pt-1.5 pb-1 rounded-lg shadow-sm text-sm',
                  msg.direction === 'outbound'
                    ? 'bg-[#d9fdd3] rounded-tr-none'
                    : 'bg-white rounded-tl-none',
                ]"
              >
                <!-- Sender name in groups (inbound only) -->
                <p
                  v-if="isGroup && msg.direction === 'inbound'"
                  :class="['text-xs font-semibold mb-0.5', senderColor(msg.sender_name)]"
                >
                  {{ msg.sender_name || msg.sender_number }}
                </p>

                <!-- Image -->
                <div v-if="msg.message_type === 'image'" class="mb-1">
                  <img
                    v-if="mediaSrc(msg.media_url)"
                    :src="mediaSrc(msg.media_url)"
                    class="max-w-[240px] max-h-64 rounded-lg object-cover cursor-zoom-in hover:opacity-95 transition-opacity"
                    loading="lazy"
                    @click="openLightbox(mediaSrc(msg.media_url), 'image')"
                  />
                  <div v-else class="w-52 h-36 bg-gray-200 rounded-lg flex flex-col items-center justify-center gap-1 text-gray-400">
                    <svg class="w-8 h-8" fill="currentColor" viewBox="0 0 24 24"><path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z"/></svg>
                    <span class="text-xs">Photo</span>
                  </div>
                  <p v-if="msg.message_text" class="mt-1 whitespace-pre-wrap break-words leading-relaxed text-gray-900 text-sm">{{ msg.message_text }}</p>
                </div>

                <!-- Video -->
                <div v-else-if="msg.message_type === 'video'" class="mb-1">
                  <div
                    v-if="mediaSrc(msg.media_url)"
                    class="relative max-w-[240px] cursor-zoom-in group"
                    @click="openLightbox(mediaSrc(msg.media_url), 'video')"
                  >
                    <video
                      :src="mediaSrc(msg.media_url)"
                      class="max-w-[240px] max-h-64 rounded-lg pointer-events-none"
                      preload="metadata"
                    />
                    <!-- Play overlay hint -->
                    <div class="absolute inset-0 flex items-center justify-center rounded-lg bg-black/20 group-hover:bg-black/30 transition-colors">
                      <div class="w-12 h-12 rounded-full bg-black/50 flex items-center justify-center">
                        <svg class="w-6 h-6 text-white ml-0.5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                      </div>
                    </div>
                  </div>
                  <div v-else class="w-52 h-36 bg-gray-800 rounded-lg flex flex-col items-center justify-center gap-1 text-gray-300">
                    <svg class="w-10 h-10 text-white" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                    <span class="text-xs text-gray-400">Video</span>
                  </div>
                  <p v-if="msg.message_text" class="mt-1 whitespace-pre-wrap break-words leading-relaxed text-gray-900 text-sm">{{ msg.message_text }}</p>
                </div>

                <!-- Audio / Voice note -->
                <div v-else-if="msg.message_type === 'audio'" class="mb-1">
                  <audio
                    v-if="mediaSrc(msg.media_url)"
                    :src="mediaSrc(msg.media_url)"
                    controls
                    class="w-52 h-10"
                    preload="metadata"
                  />
                  <div v-else class="flex items-center gap-3 w-52 py-1">
                    <div class="w-10 h-10 rounded-full flex items-center justify-center shrink-0"
                      :class="msg.direction === 'outbound' ? 'bg-[#b9f5b0]' : 'bg-gray-200'">
                      <svg class="w-5 h-5 text-gray-600" fill="currentColor" viewBox="0 0 24 24"><path d="M12 15c1.66 0 3-1.34 3-3V6c0-1.66-1.34-3-3-3S9 4.34 9 6v6c0 1.66 1.34 3 3 3zm-1-9c0-.55.45-1 1-1s1 .45 1 1v6c0 .55-.45 1-1 1s-1-.45-1-1V6zm6 6c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-2.08c3.39-.49 6-3.39 6-6.92h-2z"/></svg>
                    </div>
                    <div class="flex-1">
                      <div class="flex gap-0.5 items-end h-6">
                        <div v-for="n in 18" :key="n" class="w-1 rounded-full"
                          :class="msg.direction === 'outbound' ? 'bg-[#8fbd87]' : 'bg-gray-300'"
                          :style="`height: ${6 + (n % 5) * 4}px`" />
                      </div>
                      <span class="text-[10px] text-gray-400 mt-0.5 block">Voice message</span>
                    </div>
                  </div>
                </div>

                <!-- Document -->
                <a
                  v-else-if="msg.message_type === 'document'"
                  :href="mediaSrc(msg.media_url) || undefined"
                  :download="msg.media_file_name || true"
                  target="_blank"
                  :class="[
                    'flex items-center gap-3 w-56 rounded-lg px-3 py-2 mb-1',
                    mediaSrc(msg.media_url) ? 'bg-black/5 hover:bg-black/10 cursor-pointer' : 'bg-black/5 cursor-default',
                  ]"
                >
                  <div class="w-9 h-9 rounded-lg bg-blue-500 flex items-center justify-center shrink-0">
                    <svg class="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 24 24"><path d="M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/></svg>
                  </div>
                  <div class="flex-1 min-w-0">
                    <p class="text-xs font-medium text-gray-800 truncate">{{ msg.media_file_name || 'Document' }}</p>
                    <p class="text-[10px] text-gray-500 mt-0.5">
                      {{ mimeLabel(msg.media_mime_type) || 'File' }}
                      <span v-if="mediaSrc(msg.media_url)" class="text-blue-500"> · Download</span>
                    </p>
                  </div>
                </a>

                <!-- Sticker -->
                <div v-else-if="msg.message_type === 'sticker'" class="mb-1">
                  <img
                    v-if="mediaSrc(msg.media_url)"
                    :src="mediaSrc(msg.media_url)"
                    class="w-24 h-24 object-contain cursor-zoom-in hover:opacity-90 transition-opacity"
                    loading="lazy"
                    @click="openLightbox(mediaSrc(msg.media_url), 'image')"
                  />
                  <div v-else class="flex flex-col items-center justify-center w-24 h-24 text-gray-400">
                    <svg class="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M14.828 14.828a4 4 0 01-5.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                    <span class="text-[10px]">Sticker</span>
                  </div>
                </div>

                <!-- Location -->
                <div v-else-if="msg.message_type === 'location'" class="flex items-center gap-2 w-48 bg-black/5 rounded-lg px-3 py-2 mb-1">
                  <svg class="w-6 h-6 text-red-500 shrink-0" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>
                  <div>
                    <p class="text-xs font-medium text-gray-800">Location</p>
                    <p class="text-[10px] text-gray-500">Shared location</p>
                  </div>
                </div>

                <!-- Contact -->
                <div v-else-if="msg.message_type === 'contact'" class="flex items-center gap-2 w-48 bg-black/5 rounded-lg px-3 py-2 mb-1">
                  <div class="w-8 h-8 rounded-full bg-gray-400 flex items-center justify-center shrink-0">
                    <svg class="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 24 24"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>
                  </div>
                  <div>
                    <p class="text-xs font-medium text-gray-800">Contact</p>
                    <p class="text-[10px] text-gray-500">Shared a contact</p>
                  </div>
                </div>

                <!-- Unknown / fallback -->
                <div v-else-if="msg.has_media" class="flex items-center gap-2 text-gray-500 text-xs italic mb-1">
                  <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M16.5 6v11.5c0 2.21-1.79 4-4 4s-4-1.79-4-4V5c0-1.38 1.12-2.5 2.5-2.5s2.5 1.12 2.5 2.5v10.5c0 .55-.45 1-1 1s-1-.45-1-1V6H10v9.5c0 1.38 1.12 2.5 2.5 2.5s2.5-1.12 2.5-2.5V5c0-2.21-1.79-4-4-4S7 2.79 7 5v12.5c0 3.04 2.46 5.5 5.5 5.5s5.5-2.46 5.5-5.5V6h-1.5z"/></svg>
                  <span>{{ msg.message_type || 'Media' }} attachment</span>
                </div>

                <!-- Plain text -->
                <p v-if="msg.message_text && msg.message_type === 'text'" class="whitespace-pre-wrap break-words leading-relaxed text-gray-900">{{ msg.message_text }}</p>

                <!-- Time + tick row -->
                <div :class="['flex items-center justify-end gap-1 mt-0.5 -mb-0.5', msg.direction === 'outbound' ? 'text-[#667781]' : 'text-gray-400']">
                  <span class="text-[10px]">{{ formatTime(msg.message_time) }}</span>
                  <!-- Outbound double tick -->
                  <svg v-if="msg.direction === 'outbound'" class="w-3.5 h-3.5 text-[#53bdeb]" viewBox="0 0 16 11" fill="currentColor">
                    <path d="M11.071.653a.75.75 0 0 1 .052 1.059l-6.25 7a.75.75 0 0 1-1.114-.006L.66 4.906a.75.75 0 1 1 1.134-.984l2.543 2.93 5.675-6.252a.75.75 0 0 1 1.059-.047z"/>
                    <path d="M15 1.5l-6 6.75-1.5-1.5 6-6.75L15 1.5z"/>
                  </svg>
                </div>
              </div>
            </div>

          </template>
        </template>
      </div>

      <!-- Input bar (read-only indicator) -->
      <div class="bg-[#f0f2f5] border-t border-gray-200 px-4 py-3 flex items-center gap-3 shrink-0">
        <div class="flex-1 bg-white rounded-full px-4 py-2 text-sm text-gray-400 border border-gray-200 select-none">
          Read-only mode — messages are captured automatically
        </div>
      </div>
    </template>
  </div>

  <!-- Lightbox -->
  <Teleport to="body">
    <div
      v-if="lightbox"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-sm"
      @click.self="closeLightbox"
    >
      <!-- Close button -->
      <button
        @click="closeLightbox"
        class="absolute top-4 right-4 w-10 h-10 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center transition-colors"
      >
        <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
        </svg>
      </button>

      <!-- Image -->
      <img
        v-if="lightbox.type === 'image'"
        :src="lightbox.src"
        class="max-w-[90vw] max-h-[90vh] object-contain rounded-lg shadow-2xl"
        @click.stop
      />

      <!-- Video -->
      <video
        v-else-if="lightbox.type === 'video'"
        :src="lightbox.src"
        controls
        autoplay
        class="max-w-[90vw] max-h-[90vh] rounded-lg shadow-2xl"
        @click.stop
      />
    </div>
  </Teleport>
</template>
