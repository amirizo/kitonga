// Kitonga Wi-Fi API Frontend Integration Examples
// Complete JavaScript examples for interacting with your Django API

// ========================================
// Configuration
// ========================================
const API_BASE_URL = 'https://api.kitonga.klikcell.com';
const LOCAL_API_URL = 'http://127.0.0.1:8000';

// Use this for development
const API_URL = API_BASE_URL; // Change to LOCAL_API_URL for local testing

// ========================================
// Authentication Helper Class
// ========================================
class AuthManager {
    static setToken(token) {
        localStorage.setItem('admin_token', token);
    }
    
    static getToken() {
        return localStorage.getItem('admin_token');
    }
    
    static clearToken() {
        localStorage.removeItem('admin_token');
    }
    
    static isAuthenticated() {
        return !!this.getToken();
    }
    
    static getAuthHeaders() {
        const token = this.getToken();
        return token ? { 'Authorization': `Bearer ${token}` } : {};
    }
}

// ========================================
// API Request Helper
// ========================================
async function apiRequest(endpoint, options = {}) {
    try {
        const url = `${API_URL}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };
        
        const response = await fetch(url, config);
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ 
                error: 'Request failed', 
                message: `HTTP ${response.status}` 
            }));
            throw new Error(errorData.message || errorData.error || 'Request failed');
        }
        
        return await response.json();
    } catch (error) {
        console.error(`API request failed for ${endpoint}:`, error);
        throw error;
    }
}

// ========================================
// Admin Authentication Functions
// ========================================

// Admin Login
async function adminLogin(username, password) {
    try {
        const response = await apiRequest('/auth/login/', {
            method: 'POST',
            body: JSON.stringify({ username, password })
        });
        
        if (response.success && response.token) {
            AuthManager.setToken(response.token);
            return response;
        }
        
        throw new Error(response.message || 'Login failed');
    } catch (error) {
        console.error('Admin login failed:', error);
        throw error;
    }
}

// Admin Logout
async function adminLogout() {
    try {
        await apiRequest('/auth/logout/', {
            method: 'POST',
            headers: AuthManager.getAuthHeaders()
        });
        
        AuthManager.clearToken();
        return { success: true, message: 'Logged out successfully' };
    } catch (error) {
        // Clear token even if logout fails
        AuthManager.clearToken();
        throw error;
    }
}

// Get Admin Profile
async function getAdminProfile() {
    return await apiRequest('/auth/profile/', {
        method: 'GET',
        headers: AuthManager.getAuthHeaders()
    });
}

// ========================================
// User Wi-Fi Access Functions
// ========================================

// Check User Status
async function getUserStatus(phoneNumber) {
    return await apiRequest(`/user-status/${phoneNumber}/`);
}

// Verify User Access
async function verifyUserAccess(phoneNumber, macAddress, ipAddress) {
    return await apiRequest('/verify/', {
        method: 'POST',
        body: JSON.stringify({
            phone_number: phoneNumber,
            mac_address: macAddress,
            ip_address: ipAddress
        })
    });
}

// Get Available Bundles
async function getBundles() {
    return await apiRequest('/bundles/');
}

// ========================================
// Payment Functions
// ========================================

// Initiate Payment
async function initiatePayment(phoneNumber, bundleId, macAddress) {
    return await apiRequest('/initiate-payment/', {
        method: 'POST',
        body: JSON.stringify({
            phone_number: phoneNumber,
            bundle_id: bundleId,
            mac_address: macAddress
        })
    });
}

// Check Payment Status
async function getPaymentStatus(orderReference) {
    return await apiRequest(`/payment-status/${orderReference}/`);
}

// Poll Payment Status (with timeout)
async function pollPaymentStatus(orderReference, maxAttempts = 30, intervalMs = 10000) {
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
        try {
            const status = await getPaymentStatus(orderReference);
            
            if (status.payment_status === 'COMPLETED') {
                return { success: true, ...status };
            }
            
            if (status.payment_status === 'FAILED') {
                return { success: false, ...status };
            }
            
            // Wait before next check
            await new Promise(resolve => setTimeout(resolve, intervalMs));
        } catch (error) {
            console.error('Payment status check failed:', error);
        }
    }
    
    return { success: false, error: 'Payment status check timeout' };
}

// ========================================
// Device Management Functions
// ========================================

// List User Devices
async function getUserDevices(phoneNumber) {
    return await apiRequest(`/devices/${phoneNumber}/`);
}

// Remove Device
async function removeDevice(phoneNumber, macAddress) {
    return await apiRequest('/devices/remove/', {
        method: 'POST',
        body: JSON.stringify({
            phone_number: phoneNumber,
            mac_address: macAddress
        })
    });
}

// ========================================
// Voucher Functions
// ========================================

// Generate Vouchers (Admin only)
async function generateVouchers(bundleId, quantity, expiryDays) {
    return await apiRequest('/vouchers/generate/', {
        method: 'POST',
        headers: AuthManager.getAuthHeaders(),
        body: JSON.stringify({
            bundle_id: bundleId,
            quantity: quantity,
            expiry_days: expiryDays
        })
    });
}

// Redeem Voucher
async function redeemVoucher(phoneNumber, voucherCode, macAddress) {
    return await apiRequest('/vouchers/redeem/', {
        method: 'POST',
        body: JSON.stringify({
            phone_number: phoneNumber,
            voucher_code: voucherCode,
            mac_address: macAddress
        })
    });
}

// List Vouchers (Admin only)
async function listVouchers() {
    return await apiRequest('/vouchers/list/', {
        method: 'GET',
        headers: AuthManager.getAuthHeaders()
    });
}

// ========================================
// MikroTik Integration Functions
// ========================================

// MikroTik Authentication
async function mikrotikAuth(phoneNumber, macAddress, ipAddress) {
    return await apiRequest('/mikrotik/auth/', {
        method: 'POST',
        body: JSON.stringify({
            phone_number: phoneNumber,
            mac_address: macAddress,
            ip_address: ipAddress
        })
    });
}

// MikroTik Logout
async function mikrotikLogout(phoneNumber, ipAddress) {
    return await apiRequest('/mikrotik/logout/', {
        method: 'POST',
        body: JSON.stringify({
            phone_number: phoneNumber,
            ip_address: ipAddress
        })
    });
}

// MikroTik Status (Admin only)
async function getMikrotikStatus() {
    return await apiRequest('/mikrotik/status/', {
        method: 'GET',
        headers: AuthManager.getAuthHeaders()
    });
}

// ========================================
// Admin Dashboard Functions
// ========================================

// Get Dashboard Statistics
async function getDashboardStats() {
    return await apiRequest('/dashboard-stats/', {
        method: 'GET',
        headers: AuthManager.getAuthHeaders()
    });
}

// Get Webhook Logs
async function getWebhookLogs() {
    return await apiRequest('/webhook-logs/', {
        method: 'GET',
        headers: AuthManager.getAuthHeaders()
    });
}

// Force User Logout
async function forceUserLogout(phoneNumber) {
    return await apiRequest('/force-logout/', {
        method: 'POST',
        headers: AuthManager.getAuthHeaders(),
        body: JSON.stringify({
            phone_number: phoneNumber
        })
    });
}

// ========================================
// Complete User Flow Examples
// ========================================

// Complete Wi-Fi Access Request Flow
async function requestWiFiAccess(phoneNumber, macAddress) {
    try {
        // 1. Check if user already has access
        console.log('Checking user status...');
        const status = await getUserStatus(phoneNumber);
        
        if (status.has_access) {
            return {
                success: true,
                message: 'User already has Wi-Fi access',
                user: status.user
            };
        }
        
        // 2. Get available bundles
        console.log('Getting available bundles...');
        const bundles = await getBundles();
        
        if (!bundles.length) {
            throw new Error('No bundles available');
        }
        
        // 3. Use the first available bundle (or let user choose)
        const selectedBundle = bundles[0];
        
        // 4. Initiate payment
        console.log('Initiating payment...');
        const payment = await initiatePayment(phoneNumber, selectedBundle.id, macAddress);
        
        if (payment.success) {
            return {
                success: true,
                message: 'Payment initiated successfully',
                payment_reference: payment.payment_reference,
                order_reference: payment.order_reference,
                redirect_url: payment.redirect_url,
                amount: payment.amount
            };
        }
        
        throw new Error(payment.message || 'Payment initiation failed');
        
    } catch (error) {
        console.error('Wi-Fi access request failed:', error);
        return {
            success: false,
            error: error.message,
            message: 'Failed to request Wi-Fi access'
        };
    }
}

// Complete Payment Verification Flow
async function verifyPaymentAndGrantAccess(orderReference, phoneNumber, macAddress, ipAddress) {
    try {
        // 1. Check payment status
        console.log('Checking payment status...');
        const paymentStatus = await getPaymentStatus(orderReference);
        
        if (paymentStatus.payment_status !== 'COMPLETED') {
            return {
                success: false,
                message: 'Payment not completed',
                status: paymentStatus.payment_status
            };
        }
        
        // 2. Verify access is granted
        console.log('Verifying access...');
        const accessCheck = await verifyUserAccess(phoneNumber, macAddress, ipAddress);
        
        if (accessCheck.has_access) {
            // 3. Authenticate with MikroTik
            console.log('Authenticating with MikroTik...');
            const mikrotikAuth = await mikrotikAuth(phoneNumber, macAddress, ipAddress);
            
            return {
                success: true,
                message: 'Access granted successfully',
                user: accessCheck.user,
                mikrotik_response: mikrotikAuth
            };
        }
        
        throw new Error('Access verification failed');
        
    } catch (error) {
        console.error('Payment verification failed:', error);
        return {
            success: false,
            error: error.message,
            message: 'Failed to verify payment and grant access'
        };
    }
}

// Admin Dashboard Data Loading
async function loadAdminDashboard() {
    try {
        if (!AuthManager.isAuthenticated()) {
            throw new Error('Admin authentication required');
        }
        
        console.log('Loading dashboard data...');
        
        // Load all dashboard data in parallel
        const [stats, webhookLogs, vouchers, mikrotikStatus] = await Promise.all([
            getDashboardStats(),
            getWebhookLogs(),
            listVouchers(),
            getMikrotikStatus().catch(() => ({ success: false, message: 'MikroTik status unavailable' }))
        ]);
        
        return {
            success: true,
            data: {
                statistics: stats,
                webhook_logs: webhookLogs,
                vouchers: vouchers,
                mikrotik_status: mikrotikStatus
            }
        };
        
    } catch (error) {
        console.error('Dashboard loading failed:', error);
        return {
            success: false,
            error: error.message,
            message: 'Failed to load dashboard data'
        };
    }
}

// ========================================
// React Hook Examples
// ========================================

// Custom hook for user status (React)
function useUserStatus(phoneNumber) {
    const [status, setStatus] = React.useState(null);
    const [loading, setLoading] = React.useState(true);
    const [error, setError] = React.useState(null);
    
    React.useEffect(() => {
        if (!phoneNumber) {
            setLoading(false);
            return;
        }
        
        const fetchStatus = async () => {
            try {
                setLoading(true);
                const data = await getUserStatus(phoneNumber);
                setStatus(data);
                setError(null);
            } catch (err) {
                setError(err.message);
                setStatus(null);
            } finally {
                setLoading(false);
            }
        };
        
        fetchStatus();
    }, [phoneNumber]);
    
    return { status, loading, error };
}

// Custom hook for admin authentication (React)
function useAdminAuth() {
    const [isAuthenticated, setIsAuthenticated] = React.useState(AuthManager.isAuthenticated());
    const [user, setUser] = React.useState(null);
    const [loading, setLoading] = React.useState(false);
    
    const login = async (username, password) => {
        try {
            setLoading(true);
            const response = await adminLogin(username, password);
            setIsAuthenticated(true);
            setUser(response.user);
            return response;
        } catch (error) {
            setIsAuthenticated(false);
            setUser(null);
            throw error;
        } finally {
            setLoading(false);
        }
    };
    
    const logout = async () => {
        try {
            await adminLogout();
        } finally {
            setIsAuthenticated(false);
            setUser(null);
        }
    };
    
    React.useEffect(() => {
        if (isAuthenticated && !user) {
            getAdminProfile()
                .then(setUser)
                .catch(() => {
                    setIsAuthenticated(false);
                    AuthManager.clearToken();
                });
        }
    }, [isAuthenticated, user]);
    
    return { isAuthenticated, user, login, logout, loading };
}

// ========================================
// Export for Module Usage
// ========================================
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        // Auth
        AuthManager,
        adminLogin,
        adminLogout,
        getAdminProfile,
        
        // User Access
        getUserStatus,
        verifyUserAccess,
        getBundles,
        
        // Payments
        initiatePayment,
        getPaymentStatus,
        pollPaymentStatus,
        
        // Devices
        getUserDevices,
        removeDevice,
        
        // Vouchers
        generateVouchers,
        redeemVoucher,
        listVouchers,
        
        // MikroTik
        mikrotikAuth,
        mikrotikLogout,
        getMikrotikStatus,
        
        // Admin
        getDashboardStats,
        getWebhookLogs,
        forceUserLogout,
        
        // Complete Flows
        requestWiFiAccess,
        verifyPaymentAndGrantAccess,
        loadAdminDashboard,
        
        // Utilities
        apiRequest
    };
}

// ========================================
// Usage Examples in Comments
// ========================================

/*
// Example 1: Basic user Wi-Fi access request
async function handleWiFiRequest() {
    const phoneNumber = '255700000000';
    const macAddress = 'AA:BB:CC:DD:EE:FF';
    
    try {
        const result = await requestWiFiAccess(phoneNumber, macAddress);
        
        if (result.success) {
            if (result.redirect_url) {
                // Redirect to payment
                window.location.href = result.redirect_url;
            } else {
                // Already has access
                alert('You already have Wi-Fi access!');
            }
        } else {
            alert('Error: ' + result.message);
        }
    } catch (error) {
        console.error('Wi-Fi request failed:', error);
        alert('Failed to request Wi-Fi access');
    }
}

// Example 2: Admin login and dashboard loading
async function adminDashboardFlow() {
    try {
        // Login
        await adminLogin('admin', 'your_password');
        
        // Load dashboard
        const dashboard = await loadAdminDashboard();
        
        if (dashboard.success) {
            console.log('Dashboard data:', dashboard.data);
            // Update UI with dashboard data
        }
    } catch (error) {
        console.error('Admin flow failed:', error);
    }
}

// Example 3: Voucher redemption
async function redeemUserVoucher() {
    const phoneNumber = '255700000000';
    const voucherCode = 'KITONGA-12345';
    const macAddress = 'AA:BB:CC:DD:EE:FF';
    
    try {
        const result = await redeemVoucher(phoneNumber, voucherCode, macAddress);
        
        if (result.success) {
            alert('Voucher redeemed successfully! You now have Wi-Fi access.');
        } else {
            alert('Voucher redemption failed: ' + result.message);
        }
    } catch (error) {
        console.error('Voucher redemption failed:', error);
    }
}

// Example 4: Payment status polling
async function waitForPayment(orderReference) {
    try {
        const result = await pollPaymentStatus(orderReference, 30, 10000);
        
        if (result.success) {
            alert('Payment completed successfully!');
            // Grant access or redirect to success page
        } else {
            alert('Payment failed or timed out');
        }
    } catch (error) {
        console.error('Payment polling failed:', error);
    }
}
*/
