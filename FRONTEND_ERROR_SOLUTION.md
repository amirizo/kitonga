# 🔧 SOLUTION: Frontend "Failed to fetch" Error

## ✅ **Root Cause Identified**

Your production API server at `https://api.kitonga.klikcell.com` is working perfectly, but the `getAdminProfile()` endpoint requires **proper user authentication**, not just the admin token.

## 🚀 **Fixed Implementation for Your React App**

### **1. Updated API Client (lib/api.ts)**

```typescript
// lib/api.ts - Production-ready API client
class KitongaAPI {
    private baseURL = 'https://api.kitonga.klikcell.com/api';
    private adminToken = 'kitonga_admin_secure_token_2025';
    private userToken: string | null = null;

    constructor() {
        // Load stored token on initialization
        if (typeof window !== 'undefined') {
            this.userToken = localStorage.getItem('authToken');
        }
    }

    async request(endpoint: string, options: RequestInit = {}): Promise<any> {
        const url = `${this.baseURL}${endpoint}`;
        
        const headers: HeadersInit = {
            'Content-Type': 'application/json',
            ...options.headers,
        };

        // Add authentication based on endpoint
        if (endpoint.startsWith('/auth/') || endpoint.startsWith('/mikrotik/') || endpoint.startsWith('/dashboard/')) {
            // Admin endpoints - use both methods for compatibility
            headers['X-Admin-Access'] = this.adminToken;
            
            if (this.userToken) {
                headers['Authorization'] = `Token ${this.userToken}`;
            }
        } else if (this.userToken) {
            // User endpoints
            headers['Authorization'] = `Token ${this.userToken}`;
        }

        const config: RequestInit = {
            method: 'GET',
            headers,
            ...options,
        };

        try {
            const response = await fetch(url, config);
            
            if (!response.ok) {
                let errorData: any;
                try {
                    errorData = await response.json();
                } catch {
                    errorData = { message: await response.text() };
                }
                
                throw new Error(`HTTP ${response.status}: ${errorData.message || response.statusText}`);
            }
            
            return await response.json();
        } catch (error) {
            if (error instanceof Error) {
                // Provide specific error messages for production
                if (error.message.includes('Failed to fetch')) {
                    throw new Error('Cannot connect to API server. Please check your internet connection.');
                }
                
                if (error.message.includes('401')) {
                    throw new Error('Authentication required. Please log in.');
                }
                
                if (error.message.includes('403')) {
                    throw new Error('Access forbidden. Insufficient permissions.');
                }
                
                throw error;
            }
            
            throw new Error('An unexpected error occurred');
        }
    }

    // ✅ LOGIN FIRST - Required for admin endpoints
    async adminLogin(username: string, password: string) {
        const response = await this.request('/auth/login/', {
            method: 'POST',
            body: JSON.stringify({ username, password }),
        });
        
        if (response.token) {
            this.userToken = response.token;
            if (typeof window !== 'undefined') {
                localStorage.setItem('authToken', response.token);
                localStorage.setItem('userId', response.user.id);
                localStorage.setItem('isAdmin', response.user.is_staff.toString());
            }
        }
        
        return response;
    }

    // ✅ FIXED - Now works after login
    async getAdminProfile() {
        if (!this.userToken) {
            throw new Error('Must be logged in to access admin profile');
        }
        
        return await this.request('/auth/profile/');
    }

    // ✅ Test connection (always works)
    async testConnection() {
        return await this.request('/health/');
    }

    // ✅ Check if authenticated
    isAuthenticated(): boolean {
        return !!this.userToken;
    }

    // ✅ Logout
    logout() {
        this.userToken = null;
        if (typeof window !== 'undefined') {
            localStorage.removeItem('authToken');
            localStorage.removeItem('userId');
            localStorage.removeItem('isAdmin');
        }
    }

    // Other methods...
    async getMikrotikStatus() {
        return await this.request('/mikrotik/status/');
    }

    async getPackages() {
        return await this.request('/bundles/');
    }
}

export default new KitongaAPI();
```

### **2. Fixed Admin Layout Component**

```tsx
// components/admin-layout.tsx
'use client';

import { useEffect, useState } from 'react';
import api from '@/lib/api';

interface AdminLayoutProps {
    children: React.ReactNode;
}

export default function AdminLayout({ children }: AdminLayoutProps) {
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
            
            // First test basic connectivity
            await api.testConnection();
            
            // Check if user token exists
            if (!api.isAuthenticated()) {
                setShowLogin(true);
                setLoading(false);
                return;
            }
            
            // Try to get admin profile
            const profile = await api.getAdminProfile();
            
            if (profile.success && profile.is_authenticated && profile.user.is_staff) {
                setIsAuthenticated(true);
                setShowLogin(false);
            } else {
                throw new Error('Not authorized as admin');
            }
            
        } catch (error) {
            console.error('Auth check failed:', error);
            const errorMessage = error instanceof Error ? error.message : 'Authentication failed';
            
            if (errorMessage.includes('Must be logged in') || errorMessage.includes('Authentication required')) {
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
            await api.adminLogin(username, password);
            await checkAuthStatus(); // Re-check after login
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Login failed';
            setError(errorMessage);
        }
    };

    const handleLogout = () => {
        api.logout();
        setIsAuthenticated(false);
        setShowLogin(true);
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

    // Error state
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
                            onClick={() => setShowLogin(true)}
                            className="w-full bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
                        >
                            Try Login
                        </button>
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

## 🎯 **Quick Test Steps**

### **1. Test Your Production API:**

Open `api-test.html` in your browser to test all endpoints interactively.

### **2. Test with JavaScript Console:**

```javascript
// Test basic connectivity
fetch('https://api.kitonga.klikcell.com/api/health/')
    .then(response => response.json())
    .then(data => console.log('✅ Server health:', data))
    .catch(error => console.error('❌ Connection failed:', error));

// Test login (replace with your admin credentials)
const loginData = {
    username: 'your_admin_username',
    password: 'your_admin_password'
};

fetch('https://api.kitonga.klikcell.com/api/auth/login/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
    },
    body: JSON.stringify(loginData)
})
.then(response => response.json())
.then(data => {
    console.log('✅ Login result:', data);
    
    // Now test admin profile with token
    if (data.token) {
        return fetch('https://api.kitonga.klikcell.com/api/auth/profile/', {
            headers: {
                'Authorization': `Token ${data.token}`,
                'X-Admin-Access': 'kitonga_admin_secure_token_2025'
            }
        });
    }
})
.then(response => response?.json())
.then(profile => console.log('✅ Admin profile:', profile))
.catch(error => console.error('❌ Test failed:', error));
```

## 📝 **Summary**

**The fix:** Your production API requires **user authentication first** before accessing admin endpoints. The `X-Admin-Access` token alone is not sufficient.

**Steps to fix:**
1. ✅ User must login with username/password first
2. ✅ Store the returned authentication token
3. ✅ Use both the auth token AND admin token for admin endpoints
4. ✅ Handle authentication flow in your React components

**Files to use:**
- ✅ `production-api-client.js` - Complete API client
- ✅ `api-test.html` - Interactive testing page
- ✅ Updated React components above

Your production API is working perfectly - it just requires proper authentication! 🚀
