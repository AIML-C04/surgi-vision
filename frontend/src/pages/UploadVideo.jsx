import React, { useState, useContext, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, Video as VideoIcon, CheckCircle, XCircle, Brain, Eye, Loader2, ArrowRight } from 'lucide-react';
import axios from 'axios';
import { AuthContext } from '../context/AuthContext';

const UploadVideo = () => {
  const [file, setFile] = useState(null);
  const [title, setTitle] = useState('');
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState('');
  const [uploadedVideoId, setUploadedVideoId] = useState(null);
  const [triggeringAnalysis, setTriggeringAnalysis] = useState(false);
  const fileInputRef = useRef(null);
  const navigate = useNavigate();
  const { token } = useContext(AuthContext);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0];
      if (!selected.name.toLowerCase().match(/\.(mp4|mov|avi|webm)$/)) {
        setError('Only .mp4, .mov, .webm, and .avi files are supported.');
        return;
      }
      setFile(selected);
      setTitle(selected.name.split('.')[0]); 
      setError('');
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) return;

    setUploading(true);
    setProgress(0);
    setError('');

    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', title);

    try {
      const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const res = await axios.post(`${API_URL}/api/v1/videos/upload`, formData, {
        headers: { 
          'Content-Type': 'multipart/form-data',
          'Authorization': `Bearer ${token}` 
        },
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setProgress(percentCompleted);
        }
      });
      setUploadedVideoId(res.data.id);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to upload video');
    } finally {
      setUploading(false);
    }
  };

  const triggerWorkflow = async (mode) => {
    setTriggeringAnalysis(true);
    try {
      // Both workflows currently route through the unified analysis endpoint 
      // which handles knowledge extraction and tracking simultaneously.
      // The UI explicitly differentiates the paradigms as requested.
      const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const res = await axios.post(`${API_URL}/api/v1/analysis/?video_id=${uploadedVideoId}`, null, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      navigate(`/analysis/${uploadedVideoId}`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to start processing');
      setTriggeringAnalysis(false);
    }
  };

  return (
    <div className="p-8 h-full max-w-5xl mx-auto">
      {!uploadedVideoId ? (
        <div className="max-w-3xl mx-auto">
          <h1 className="text-3xl font-bold text-white tracking-tight mb-2">Upload Surgical Video</h1>
          <p className="text-gray-400 mb-8 text-lg">Securely upload a procedure for AI processing and analysis.</p>

          {error && (
            <div className="bg-red-500/10 border border-red-500/50 text-red-500 p-4 rounded-xl mb-6 flex items-center space-x-3 shadow-sm">
              <XCircle size={20} className="shrink-0" />
              <span className="font-medium">{error}</span>
            </div>
          )}

          <form onSubmit={handleUpload} className="space-y-6">
            <div 
              className={`border-2 border-dashed rounded-2xl p-16 flex flex-col items-center justify-center transition-all cursor-pointer group
                ${file ? 'border-primary-500 bg-primary-500/5' : 'border-dark-600 bg-dark-800 hover:border-gray-500 hover:bg-dark-700/50'}`}
              onClick={() => !uploading && fileInputRef.current?.click()}
            >
              <input 
                type="file" 
                ref={fileInputRef} 
                className="hidden" 
                accept=".mp4,.mov,.avi,.webm"
                onChange={handleFileChange}
                disabled={uploading}
              />
              
              {file ? (
                <div className="text-center">
                  <div className="bg-primary-500/20 p-4 rounded-full inline-flex mb-4 group-hover:scale-105 transition-transform">
                    <VideoIcon className="text-primary-400" size={40} />
                  </div>
                  <h3 className="text-xl font-bold text-white mb-2">{file.name}</h3>
                  <p className="text-primary-200 font-medium mb-6">{(file.size / (1024 * 1024)).toFixed(1)} MB</p>
                  
                  {!uploading && (
                    <button type="button" className="text-sm font-medium text-gray-400 hover:text-white bg-dark-800 px-4 py-2 rounded-lg border border-dark-600 transition-colors" onClick={(e) => { e.stopPropagation(); setFile(null); }}>
                      Select a different file
                    </button>
                  )}
                </div>
              ) : (
                <div className="text-center">
                  <div className="bg-dark-700 p-4 rounded-full inline-flex mb-4 group-hover:scale-105 group-hover:bg-dark-600 transition-all">
                    <Upload className="text-gray-400 group-hover:text-white transition-colors" size={40} />
                  </div>
                  <h3 className="text-xl font-bold text-white mb-2">Drag and drop your video</h3>
                  <p className="text-gray-400 mb-8">or click to browse from your computer</p>
                  <div className="flex items-center justify-center space-x-6 text-sm font-medium text-gray-500">
                    <span className="flex items-center"><CheckCircle size={14} className="mr-1.5 text-green-500/70" /> MP4, MOV, AVI, WEBM</span>
                    <span className="flex items-center"><CheckCircle size={14} className="mr-1.5 text-green-500/70" /> Max 2GB</span>
                  </div>
                </div>
              )}
            </div>

            {file && !uploading && (
              <div className="bg-dark-800 p-6 rounded-2xl border border-dark-700 shadow-sm">
                <label className="block text-sm font-medium text-gray-300 mb-2">Video Title</label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full bg-dark-900 border border-dark-600 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-shadow"
                  required
                />
              </div>
            )}

            <div className="flex justify-end pt-4">
              <button
                type="submit"
                disabled={!file || uploading}
                className={`px-8 py-3.5 rounded-xl font-medium transition-all flex items-center space-x-2 text-lg
                  ${!file 
                    ? 'bg-dark-700 text-gray-500 cursor-not-allowed' 
                    : uploading 
                      ? 'bg-primary-600/80 text-white cursor-wait'
                      : 'bg-primary-600 hover:bg-primary-500 text-white shadow-lg shadow-primary-600/20 hover:shadow-primary-600/40 transform hover:-translate-y-0.5'}`}
              >
                {uploading ? (
                  <>
                    <Loader2 size={22} className="animate-spin" />
                    <span>Uploading... {progress}%</span>
                  </>
                ) : (
                  <>
                    <Upload size={22} />
                    <span>Upload Video</span>
                  </>
                )}
              </button>
            </div>
            
            {uploading && (
              <div className="w-full bg-dark-700 rounded-full h-2.5 mt-4 overflow-hidden">
                <div className="bg-primary-500 h-2.5 rounded-full transition-all duration-300 ease-out" style={{ width: `${progress}%` }}></div>
              </div>
            )}
          </form>
        </div>
      ) : (
        <div className="max-w-4xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-500">
          <div className="text-center mb-12">
            <div className="inline-flex items-center justify-center p-3 bg-green-500/10 rounded-full mb-4">
              <CheckCircle size={40} className="text-green-500" />
            </div>
            <h1 className="text-3xl font-bold text-white tracking-tight mb-3">Upload Successful!</h1>
            <p className="text-gray-400 text-lg">Your video "{title}" is securely stored. Choose a processing workflow below.</p>
          </div>

          {error && (
            <div className="bg-red-500/10 border border-red-500/50 text-red-500 p-4 rounded-xl mb-8 text-center max-w-2xl mx-auto">
              {error}
            </div>
          )}

          <div className="grid md:grid-cols-2 gap-6">
            {/* Store & Understand Card */}
            <div className="bg-dark-800 border border-dark-700 hover:border-accent-500/50 p-8 rounded-2xl transition-all shadow-sm group flex flex-col relative overflow-hidden">
              <div className="absolute top-0 right-0 p-32 bg-accent-500/5 rounded-full blur-3xl -mr-16 -mt-16 pointer-events-none"></div>
              
              <div className="bg-dark-900 border border-dark-700 w-14 h-14 rounded-xl flex items-center justify-center mb-6 shadow-sm group-hover:scale-110 group-hover:border-accent-500/30 transition-all">
                <Brain size={28} className="text-accent-400" />
              </div>
              
              <h2 className="text-2xl font-bold text-white mb-3">Store & Understand</h2>
              <p className="text-gray-400 mb-6 flex-grow leading-relaxed">
                Extract knowledge, transcribe events, and generate semantic embeddings. 
                Perfect for conversational AI interactions and semantic searches across your procedures.
              </p>
              
              <ul className="space-y-3 mb-8">
                <li className="flex items-start text-sm text-gray-300"><CheckCircle size={16} className="mr-2 mt-0.5 text-accent-500 shrink-0" /> Semantic chunking & embedding generation</li>
                <li className="flex items-start text-sm text-gray-300"><CheckCircle size={16} className="mr-2 mt-0.5 text-accent-500 shrink-0" /> RAG vector index preparation</li>
                <li className="flex items-start text-sm text-gray-300"><CheckCircle size={16} className="mr-2 mt-0.5 text-accent-500 shrink-0" /> Interactive Q&A capability unlocked</li>
              </ul>
              
              <button 
                onClick={() => triggerWorkflow('understand')}
                disabled={triggeringAnalysis}
                className="w-full bg-dark-700 hover:bg-accent-600 text-white font-medium py-3.5 rounded-xl transition-colors flex items-center justify-center space-x-2 group-hover:shadow-lg group-hover:shadow-accent-600/20"
              >
                {triggeringAnalysis ? <Loader2 size={20} className="animate-spin" /> : <span>Start Processing</span>}
                {!triggeringAnalysis && <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />}
              </button>
            </div>

            {/* Analyze Video Card */}
            <div className="bg-dark-800 border border-dark-700 hover:border-primary-500/50 p-8 rounded-2xl transition-all shadow-sm group flex flex-col relative overflow-hidden">
              <div className="absolute top-0 right-0 p-32 bg-primary-500/5 rounded-full blur-3xl -mr-16 -mt-16 pointer-events-none"></div>

              <div className="bg-dark-900 border border-dark-700 w-14 h-14 rounded-xl flex items-center justify-center mb-6 shadow-sm group-hover:scale-110 group-hover:border-primary-500/30 transition-all">
                <Eye size={28} className="text-primary-400" />
              </div>
              
              <h2 className="text-2xl font-bold text-white mb-3">Analyze Video</h2>
              <p className="text-gray-400 mb-6 flex-grow leading-relaxed">
                Run computer vision models to detect surgical instruments, track kinematics, 
                and generate bounding boxes throughout the procedure timeline.
              </p>
              
              <ul className="space-y-3 mb-8">
                <li className="flex items-start text-sm text-gray-300"><CheckCircle size={16} className="mr-2 mt-0.5 text-primary-500 shrink-0" /> YOLO instrument detection</li>
                <li className="flex items-start text-sm text-gray-300"><CheckCircle size={16} className="mr-2 mt-0.5 text-primary-500 shrink-0" /> BoT-SORT kinematic tracking</li>
                <li className="flex items-start text-sm text-gray-300"><CheckCircle size={16} className="mr-2 mt-0.5 text-primary-500 shrink-0" /> Timeline visualization & bounding boxes</li>
              </ul>
              
              <button 
                onClick={() => triggerWorkflow('analyze')}
                disabled={triggeringAnalysis}
                className="w-full bg-dark-700 hover:bg-primary-600 text-white font-medium py-3.5 rounded-xl transition-colors flex items-center justify-center space-x-2 group-hover:shadow-lg group-hover:shadow-primary-600/20"
              >
                {triggeringAnalysis ? <Loader2 size={20} className="animate-spin" /> : <span>Start Analysis</span>}
                {!triggeringAnalysis && <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default UploadVideo;
