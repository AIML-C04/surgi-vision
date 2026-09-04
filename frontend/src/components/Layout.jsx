import React, { useContext } from 'react';
import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import { Activity, LayoutDashboard, Video, LogOut, Upload, GitCompare } from 'lucide-react';

const Layout = () => {
  const { logout, user } = useContext(AuthContext);
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const navItems = [
    { name: 'Video Workspace', path: '/', icon: <Video size={20} /> },
    { name: 'Upload Video', path: '/upload', icon: <Upload size={20} /> },
    { name: 'Live Stream', path: '/live', icon: <Activity size={20} /> },
    { name: 'Research Eval', path: '/research', icon: <LayoutDashboard size={20} /> },
    { name: 'Compare Procedures', path: '/compare', icon: <GitCompare size={20} /> },
  ];

  return (
    <div className="flex h-screen bg-dark-900 text-white overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 bg-dark-800 border-r border-dark-700 flex flex-col">
        <div className="p-4 border-b border-dark-700 flex items-center space-x-2">
          <Activity className="text-primary-500" size={24} />
          <span className="text-xl font-bold">SurgiVision AI</span>
        </div>
        
        <nav className="flex-1 overflow-y-auto p-4 space-y-2">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center space-x-3 px-4 py-3 rounded-lg transition-colors ${
                location.pathname === item.path ? 'bg-primary-600 text-white' : 'text-gray-400 hover:bg-dark-700 hover:text-white'
              }`}
            >
              {item.icon}
              <span>{item.name}</span>
            </Link>
          ))}
        </nav>

        <div className="p-4 border-t border-dark-700">
          <div className="flex items-center justify-between">
            <div className="flex flex-col">
              <span className="text-sm font-medium truncate">{user?.full_name}</span>
              <span className="text-xs text-gray-400">{user?.role}</span>
            </div>
            <button onClick={handleLogout} className="text-gray-400 hover:text-white transition-colors">
              <LogOut size={20} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto bg-dark-900">
        <Outlet />
      </main>
    </div>
  );
};

export default Layout;
