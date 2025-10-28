// 🌐 PRODUCTION API CLIENT FOR KITONGA WI-FI
// Updated for production server: https://api.kitonga.klikcell.com

class KitongaProductionAPI {
    constructor() {
        this.baseURL = 'https://api.kitonga.klikcell.com/api';
        this.adminToken = 'kitonga_admin_secure_token_2025';
        this.userToken = localStorage.getItem('authToken');
        
        console.log('🔧 Kitonga API initialized for production server');
        console.log('🌐 Base URL:', this.baseURL);
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        
        // Default headers
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };

        // Add authentication based on endpoint
        if (endpoint.startsWith('/auth/') || endpoint.startsWith('/mikrotik/') || endpoint.startsWith('/dashboard/')) {
            // Admin endpoints - try both methods
            headers['X-Admin-Access'] = this.adminToken;
            
            // Also try user token if available
            if (this.userToken) {
                headers['Authorization'] = `Token ${this.userToken}`;
            }
        } else if (this.userToken) {
            // User endpoints
            headers['Authorization'] = `Token ${this.userToken}`;
        }

        const config = {
            method: 'GET',
            headers,
            ...options
        };

        try {
            console.log(`🔗 API Request: ${config.method} ${url}`);
            console.log('📋 Headers:', Object.keys(headers));
            
            const response = await fetch(url, config);
            
            console.log(`📊 Response Status: ${response.status}`);
            
            if (!response.ok) {
                let errorData;
                try {
                    errorData = await response.json();
                } catch {
                    errorData = { message: await response.text() };
                }
                
                console.error(`❌ API Error ${response.status}:`, errorData);
                throw new Error(`HTTP ${response.status}: ${errorData.message || response.statusText}`);
            }
            
            const data = await response.json();
            console.log('✅ API Response received');
            return data;
            
        } catch (error) {
            console.error('❌ Request failed:', error);
            
            // Specific error messages for production
            if (error.message.includes('Failed to fetch')) {
                throw new Error('Cannot connect to production API server. Please check your internet connection and ensure https://api.kitonga.klikcell.com is accessible.');
            }
            
            if (error.message.includes('401')) {
                throw new Error('Authentication failed. Please log in or check your credentials.');
            }
            
            if (error.message.includes('403')) {
                throw new Error('Access forbidden. You may not have the required permissions.');
            }
            
            if (error.message.includes('500')) {
                throw new Error('Server error. The production server is experiencing issues.');
            }
            
            throw error;
        }
    }

    // ✅ Health check - always works
    async testConnection() {
        try {
            const health = await this.request('/health/');
            console.log('✅ Production server connection successful:', health);
            return { success: true, data: health };
        } catch (error) {
            console.error('❌ Production server connection failed:', error);
            return { success: false, error: error.message };
        }
    }

    // ✅ Admin login - required for authentication
    async adminLogin(username, password) {
        try {
            const response = await this.request('/auth/login/', {
                method: 'POST',
                body: JSON.stringify({ username, password })
            });
            
            if (response.token) {
                this.userToken = response.token;
                localStorage.setItem('authToken', response.token);
                localStorage.setItem('userId', response.user.id);
                localStorage.setItem('isAdmin', response.user.is_staff);
                console.log('✅ Admin login successful');
            }
            
            return response;
        } catch (error) {
            console.error('❌ Admin login failed:', error);
            throw error;
        }
    }

    // ✅ Get admin profile (requires login first)
    async getAdminProfile() {
        try {
            return await this.request('/auth/profile/');
        } catch (error) {
            console.error('❌ Admin profile fetch failed:', error);
            
            if (error.message.includes('401')) {
                throw new Error('Not authenticated. Please log in first using adminLogin()');
            }
            
            throw error;
        }
    }

    // ✅ Get MikroTik status
    async getMikrotikStatus() {
        return await this.request('/mikrotik/status/');
    }

    // ✅ Get user status
    async getUserMikrotikStatus(username) {
        return await this.request(`/mikrotik/user-status/?username=${encodeURIComponent(username)}`);
    }

    // ✅ Get packages/bundles
    async getPackages() {
        return await this.request('/bundles/');
    }

    // ✅ Check user subscription status
    async getUserStatus(phoneNumber) {
        return await this.request(`/user-status/${encodeURIComponent(phoneNumber)}/`);
    }

    // ✅ Initiate payment
    async initiatePayment(paymentData) {
        return await this.request('/initiate-payment/', {
            method: 'POST',
            body: JSON.stringify(paymentData)
        });
    }

    // ✅ Check payment status
    async checkPaymentStatus(orderReference) {
        return await this.request(`/payment-status/${orderReference}/`);
    }

    // ✅ Dashboard stats (admin only)
    async getDashboardStats() {
        return await this.request('/dashboard-stats/');
    }

    // ✅ Logout
    logout() {
        this.userToken = null;
        localStorage.removeItem('authToken');
        localStorage.removeItem('userId');
        localStorage.removeItem('isAdmin');
        console.log('✅ Logged out successfully');
    }

    // ✅ Check if user is authenticated
    isAuthenticated() {
        return !!this.userToken || !!localStorage.getItem('authToken');
    }

    // ✅ Check if user is admin
    isAdmin() {
        return localStorage.getItem('isAdmin') === 'true';
    }
}

// ✅ Comprehensive testing function
async function testProductionAPI() {
    console.log('🧪 Starting Production API Tests...\n');
    
    const api = new KitongaProductionAPI();
    let testResults = [];

    // Test 1: Basic connectivity
    console.log('1️⃣ Testing production server connectivity...');
    const connectionTest = await api.testConnection();
    testResults.push({
        test: 'Server Connection',
        status: connectionTest.success ? '✅' : '❌',
        message: connectionTest.success ? 'Connected successfully' : connectionTest.error
    });

    if (!connectionTest.success) {
        console.log('❌ Cannot connect to production server. Stopping tests.');
        return testResults;
    }

    // Test 2: Anonymous endpoints
    console.log('\n2️⃣ Testing public endpoints...');
    try {
        const packages = await api.getPackages();
        testResults.push({
            test: 'Get Packages (Public)',
            status: '✅',
            message: `Found ${packages.length || 0} packages`
        });
    } catch (error) {
        testResults.push({
            test: 'Get Packages (Public)',
            status: '❌',
            message: error.message
        });
    }

    // Test 3: Authentication required endpoints
    console.log('\n3️⃣ Testing authentication required endpoints...');
    try {
        await api.getAdminProfile();
        testResults.push({
            test: 'Admin Profile (Auth Required)',
            status: '✅',
            message: 'Profile retrieved successfully'
        });
    } catch (error) {
        testResults.push({
            test: 'Admin Profile (Auth Required)',
            status: '❌',
            message: 'Expected: Requires authentication first'
        });
    }

    // Test 4: MikroTik endpoints
    console.log('\n4️⃣ Testing MikroTik endpoints...');
    try {
        const status = await api.getMikrotikStatus();
        testResults.push({
            test: 'MikroTik Status (Admin)',
            status: '✅',
            message: `Router status: ${status.connection_status || 'Unknown'}`
        });
    } catch (error) {
        testResults.push({
            test: 'MikroTik Status (Admin)',
            status: '❌',
            message: error.message
        });
    }

    // Display results
    console.log('\n📊 Test Results Summary:');
    testResults.forEach(result => {
        console.log(`${result.status} ${result.test}: ${result.message}`);
    });

    // Authentication guide
    if (testResults.some(r => r.message.includes('authentication'))) {
        console.log('\n🔐 Authentication Required:');
        console.log('To access admin endpoints, you need to log in first:');
        console.log('');
        console.log('// Example login:');
        console.log('await api.adminLogin("your_admin_username", "your_password");');
        console.log('');
        console.log('// Then you can access admin endpoints:');
        console.log('const profile = await api.getAdminProfile();');
        console.log('const mikrotikStatus = await api.getMikrotikStatus();');
    }

    return testResults;
}

// ✅ Simple login form for testing
function createTestLoginForm() {
    const formHTML = `
        <div id="api-test-container" style="
            position: fixed; 
            top: 20px; 
            right: 20px; 
            background: white; 
            border: 2px solid #007bff; 
            border-radius: 8px; 
            padding: 20px; 
            box-shadow: 0 4px 12px rgba(0,0,0,0.15); 
            z-index: 10000;
            max-width: 300px;
            font-family: Arial, sans-serif;
        ">
            <h3 style="margin: 0 0 15px 0; color: #007bff;">🧪 API Test Panel</h3>
            
            <div style="margin-bottom: 15px;">
                <button onclick="testProductionAPI()" style="
                    background: #28a745; 
                    color: white; 
                    border: none; 
                    padding: 8px 12px; 
                    border-radius: 4px; 
                    cursor: pointer;
                    width: 100%;
                    margin-bottom: 8px;
                ">🔍 Test API Connection</button>
            </div>

            <div style="border-top: 1px solid #eee; padding-top: 15px;">
                <h4 style="margin: 0 0 10px 0; font-size: 14px;">Admin Login Test:</h4>
                <input type="text" id="test-username" placeholder="Admin Username" style="
                    width: 100%; 
                    padding: 6px; 
                    margin-bottom: 8px; 
                    border: 1px solid #ddd; 
                    border-radius: 4px;
                    box-sizing: border-box;
                ">
                <input type="password" id="test-password" placeholder="Admin Password" style="
                    width: 100%; 
                    padding: 6px; 
                    margin-bottom: 8px; 
                    border: 1px solid #ddd; 
                    border-radius: 4px;
                    box-sizing: border-box;
                ">
                <button onclick="testAdminLogin()" style="
                    background: #007bff; 
                    color: white; 
                    border: none; 
                    padding: 6px 12px; 
                    border-radius: 4px; 
                    cursor: pointer;
                    width: 100%;
                ">🔐 Test Login</button>
            </div>

            <div style="margin-top: 15px;">
                <button onclick="document.getElementById('api-test-container').remove()" style="
                    background: #dc3545; 
                    color: white; 
                    border: none; 
                    padding: 4px 8px; 
                    border-radius: 4px; 
                    cursor: pointer;
                    font-size: 12px;
                ">✕ Close</button>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', formHTML);
}

// ✅ Test admin login function
async function testAdminLogin() {
    const username = document.getElementById('test-username').value;
    const password = document.getElementById('test-password').value;
    
    if (!username || !password) {
        alert('Please enter both username and password');
        return;
    }
    
    const api = new KitongaProductionAPI();
    
    try {
        console.log('🔐 Attempting admin login...');
        const loginResult = await api.adminLogin(username, password);
        console.log('✅ Login successful:', loginResult);
        
        // Test admin profile after login
        const profile = await api.getAdminProfile();
        console.log('✅ Admin profile retrieved:', profile);
        
        alert('✅ Login successful! Check console for details.');
        
        // Test MikroTik status
        try {
            const mikrotikStatus = await api.getMikrotikStatus();
            console.log('✅ MikroTik status:', mikrotikStatus);
        } catch (error) {
            console.log('⚠️ MikroTik status failed:', error.message);
        }
        
    } catch (error) {
        console.error('❌ Login failed:', error);
        alert('❌ Login failed: ' + error.message);
    }
}

// ✅ Initialize for global use
window.KitongaProductionAPI = KitongaProductionAPI;
window.testProductionAPI = testProductionAPI;
window.createTestLoginForm = createTestLoginForm;
window.testAdminLogin = testAdminLogin;

// ✅ Auto-create API instance
window.kitongaAPI = new KitongaProductionAPI();

console.log('🚀 Kitonga Production API Client loaded!');
console.log('📖 Usage:');
console.log('  • testProductionAPI() - Test all endpoints');
console.log('  • createTestLoginForm() - Show login test form');
console.log('  • kitongaAPI.adminLogin(username, password) - Login');
console.log('  • kitongaAPI.getMikrotikStatus() - Get router status');

export default KitongaProductionAPI;
