# Kitonga Wi-Fi API Frontend Authentication Guide

## 🔐 Authentication Methods

Your Django API supports **3 authentication methods**:

### 1. **Django Token Authentication** (Recommended for frontend)
- Header: `Authorization: Token YOUR_TOKEN_HERE`
- Get token from login response: `response.token`

### 2. **Simple Admin Token** (Static token)
- Header: `X-Admin-Access: kitonga_admin_secure_token_2025`
- Use the `SIMPLE_ADMIN_TOKEN` from your .env file

### 3. **Session Authentication** (For Django admin)
- Uses Django session cookies
- For browser-based admin interface

## ❌ **Current Frontend Errors & Solutions**

### Error 1: "Username is required"
**Cause:** Missing authentication headers
**Solution:** Add proper authentication headers

### Error 2: "Not authenticated or not admin" 
**Cause:** Wrong authentication method
**Solution:** Use Token or X-Admin-Access header

### Error 3: "HTTP error! status: 403"
**Cause:** Invalid token or insufficient permissions
**Solution:** Ensure user has admin privileges

## ✅ **Correct Frontend Implementation**

### JavaScript/TypeScript API Class:
```javascript
class KitongaAPI {
    constructor(baseURL = 'https://api.kitonga.klikcell.com') {
        this.baseURL = baseURL;
        this.token = null;
        this.adminToken = 'kitonga_admin_secure_token_2025'; // From .env SIMPLE_ADMIN_TOKEN
    }

    // Set authentication token after login
    setToken(token) {
        this.token = token;
        localStorage.setItem('kitonga_auth_token', token);
    }

    // Get token from storage
    getToken() {
        if (!this.token) {
            this.token = localStorage.getItem('kitonga_auth_token');
        }
        return this.token;
    }

    // Get authentication headers
    getAuthHeaders() {
        const headers = {
            'Content-Type': 'application/json',
        };

        // Method 1: Use Django Token (preferred)
        const token = this.getToken();
        if (token) {
            headers['Authorization'] = `Token ${token}`;
        } else {
            // Method 2: Fallback to static admin token
            headers['X-Admin-Access'] = this.adminToken;
        }

        return headers;
    }

    // Make authenticated API request
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const config = {
            headers: this.getAuthHeaders(),
            ...options,
            headers: {
                ...this.getAuthHeaders(),
                ...options.headers
            }
        };

        try {
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
            console.error(`API Error for ${endpoint}:`, error);
            throw error;
        }
    }

    // Admin login
    async login(username, password) {
        try {
            const response = await fetch(`${this.baseURL}/auth/login/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ username, password })
            });

            const data = await response.json();

            if (data.success && data.token) {
                this.setToken(data.token);
                return data;
            }

            throw new Error(data.message || 'Login failed');
        } catch (error) {
            console.error('Login failed:', error);
            throw error;
        }
    }

    // Get admin profile
    async getProfile() {
        return await this.request('/auth/profile/');
    }

    // Get dashboard statistics
    async getDashboardStats() {
        return await this.request('/dashboard-stats/');
    }

    // Get MikroTik status
    async getMikrotikStatus() {
        return await this.request('/mikrotik/status/');
    }

    // Get user status
    async getUserStatus(phoneNumber) {
        return await this.request(`/user-status/${phoneNumber}/`);
    }

    // Other API methods...
}

// Usage example
const api = new KitongaAPI();

// Login first
try {
    await api.login('admin', 'your_password');
    console.log('Logged in successfully');
    
    // Now make authenticated requests
    const stats = await api.getDashboardStats();
    const mikrotikStatus = await api.getMikrotikStatus();
    
} catch (error) {
    console.error('Authentication failed:', error);
}
```

### React Hook Example:
```tsx
import { useState, useEffect, useContext, createContext } from 'react';

// Auth Context
const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [token, setToken] = useState(null);
    const [loading, setLoading] = useState(true);
    const api = new KitongaAPI();

    useEffect(() => {
        // Check for existing token
        const savedToken = localStorage.getItem('kitonga_auth_token');
        if (savedToken) {
            api.setToken(savedToken);
            setToken(savedToken);
            
            // Verify token is still valid
            api.getProfile()
                .then(setUser)
                .catch(() => {
                    // Token invalid, clear it
                    localStorage.removeItem('kitonga_auth_token');
                    setToken(null);
                })
                .finally(() => setLoading(false));
        } else {
            setLoading(false);
        }
    }, []);

    const login = async (username, password) => {
        try {
            const response = await api.login(username, password);
            setUser(response.user);
            setToken(response.token);
            return response;
        } catch (error) {
            throw error;
        }
    };

    const logout = () => {
        localStorage.removeItem('kitonga_auth_token');
        setUser(null);
        setToken(null);
    };

    return (
        <AuthContext.Provider value={{
            user,
            token,
            loading,
            login,
            logout,
            api,
            isAuthenticated: !!user
        }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within AuthProvider');
    }
    return context;
};

// Dashboard component example
export const AdminDashboard = () => {
    const { api, isAuthenticated } = useAuth();
    const [stats, setStats] = useState(null);
    const [mikrotikStatus, setMikrotikStatus] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        if (!isAuthenticated) return;

        const loadData = async () => {
            try {
                setLoading(true);
                const [statsData, mikrotikData] = await Promise.all([
                    api.getDashboardStats(),
                    api.getMikrotikStatus().catch(err => ({ error: err.message }))
                ]);
                
                setStats(statsData);
                setMikrotikStatus(mikrotikData);
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        loadData();
    }, [isAuthenticated, api]);

    if (!isAuthenticated) {
        return <div>Please log in</div>;
    }

    if (loading) {
        return <div>Loading...</div>;
    }

    if (error) {
        return <div>Error: {error}</div>;
    }

    return (
        <div>
            <h1>Admin Dashboard</h1>
            {stats && (
                <div>
                    <p>Total Users: {stats.total_users}</p>
                    <p>Active Users: {stats.active_users}</p>
                    <p>Today Revenue: TSh {stats.today_revenue}</p>
                </div>
            )}
            {mikrotikStatus && !mikrotikStatus.error && (
                <div>
                    <p>Router Status: {mikrotikStatus.connection_status}</p>
                    <p>Active Users: {mikrotikStatus.active_users}</p>
                </div>
            )}
        </div>
    );
};
```

## 🔧 **Quick Fix for Current Frontend**

If you want to quickly fix your current frontend, update your API request headers:

```javascript
// Before (causing errors)
const response = await fetch('/api/dashboard-stats/');

// After (with authentication)
const response = await fetch('/api/dashboard-stats/', {
    headers: {
        'Authorization': `Token ${your_token}`,
        // OR use static token:
        // 'X-Admin-Access': 'kitonga_admin_secure_token_2025'
    }
});
```

## 📋 **Testing Authentication**

### Test with cURL:
```bash
# Method 1: Using Django Token (after login)
curl -H "Authorization: Token YOUR_TOKEN_HERE" \
     https://api.kitonga.klikcell.com/dashboard-stats/

# Method 2: Using Static Admin Token
curl -H "X-Admin-Access: kitonga_admin_secure_token_2025" \
     https://api.kitonga.klikcell.com/dashboard-stats/
```

### Test Login:
```bash
curl -X POST https://api.kitonga.klikcell.com/auth/login/ \
     -H "Content-Type: application/json" \
     -d '{"username":"admin","password":"your_password"}'
```

## ⚠️ **Security Notes**

1. **Never expose SIMPLE_ADMIN_TOKEN in frontend code** - only use it for testing
2. **Use Django Token authentication** for production frontend
3. **Store tokens securely** (localStorage is OK for admin dashboards)
4. **Implement token refresh** if needed
5. **Use HTTPS** in production

The key issue was that your frontend wasn't sending any authentication headers. Now it will work correctly! 🚀
