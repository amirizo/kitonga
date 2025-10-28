# 🌐 KITONGA WI-FI FRONTEND API INTEGRATION GUIDE

## 📋 Quick Start Prompts

### 1. **Basic API Fetch Pattern**
```javascript
// Copy this pattern for any API call
async function fetchKitongaAPI(endpoint, options = {}) {
    const response = await fetch(`http://127.0.0.1:8000/api${endpoint}`, {
        headers: {
            'Content-Type': 'application/json',
            'X-Admin-Access': 'kitonga_admin_secure_token_2025',
            ...options.headers
        },
        ...options
    });
    
    if (!response.ok) throw new Error(`API Error: ${response.statusText}`);
    return await response.json();
}
```

### 2. **Get Router Status**
```javascript
// ✅ WORKING - Get MikroTik router status
fetchKitongaAPI('/mikrotik/status/')
    .then(data => {
        console.log('Router Status:', data);
        // Expected response:
        // {
        //     "success": true,
        //     "router_ip": "192.168.0.173",
        //     "hotspot_name": "kitonga-hotspot", 
        //     "connection_status": "connected",
        //     "active_users": 0
        // }
    })
    .catch(error => console.error('Error:', error));
```

### 3. **Get Available Packages**
```javascript
// ✅ Get all Wi-Fi packages
fetchKitongaAPI('/packages/')
    .then(packages => {
        console.log('Available Packages:', packages);
        // Display packages in your UI
        packages.forEach(pkg => {
            console.log(`${pkg.name}: ${pkg.price} TZS for ${pkg.duration_hours}h`);
        });
    });
```

### 4. **User Registration**
```javascript
// ✅ Register new user
fetchKitongaAPI('/register/', {
    method: 'POST',
    body: JSON.stringify({
        username: 'john_doe',
        email: 'john@example.com',
        password: 'SecurePass123!',
        phone_number: '+255700123456',
        first_name: 'John',
        last_name: 'Doe'
    })
})
.then(response => {
    console.log('Registration successful:', response);
    localStorage.setItem('authToken', response.token);
});
```

### 5. **User Login**
```javascript
// ✅ Login user
fetchKitongaAPI('/login/', {
    method: 'POST',
    body: JSON.stringify({
        username: 'john_doe',
        password: 'SecurePass123!'
    })
})
.then(response => {
    console.log('Login successful:', response);
    localStorage.setItem('authToken', response.token);
    localStorage.setItem('userId', response.user.id);
});
```

### 6. **Check User Subscription**
```javascript
// ✅ Get user's active subscription
const userId = localStorage.getItem('userId');
fetchKitongaAPI(`/subscriptions/active/?user=${userId}`)
    .then(subscription => {
        if (subscription) {
            console.log('Active subscription:', subscription);
            const daysLeft = Math.ceil((new Date(subscription.end_date) - new Date()) / (1000*60*60*24));
            console.log(`Days remaining: ${daysLeft}`);
        } else {
            console.log('No active subscription');
        }
    });
```

### 7. **Purchase Package**
```javascript
// ✅ Initiate payment for package
async function purchasePackage(packageId, phoneNumber) {
    const userId = localStorage.getItem('userId');
    
    const payment = await fetchKitongaAPI('/payments/initiate/', {
        method: 'POST',
        body: JSON.stringify({
            user: userId,
            package: packageId,
            payment_method: 'clickpesa',
            phone_number: phoneNumber
        })
    });
    
    console.log('Payment initiated:', payment);
    alert(`Payment Reference: ${payment.payment_reference}`);
    
    // Poll for payment status
    const checkPayment = setInterval(async () => {
        const status = await fetchKitongaAPI(`/payments/${payment.payment_id}/status/`);
        
        if (status.status === 'completed') {
            clearInterval(checkPayment);
            alert('Payment successful! Your subscription is now active.');
        } else if (status.status === 'failed') {
            clearInterval(checkPayment);
            alert('Payment failed. Please try again.');
        }
    }, 3000);
}

// Usage
purchasePackage(1, '+255700123456');
```

### 8. **Connect to Wi-Fi Hotspot**
```javascript
// ✅ Connect user to MikroTik hotspot
fetchKitongaAPI('/mikrotik/connect/', {
    method: 'POST',
    body: JSON.stringify({
        username: 'john_doe',
        mac_address: 'AA:BB:CC:DD:EE:FF' // Get from device
    })
})
.then(response => {
    console.log('Connected to hotspot:', response);
    alert('Successfully connected to Wi-Fi!');
})
.catch(error => {
    console.error('Connection failed:', error);
    alert('Failed to connect. Please check your subscription.');
});
```

### 9. **Complete Dashboard Data Load**
```javascript
// ✅ Load all dashboard data at once
async function loadDashboard() {
    const userId = localStorage.getItem('userId');
    
    try {
        // Load all data in parallel
        const [user, subscription, packages, routerStatus, payments] = await Promise.all([
            fetchKitongaAPI(`/users/${userId}/`),
            fetchKitongaAPI(`/subscriptions/active/?user=${userId}`),
            fetchKitongaAPI('/packages/'),
            fetchKitongaAPI('/mikrotik/status/'),
            fetchKitongaAPI(`/payments/history/?user=${userId}`)
        ]);
        
        // Update UI with loaded data
        updateDashboardUI({
            user,
            subscription,
            packages,
            routerStatus,
            payments
        });
        
    } catch (error) {
        console.error('Dashboard load failed:', error);
    }
}

function updateDashboardUI(data) {
    // Update user info
    document.getElementById('userName').textContent = data.user.first_name || data.user.username;
    
    // Update subscription status
    if (data.subscription) {
        document.getElementById('subscriptionStatus').innerHTML = `
            <h3>${data.subscription.package.name}</h3>
            <p>Expires: ${new Date(data.subscription.end_date).toLocaleDateString()}</p>
        `;
    } else {
        document.getElementById('subscriptionStatus').innerHTML = '<p>No active subscription</p>';
    }
    
    // Update router status
    document.getElementById('routerStatus').innerHTML = `
        <p>Status: ${data.routerStatus.connection_status}</p>
        <p>Active Users: ${data.routerStatus.active_users}</p>
    `;
    
    // Update packages
    const packageList = document.getElementById('packageList');
    packageList.innerHTML = data.packages.map(pkg => `
        <div class="package-card">
            <h4>${pkg.name}</h4>
            <p>Price: ${pkg.price} TZS</p>
            <p>Duration: ${pkg.duration_hours}h</p>
            <button onclick="purchasePackage(${pkg.id}, '+255700123456')">Buy Now</button>
        </div>
    `).join('');
}
```

### 10. **Error Handling Pattern**
```javascript
// ✅ Robust error handling for all API calls
async function safeApiCall(endpoint, options = {}) {
    try {
        const response = await fetchKitongaAPI(endpoint, options);
        return { success: true, data: response };
    } catch (error) {
        console.error(`API call failed for ${endpoint}:`, error);
        
        // Handle specific error types
        if (error.message.includes('401')) {
            // Unauthorized - redirect to login
            localStorage.removeItem('authToken');
            window.location.href = '/login';
        } else if (error.message.includes('404')) {
            // Not found
            return { success: false, error: 'Resource not found' };
        } else if (error.message.includes('500')) {
            // Server error
            return { success: false, error: 'Server error. Please try again later.' };
        }
        
        return { success: false, error: error.message };
    }
}

// Usage with error handling
async function loadUserData() {
    const result = await safeApiCall('/users/1/');
    
    if (result.success) {
        console.log('User data:', result.data);
        updateUI(result.data);
    } else {
        console.error('Failed to load user data:', result.error);
        showErrorMessage(result.error);
    }
}
```

## 🎯 **Copy-Paste Ready Examples**

### React Hook Example
```javascript
// React hook for Kitonga API
import { useState, useEffect } from 'react';

export function useKitongaAPI(endpoint) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    
    useEffect(() => {
        async function fetchData() {
            try {
                const response = await fetchKitongaAPI(endpoint);
                setData(response);
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        }
        
        fetchData();
    }, [endpoint]);
    
    return { data, loading, error };
}

// Usage in React component
function Dashboard() {
    const { data: packages, loading } = useKitongaAPI('/packages/');
    
    if (loading) return <div>Loading...</div>;
    
    return (
        <div>
            {packages?.map(pkg => (
                <div key={pkg.id}>{pkg.name} - {pkg.price} TZS</div>
            ))}
        </div>
    );
}
```

### Vue.js Example
```javascript
// Vue.js component
export default {
    data() {
        return {
            packages: [],
            routerStatus: null,
            loading: true
        }
    },
    
    async mounted() {
        await this.loadData();
    },
    
    methods: {
        async loadData() {
            try {
                const [packages, status] = await Promise.all([
                    fetchKitongaAPI('/packages/'),
                    fetchKitongaAPI('/mikrotik/status/')
                ]);
                
                this.packages = packages;
                this.routerStatus = status;
            } catch (error) {
                console.error('Load failed:', error);
            } finally {
                this.loading = false;
            }
        },
        
        async purchasePackage(packageId) {
            const result = await safeApiCall('/payments/initiate/', {
                method: 'POST',
                body: JSON.stringify({
                    user: this.$store.state.userId,
                    package: packageId,
                    payment_method: 'clickpesa',
                    phone_number: this.phoneNumber
                })
            });
            
            if (result.success) {
                this.$toast.success('Payment initiated!');
            } else {
                this.$toast.error(result.error);
            }
        }
    }
}
```

## 🚀 **Quick Integration Checklist**

1. ✅ **Copy the `fetchKitongaAPI` function** - This handles authentication
2. ✅ **Set correct API base URL** - Use your Django server URL
3. ✅ **Include authentication header** - `X-Admin-Access: kitonga_admin_secure_token_2025`
4. ✅ **Handle errors properly** - Use try/catch blocks
5. ✅ **Store auth tokens** - Save to localStorage after login
6. ✅ **Test with router status** - `/mikrotik/status/` endpoint works
7. ✅ **Test package loading** - `/packages/` endpoint for pricing
8. ✅ **Test user registration** - `/register/` for new users
9. ✅ **Test payment flow** - `/payments/initiate/` for purchases
10. ✅ **Test Wi-Fi connection** - `/mikrotik/connect/` for hotspot access

## 📱 **Mobile-Friendly Example**
```javascript
// Mobile app integration (React Native / Ionic)
class KitongaWiFiService {
    constructor() {
        this.baseURL = 'http://192.168.0.100:8000/api'; // Use your server IP
        this.token = null;
    }
    
    async login(username, password) {
        const response = await fetch(`${this.baseURL}/login/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        
        const data = await response.json();
        this.token = data.token;
        await AsyncStorage.setItem('authToken', data.token);
        return data;
    }
    
    async getPackages() {
        return await this.apiCall('/packages/');
    }
    
    async purchasePackage(packageId, phoneNumber) {
        return await this.apiCall('/payments/initiate/', {
            method: 'POST',
            body: JSON.stringify({
                user: await AsyncStorage.getItem('userId'),
                package: packageId,
                payment_method: 'clickpesa',
                phone_number: phoneNumber
            })
        });
    }
    
    async apiCall(endpoint, options = {}) {
        const token = this.token || await AsyncStorage.getItem('authToken');
        
        const response = await fetch(`${this.baseURL}${endpoint}`, {
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Token ${token}`,
                'X-Admin-Access': 'kitonga_admin_secure_token_2025'
            },
            ...options
        });
        
        return await response.json();
    }
}

// Usage
const wifiService = new KitongaWiFiService();
await wifiService.login('username', 'password');
const packages = await wifiService.getPackages();
```

## 🔧 **Debug Commands**

Test your API integration with these curl commands:

```bash
# Test router status
curl -X GET "http://127.0.0.1:8000/api/mikrotik/status/" \
  -H "X-Admin-Access: kitonga_admin_secure_token_2025"

# Test package list
curl -X GET "http://127.0.0.1:8000/api/packages/" \
  -H "X-Admin-Access: kitonga_admin_secure_token_2025"

# Test user registration
curl -X POST "http://127.0.0.1:8000/api/register/" \
  -H "Content-Type: application/json" \
  -H "X-Admin-Access: kitonga_admin_secure_token_2025" \
  -d '{"username":"testuser","email":"test@test.com","password":"testpass123"}'
```

## 📄 **Files Created**

1. **`frontend_integration_guide.js`** - Complete API integration library
2. **`frontend_demo.html`** - Working demo with UI examples  
3. **`FRONTEND_API_GUIDE.md`** - This comprehensive guide

🎯 **Ready to use!** Copy any of these examples into your frontend application.
