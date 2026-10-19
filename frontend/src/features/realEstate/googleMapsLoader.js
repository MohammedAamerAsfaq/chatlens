let loadPromise
let loadedKey = ''

export function loadGoogleMaps(apiKey) {
  if (window.google?.maps) return Promise.resolve(window.google.maps)
  if (loadPromise && loadedKey === apiKey) return loadPromise

  loadedKey = apiKey
  const callbackName = `__chatlensMapsReady_${Date.now()}`
  loadPromise = new Promise((resolve, reject) => {
    window[callbackName] = () => {
      delete window[callbackName]
      resolve(window.google.maps)
    }
    const script = document.createElement('script')
    const params = new URLSearchParams({
      key: apiKey,
      loading: 'async',
      callback: callbackName,
      v: 'weekly',
      region: 'AE',
      language: 'en',
      auth_referrer_policy: 'origin',
    })
    script.src = `https://maps.googleapis.com/maps/api/js?${params}`
    script.async = true
    script.onerror = () => {
      delete window[callbackName]
      loadPromise = null
      reject(new Error('Google Maps JavaScript could not be loaded.'))
    }
    document.head.appendChild(script)
  })
  return loadPromise
}
