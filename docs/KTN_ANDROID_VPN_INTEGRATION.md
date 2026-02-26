# KTN Android Integration Guide

## What is KTN?

**KTN (Kitonga Network)** is a **paid internet access product**. It lets users access the internet from anywhere — **even outside WiFi hotspot areas**. It is NOT a traditional VPN service. It is a **private encrypted internet tunnel**.

**User pays → Gets private encrypted tunnel → Direct routed internet.**

**User flow:**

1. User opens the Kitonga app
2. User purchases a KTN plan (e.g. 30 days)
3. App calls the API to get tunnel credentials
4. App creates a private encrypted tunnel using WireGuard protocol
5. **User now has internet access** — all traffic routed securely

**Key difference from VPN:** Users don't think of this as "VPN". They think of it as "buying internet". The tunnel is just the delivery mechanism.

---

## Architecture

### System Components

| Component | Role | Description |
|-----------|------|-------------|
| **VPS (Ubuntu)** | **WireGuard Hub** | Public-facing server with public IP. Accepts encrypted tunnels from user phones. Routes traffic onward. |
| **MikroTik Router** | **Infrastructure Controller** | Controls bandwidth, traffic shaping, user management. Connected to VPS via secure site-to-site tunnel. |
| **Android App** | **KTN Client** | Creates encrypted tunnel to VPS. User gets internet through this tunnel. |

### Full Traffic Flow

```
    User's Phone                    VPS (Public IP)                  MikroTik Router
   ┌─────────────┐              ┌──────────────────┐              ┌─────────────────┐
   │  KTN App    │   Encrypted  │  WireGuard Hub   │  Site-to-    │  Infrastructure │
   │  10.200.0.x │◄────Tunnel──►│  66.29.143.116   │◄───Site────►│  Controller     │
   │             │   UDP 51820  │  wg0: 10.100.0.1 │   Tunnel     │  10.100.0.40    │
   └─────────────┘              └────────┬─────────┘              └────────┬────────┘
                                         │                                 │
                                    NAT + Routing                    Traffic Control
                                         │                          Bandwidth / QoS
                                         ▼                                 │
                                    ┌─────────┐                           ▼
                                    │ Internet │◄──────────────────── Internet
                                    └─────────┘
```

### How It Works (Step by Step)

1. **User activates KTN** → App creates encrypted WireGuard tunnel to VPS (`66.29.143.116:51820`)
2. **All phone traffic** enters the encrypted tunnel → arrives at VPS
3. **VPS routes traffic** → Through site-to-site tunnel to MikroTik for traffic control
4. **MikroTik handles** → Bandwidth management, QoS, user policies
5. **Traffic exits** → To the internet
6. **Response comes back** → MikroTik → VPS → Encrypted tunnel → User's phone

### Network Addressing

| Network | Range | Purpose |
|---------|-------|---------|
| `10.100.0.0/24` | Infrastructure | VPS ↔ MikroTik site-to-site tunnel |
| `10.200.0.0/24` | Clients | User phones (each user gets a unique /32 IP) |

### Security

- **UFW firewall** enabled on VPS — only ports 22, 80, 443, 51820/udp open
- **All user traffic encrypted** end-to-end between phone and VPS
- **Site-to-site tunnel** encrypted between VPS and MikroTik
- **NAT masquerade** — user IPs are not exposed to the internet
- **IP forwarding** enabled for routing between wg0 and eth0
- **Per-user keys** — each user has unique private key, public key, and preshared key

This document describes exactly how the Android app must build and activate the KTN tunnel using the credentials returned by the backend API.

---

## Step 1: Get Tunnel Credentials from API

### Request

```
GET /api/vpn/session/
Headers:
  Authorization: Token <user_auth_token>
  X-Tenant-Id: <tenant_uuid>  (optional)
```

### Response (200 OK)

```json
{
  "success": true,
  "tunnel_name": "KTN",
  "interface": {
    "private_key": "KPdwlsTVNwBo0v3H0UkdI1UjQfmJdm2/oQSfExvYi1E=",
    "address": "10.200.0.2/32",
    "dns": "1.1.1.1, 8.8.8.8",
    "mtu": 1420
  },
  "peer": {
    "public_key": "0ItNRIAXdf090Z3RpIVsmrA1JjRJrZveYweNZXXo3mQ=",
    "preshared_key": "QjQIPP6E94twMHcdwjENSF5QFkrY9XggvhifbMoUPYM=",
    "endpoint": "66.29.143.116:51820",
    "allowed_ips": "0.0.0.0/0",
    "persistent_keepalive": 25
  },
  "plan": {
    "name": "Basic KTN",
    "expires_at": "2026-03-26T13:03:06.753769+00:00",
    "duration_days": 30
  },
  "tenant": {
    "id": "5f241f75-6fc5-4bc3-9320-ca1b5eb10c43",
    "name": "Kitonga WiFi"
  }
}
```

---

## Step 2: Build the KTN Tunnel Configuration

Using the API response, construct a WireGuard config (KTN uses WireGuard protocol). This is the equivalent `.conf` file:

```ini
[Interface]
PrivateKey = KPdwlsTVNwBo0v3H0UkdI1UjQfmJdm2/oQSfExvYi1E=
Address = 10.200.0.2/32
DNS = 1.1.1.1, 8.8.8.8
MTU = 1420

[Peer]
PublicKey = 0ItNRIAXdf090Z3RpIVsmrA1JjRJrZveYweNZXXo3mQ=
PresharedKey = QjQIPP6E94twMHcdwjENSF5QFkrY9XggvhifbMoUPYM=
AllowedIPs = 0.0.0.0/0
Endpoint = 66.29.143.116:51820
PersistentKeepalive = 25
```

### Field Mapping (API → WireGuard)

| API Response Field          | WireGuard Config Field | Section       | Notes                                                     |
| --------------------------- | ---------------------- | ------------- | --------------------------------------------------------- |
| `interface.private_key`     | `PrivateKey`           | `[Interface]` | Base64, 44 chars. **Secret — never log this.**            |
| `interface.address`         | `Address`              | `[Interface]` | Always `/32` (single IP).                                 |
| `interface.dns`             | `DNS`                  | `[Interface]` | Comma-separated. May contain spaces after comma.          |
| `interface.mtu`             | `MTU`                  | `[Interface]` | Usually `1420`.                                           |
| `peer.public_key`           | `PublicKey`            | `[Peer]`      | Base64, 44 chars. This is the **server's** public key.    |
| `peer.preshared_key`        | `PresharedKey`         | `[Peer]`      | Base64, 44 chars. **Optional** — omit if empty string.    |
| `peer.endpoint`             | `Endpoint`             | `[Peer]`      | Format: `IP:PORT`. This is where the phone sends packets. |
| `peer.allowed_ips`          | `AllowedIPs`           | `[Peer]`      | `0.0.0.0/0` = route ALL traffic through KTN tunnel.       |
| `peer.persistent_keepalive` | `PersistentKeepalive`  | `[Peer]`      | Seconds. Keeps NAT mappings alive.                        |

---

## Step 3: Android WireGuard Implementation (KTN Tunnel)

### Option A: Using `wireguard-android` Library (Recommended)

The official WireGuard Android library (`com.wireguard.android.tunnel`) provides a clean API. KTN uses the WireGuard protocol under the hood for its encrypted tunnel.

#### Gradle Dependency

```groovy
implementation 'com.wireguard.android:tunnel:1.0.20230706'
```

#### Kotlin Code

```kotlin
import com.wireguard.config.Config
import com.wireguard.config.Interface
import com.wireguard.config.Peer
import com.wireguard.config.InetEndpoint
import com.wireguard.config.InetNetwork
import com.wireguard.crypto.Key

fun buildWireGuardConfig(session: KtnSessionResponse): Config {
    // === [Interface] ===
    val interfaceBuilder = Interface.Builder()

    // Private key (from API: interface.private_key)
    interfaceBuilder.parsePrivateKey(session.interfaceData.privateKey)

    // Address (from API: interface.address, e.g. "10.200.0.2/32")
    interfaceBuilder.parseAddresses(session.interfaceData.address)

    // DNS (from API: interface.dns, e.g. "1.1.1.1, 8.8.8.8")
    // Split by comma, trim spaces
    interfaceBuilder.parseDnsServers(session.interfaceData.dns)

    // MTU (from API: interface.mtu, e.g. 1420)
    interfaceBuilder.parseMtu(session.interfaceData.mtu.toString())

    // === [Peer] ===
    val peerBuilder = Peer.Builder()

    // Server public key (from API: peer.public_key)
    peerBuilder.parsePublicKey(session.peer.publicKey)

    // Preshared key (from API: peer.preshared_key) — IMPORTANT: include if non-empty
    if (session.peer.presharedKey.isNotEmpty()) {
        peerBuilder.parsePreSharedKey(session.peer.presharedKey)
    }

    // Endpoint (from API: peer.endpoint, e.g. "66.29.143.116:51820")
    peerBuilder.parseEndpoint(session.peer.endpoint)

    // AllowedIPs (from API: peer.allowed_ips, e.g. "0.0.0.0/0")
    peerBuilder.parseAllowedIPs(session.peer.allowedIps)

    // PersistentKeepalive (from API: peer.persistent_keepalive, e.g. 25)
    peerBuilder.parsePersistentKeepalive(session.peer.persistentKeepalive.toString())

    // Build config
    return Config.Builder()
        .setInterface(interfaceBuilder.build())
        .addPeer(peerBuilder.build())
        .build()
}
```

#### Activating the Tunnel

```kotlin
import com.wireguard.android.backend.GoBackend
import com.wireguard.android.backend.Tunnel

class KtnTunnel : Tunnel {
    override fun getName(): String = "KTN"
    override fun onStateChange(newState: Tunnel.State) {
        // Update UI: connected / disconnected
    }
}

// In your KTN service / activity:
val backend = GoBackend(context)
val tunnel = KtnTunnel()
val config = buildWireGuardConfig(sessionResponse)

// Activate KTN
backend.setState(tunnel, Tunnel.State.UP, config)

// Deactivate KTN
backend.setState(tunnel, Tunnel.State.DOWN, null)
```

### Option B: Using Raw WireGuard Config String

If you're using a library that accepts a raw `.conf` string:

```kotlin
fun buildConfigString(session: KtnSessionResponse): String {
    val sb = StringBuilder()

    sb.appendLine("[Interface]")
    sb.appendLine("PrivateKey = ${session.interfaceData.privateKey}")
    sb.appendLine("Address = ${session.interfaceData.address}")
    sb.appendLine("DNS = ${session.interfaceData.dns}")
    sb.appendLine("MTU = ${session.interfaceData.mtu}")
    sb.appendLine()
    sb.appendLine("[Peer]")
    sb.appendLine("PublicKey = ${session.peer.publicKey}")
    if (session.peer.presharedKey.isNotEmpty()) {
        sb.appendLine("PresharedKey = ${session.peer.presharedKey}")
    }
    sb.appendLine("AllowedIPs = ${session.peer.allowedIps}")
    sb.appendLine("Endpoint = ${session.peer.endpoint}")
    sb.appendLine("PersistentKeepalive = ${session.peer.persistentKeepalive}")

    return sb.toString()
}

// Parse it:
val config = Config.parse(BufferedReader(StringReader(configString)))
```

---

## Step 4: Android Permissions

KTN uses Android's `VpnService` under the hood (this is how Android allows apps to create encrypted tunnels):

```xml
<!-- AndroidManifest.xml -->
<uses-permission android:name="android.permission.INTERNET" />

<service
    android:name=".ktn.KtnTunnelService"
    android:permission="android.permission.BIND_VPN_SERVICE">
    <intent-filter>
        <action android:name="android.net.VpnService" />
    </intent-filter>
</service>
```

Before activating KTN, you must request tunnel permission:

```kotlin
val intent = GoBackend.VpnService.prepare(context)
if (intent != null) {
    // User must approve tunnel permission (one-time)
    startActivityForResult(intent, KTN_REQUEST_CODE)
} else {
    // Permission already granted — activate KTN
    activateKtn()
}
```

---

## Common Mistakes to Check

### ❌ 1. Missing or Wrong PresharedKey

If the API returns a non-empty `preshared_key`, it **MUST** be included in the config. If the Android side omits it, the handshake will fail silently — the phone shows "connected" but no data flows.

**Check:** Does your Android code include `PresharedKey`?

### ❌ 2. DNS Field Has Spaces After Commas

The API returns `"1.1.1.1, 8.8.8.8"` (with space after comma). Some WireGuard parsers choke on this. Either:

- Use the library's `parseDnsServers()` which handles it, OR
- Strip spaces: `dns.replace(" ", "")`

### ❌ 3. AllowedIPs Missing or Wrong

`AllowedIPs = 0.0.0.0/0` means "route ALL traffic through KTN". If the Android app sets something else (e.g. only `10.200.0.0/24`), then internet traffic won't go through the tunnel.

**Check:** Is `AllowedIPs` set to exactly `0.0.0.0/0`?

### ❌ 4. Endpoint Missing or Wrong

The endpoint must be exactly `66.29.143.116:51820` (the KTN server public IP + port). If the app hardcodes a different IP or port, the tunnel won't connect.

**Check:** Is `Endpoint` taken from `peer.endpoint` in the API response?

### ❌ 5. Shows "Connected" But No Handshake

Android's WireGuard will show "connected" as soon as the local tunnel interface is up — even before a handshake with the server completes. This is a WireGuard design behavior, not a bug. **"Connected" does NOT mean "handshake successful".**

To verify a real connection:

- Check `latestHandshake` — it should be non-zero after activating KTN
- Try to ping `10.100.0.1` (KTN server tunnel address) from the app
- Check if data transfer counters increase (rx/tx bytes)

### ❌ 6. Using Wrong Key Type

- `interface.private_key` = the **client's PRIVATE key** → goes in `[Interface] PrivateKey`
- `peer.public_key` = the **server's PUBLIC key** → goes in `[Peer] PublicKey`

If these are swapped, handshake will fail.

---

## Debugging Checklist

### On the Android side:

1. Log the full config string (redact PrivateKey) before activating KTN
2. Check that all 6 fields in `[Interface]` and all 5 fields in `[Peer]` are populated
3. After activating, check `tunnel.getStatistics()` for:
   - `latestHandshake` > 0 → handshake succeeded
   - `rxBytes` > 0 → receiving data from server

### On the server side (we can check):

```bash
# See if the phone's peer has completed a handshake:
wg show wg0

# Look for the peer's public key and check:
#   latest handshake: X seconds ago    ← GOOD (handshake works)
#   latest handshake: (none)           ← BAD (phone never connected)
#   transfer: X received, Y sent       ← GOOD (data flowing)
#   transfer: 0 B received, 0 B sent   ← BAD (no data)
```

---

## Quick Test: Manual WireGuard App

To rule out Android code issues, test with the **official WireGuard app** from Play Store:

1. Install "WireGuard" by Jason A. Donenfeld from Play Store
2. Tap `+` → "Create from scratch"
3. Enter the **[Interface]** fields:
   - **Name:** `KTN`
   - **Private key:** `KPdwlsTVNwBo0v3H0UkdI1UjQfmJdm2/oQSfExvYi1E=`
   - **Addresses:** `10.200.0.2/32`
   - **DNS servers:** `1.1.1.1, 8.8.8.8`
   - **MTU:** `1420`
4. Tap "Add peer" and enter **[Peer]** fields:
   - **Public key:** `0ItNRIAXdf090Z3RpIVsmrA1JjRJrZveYweNZXXo3mQ=`
   - **Pre-shared key:** `QjQIPP6E94twMHcdwjENSF5QFkrY9XggvhifbMoUPYM=`
   - **Endpoint:** `66.29.143.116:51820`
   - **Allowed IPs:** `0.0.0.0/0`
   - **Persistent keepalive:** `25`
5. Save and toggle ON
6. Check:
   - Does "Latest handshake" appear? (should show "X seconds ago")
   - Does transfer show bytes? (rx and tx should increase)
   - Can you open a website?

**If the official WireGuard app works but your KTN app doesn't**, the problem is in the Android KTN implementation. **If even the official app doesn't work**, the problem is server-side and we'll investigate further.

---

## API Error Responses

| Status | Error Code  | Meaning                                                         |
| ------ | ----------- | --------------------------------------------------------------- |
| 404    | `no_plan`   | User has no active KTN plan — needs to purchase one             |
| 403    | `expired`   | KTN plan expired — needs renewal                                |
| 500    | `no_config` | Tunnel config not ready (missing private key) — contact support |

---

## Data Models (Kotlin)

```kotlin
data class KtnSessionResponse(
    val success: Boolean,
    @SerializedName("tunnel_name") val tunnelName: String,
    @SerializedName("interface") val interfaceData: InterfaceData,
    val peer: PeerData,
    val plan: PlanData?,
    val tenant: TenantData?
)

data class InterfaceData(
    @SerializedName("private_key") val privateKey: String,
    val address: String,
    val dns: String,
    val mtu: Int
)

data class PeerData(
    @SerializedName("public_key") val publicKey: String,
    @SerializedName("preshared_key") val presharedKey: String,
    val endpoint: String,
    @SerializedName("allowed_ips") val allowedIps: String,
    @SerializedName("persistent_keepalive") val persistentKeepalive: Int
)

data class PlanData(
    val name: String,
    @SerializedName("expires_at") val expiresAt: String?,
    @SerializedName("duration_days") val durationDays: Int?
)

data class TenantData(
    val id: String,
    val name: String
)
```

---

## Retrofit API Interface

```kotlin
interface KtnApi {
    @GET("api/vpn/session/")
    suspend fun getKtnSession(
        @Header("Authorization") token: String,
        @Query("tenant_id") tenantId: String? = null
    ): KtnSessionResponse

    @GET("api/vpn/status/")
    suspend fun getKtnStatus(
        @Header("Authorization") token: String
    ): KtnStatusResponse

    @GET("api/vpn/status/check/")
    suspend fun checkPlanByPhone(
        @Query("phone") phone: String
    ): KtnStatusCheckResponse
}
```
