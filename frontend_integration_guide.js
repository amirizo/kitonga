/**
 * KITONGA WI-FI BILLING SYSTEM - FRONTEND API INTEGRATION GUIDE
 * Complete JavaScript examples for all API endpoints
 * Updated: October 28, 2025
 */

// ========================================
// CONFIGURATION
// ========================================

const API_CONFIG = {
    baseURL: 'http://127.0.0.1:8000/api',  // Development URL
    // baseURL: 'https://api.kitonga.klikcell.com/api',  // Production URL
    adminToken: 'kitonga_admin_secure_token_2025',
    headers: {
        'Content-Type': 'application/json',
        'X-Admin-Access': 'kitonga_admin_secure_token_2025'
    }
};

// ========================================
// UTILITY FUNCTIONS
// ========================================

// Generic API request function
async function apiRequest(endpoint, options = {}) {
    const url = `${API_CONFIG.baseURL}${endpoint}`;
    const config = {
        headers: API_CONFIG.headers,
        ...options
    };

    try {
        console.log(`🔗 API Request: ${config.method || 'GET'} ${url}`);
        const response = await fetch(url, config);
        
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP ${response.status}: ${errorText}`);
        }
        
        const data = await response.json();
        console.log('✅ API Response:', data);
        return data;
    } catch (error) {
        console.error('❌ API Error:', error);
        throw error;
    }
}

// ========================================
// AUTHENTICATION APIs
// ========================================

// User Registration
async function registerUser(userData) {
    return await apiRequest('/register/', {
        method: 'POST',
        body: JSON.stringify({
            username: userData.username,
            email: userData.email,
            password: userData.password,
            phone_number: userData.phoneNumber,
            first_name: userData.firstName,
            last_name: userData.lastName
        })
    });
}

// Example usage:
const registerExample = () => {
    registerUser({
        username: 'john_doe',
        email: 'john@example.com',
        password: 'SecurePass123!',
        phoneNumber: '+255700123456',
        firstName: 'John',
        lastName: 'Doe'
    }).then(response => {
        console.log('User registered:', response);
        // Handle successful registration
        localStorage.setItem('authToken', response.token);
    }).catch(error => {
        console.error('Registration failed:', error);
    });
};

// User Login
async function loginUser(credentials) {
    return await apiRequest('/login/', {
        method: 'POST',
        body: JSON.stringify({
            username: credentials.username,
            password: credentials.password
        })
    });
}

// Example usage:
const loginExample = () => {
    loginUser({
        username: 'john_doe',
        password: 'SecurePass123!'
    }).then(response => {
        console.log('Login successful:', response);
        localStorage.setItem('authToken', response.token);
        localStorage.setItem('userId', response.user.id);
    }).catch(error => {
        console.error('Login failed:', error);
    });
};

// ========================================
// USER MANAGEMENT APIs
// ========================================

// Get All Users (Admin only)
async function getAllUsers() {
    return await apiRequest('/users/');
}

// Get User Profile
async function getUserProfile(userId) {
    return await apiRequest(`/users/${userId}/`);
}

// Update User Profile
async function updateUserProfile(userId, updateData) {
    return await apiRequest(`/users/${userId}/`, {
        method: 'PUT',
        body: JSON.stringify(updateData)
    });
}

// Example usage:
const userManagementExample = () => {
    // Get current user profile
    const userId = localStorage.getItem('userId');
    getUserProfile(userId).then(user => {
        console.log('User profile:', user);
        document.getElementById('userName').textContent = user.username;
        document.getElementById('userEmail').textContent = user.email;
    });

    // Update user profile
    updateUserProfile(userId, {
        first_name: 'Updated Name',
        phone_number: '+255700987654'
    }).then(response => {
        console.log('Profile updated:', response);
    });
};

// ========================================
// PACKAGE MANAGEMENT APIs
// ========================================

// Get All Packages
async function getPackages() {
    return await apiRequest('/packages/');
}

// Get Package by ID
async function getPackage(packageId) {
    return await apiRequest(`/packages/${packageId}/`);
}

// Create Package (Admin only)
async function createPackage(packageData) {
    return await apiRequest('/packages/', {
        method: 'POST',
        body: JSON.stringify(packageData)
    });
}

// Example usage:
const packageExample = () => {
    // Display packages in UI
    getPackages().then(packages => {
        const packageList = document.getElementById('packageList');
        packageList.innerHTML = '';
        
        packages.forEach(pkg => {
            const packageElement = document.createElement('div');
            packageElement.className = 'package-card';
            packageElement.innerHTML = `
                <h3>${pkg.name}</h3>
                <p>Price: ${pkg.price} TZS</p>
                <p>Duration: ${pkg.duration_hours} hours</p>
                <p>Data Limit: ${pkg.data_limit_mb || 'Unlimited'} MB</p>
                <button onclick="purchasePackage(${pkg.id})">Buy Now</button>
            `;
            packageList.appendChild(packageElement);
        });
    });
};

// ========================================
// SUBSCRIPTION MANAGEMENT APIs
// ========================================

// Get User Subscriptions
async function getUserSubscriptions(userId) {
    return await apiRequest(`/subscriptions/?user=${userId}`);
}

// Create Subscription
async function createSubscription(subscriptionData) {
    return await apiRequest('/subscriptions/', {
        method: 'POST',
        body: JSON.stringify(subscriptionData)
    });
}

// Get Active Subscription
async function getActiveSubscription(userId) {
    return await apiRequest(`/subscriptions/active/?user=${userId}`);
}

// Example usage:
const subscriptionExample = () => {
    const userId = localStorage.getItem('userId');
    
    // Check active subscription
    getActiveSubscription(userId).then(subscription => {
        if (subscription) {
            document.getElementById('subscriptionStatus').innerHTML = `
                <div class="active-subscription">
                    <h3>Active Plan: ${subscription.package.name}</h3>
                    <p>Expires: ${new Date(subscription.end_date).toLocaleDateString()}</p>
                    <p>Data Used: ${subscription.data_used_mb || 0} MB</p>
                </div>
            `;
        } else {
            document.getElementById('subscriptionStatus').innerHTML = `
                <div class="no-subscription">
                    <p>No active subscription</p>
                    <button onclick="showPackages()">Choose a Plan</button>
                </div>
            `;
        }
    });
};

// ========================================
// PAYMENT APIs
// ========================================

// Initiate Payment
async function initiatePayment(paymentData) {
    return await apiRequest('/payments/initiate/', {
        method: 'POST',
        body: JSON.stringify(paymentData)
    });
}

// Check Payment Status
async function checkPaymentStatus(paymentId) {
    return await apiRequest(`/payments/${paymentId}/status/`);
}

// Get Payment History
async function getPaymentHistory(userId) {
    return await apiRequest(`/payments/history/?user=${userId}`);
}

// Example usage:
const paymentExample = () => {
    // Purchase package
    function purchasePackage(packageId) {
        const userId = localStorage.getItem('userId');
        
        initiatePayment({
            user: userId,
            package: packageId,
            payment_method: 'clickpesa',
            phone_number: '+255700123456'
        }).then(response => {
            console.log('Payment initiated:', response);
            
            // Show payment instructions
            alert(`Payment initiated! Reference: ${response.payment_reference}`);
            
            // Poll for payment status
            const pollPayment = setInterval(() => {
                checkPaymentStatus(response.payment_id).then(status => {
                    if (status.status === 'completed') {
                        clearInterval(pollPayment);
                        alert('Payment successful! Your subscription is now active.');
                        location.reload(); // Refresh to show new subscription
                    } else if (status.status === 'failed') {
                        clearInterval(pollPayment);
                        alert('Payment failed. Please try again.');
                    }
                });
            }, 3000); // Check every 3 seconds
        });
    }
    
    window.purchasePackage = purchasePackage; // Make function global
};

// ========================================
// MIKROTIK INTEGRATION APIs
// ========================================

// Get MikroTik Status
async function getMikrotikStatus() {
    return await apiRequest('/mikrotik/status/');
}

// Get User Status on MikroTik
async function getUserMikrotikStatus(username) {
    return await apiRequest(`/mikrotik/user-status/?username=${username}`);
}

// Connect User to Hotspot
async function connectToHotspot(userData) {
    return await apiRequest('/mikrotik/connect/', {
        method: 'POST',
        body: JSON.stringify(userData)
    });
}

// Disconnect User from Hotspot
async function disconnectFromHotspot(username) {
    return await apiRequest('/mikrotik/disconnect/', {
        method: 'POST',
        body: JSON.stringify({ username })
    });
}

// Example usage:
const mikrotikExample = () => {
    // Dashboard status
    getMikrotikStatus().then(status => {
        document.getElementById('routerStatus').innerHTML = `
            <div class="router-status ${status.connection_status}">
                <h3>Router Status</h3>
                <p>Status: ${status.connection_status}</p>
                <p>Router IP: ${status.router_ip}</p>
                <p>Hotspot: ${status.hotspot_name}</p>
                <p>Active Users: ${status.active_users}</p>
            </div>
        `;
    });

    // Connect to Wi-Fi
    function connectToWiFi() {
        const username = localStorage.getItem('username');
        const macAddress = 'AA:BB:CC:DD:EE:FF'; // Get from device
        
        connectToHotspot({
            username: username,
            mac_address: macAddress
        }).then(response => {
            console.log('Connected to hotspot:', response);
            alert('Successfully connected to Wi-Fi!');
        }).catch(error => {
            console.error('Connection failed:', error);
            alert('Failed to connect to Wi-Fi. Please check your subscription.');
        });
    }
    
    window.connectToWiFi = connectToWiFi;
};

// ========================================
// COMPLETE DASHBOARD EXAMPLE
// ========================================

class KitongaDashboard {
    constructor() {
        this.userId = localStorage.getItem('userId');
        this.authToken = localStorage.getItem('authToken');
        this.init();
    }

    async init() {
        if (!this.userId || !this.authToken) {
            this.showLogin();
            return;
        }

        try {
            await this.loadDashboard();
        } catch (error) {
            console.error('Dashboard load error:', error);
            this.showLogin();
        }
    }

    async loadDashboard() {
        // Load user profile
        const user = await getUserProfile(this.userId);
        document.getElementById('userName').textContent = user.first_name || user.username;

        // Load active subscription
        const subscription = await getActiveSubscription(this.userId);
        this.displaySubscription(subscription);

        // Load packages
        const packages = await getPackages();
        this.displayPackages(packages);

        // Load router status
        const routerStatus = await getMikrotikStatus();
        this.displayRouterStatus(routerStatus);

        // Load payment history
        const payments = await getPaymentHistory(this.userId);
        this.displayPaymentHistory(payments);
    }

    displaySubscription(subscription) {
        const container = document.getElementById('subscriptionContainer');
        if (subscription) {
            const daysRemaining = Math.ceil((new Date(subscription.end_date) - new Date()) / (1000 * 60 * 60 * 24));
            container.innerHTML = `
                <div class="subscription-active">
                    <h3>${subscription.package.name}</h3>
                    <p>Expires in ${daysRemaining} days</p>
                    <p>Data Used: ${subscription.data_used_mb || 0} MB</p>
                    <div class="progress-bar">
                        <div class="progress" style="width: ${(subscription.data_used_mb / subscription.package.data_limit_mb) * 100}%"></div>
                    </div>
                </div>
            `;
        } else {
            container.innerHTML = `
                <div class="no-subscription">
                    <p>No active subscription</p>
                    <button onclick="dashboard.showPackages()">Choose a Plan</button>
                </div>
            `;
        }
    }

    displayPackages(packages) {
        const container = document.getElementById('packagesContainer');
        container.innerHTML = packages.map(pkg => `
            <div class="package-card">
                <h4>${pkg.name}</h4>
                <p class="price">${pkg.price} TZS</p>
                <p>Duration: ${pkg.duration_hours}h</p>
                <p>Data: ${pkg.data_limit_mb || 'Unlimited'} MB</p>
                <button onclick="dashboard.purchasePackage(${pkg.id})" class="btn-primary">
                    Buy Now
                </button>
            </div>
        `).join('');
    }

    displayRouterStatus(status) {
        const container = document.getElementById('routerStatusContainer');
        const statusClass = status.connection_status === 'connected' ? 'status-online' : 'status-offline';
        container.innerHTML = `
            <div class="router-status ${statusClass}">
                <h4>Router Status</h4>
                <p>Status: <span class="${statusClass}">${status.connection_status}</span></p>
                <p>Active Users: ${status.active_users}</p>
                <p>Hotspot: ${status.hotspot_name}</p>
            </div>
        `;
    }

    displayPaymentHistory(payments) {
        const container = document.getElementById('paymentHistoryContainer');
        container.innerHTML = `
            <h4>Payment History</h4>
            <div class="payment-list">
                ${payments.map(payment => `
                    <div class="payment-item">
                        <span>${payment.package_name}</span>
                        <span>${payment.amount} TZS</span>
                        <span class="status-${payment.status}">${payment.status}</span>
                        <span>${new Date(payment.created_at).toLocaleDateString()}</span>
                    </div>
                `).join('')}
            </div>
        `;
    }

    async purchasePackage(packageId) {
        try {
            const payment = await initiatePayment({
                user: this.userId,
                package: packageId,
                payment_method: 'clickpesa',
                phone_number: '+255700123456' // Should get from user input
            });

            alert(`Payment initiated! Reference: ${payment.payment_reference}`);
            
            // Poll for payment completion
            this.pollPaymentStatus(payment.payment_id);
        } catch (error) {
            alert('Payment initiation failed. Please try again.');
        }
    }

    pollPaymentStatus(paymentId) {
        const interval = setInterval(async () => {
            try {
                const status = await checkPaymentStatus(paymentId);
                if (status.status === 'completed') {
                    clearInterval(interval);
                    alert('Payment successful! Your subscription is now active.');
                    this.loadDashboard(); // Refresh dashboard
                } else if (status.status === 'failed') {
                    clearInterval(interval);
                    alert('Payment failed. Please try again.');
                }
            } catch (error) {
                clearInterval(interval);
                console.error('Payment status check failed:', error);
            }
        }, 3000);
    }

    showLogin() {
        document.body.innerHTML = `
            <div class="login-container">
                <h2>Kitonga Wi-Fi Login</h2>
                <form id="loginForm">
                    <input type="text" id="username" placeholder="Username" required>
                    <input type="password" id="password" placeholder="Password" required>
                    <button type="submit">Login</button>
                </form>
            </div>
        `;

        document.getElementById('loginForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;

            try {
                const response = await loginUser({ username, password });
                localStorage.setItem('authToken', response.token);
                localStorage.setItem('userId', response.user.id);
                localStorage.setItem('username', response.user.username);
                location.reload();
            } catch (error) {
                alert('Login failed. Please check your credentials.');
            }
        });
    }
}

// ========================================
// INITIALIZATION
// ========================================

// Initialize dashboard when page loads
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new KitongaDashboard();
});

// ========================================
// CSS STYLES (Add to your stylesheet)
// ========================================

const CSS_STYLES = `
.package-card {
    border: 1px solid #ddd;
    border-radius: 8px;
    padding: 16px;
    margin: 8px;
    text-align: center;
}

.subscription-active {
    background: #e8f5e8;
    border: 1px solid #4caf50;
    border-radius: 8px;
    padding: 16px;
}

.no-subscription {
    background: #fff3cd;
    border: 1px solid #ffc107;
    border-radius: 8px;
    padding: 16px;
    text-align: center;
}

.router-status {
    padding: 16px;
    border-radius: 8px;
    margin: 16px 0;
}

.status-online {
    background: #e8f5e8;
    border: 1px solid #4caf50;
}

.status-offline {
    background: #ffebee;
    border: 1px solid #f44336;
}

.progress-bar {
    width: 100%;
    height: 20px;
    background: #f0f0f0;
    border-radius: 10px;
    overflow: hidden;
}

.progress {
    height: 100%;
    background: #4caf50;
    transition: width 0.3s ease;
}

.btn-primary {
    background: #2196f3;
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 4px;
    cursor: pointer;
}

.btn-primary:hover {
    background: #1976d2;
}
`;

console.log('🚀 Kitonga Wi-Fi API Integration Guide Loaded');
console.log('📖 Usage: Call any function or initialize new KitongaDashboard()');
