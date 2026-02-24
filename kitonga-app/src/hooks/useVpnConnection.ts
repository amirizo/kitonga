/**
 * React hook: useVpnConnection
 *
 * Manages the full VPN lifecycle from the React WebView:
 *   1. Fetch WireGuard config from backend (/api/app/wireguard-config/)
 *   2. Pass config to native bridge → connect
 *   3. Listen for status changes from native
 *   4. Handle disconnect, expiry, errors
 *
 * Usage in a component:
 *
 *   const { status, connect, disconnect, stats, error, isLoading } = useVpnConnection({
 *     token: "abc123",
 *     tenantId: "5f241f75-...",
 *   });
 *
 *   <button onClick={connect}>Connect</button>
 *   <button onClick={disconnect}>Disconnect</button>
 *   <p>Status: {status}</p>
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { VpnStatus, VpnStatusEvent, WireGuardConfig, connectVpn, disconnectVpn, getVpnStatus, onVpnStatusChange, isNativeAvailable } from '../lib/ktn-bridge'

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const API_BASE = import.meta.env.VITE_API_BASE || 'https://api.kitonga.klikcell.com/api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface UseVpnConnectionProps {
  /** Auth token from login */
  token: string | null
  /** Selected tenant UUID */
  tenantId: string | null
}

interface VpnConnectionState {
  /** Current VPN status */
  status: VpnStatus
  /** Human-readable status message */
  message: string
  /** Whether an API call is in progress */
  isLoading: boolean
  /** Error message if any */
  error: string | null
  /** Traffic stats when connected */
  stats: {
    rxBytes: number
    txBytes: number
    lastHandshake: number | null
    tunnelIp: string | null
    endpoint: string | null
  }
  /** Plan expiry date */
  expiresAt: string | null
  /** Whether native bridge is available */
  isNativeAvailable: boolean
  /** Connect to VPN */
  connect: () => Promise<void>
  /** Disconnect from VPN */
  disconnect: () => Promise<void>
  /** Refresh status from native */
  refreshStatus: () => void
  /** The raw config content (for debug) */
  configContent: string | null
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useVpnConnection({ token, tenantId }: UseVpnConnectionProps): VpnConnectionState {
  const [status, setStatus] = useState<VpnStatus>('disconnected')
  const [message, setMessage] = useState('Not connected')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expiresAt, setExpiresAt] = useState<string | null>(null)
  const [configContent, setConfigContent] = useState<string | null>(null)
  const [stats, setStats] = useState({
    rxBytes: 0,
    txBytes: 0,
    lastHandshake: null as number | null,
    tunnelIp: null as string | null,
    endpoint: null as string | null
  })

  const configRef = useRef<WireGuardConfig | null>(null)

  // -----------------------------------------------------------------------
  // Listen for native status changes
  // -----------------------------------------------------------------------

  useEffect(() => {
    const unsubscribe = onVpnStatusChange((event: VpnStatusEvent) => {
      setStatus(event.status)
      setMessage(event.message)
      if (event.error) setError(event.error)
      if (event.status === 'connected') setError(null)

      setStats({
        rxBytes: event.rxBytes || 0,
        txBytes: event.txBytes || 0,
        lastHandshake: event.lastHandshake || null,
        tunnelIp: event.tunnelIp || null,
        endpoint: event.endpoint || null
      })
    })

    return unsubscribe
  }, [])

  // -----------------------------------------------------------------------
  // On mount, check current native VPN status
  // -----------------------------------------------------------------------

  useEffect(() => {
    if (isNativeAvailable()) {
      const currentStatus = getVpnStatus()
      setStatus(currentStatus.status)
      setMessage(currentStatus.message)
    }
  }, [])

  // -----------------------------------------------------------------------
  // Fetch config from backend
  // -----------------------------------------------------------------------

  const fetchConfig = useCallback(async (): Promise<WireGuardConfig | null> => {
    if (!token) {
      setError('Not logged in')
      return null
    }

    try {
      const url = tenantId ? `${API_BASE}/app/wireguard-config/?tenant_id=${tenantId}` : `${API_BASE}/app/wireguard-config/`

      const response = await fetch(url, {
        headers: {
          Authorization: `Token ${token}`,
          'Content-Type': 'application/json'
        }
      })

      if (response.status === 404) {
        setError('No active KTN plan. Please purchase a plan first.')
        setStatus('no_config')
        return null
      }

      if (response.status === 403) {
        setError('Your KTN plan has expired. Please renew.')
        setStatus('expired')
        return null
      }

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || `Server error ${response.status}`)
      }

      const data = await response.json()

      // data = { download_url, filename, expires_at, config_content }

      const config: WireGuardConfig = {
        configContent: data.config_content,
        tunnelName: 'KTN',
        expiresAt: data.expires_at,
        tenantSlug: data.filename?.replace('-ktn.conf', '') || 'kitonga'
      }

      setExpiresAt(data.expires_at)
      setConfigContent(data.config_content)
      configRef.current = config

      return config
    } catch (e: any) {
      setError(e.message || 'Failed to fetch VPN config')
      return null
    }
  }, [token, tenantId])

  // -----------------------------------------------------------------------
  // Connect
  // -----------------------------------------------------------------------

  const connect = useCallback(async () => {
    setIsLoading(true)
    setError(null)

    try {
      // Step 1: Check native bridge
      if (!isNativeAvailable()) {
        setError('VPN requires the Kitonga app. Please download from Play Store / App Store.')
        setIsLoading(false)
        return
      }

      // Step 2: Fetch fresh config from backend
      setMessage('Fetching VPN configuration...')
      const config = await fetchConfig()

      if (!config) {
        setIsLoading(false)
        return
      }

      // Step 3: Send to native bridge
      setStatus('connecting')
      setMessage('Starting KTN tunnel...')

      const result = connectVpn(config)

      if (!result.success) {
        setError(result.error || 'Failed to connect')
        setStatus('error')
      }
      // Status will be updated via onKTNStatusChange callback from native
    } catch (e: any) {
      setError(e.message || 'Connection failed')
      setStatus('error')
    } finally {
      setIsLoading(false)
    }
  }, [fetchConfig])

  // -----------------------------------------------------------------------
  // Disconnect
  // -----------------------------------------------------------------------

  const disconnect = useCallback(async () => {
    setIsLoading(true)
    setError(null)

    try {
      setStatus('disconnecting')
      setMessage('Disconnecting...')

      const result = disconnectVpn()

      if (!result.success) {
        setError(result.error || 'Failed to disconnect')
      }
    } catch (e: any) {
      setError(e.message || 'Disconnect failed')
    } finally {
      setIsLoading(false)
    }
  }, [])

  // -----------------------------------------------------------------------
  // Refresh status
  // -----------------------------------------------------------------------

  const refreshStatus = useCallback(() => {
    if (isNativeAvailable()) {
      const current = getVpnStatus()
      setStatus(current.status)
      setMessage(current.message)
      if (current.rxBytes) {
        setStats(prev => ({
          ...prev,
          rxBytes: current.rxBytes || 0,
          txBytes: current.txBytes || 0,
          lastHandshake: current.lastHandshake || null,
          tunnelIp: current.tunnelIp || null,
          endpoint: current.endpoint || null
        }))
      }
    }
  }, [])

  // -----------------------------------------------------------------------
  // Auto-refresh stats every 3 seconds while connected
  // -----------------------------------------------------------------------

  useEffect(() => {
    if (status !== 'connected') return

    const interval = setInterval(refreshStatus, 3000)
    return () => clearInterval(interval)
  }, [status, refreshStatus])

  // -----------------------------------------------------------------------
  // Auto-check expiry
  // -----------------------------------------------------------------------

  useEffect(() => {
    if (!expiresAt || status !== 'connected') return

    const expiryDate = new Date(expiresAt)
    const now = new Date()
    const msUntilExpiry = expiryDate.getTime() - now.getTime()

    if (msUntilExpiry <= 0) {
      // Already expired — disconnect
      disconnectVpn()
      setStatus('expired')
      setMessage('Your KTN plan has expired.')
      setError('Plan expired. Please renew to continue.')
      return
    }

    // Schedule auto-disconnect at expiry
    const timer = setTimeout(() => {
      disconnectVpn()
      setStatus('expired')
      setMessage('Your KTN plan has expired.')
      setError('Plan expired. Please renew to continue.')
    }, msUntilExpiry)

    return () => clearTimeout(timer)
  }, [expiresAt, status])

  return {
    status,
    message,
    isLoading,
    error,
    stats,
    expiresAt,
    isNativeAvailable: isNativeAvailable(),
    connect,
    disconnect,
    refreshStatus,
    configContent
  }
}
