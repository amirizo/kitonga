// lib/api.ts - Fixed Authentication
class KitongaAPI {
    private baseURL: string;
    private token: string | null = null;
    private adminToken: string = 'kitonga_admin_secure_token_2025'; // From your .env

    constructor(baseURL: string = 'https://api.kitonga.klikcell.com') {
        this.baseURL = baseURL;
        // For development, use local server
        if (process.env.NODE_ENV === 'development') {
            this.baseURL = 'http://127.0.0.1:8000';
        }
    }

    // Set authentication token after login
    setToken(token: string) {
        this.token = token;
        if (typeof window !== 'undefined') {
            localStorage.setItem('kitonga_auth_token', token);
        }
    }

    // Get token from storage
    getToken(): string | null {
        if (!this.token && typeof window !== 'undefined') {
            this.token = localStorage.getItem('kitonga_auth_token');
        }
        return this.token;
    }

    // Get authentication headers - THIS IS THE KEY FIX
    private getAuthHeaders(): Record<string, string> {
        const headers: Record<string, string> = {
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
    async request(endpoint: string, options: RequestInit = {}): Promise<any> {
        // IMPORTANT: Add /api prefix for all endpoints
        const url = `${this.baseURL}/api${endpoint}`;
        
        const config: RequestInit = {
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
    async login(username: string, password: string) {
        try {
            const response = await fetch(`${this.baseURL}/api/auth/login/`, {
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

    // Fixed API methods with correct authentication
    async checkAuthStatus() {
        return await this.request('/auth/profile/');
    }

    async loadDashboardStats() {
        return await this.request('/dashboard-stats/');
    }

    async loadMikrotikStatus() {
        return await this.request('/mikrotik/status/');
    }

    async getUserStatus(phoneNumber: string) {
        return await this.request(`/user-status/${phoneNumber}/`);
    }

    // Add other API methods as needed...
}

// Export singleton instance
export const api = new KitongaAPI();

// Helper function for React components
export async function withAuth<T>(apiCall: () => Promise<T>): Promise<T> {
    try {
        return await apiCall();
    } catch (error: any) {
        if (error.message.includes('401') || error.message.includes('403')) {
            // Redirect to login
            if (typeof window !== 'undefined') {
                localStorage.removeItem('kitonga_auth_token');
                window.location.href = '/admin/login';
            }
        }
        throw error;
    }
}
