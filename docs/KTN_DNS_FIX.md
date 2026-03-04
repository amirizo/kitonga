# KTN DNS Fix — Critical Client App Update Required

## Date: March 4, 2026

## Problem Summary

**Symptom:** After connecting to KTN (WireGuard tunnel), only WhatsApp works. Browsers, other apps, and the KTN client app itself all report "No Internet Connection."

**Root Cause:** DNS resolution failure. The client app was configured to use public DNS servers (`1.1.1.1`, `8.8.8.8`) but those DNS queries were not reaching the DNS servers through the tunnel because of the network architecture.

---

## Why WhatsApp Worked But Nothing Else

| App                                | Uses DNS?                                    | Behavior | Why                                                                                                                      |
| ---------------------------------- | -------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------ |
| **WhatsApp**                       | Minimal — uses cached/hardcoded IPs          | ✅ Works | WhatsApp connects to pre-known IP addresses (Meta servers). It doesn't need to resolve domain names for basic messaging. |
| **Browsers**                       | Yes — every URL needs DNS                    | ❌ Fails | Typing `google.com` requires resolving it to `142.251.x.x`. Without DNS, the browser can't find any server.              |
| **Most apps**                      | Yes — API calls need DNS                     | ❌ Fails | Apps call `api.example.com` which requires DNS. Without it, they report "no internet."                                   |
| **Android/iOS connectivity check** | Yes — checks `connectivitycheck.gstatic.com` | ❌ Fails | The OS itself pings a Google domain to verify internet. DNS failure = OS thinks there's no internet.                     |

---

## Technical Root Cause (Detailed)

### KTN Architecture

```
  Client Phone          VPS (66.29.143.116)         MikroTik (10.100.0.20)
  ┌───────────┐        ┌──────────────────┐        ┌─────────────────────┐
  │ KTN App   │  WG    │ WireGuard Hub    │  WG    │ Exit Node           │
  │ 10.200.0.x├───────►│ wg0: 10.100.0.1 ├───────►│ wg-kitonga          │
  │           │ :51820 │                  │ :51820 │ 10.100.0.20         │
  └───────────┘        │ Policy Routing   │        │                     │
                       │ fwmark + table   │        │ NAT → Internet      │
                       └──────────────────┘        │ DNS Server (port 53)│
                                                   └─────────────────────┘
```

Traffic flows: **Client → VPS → MikroTik → Internet**

### What Happened With DNS

1. Client app configured `DNS = 1.1.1.1, 8.8.8.8`
2. Phone sends DNS query: `10.200.0.2 → 1.1.1.1:53` (through WireGuard tunnel)
3. Query arrives at VPS on `wg0` interface
4. VPS policy routing sends it to MikroTik (correct)
5. MikroTik forwards it to 1.1.1.1 (correct)
6. Response comes back from 1.1.1.1 → MikroTik → VPS
7. **But MikroTik's input firewall (`drop all not coming from LAN`) was blocking DNS queries addressed to MikroTik itself**
8. Additionally, the WireGuard interfaces (`wg-kitonga`, `wg-ktn`) were NOT in the MikroTik LAN interface list, so traffic from these interfaces was treated as untrusted

### Three Server-Side Fixes Applied

| #   | Fix                                                   | Where        | What                                                                                     |
| --- | ----------------------------------------------------- | ------------ | ---------------------------------------------------------------------------------------- |
| 1   | Added `wg-kitonga` and `wg-ktn` to LAN interface list | MikroTik     | DNS queries from WireGuard interfaces are now accepted                                   |
| 2   | Added DNS DNAT redirect                               | VPS iptables | All port-53 traffic from 10.200.0.0/24 on wg0 is redirected to MikroTik (10.100.0.20:53) |
| 3   | Added 10.200.0.0/24 route in main table               | VPS routing  | Return traffic from MikroTik to VPN clients now routes correctly via wg0                 |

### Remaining Client-Side Fix Required

The client app must set `DNS = 10.100.0.20` (MikroTik's IP) as the primary DNS server. This is the most reliable DNS path because:

- **10.100.0.20** is directly reachable via the WireGuard tunnel (one hop: VPS → MikroTik)
- MikroTik has `allow-remote-requests=true` and uses `8.8.8.8` upstream
- It adds zero extra latency compared to public DNS (which also goes through MikroTik anyway)

---

## API Change

The `/api/vpn/session/` endpoint now returns updated DNS:

### Before (broken)

```json
{
  "interface": {
    "dns": "1.1.1.1,8.8.8.8",
    "mtu": 1420
  }
}
```

### After (fixed)

```json
{
  "interface": {
    "dns": "10.100.0.20,1.1.1.1",
    "mtu": 1280
  }
}
```

**Changes:**
| Field | Old Value | New Value | Reason |
|-------|-----------|-----------|--------|
| `dns` | `1.1.1.1,8.8.8.8` | `10.100.0.20,1.1.1.1` | MikroTik DNS is primary (lowest latency, most reliable). 1.1.1.1 is fallback (DNAT-redirected to MikroTik anyway). |
| `mtu` | `1420` | `1280` | Double WireGuard encapsulation (Client→VPS→MikroTik) requires lower MTU to avoid fragmentation. 1280 is the IPv6 minimum and safe for all paths. |

---

## Android Client App — Required Changes

### 1. DNS Configuration (Critical)

The DNS servers MUST be set from the API response `interface.dns` field. The app must parse and apply them correctly.

#### WireGuard Library Approach

```kotlin
fun buildWireGuardConfig(session: KtnSessionResponse): Config {
    val interfaceBuilder = Interface.Builder()

    interfaceBuilder.parsePrivateKey(session.interfaceData.privateKey)
    interfaceBuilder.parseAddresses(session.interfaceData.address)

    // ✅ CRITICAL: Parse DNS from API response
    // API returns: "10.100.0.20,1.1.1.1"
    // This sets the phone's DNS resolver to use these servers THROUGH the tunnel
    interfaceBuilder.parseDnsServers(session.interfaceData.dns)

    interfaceBuilder.parseMtu(session.interfaceData.mtu.toString())

    // ... peer config ...
}
```

#### VpnService.Builder Approach (if using raw VpnService)

If the Android app uses `VpnService.Builder` directly instead of the WireGuard library:

```kotlin
// When building the VPN interface, DNS MUST be added:
val builder = VpnService.Builder()
    .setSession("KTN")
    .addAddress("10.200.0.2", 32)
    .addRoute("0.0.0.0", 0)  // Route ALL traffic through tunnel
    .setMtu(1280)

// ✅ CRITICAL: Add DNS servers from API response
// Split by comma, trim whitespace
val dnsServers = session.interfaceData.dns.split(",").map { it.trim() }
for (dns in dnsServers) {
    if (dns.isNotEmpty()) {
        builder.addDnsServer(dns)  // <-- THIS IS THE KEY LINE
    }
}

// Establish the VPN
val vpnInterface = builder.establish()
```

**⚠️ Common Bug:** If `builder.addDnsServer()` is never called, Android continues using the system DNS (e.g., the WiFi router's DNS or mobile carrier DNS). Those DNS servers are NOT reachable through the tunnel, so DNS fails → "no internet."

### 2. MTU Configuration

```kotlin
// ✅ Use MTU from API response (now 1280)
builder.setMtu(session.interfaceData.mtu)

// ❌ DON'T hardcode 1420
// builder.setMtu(1420)  // This causes packet fragmentation
```

### 3. Connectivity Check Workaround

Android performs connectivity checks by resolving `connectivitycheck.gstatic.com`. If DNS takes too long (high latency tunnel), Android may falsely report "no internet" even though the connection works. To prevent this:

```kotlin
// Option A: Disable captive portal detection (requires system permission)
// Not recommended for production apps

// Option B: Set the VPN as the default network (recommended)
val connectivityManager = getSystemService(ConnectivityManager::class.java)
val networkRequest = NetworkRequest.Builder()
    .addTransportType(NetworkCapabilities.TRANSPORT_VPN)
    .removeCapability(NetworkCapabilities.NET_CAPABILITY_NOT_VPN)
    .build()

// This tells Android to prefer the VPN network
connectivityManager.requestNetwork(networkRequest, object : ConnectivityManager.NetworkCallback() {
    override fun onAvailable(network: Network) {
        // Set as default network for the process
        connectivityManager.bindProcessToNetwork(network)
    }
})
```

### 4. Full Android Implementation Checklist

```kotlin
class KtnTunnelService : VpnService() {

    fun startTunnel(session: KtnSessionResponse) {
        val builder = Builder()
            .setSession("KTN")
            .setBlocking(false)

        // ── Interface ──
        val address = session.interfaceData.address.split("/")
        builder.addAddress(address[0], address[1].toInt())

        // ✅ MTU from API (1280 for double-tunnel)
        builder.setMtu(session.interfaceData.mtu)

        // ✅ DNS from API — THIS IS CRITICAL
        session.interfaceData.dns
            .split(",")
            .map { it.trim() }
            .filter { it.isNotEmpty() }
            .forEach { dns ->
                builder.addDnsServer(dns)
            }

        // ✅ Route ALL traffic through tunnel
        builder.addRoute("0.0.0.0", 0)

        // ✅ Also add IPv6 catch-all to prevent IPv6 DNS leaks
        builder.addRoute("::", 0)

        // Establish tunnel
        val vpnInterface = builder.establish()
            ?: throw IllegalStateException("VPN interface could not be established")

        // ... start WireGuard protocol handler with the session keys ...
    }
}
```

---

## iOS Client App — Required Changes

### 1. Network Extension DNS Configuration (Critical)

If the iOS app uses `NetworkExtension` framework with `NETunnelProviderProtocol`:

```swift
// In your PacketTunnelProvider:
override func startTunnel(options: [String : NSObject]?, completionHandler: @escaping (Error?) -> Void) {

    let tunnelSettings = NEPacketTunnelNetworkSettings(tunnelRemoteAddress: session.peer.endpoint)

    // ✅ CRITICAL: Set DNS
    let dnsServers = session.interface.dns
        .components(separatedBy: ",")
        .map { $0.trimmingCharacters(in: .whitespaces) }
        .filter { !$0.isEmpty }

    let dnsSettings = NEDNSSettings(servers: dnsServers)
    // Match all domains — force ALL DNS through the tunnel
    dnsSettings.matchDomains = [""]  // Empty string = match all domains
    tunnelSettings.dnsSettings = dnsSettings

    // ✅ MTU from API
    tunnelSettings.mtu = NSNumber(value: session.interface.mtu)  // 1280

    // ✅ IPv4 settings
    let ipv4Settings = NEIPv4Settings(
        addresses: [session.interface.address.components(separatedBy: "/").first ?? ""],
        subnetMasks: ["255.255.255.255"]
    )
    // Route ALL traffic through tunnel
    ipv4Settings.includedRoutes = [NEIPv4Route.default()]
    tunnelSettings.ipv4Settings = ipv4Settings

    // Apply settings
    setTunnelNetworkSettings(tunnelSettings) { error in
        if let error = error {
            completionHandler(error)
            return
        }
        // Start WireGuard protocol...
        completionHandler(nil)
    }
}
```

### 2. Using WireGuardKit (if using the official Swift library)

```swift
import WireGuardKit

func buildTunnelConfiguration(from session: KTNSessionResponse) -> TunnelConfiguration {
    // Build WireGuard config string from API response
    var configString = """
    [Interface]
    PrivateKey = \(session.interface.privateKey)
    Address = \(session.interface.address)
    DNS = \(session.interface.dns)
    MTU = \(session.interface.mtu)

    [Peer]
    PublicKey = \(session.peer.publicKey)
    """

    if !session.peer.presharedKey.isEmpty {
        configString += "PresharedKey = \(session.peer.presharedKey)\n"
    }

    configString += """
    AllowedIPs = \(session.peer.allowedIPs)
    Endpoint = \(session.peer.endpoint)
    PersistentKeepalive = \(session.peer.persistentKeepalive)
    """

    return try! TunnelConfiguration(fromWgQuickConfig: configString, called: "KTN")
}
```

### 3. iOS DNS Important Notes

- **`matchDomains = [""]`** (empty string) means ALL DNS queries go through the tunnel DNS. If you set `matchDomains = []` (empty array), iOS does NOT route DNS through the tunnel — this is a common iOS bug/gotcha.
- **NEDNSSettings** must be set on the `NEPacketTunnelNetworkSettings` BEFORE calling `setTunnelNetworkSettings()`.
- If DNS is not configured, iOS will use the device's default DNS (WiFi/Cellular), which cannot reach DNS servers through the tunnel.

---

## Verification Steps

### After updating the client app, verify:

#### On the phone:

1. Connect to KTN
2. Open a browser → navigate to `http://neverssl.com` (HTTP, no HTTPS) → should load
3. Try `https://www.google.com` → should load
4. Open WhatsApp → should work (it already did)
5. Check the KTN app's tunnel stats → `rx` and `tx` bytes should both increase

#### On the server (we can check):

```bash
# Check if DNS queries are now flowing:
ssh root@66.29.143.116 "timeout 10 tcpdump -i wg0 -n 'host 10.200.0.2 and port 53'"

# Expected output (GOOD):
# 10.200.0.2.52341 > 10.100.0.20.53: UDP, length 45   ← DNS query
# 10.100.0.20.53 > 10.200.0.2.52341: UDP, length 61   ← DNS response

# If you see queries to 1.1.1.1 or 8.8.8.8 instead:
# That's also OK — the VPS DNAT rule redirects them to MikroTik
```

---

## Summary of All Changes

### Server-Side (already applied)

| Component      | Change                                               | Purpose                                                                     |
| -------------- | ---------------------------------------------------- | --------------------------------------------------------------------------- |
| VPS `wg0.conf` | Added `ip route add 10.200.0.0/24 dev wg0` to PostUp | Return traffic from MikroTik reaches VPN clients                            |
| VPS `wg0.conf` | Added DNS DNAT rules (port 53 → 10.100.0.20:53)      | Intercepts any DNS query from VPN clients, redirects to MikroTik            |
| VPS `wg0.conf` | MTU changed to 1280                                  | Prevents packet fragmentation in double WireGuard tunnel                    |
| MikroTik       | Added `wg-kitonga` to LAN interface list             | DNS and other input traffic from WireGuard is no longer dropped by firewall |
| MikroTik       | Added `wg-ktn` to LAN interface list                 | Same — allows direct VPN client access to MikroTik services                 |
| MikroTik       | Moved VPN forward rules before fasttrack/drop        | Ensures VPN traffic is accepted before default drop rules                   |

### API (already applied)

| Change          | Old               | New                   |
| --------------- | ----------------- | --------------------- |
| `interface.dns` | `1.1.1.1,8.8.8.8` | `10.100.0.20,1.1.1.1` |
| `interface.mtu` | `1420`            | `1280`                |

### Client App (REQUIRED — mobile dev team)

| Platform | Change                                                                 | Priority     |
| -------- | ---------------------------------------------------------------------- | ------------ |
| Android  | Ensure `VpnService.Builder.addDnsServer()` is called with DNS from API | 🔴 Critical  |
| Android  | Ensure MTU from API is applied (not hardcoded 1420)                    | 🟡 Important |
| Android  | Add `addRoute("::", 0)` to prevent IPv6 DNS leaks                      | 🟡 Important |
| iOS      | Ensure `NEDNSSettings` is set with `matchDomains = [""]`               | 🔴 Critical  |
| iOS      | Ensure MTU from API is applied                                         | 🟡 Important |
| Both     | Do NOT hardcode DNS — always use `interface.dns` from API response     | 🔴 Critical  |

---

## Quick Debugging Checklist for Mobile Devs

If "no internet" persists after the update:

1. **Log the full WireGuard config** (redact PrivateKey) before activating — verify DNS is present
2. **Check DNS value** — should be `10.100.0.20,1.1.1.1` (NOT `1.1.1.1,8.8.8.8`)
3. **Check MTU value** — should be `1280` (NOT `1420`)
4. **Verify `addDnsServer()` / `NEDNSSettings`** — this is the #1 cause of "connected but no internet"
5. **Test with a raw IP** — try loading `http://1.1.1.1` in a browser. If this works but domains don't, it confirms DNS is the issue
6. **Check handshake** — if `latestHandshake` is 0 or `(none)`, the tunnel itself isn't connecting (different problem)
7. **Check transfer counters** — if `rx = 0`, server is not sending data back (routing issue). If `tx = 0`, phone is not sending data (tunnel not active)
