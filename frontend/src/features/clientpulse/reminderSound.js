let audioContext

function context() {
  const AudioContext = window.AudioContext || window.webkitAudioContext
  if (!AudioContext) return null
  audioContext ||= new AudioContext()
  return audioContext
}

export async function primeReminderAudio() {
  const activeContext = context()
  if (activeContext?.state === 'suspended') await activeContext.resume()
  return activeContext?.state === 'running'
}

function tone(activeContext, frequency, startsAt, duration, volume) {
  const oscillator = activeContext.createOscillator()
  const gain = activeContext.createGain()
  oscillator.type = 'sine'
  oscillator.frequency.setValueAtTime(frequency, startsAt)
  gain.gain.setValueAtTime(0.0001, startsAt)
  gain.gain.exponentialRampToValueAtTime(Math.max(0.0001, volume), startsAt + 0.02)
  gain.gain.exponentialRampToValueAtTime(0.0001, startsAt + duration)
  oscillator.connect(gain)
  gain.connect(activeContext.destination)
  oscillator.start(startsAt)
  oscillator.stop(startsAt + duration + 0.03)
}

export async function playReminderSound(style = 'chime', volume = 70) {
  const activeContext = context()
  if (!activeContext) return false
  if (activeContext.state === 'suspended') await activeContext.resume()
  if (activeContext.state !== 'running') return false

  const level = Math.min(100, Math.max(0, Number(volume))) / 500
  const now = activeContext.currentTime
  const patterns = {
    bell: [[784, 0, 0.42], [1046, 0.13, 0.48]],
    soft: [[523, 0, 0.28], [659, 0.15, 0.32]],
    chime: [[659, 0, 0.30], [880, 0.16, 0.38], [1046, 0.34, 0.44]],
  }
  for (const [frequency, offset, duration] of patterns[style] || patterns.chime) {
    tone(activeContext, frequency, now + offset, duration, level)
  }
  return true
}
