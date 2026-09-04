import React, { useEffect, useState, useContext } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { AuthContext } from '../context/AuthContext';
import { Video, Plus, Clock, FileText, ChevronRight, Play, Loader2, Upload, Trash2, AlertTriangle, X } from 'lucide-react';

const Dashboard = () => {
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [videoToDelete, setVideoToDelete] = useState(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [deleteError, setDeleteError] = useState('');
  const { token } = useContext(AuthContext);
  const navigate = useNavigate();
  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  useEffect(() => {
    const fetchVideos = async () => {
      try {
        const res = await axios.get(`${API_URL}/api/v1/videos/`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (Array.isArray(res.data)) {
            setVideos(res.data);
        } else {
            setVideos([]);
            console.error("Backend returned non-array:", res.data);
            setError('Unexpected response format from server.');
        }
      } catch (err) {
        setError('Failed to load video library.');
      } finally {
        setLoading(false);
      }
    };
    fetchVideos();
  }, [token, API_URL]);

  const handleDelete = async () => {
    if (!videoToDelete) return;
    setDeleteLoading(true);
    setDeleteError('');
    try {
      await axios.delete(`${API_URL}/api/v1/videos/${videoToDelete.id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setVideos(videos.filter(v => v.id !== videoToDelete.id));
      setVideoToDelete(null);
    } catch (err) {
      setDeleteError(err.response?.data?.detail || 'Failed to delete video.');
    } finally {
      setDeleteLoading(false);
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto relative">
      {/* Delete Modal */}
      {videoToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="bg-dark-800 border border-dark-700 rounded-2xl p-6 max-w-md w-full shadow-2xl">
            <div className="flex justify-between items-start mb-4">
              <div className="flex items-center space-x-3 text-red-500">
                <AlertTriangle size={24} />
                <h3 className="text-lg font-bold text-white">Delete Video</h3>
              </div>
              <button onClick={() => !deleteLoading && setVideoToDelete(null)} className="text-gray-400 hover:text-white">
                <X size={20} />
              </button>
            </div>
            <p className="text-gray-300 mb-2">
              Are you sure you want to delete <span className="font-semibold text-white">"{videoToDelete.title}"</span>?
            </p>
            <p className="text-sm text-gray-400 mb-6">
              This action is permanent and will completely remove the video file, as well as all associated analysis data, tracking information, and knowledge records.
            </p>
            
            {deleteError && (
              <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-sm text-red-400">
                {deleteError}
              </div>
            )}
            
            <div className="flex space-x-3 justify-end">
              <button 
                onClick={() => setVideoToDelete(null)} 
                disabled={deleteLoading}
                className="px-4 py-2 bg-dark-700 hover:bg-dark-600 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button 
                onClick={handleDelete}
                disabled={deleteLoading}
                className="px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded-lg font-medium transition-colors flex items-center disabled:opacity-50"
              >
                {deleteLoading ? (
                  <><Loader2 size={16} className="animate-spin mr-2" /> Deleting...</>
                ) : (
                  'Delete Permanently'
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Video Workspace</h1>
          <p className="text-gray-400 mt-1">Manage and analyze your surgical recordings</p>
        </div>
        <button 
          onClick={() => navigate('/upload')}
          className="flex items-center space-x-2 bg-primary-600 hover:bg-primary-500 text-white px-5 py-2.5 rounded-lg transition-all shadow-lg shadow-primary-600/20 font-medium"
        >
          <Plus size={18} />
          <span>Upload Video</span>
        </button>
      </div>

      {loading ? (
        <div className="flex flex-col justify-center items-center h-64 space-y-4">
          <Loader2 className="w-8 h-8 text-primary-500 animate-spin" />
          <p className="text-gray-400 font-medium">Loading workspace...</p>
        </div>
      ) : error ? (
        <div className="bg-red-500/10 border border-red-500/50 text-red-500 p-4 rounded-xl shadow-sm">
          {error}
        </div>
      ) : videos.length === 0 ? (
        <div className="bg-dark-800 border border-dark-700 rounded-2xl p-16 flex flex-col items-center justify-center text-center shadow-sm">
          <div className="bg-dark-700/50 p-4 rounded-full mb-6">
            <Video size={48} className="text-gray-400" />
          </div>
          <h2 className="text-xl font-bold text-white mb-2">No videos yet</h2>
          <p className="text-gray-400 max-w-md mx-auto mb-8">
            Upload your first surgical video to begin analysis, extract knowledge, and interact with the AI assistant.
          </p>
          <button 
            onClick={() => navigate('/upload')}
            className="flex items-center space-x-2 bg-dark-700 hover:bg-dark-600 text-white px-6 py-3 rounded-lg transition-colors font-medium border border-dark-600"
          >
            <Upload size={18} />
            <span>Upload your first video</span>
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {videos.map(video => (
            <div key={video.id} className="bg-dark-800 border border-dark-700 hover:border-primary-500/50 transition-all rounded-xl overflow-hidden shadow-sm group">
              <div className="aspect-video bg-dark-900 flex items-center justify-center border-b border-dark-700 relative">
                <Video size={32} className="text-dark-600" />
                <div className="absolute inset-0 bg-dark-900/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center backdrop-blur-[2px]">
                  <button 
                    onClick={() => navigate(`/analysis/${video.id}`)}
                    className="bg-primary-600 text-white rounded-full p-3 shadow-lg transform translate-y-2 group-hover:translate-y-0 transition-all"
                  >
                    <Play size={24} className="fill-white ml-1" />
                  </button>
                </div>
              </div>
              <div className="p-5">
                <div className="flex justify-between items-start mb-1">
                  <h3 className="font-semibold text-white text-lg truncate" title={video.title}>{video.title}</h3>
                  <button 
                    onClick={() => setVideoToDelete(video)}
                    className="text-gray-500 hover:text-red-400 p-1 rounded-md hover:bg-red-500/10 transition-colors"
                    title="Delete Video"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
                <div className="flex items-center text-sm text-gray-400 mb-4 space-x-4">
                  <div className="flex items-center space-x-1.5">
                    <Clock size={14} />
                    <span>{new Date(video.created_at).toLocaleDateString()}</span>
                  </div>
                  <div className="flex items-center space-x-1.5">
                    <FileText size={14} />
                    <span>{(video.file_size / (1024 * 1024)).toFixed(1)} MB</span>
                  </div>
                </div>
                <div className="flex justify-between items-center pt-4 border-t border-dark-700">
                  <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${
                    video.status === 'uploaded' ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20' :
                    video.status === 'processing' ? 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20' :
                    video.status === 'ready' ? 'bg-green-500/10 text-green-400 border border-green-500/20' :
                    'bg-red-500/10 text-red-400 border border-red-500/20'
                  }`}>
                    {video.status.charAt(0).toUpperCase() + video.status.slice(1)}
                  </span>
                  
                  <Link 
                    to={`/analysis/${video.id}`}
                    className="text-sm font-medium text-primary-400 hover:text-primary-300 flex items-center group-hover:translate-x-1 transition-transform"
                  >
                    Open Workspace
                    <ChevronRight size={16} className="ml-0.5" />
                  </Link>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default Dashboard;
