import { ref } from 'vue'

export function useDraggableDialog() {
  const position = ref({ x: 0, y: 0 })
  let dragState = null

  function reset() {
    position.value = { x: 0, y: 0 }
  }

  function move(event) {
    if (!dragState) return
    position.value = {
      x: dragState.baseX + event.clientX - dragState.startX,
      y: dragState.baseY + event.clientY - dragState.startY,
    }
  }

  function stop() {
    dragState = null
    window.removeEventListener('mousemove', move)
    window.removeEventListener('mouseup', stop)
  }

  function start(event) {
    stop()
    dragState = {
      startX: event.clientX,
      startY: event.clientY,
      baseX: position.value.x,
      baseY: position.value.y,
    }
    window.addEventListener('mousemove', move)
    window.addEventListener('mouseup', stop)
  }

  return { position, reset, start, stop }
}
