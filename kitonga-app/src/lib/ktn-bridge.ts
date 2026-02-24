/**
 * KTN Bridge — JavaScript ↔ Native VPN Communication Layer
 *
 * This module is the ONLY interface between the React WebView UI
 * and the native Android (Kotlin) / iOS (Swift) VPN layer.
 *
 * The native app injects `window.KTNBridge` into the WebView.
 * This module wraps it with type safety, fallbacks, and event handling.
 *
 * Architecture:
 *   React Component → ktn-bridge.ts → window.KTNBridge → Native VpnService
 *
 * Native side must implement:
 *   window.KTNBridge.connect(configJson)   → starts WireGuard tunnel
 *   window.KTNBridge.disconnect()          → tears down tunnel
 *   window.KTNBridge.getStatus()           → returns current VPN state
 *   window.KTNBridge.isAvailable()         → true if native layer exists
 *
 * Native side calls back via:
 *   window.onKTNStatusChange(status)       → pushed from native on state change
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type VpnStatus = 'disconnected' | 'connecting' | 'connected' | 'disconnecting' | 'error' | 'no_config' | 'expired'

export interface VpnStatusEvent {
  status: VpnStatus
  /** Human-readable message, e.g. "Connected to KTN" */
  message: string
  /** Server endpoint IP:port if connected */
  endpoint?: string
  /** Assigned tunnel IP */
  tunnelIp?: string
  /** Bytes received since connection */
  rxBytes?: number
  /** Bytes transmitted since connection */
  txBytes?: number
  /** Timestamp of last handshake (epoch ms) */
  lastHandshake?: number
  /** Error description if status === "error" */
  error?: string
}

export interface WireGuardConfig {
  /** Raw .conf text from backend */
  configContent: string
  /** Tunnel display name — always "KTN" */
  tunnelName: string
  /** Plan expiry ISO string */
  expiresAt: string | null
  /** Tenant slug for identification */
  tenantSlug: string
}

/**
 * Shape of the native bridge object injected into the WebView.
 * Android: `@JavascriptInterface` methods on `WebView.addJavascriptInterface(obj, "KTNBridge")`
 * iOS: `WKScriptMessageHandler` mapped to `window.KTNBridge`
 */
interface NativeBridge {
  connect(configJson: string): void
  disconnect(): void
  getStatus(): string // JSON string of VpnStatusEvent
  isAvailable(): boolean
}

// ---------------------------------------------------------------------------
// Global augmentation — the native app injects this
// ---------------------------------------------------------------------------

declare global {
  interface Window {
    KTNBridge?: NativeBridge
    /** Called BY native when VPN status changes */
    onKTNStatusChange?: (statusJson: string) => void
  }
}

// ---------------------------------------------------------------------------
// Status listener registry
// ---------------------------------------------------------------------------

type StatusListener = (event: VpnStatusEvent) => void
const listeners = new Set<StatusListener>()

/** Register a listener for VPN status changes pushed from native. */
export function onVpnStatusChange(listener: StatusListener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

// Install global callback that native code will call
window.onKTNStatusChange = (statusJson: string) => {
  try {
    const event: VpnStatusEvent = JSON.parse(statusJson)
    listeners.forEach(fn => {
      try {
        fn(event)
      } catch (e) {
        console.error('[KTN Bridge] Listener error:', e)
      }
    })
  } catch (e) {
    console.error('[KTN Bridge] Failed to parse status JSON:', e)
  }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Check if the native VPN bridge is available.
 * Returns false when running in a normal browser (dev mode).
 */
export function isNativeAvailable(): boolean {
  try {
    return !!window.KTNBridge?.isAvailable()
  } catch {
    return false
  }
}

/**
 * Parse a raw WireGuard .conf string into the structured JSON
 * that the native layer expects.
 */
export function parseWireGuardConfig(rawConf: string): {
  interface: {
    privateKey: string
    address: string
    dns: string
    mtu: number
  }
  peer: {
    publicKey: string
    presharedKey: string
    allowedIPs: string
    endpoint: string
    persistentKeepalive: number
  }
} {
  const lines = rawConf.split('\n').map(l => l.trim())

  const iface: Record<string, string> = {}
  const peer: Record<string, string> = {}
  let section = ''

  for (const line of lines) {
    if (line === '[Interface]') {
      section = 'interface'
      continue
    }
    if (line === '[Peer]') {
      section = 'peer'
      continue
    }
    if (!line || line.startsWith('#')) continue

    const eqIdx = line.indexOf('=')
    if (eqIdx === -1) continue

    const key = line.slice(0, eqIdx).trim()
    const value = line.slice(eqIdx + 1).trim()

    if (section === 'interface') iface[key] = value
    if (section === 'peer') peer[key] = value
  }

  return {
    interface: {
      privateKey: iface['PrivateKey'] || '',
      address: iface['Address'] || '',
      dns: iface['DNS'] || '1.1.1.1, 8.8.8.8',
      mtu: parseInt(iface['MTU'] || '1420', 10)
    },
    peer: {
      publicKey: peer['PublicKey'] || '',
      presharedKey: peer['PresharedKey'] || '',
      allowedIPs: peer['AllowedIPs'] || '0.0.0.0/0',
      endpoint: peer['Endpoint'] || '',
      persistentKeepalive: parseInt(peer['PersistentKeepalive'] || '25', 10)
    }
  }
}

/**
 * Send the WireGuard config to the native layer and start the VPN tunnel.
 *
 * The native side will:
 *  1. Parse the config JSON
 *  2. Create a WireGuard tunnel named "KTN"
 *  3. Start the OS VpnService / NetworkExtension
 *  4. Push status updates via window.onKTNStatusChange()
 */
export function connectVpn(config: WireGuardConfig): {
  success: boolean
  error?: string
} {
  if (!isNativeAvailable()) {
    return {
      success: false,
      error: 'Native VPN bridge not available. Please use the Kitonga app.'
    }
  }

  try {
    // Check expiry before connecting
    if (config.expiresAt) {
      const expiry = new Date(config.expiresAt)
      if (expiry < new Date()) {
        return {
          success: false,
          error: 'Your KTN plan has expired. Please renew.'
        }
      }
    }

    const parsed = parseWireGuardConfig(config.configContent)

    const nativePayload = JSON.stringify({
      tunnelName: config.tunnelName,
      tenantSlug: config.tenantSlug,
      expiresAt: config.expiresAt,
      interface: parsed.interface,
      peer: parsed.peer
    })

    window.KTNBridge!.connect(nativePayload)
    return { success: true }
  } catch (e: any) {
    return { success: false, error: e.message || 'Failed to start VPN' }
  }
}

/**
 * Disconnect the active VPN tunnel.
 */
export function disconnectVpn(): { success: boolean; error?: string } {
  if (!isNativeAvailable()) {
    return { success: false, error: 'Native VPN bridge not available.' }
  }

  try {
    window.KTNBridge!.disconnect()
    return { success: true }
  } catch (e: any) {
    return { success: false, error: e.message || 'Failed to disconnect' }
  }
}

/**
 * Get the current VPN status synchronously from the native layer.
 */
export function getVpnStatus(): VpnStatusEvent {
  if (!isNativeAvailable()) {
    return {
      status: 'disconnected',
      message: 'Native bridge not available'
    }
  }

  try {
    const raw = window.KTNBridge!.getStatus()
    return JSON.parse(raw)
  } catch {
    return {
      status: 'disconnected',
      message: 'Failed to get status'
    }
  }
}

/**
 * Format bytes to a human-readable string.
 */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}
