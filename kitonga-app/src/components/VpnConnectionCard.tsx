/**
 * VpnConnectionCard — Main VPN connect/disconnect UI component
 *
 * This is the core screen users see after purchasing a plan.
 * It shows:
 *   - Big Connect / Disconnect button
 *   - VPN status (Active / Inactive / Connecting...)
 *   - Traffic stats when connected
 *   - Plan expiry countdown
 *   - Error messages
 *
 * Props:
 *   token    — auth token from login
 *   tenantId — selected tenant UUID
 *   onBuyPlan — callback when user needs to purchase/renew
 */

import React from 'react'
import { useVpnConnection } from '../hooks/useVpnConnection'
import { formatBytes } from '../lib/ktn-bridge'

interface VpnConnectionCardProps {
  token: string
  tenantId: string
  onBuyPlan: () => void
}

export const VpnConnectionCard: React.FC<VpnConnectionCardProps> = ({ token, tenantId, onBuyPlan }) => {
  const { status, message, isLoading, error, stats, expiresAt, isNativeAvailable, connect, disconnect } = useVpnConnection({ token, tenantId })

  // -----------------------------------------------------------------------
  // Helpers
  // -----------------------------------------------------------------------

  const isConnected = status === 'connected'
  const isConnecting = status === 'connecting'
  const isDisconnecting = status === 'disconnecting'
  const isBusy = isConnecting || isDisconnecting || isLoading
  const needsPlan = status === 'no_config' || status === 'expired'

  const getExpiryText = () => {
    if (!expiresAt) return null
    const exp = new Date(expiresAt)
    const now = new Date()
    const diff = exp.getTime() - now.getTime()

    if (diff <= 0) return 'Expired'

    const days = Math.floor(diff / (1000 * 60 * 60 * 24))
    const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60))

    if (days > 0) return `${days}d ${hours}h remaining`
    if (hours > 0) return `${hours}h remaining`

    const mins = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))
    return `${mins}m remaining`
  }

  const getStatusColor = () => {
    switch (status) {
      case 'connected':
        return '#22c55e' // green
      case 'connecting':
      case 'disconnecting':
        return '#f59e0b' // amber
      case 'error':
        return '#ef4444' // red
      case 'expired':
        return '#ef4444'
      default:
        return '#94a3b8' // gray
    }
  }

  const getStatusLabel = () => {
    switch (status) {
      case 'connected':
        return 'Connected'
      case 'connecting':
        return 'Connecting...'
      case 'disconnecting':
        return 'Disconnecting...'
      case 'error':
        return 'Error'
      case 'no_config':
        return 'No Active Plan'
      case 'expired':
        return 'Plan Expired'
      default:
        return 'Disconnected'
    }
  }

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  return (
    <div style={styles.card}>
      {/* Status indicator */}
      <div style={styles.statusSection}>
        <div
          style={{
            ...styles.statusDot,
            backgroundColor: getStatusColor(),
            boxShadow: isConnected ? `0 0 12px ${getStatusColor()}` : 'none'
          }}
        />
        <div style={styles.statusInfo}>
          <span style={{ ...styles.statusLabel, color: getStatusColor() }}>{getStatusLabel()}</span>
          <span style={styles.vpnLabel}>KTN — Kitonga Network</span>
        </div>
      </div>

      {/* Error message */}
      {error && (
        <div style={styles.errorBanner}>
          <span style={styles.errorIcon}>⚠️</span>
          <span style={styles.errorText}>{error}</span>
        </div>
      )}

      {/* Not available in browser warning */}
      {!isNativeAvailable && (
        <div style={styles.warningBanner}>
          <span style={styles.warningText}>VPN requires the Kitonga app. This feature is not available in browsers.</span>
        </div>
      )}

      {/* Connect / Disconnect button */}
      <div style={styles.buttonContainer}>
        {needsPlan ? (
          <button style={styles.buyButton} onClick={onBuyPlan}>
            {status === 'expired' ? 'Renew Plan' : 'Buy a Plan'}
          </button>
        ) : isConnected ? (
          <button
            style={{
              ...styles.disconnectButton,
              opacity: isBusy ? 0.6 : 1
            }}
            onClick={disconnect}
            disabled={isBusy}
          >
            {isDisconnecting ? <span style={styles.spinner}>⏳</span> : 'Disconnect'}
          </button>
        ) : (
          <button
            style={{
              ...styles.connectButton,
              opacity: isBusy || !isNativeAvailable ? 0.6 : 1
            }}
            onClick={connect}
            disabled={isBusy || !isNativeAvailable}
          >
            {isConnecting || isLoading ? <span style={styles.spinner}>⏳</span> : 'Connect'}
          </button>
        )}
      </div>

      {/* Traffic stats (visible when connected) */}
      {isConnected && (
        <div style={styles.statsGrid}>
          <div style={styles.statItem}>
            <span style={styles.statLabel}>↓ Download</span>
            <span style={styles.statValue}>{formatBytes(stats.rxBytes)}</span>
          </div>
          <div style={styles.statItem}>
            <span style={styles.statLabel}>↑ Upload</span>
            <span style={styles.statValue}>{formatBytes(stats.txBytes)}</span>
          </div>
          <div style={styles.statItem}>
            <span style={styles.statLabel}>IP Address</span>
            <span style={styles.statValue}>{stats.tunnelIp || '—'}</span>
          </div>
          <div style={styles.statItem}>
            <span style={styles.statLabel}>Server</span>
            <span style={styles.statValue}>{stats.endpoint || '—'}</span>
          </div>
        </div>
      )}

      {/* Plan expiry */}
      {expiresAt && status !== 'expired' && (
        <div style={styles.expiryBar}>
          <span style={styles.expiryIcon}>🕐</span>
          <span style={styles.expiryText}>{getExpiryText()}</span>
        </div>
      )}

      {/* Status message */}
      <p style={styles.message}>{message}</p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Inline styles (Tailwind-like, but pure CSS-in-JS for portability)
// ---------------------------------------------------------------------------

const styles: Record<string, React.CSSProperties> = {
  card: {
    backgroundColor: '#ffffff',
    borderRadius: 16,
    padding: 24,
    margin: 16,
    boxShadow: '0 2px 12px rgba(0,0,0,0.08)',
    fontFamily: "'Inter', -apple-system, sans-serif"
  },
  statusSection: {
    display: 'flex',
    alignItems: 'center',
    gap: 14,
    marginBottom: 20
  },
  statusDot: {
    width: 16,
    height: 16,
    borderRadius: '50%',
    flexShrink: 0,
    transition: 'all 0.3s ease'
  },
  statusInfo: {
    display: 'flex',
    flexDirection: 'column'
  },
  statusLabel: {
    fontSize: 18,
    fontWeight: 700,
    transition: 'color 0.3s ease'
  },
  vpnLabel: {
    fontSize: 13,
    color: '#64748b',
    marginTop: 2
  },
  errorBanner: {
    backgroundColor: '#fef2f2',
    border: '1px solid #fecaca',
    borderRadius: 10,
    padding: '10px 14px',
    marginBottom: 16,
    display: 'flex',
    alignItems: 'center',
    gap: 8
  },
  errorIcon: { fontSize: 16 },
  errorText: { fontSize: 13, color: '#dc2626', lineHeight: 1.4 },
  warningBanner: {
    backgroundColor: '#fffbeb',
    border: '1px solid #fde68a',
    borderRadius: 10,
    padding: '10px 14px',
    marginBottom: 16
  },
  warningText: { fontSize: 13, color: '#92400e', lineHeight: 1.4 },
  buttonContainer: {
    display: 'flex',
    justifyContent: 'center',
    marginBottom: 20
  },
  connectButton: {
    width: '100%',
    padding: '16px 24px',
    borderRadius: 12,
    border: 'none',
    backgroundColor: '#004aad',
    color: '#fff',
    fontSize: 18,
    fontWeight: 700,
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    letterSpacing: 0.5
  },
  disconnectButton: {
    width: '100%',
    padding: '16px 24px',
    borderRadius: 12,
    border: '2px solid #dc2626',
    backgroundColor: 'transparent',
    color: '#dc2626',
    fontSize: 18,
    fontWeight: 700,
    cursor: 'pointer',
    transition: 'all 0.2s ease'
  },
  buyButton: {
    width: '100%',
    padding: '16px 24px',
    borderRadius: 12,
    border: 'none',
    backgroundColor: '#004aad',
    color: '#fff',
    fontSize: 16,
    fontWeight: 600,
    cursor: 'pointer'
  },
  spinner: { fontSize: 20, animation: 'spin 1s linear infinite' },
  statsGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: 12,
    marginBottom: 16
  },
  statItem: {
    backgroundColor: '#f8fafc',
    borderRadius: 10,
    padding: '10px 14px',
    display: 'flex',
    flexDirection: 'column',
    gap: 4
  },
  statLabel: { fontSize: 11, color: '#94a3b8', fontWeight: 500 },
  statValue: { fontSize: 15, color: '#1e293b', fontWeight: 600 },
  expiryBar: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#f0f9ff',
    borderRadius: 10,
    padding: '8px 14px',
    marginBottom: 12
  },
  expiryIcon: { fontSize: 14 },
  expiryText: { fontSize: 13, color: '#0369a1', fontWeight: 500 },
  message: {
    fontSize: 12,
    color: '#94a3b8',
    textAlign: 'center',
    margin: 0
  }
}
