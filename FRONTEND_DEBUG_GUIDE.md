# 🔧 Frontend API Error Debugging Guide

## ❌ Error: "TypeError: Failed to fetch"

This error occurs when your frontend can't connect to the Django backend. Here are the most common causes and solutions:

## 🔍 **Common Causes & Solutions**

### 1. **Backend Server Not Running**
```bash
# ✅ Start Django server
python manage.py runserver 0.0.0.0:8000

# ✅ Verify server is running
curl http://127.0.0.1:8000/api/health/
```

### 2. **Wrong API Base URL**
```javascript
// ❌ Wrong - if your frontend is on different port
const API_BASE = 'http://localhost:3000/api'

// ✅ Correct - Production API server URL
const API_BASE = 'https://api.kitonga.klikcell.com/api'
```

### 3. **CORS Issues**
Check your Django CORS settings in `settings.py`:

```python
# ✅ Ensure CORS is properly configured
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
]

CORS_ALLOW_CREDENTIALS = True
```

### 4. **Authentication Issues**
Your error is specifically on `getAdminProfile()` - this requires authentication:

```javascript
// ❌ Missing authentication
fetch('/api/auth/profile/')

// ✅ With proper authentication
fetch('/api/auth/profile/', {
    headers: {
        'Authorization': `Token ${your_token}`,
        // OR for admin access
        'X-Admin-Access': 'kitonga_admin_secure_token_2025'
    }
})
```

## 🚀 **Fixed API Client for Your Frontend**

```javascript
// ✅ Complete working API client
class KitongaAPI {
    constructor() {
        // ✅ Production API server
        this.baseURL = 'https://api.kitonga.klikcell.com/api';
        this.adminToken = 'kitonga_admin_secure_token_2025';
        this.userToken = localStorage.getItem('authToken');
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
            // Admin endpoints - use both methods for compatibility
            headers['X-Admin-Access'] = this.adminToken;
            
            // Also add user token if available (required for production)
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
            console.log('📋 Headers:', headers);
            
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
            console.log('✅ API Response:', data);
            return data;
            
        } catch (error) {
            console.error('❌ Request failed:', error);
            
            // Enhanced error handling for production
            if (error.message.includes('Failed to fetch')) {
                throw new Error('Cannot connect to server. Please check if the production API server is accessible at https://api.kitonga.klikcell.com');
            }
            
            if (error.message.includes('401')) {
                throw new Error('Authentication failed. Please log in first.');
            }
            
            if (error.message.includes('403')) {
                throw new Error('Access forbidden. You may not have admin permissions.');
            }
            
            if (error.message.includes('500')) {
                throw new Error('Server error. The production server is experiencing issues.');
            }
            
            throw error;
        }
    }

    // ✅ Admin Profile with proper error handling  
    async getAdminProfile() {
        // Check if user token exists for production requirements
        if (!this.userToken) {
            throw new Error('Authentication required. Please log in first using login() method.');
        }
        
        try {
            return await this.request('/auth/profile/');
        } catch (error) {
            console.error('Admin profile fetch failed:', error);
            
            // Provide specific error messages
            if (error.message.includes('401')) {
                throw new Error('Authentication failed. Please log in again.');
            }
            
            if (error.message.includes('403')) {
                throw new Error('Access denied. You may not have admin permissions.');
            }
            
            throw new Error(`Failed to get admin profile: ${error.message}`);
        }
    }

    // ✅ Login method with enhanced error handling
    async login(username, password) {
        try {
            const response = await this.request('/auth/login/', {
                method: 'POST',
                body: JSON.stringify({ username, password })
            });
            
            if (response.success && response.token) {
                this.userToken = response.token;
                localStorage.setItem('authToken', response.token);
                localStorage.setItem('userId', response.user.id);
                localStorage.setItem('isAdmin', response.user.is_staff.toString());
                console.log('✅ Login successful, token stored');
            } else {
                throw new Error('Login failed: Invalid response format');
            }
            
            return response;
        } catch (error) {
            console.error('Login failed:', error);
            
            if (error.message.includes('401')) {
                throw new Error('Invalid username or password');
            }
            
            if (error.message.includes('400')) {
                throw new Error('Please provide both username and password');
            }
            
            throw error;
        }
    }

    // ✅ Test connection with better error details
    async testConnection() {
        try {
            const health = await this.request('/health/');
            console.log('✅ Server connection successful:', health);
            return { success: true, data: health };
        } catch (error) {
            console.error('❌ Server connection failed:', error);
            return { success: false, error: error.message };
        }
    }

    // ✅ Test admin authentication with proper checks
    async testAdminAuth() {
        try {
            // First check if we have a token
            if (!this.userToken) {
                console.log('❌ No authentication token found. Please log in first.');
                return { success: false, error: 'No authentication token' };
            }
            
            const profile = await this.getAdminProfile();
            console.log('✅ Admin authentication successful:', profile);
            return { success: true, data: profile };
        } catch (error) {
            console.error('❌ Admin authentication failed:', error);
            return { success: false, error: error.message };
        }
    }

    // ✅ Get router status
    async getMikrotikStatus() {
        return await this.request('/mikrotik/status/');
    }

    // ✅ Get packages with error handling
    async getPackages() {
        try {
            return await this.request('/bundles/');
        } catch (error) {
            console.error('Failed to get packages:', error);
            throw new Error(`Failed to load packages: ${error.message}`);
        }
    }

    // ✅ Logout method
    logout() {
        this.userToken = null;
        localStorage.removeItem('authToken');
        localStorage.removeItem('userId');
        localStorage.removeItem('isAdmin');
        console.log('✅ Logged out successfully');
    }

    // ✅ Check if authenticated
    isAuthenticated() {
        return !!this.userToken || !!localStorage.getItem('authToken');
    }

    // ✅ Check if user is admin
    isAdmin() {
        return localStorage.getItem('isAdmin') === 'true';
    }
}

// ✅ Initialize API client
const api = new KitongaAPI();

// ✅ Enhanced test function for debugging
async function debugAPIConnection() {
    console.log('🔧 Starting Enhanced API Debug...');
    console.log('==========================================');
    
    // Test 1: Basic connection
    console.log('\n1️⃣ Testing server connection...');
    const connectionResult = await api.testConnection();
    
    if (!connectionResult.success) {
        console.log('❌ Server is not accessible. Details:', connectionResult.error);
        console.log('\n🔧 Troubleshooting steps:');
        console.log('   - Check internet connection');
        console.log('   - Verify server URL: https://api.kitonga.klikcell.com');
        console.log('   - Check if server is experiencing downtime');
        return;
    }
    
    console.log('✅ Server connection successful');
    console.log('📊 Server info:', connectionResult.data);
    
    // Test 2: Check authentication status
    console.log('\n2️⃣ Checking authentication status...');
    if (!api.isAuthenticated()) {
        console.log('⚠️ No authentication token found');
        console.log('💡 You need to log in first using: await api.login("username", "password")');
    } else {
        console.log('✅ Authentication token found');
        
        // Test admin authentication
        console.log('\n3️⃣ Testing admin authentication...');
        const adminResult = await api.testAdminAuth();
        
        if (!adminResult.success) {
            console.log('❌ Admin authentication failed:', adminResult.error);
            console.log('💡 Try logging in again with admin credentials');
        } else {
            console.log('✅ Admin authentication successful');
            
            // Test 4: MikroTik status
            console.log('\n4️⃣ Testing MikroTik endpoint...');
            try {
                const status = await api.getMikrotikStatus();
                console.log('✅ MikroTik status:', status);
            } catch (error) {
                console.log('❌ MikroTik endpoint failed:', error.message);
            }
            
            // Test 5: Packages endpoint
            console.log('\n5️⃣ Testing packages endpoint...');
            try {
                const packages = await api.getPackages();
                console.log(`✅ Packages loaded: ${packages.length} items`);
            } catch (error) {
                console.log('❌ Packages endpoint failed:', error.message);
            }
        }
    }
    
    console.log('\n==========================================');
    console.log('🎉 API Debug Complete!');
    console.log('\n📖 Next steps:');
    console.log('   1. If not authenticated, run: await api.login("username", "password")');
    console.log('   2. Then test admin endpoints');
    console.log('   3. Check console for detailed error messages');
}

// ✅ Export for use in your components
window.KitongaAPI = KitongaAPI;
window.api = api;
window.debugAPIConnection = debugAPIConnection;

export default KitongaAPI;
```

## 🐛 **Step-by-Step Debugging**

### Step 1: Check Server Status
```bash
# In terminal
python manage.py runserver 0.0.0.0:8000

# In browser or new terminal
curl http://127.0.0.1:8000/api/health/
```

### Step 2: Test in Browser Console
```javascript
// Open browser console and run
debugAPIConnection();
```

### Step 3: Check Authentication
```javascript
// Test admin profile with correct headers
fetch('https://api.kitonga.klikcell.com/api/auth/profile/', {
    headers: {
        'X-Admin-Access': 'kitonga_admin_secure_token_2025'
    }
})
.then(response => response.json())
.then(data => console.log('Profile:', data))
.catch(error => console.error('Error:', error));
```

### Step 4: Check CORS in Browser Network Tab
1. Open browser DevTools (F12)
2. Go to Network tab
3. Try your API call
4. Look for CORS errors in the failed request

## 🔧 **Quick Fixes for Your React Component**

```tsx
// ✅ Fixed admin-layout.tsx with proper error handling
import { useEffect, useState } from 'react';

export default function AdminLayout({ children }: { children: React.ReactNode }) {
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [showLogin, setShowLogin] = useState(false);

    useEffect(() => {
        checkAuthStatus();
    }, []);

    const checkAuthStatus = async () => {
        try {
            setLoading(true);
            setError(null);
            
            // Initialize API client
            const api = new KitongaAPI();
            
            // First test basic connection
            const connectionResult = await api.testConnection();
            if (!connectionResult.success) {
                throw new Error(`Server connection failed: ${connectionResult.error}`);
            }
            
            // Check if user has authentication token
            if (!api.isAuthenticated()) {
                setShowLogin(true);
                setLoading(false);
                return;
            }
            
            // Test admin authentication
            const adminResult = await api.testAdminAuth();
            if (!adminResult.success) {
                if (adminResult.error.includes('No authentication token')) {
                    setShowLogin(true);
                } else {
                    throw new Error(`Admin authentication failed: ${adminResult.error}`);
                }
                setLoading(false);
                return;
            }
            
            // Check if user has admin permissions
            const profile = adminResult.data;
            if (profile.success && profile.is_authenticated && profile.user.is_staff) {
                setIsAuthenticated(true);
                setShowLogin(false);
            } else {
                throw new Error('User does not have admin permissions');
            }
            
        } catch (error) {
            console.error('Auth check failed:', error);
            const errorMessage = error instanceof Error ? error.message : 'Authentication failed';
            
            if (errorMessage.includes('Authentication required') || 
                errorMessage.includes('No authentication token') ||
                errorMessage.includes('Please log in')) {
                setShowLogin(true);
            } else {
                setError(errorMessage);
            }
            
            setIsAuthenticated(false);
        } finally {
            setLoading(false);
        }
    };

    const handleLogin = async (username: string, password: string) => {
        try {
            setError(null);
            const api = new KitongaAPI();
            await api.login(username, password);
            await checkAuthStatus(); // Re-check after login
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Login failed';
            setError(errorMessage);
        }
    };

    const handleLogout = () => {
        const api = new KitongaAPI();
        api.logout();
        setIsAuthenticated(false);
        setShowLogin(true);
        setError(null);
    };

    // Loading state
    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <div className="text-center">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
                    <p className="mt-2 text-gray-600">Checking authentication...</p>
                </div>
            </div>
        );
    }

    // Error state (not authentication related)
    if (error && !showLogin) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <div className="text-center p-6 bg-red-50 border border-red-200 rounded-lg max-w-md">
                    <h2 className="text-lg font-semibold text-red-800 mb-2">Connection Error</h2>
                    <p className="text-red-600 mb-4">{error}</p>
                    <div className="space-y-2">
                        <button 
                            onClick={checkAuthStatus}
                            className="w-full bg-red-600 text-white px-4 py-2 rounded hover:bg-red-700"
                        >
                            Retry Connection
                        </button>
                        <button 
                            onClick={() => {
                                setError(null);
                                setShowLogin(true);
                            }}
                            className="w-full bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
                        >
                            Try Login
                        </button>
                    </div>
                    <div className="mt-4 text-sm text-gray-600">
                        <p>Make sure:</p>
                        <ul className="text-left mt-2">
                            <li>• Production API server is accessible: <code>https://api.kitonga.klikcell.com</code></li>
                            <li>• Server is not experiencing downtime</li>
                            <li>• No network connectivity issues</li>
                        </ul>
                    </div>
                </div>
            </div>
        );
    }

    // Login form
    if (showLogin) {
        return <LoginForm onLogin={handleLogin} error={error} />;
    }

    // Authenticated - show admin content
    return (
        <div className="min-h-screen bg-gray-100">
            {/* Admin Header */}
            <header className="bg-white shadow">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="flex justify-between items-center py-6">
                        <h1 className="text-2xl font-bold text-gray-900">
                            Kitonga Admin Dashboard
                        </h1>
                        <button
                            onClick={handleLogout}
                            className="bg-red-600 text-white px-4 py-2 rounded hover:bg-red-700"
                        >
                            Logout
                        </button>
                    </div>
                </div>
            </header>

            {/* Main Content */}
            <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
                {children}
            </main>
        </div>
    );
}

// Login Form Component
interface LoginFormProps {
    onLogin: (username: string, password: string) => Promise<void>;
    error: string | null;
}

function LoginForm({ onLogin, error }: LoginFormProps) {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        
        if (!username || !password) {
            return;
        }

        setLoading(true);
        try {
            await onLogin(username, password);
        } catch (error) {
            // Error handled by parent
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex items-center justify-center min-h-screen bg-gray-50">
            <div className="max-w-md w-full space-y-8">
                <div>
                    <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
                        Admin Login
                    </h2>
                    <p className="mt-2 text-center text-sm text-gray-600">
                        Sign in to access Kitonga Wi-Fi admin panel
                    </p>
                </div>
                
                <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
                    <div className="rounded-md shadow-sm -space-y-px">
                        <div>
                            <input
                                type="text"
                                required
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                className="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-t-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
                                placeholder="Username"
                            />
                        </div>
                        <div>
                            <input
                                type="password"
                                required
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-b-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
                                placeholder="Password"
                            />
                        </div>
                    </div>

                    {error && (
                        <div className="bg-red-50 border border-red-200 rounded-md p-4">
                            <p className="text-sm text-red-600">{error}</p>
                        </div>
                    )}

                    <div>
                        <button
                            type="submit"
                            disabled={loading}
                            className="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
                        >
                            {loading ? 'Signing in...' : 'Sign in'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
```

## 🎯 **Quick Test Commands**

```bash
# 1. Test production server is running
curl https://api.kitonga.klikcell.com/api/health/

# 2. Test admin profile endpoint
curl -H "X-Admin-Access: kitonga_admin_secure_token_2025" https://api.kitonga.klikcell.com/api/auth/profile/

# 3. Test CORS (if using different frontend port)
curl -H "Origin: http://localhost:3000" -H "Access-Control-Request-Method: GET" -H "Access-Control-Request-Headers: X-Admin-Access" -X OPTIONS https://api.kitonga.klikcell.com/api/auth/profile/
```

## 📝 **Summary**

Your error is likely caused by:
1. ✅ Django server not running on expected port
2. ✅ Wrong API base URL in frontend
3. ✅ Missing or incorrect authentication headers
4. ✅ CORS configuration issues

Use the provided API client and debugging tools to identify and fix the exact issue!
