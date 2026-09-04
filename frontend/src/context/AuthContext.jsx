import React, { createContext, useState, useEffect } from 'react';
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token') || null);
  // States: 'INITIALIZING', 'AUTHENTICATED', 'UNAUTHENTICATED'
  const [authState, setAuthState] = useState('INITIALIZING');

  const logout = () => {
    localStorage.removeItem('token');
    setToken(null);
    setUser(null);
    delete axios.defaults.headers.common['Authorization'];
    setAuthState('UNAUTHENTICATED');
  };

  useEffect(() => {
    const interceptor = axios.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response && error.response.status === 401) {
          logout();
        }
        return Promise.reject(error);
      }
    );
    return () => axios.interceptors.response.eject(interceptor);
  }, []);

  useEffect(() => {
    const initAuth = async () => {
      if (token) {
        axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
        try {
          const res = await axios.get(`${API_URL}/api/v1/auth/me`);
          setUser(res.data);
          setAuthState('AUTHENTICATED');
        } catch (err) {
          console.error("Failed to fetch user", err);
          logout(); // This will set state to UNAUTHENTICATED
        }
      } else {
        setAuthState('UNAUTHENTICATED');
      }
    };
    
    initAuth();
  }, []); // Only run once on mount

  const login = async (email, password) => {
    setAuthState('INITIALIZING');
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    const res = await axios.post(`${API_URL}/api/v1/auth/login`, formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    });
    
    const newToken = res.data.access_token;
    localStorage.setItem('token', newToken);
    setToken(newToken);
    axios.defaults.headers.common['Authorization'] = `Bearer ${newToken}`;
    
    try {
        const userRes = await axios.get(`${API_URL}/api/v1/auth/me`);
        setUser(userRes.data);
        setAuthState('AUTHENTICATED');
        return res.data;
    } catch (err) {
        logout();
        throw err;
    }
  };

  const register = async (email, password, fullName, role) => {
    const res = await axios.post(`${API_URL}/api/v1/auth/register`, {
      email,
      password,
      full_name: fullName,
      role
    });
    return res.data;
  };

  const loading = authState === 'INITIALIZING';
  const isAuthenticated = authState === 'AUTHENTICATED';

  return (
    <AuthContext.Provider value={{ user, token, loading, isAuthenticated, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
};
