import React, { useContext } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, AuthContext } from './context/AuthContext';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import UploadVideo from './pages/UploadVideo';
import Analysis from './pages/Analysis';
import Research from './pages/Research';
import Live from './pages/Live';
import Layout from './components/Layout';
import ScrollToTop from './components/ScrollToTop';

const ProtectedRoute = ({ children }) => {
  const { loading, isAuthenticated } = useContext(AuthContext);
  if (loading) return <div className="h-screen w-full flex items-center justify-center bg-dark-900 text-white font-medium text-lg">Authenticating...</div>;
  if (!isAuthenticated) return <Navigate to="/login" />;
  return children;
};

function App() {
  return (
    <AuthProvider>
      <Router>
        <ScrollToTop />
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            <Route index element={<Dashboard />} />
            <Route path="upload" element={<UploadVideo />} />
            <Route path="analysis/:id" element={<Analysis />} />
            <Route path="research" element={<Research />} />
            <Route path="live" element={<Live />} />
          </Route>
        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default App;
