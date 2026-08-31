import React, { useState, useContext, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, Video as VideoIcon, CheckCircle, XCircle } from 'lucide-react';
import axios from 'axios';
import { AuthContext } from '../context/AuthContext';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const UploadVideo = () => {
  const [file, setFile] = useState(null);
  const [title, setTitle] = useState('');
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState('');
  const fileInputRef = useRef(null);
  const navigate = useNavigate();

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0];
      if (!selected.name.endsWith('.mp4') && !selected.name.endsWith('.mov') && !selected.name.endsWith('.avi')) {
        setError('Only .mp4, .mov, and .avi files are supported.');
        return;
      }
      setFile(selected);
      setTitle(selected.name.split('.')[0]); // Default title
      setError('');
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) {
      setError('Please select a video file.');
      return;
    }

    setUploading(true);
    setProgress(0);
    setError('');

    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', title);

    try {
      const res = await axios.post(`${API_URL}/api/v1/videos/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setProgress(percentCompleted);
        }
      });
      
      const videoId = res.data.id;
      
      // Immediately start analysis for demo
      const analysisRes = await axios.post(`${API_URL}/api/v1/analysis/?video_id=${videoId}`);
      
      navigate(`/analysis/${analysisRes.data.analysis_id}`);
      
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to upload video');
      setUploading(false);
    }
  };

  return (
    <div className="p-8 h-full">
      <div className="max-w-3xl mx-auto">
        <h1 className="text-2xl font-bold mb-2">Upload Surgical Video</h1>
        <p className="text-gray-400 mb-8">Upload a video to start the intelligent analysis process.</p>

        {error && (
          <div className="bg-red-500/10 border border-red-500/50 text-red-500 p-4 rounded-lg mb-6 flex items-center space-x-2">
            <XCircle size={20} />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleUpload} className="space-y-6">
          <div 
            className={`border-2 border-dashed rounded-xl p-12 flex flex-col items-center justify-center transition-colors cursor-pointer
              ${file ? 'border-primary-500 bg-primary-500/5' : 'border-dark-600 bg-dark-800 hover:border-gray-500'}`}
            onClick={() => fileInputRef.current?.click()}
          >
            <input 
              type="file" 
              ref={fileInputRef} 
              className="hidden" 
              accept=".mp4,.mov,.avi"
              onChange={handleFileChange}
            />
            
            {file ? (
              <>
                <VideoIcon className="text-primary-500 mb-4" size={48} />
                <h3 className="text-xl font-medium mb-1 text-center">{file.name}</h3>
                <p className="text-gray-400 text-sm">{(file.size / (1024 * 1024)).toFixed(2)} MB</p>
                <button type="button" className="mt-6 text-sm text-primary-400 hover:text-primary-300" onClick={(e) => { e.stopPropagation(); setFile(null); }}>
                  Remove file
                </button>
              </>
            ) : (
              <>
                <Upload className="text-gray-400 mb-4" size={48} />
                <h3 className="text-xl font-medium mb-1">Drag and drop your video</h3>
                <p className="text-gray-400 text-sm mb-6">or click to browse from your computer</p>
                <div className="text-xs text-gray-500 flex space-x-4">
                  <span>Supported: MP4, MOV, AVI</span>
                  <span>Max size: 2GB</span>
                </div>
              </>
            )}
          </div>

          {file && (
            <div className="bg-dark-800 p-6 rounded-xl border border-dark-700">
              <label className="block text-sm font-medium text-gray-300 mb-2">Video Title</label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full bg-dark-900 border border-dark-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
                required
              />
            </div>
          )}

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={!file || uploading}
              className={`px-8 py-3 rounded-lg font-medium transition-colors flex items-center space-x-2
                ${!file || uploading 
                  ? 'bg-dark-700 text-gray-500 cursor-not-allowed' 
                  : 'bg-primary-600 hover:bg-primary-500 text-white'}`}
            >
              {uploading ? (
                <>
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Uploading {progress}%...</span>
                </>
              ) : (
                <>
                  <Upload size={20} />
                  <span>Start Analysis</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default UploadVideo;
