import React, { useState, useEffect, useRef, useContext } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { Activity, Clock, Play, Pause, AlertTriangle, MessageSquare, Send, Brain, Target, Info, Loader2 } from 'lucide-react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip } from 'recharts';
import { AuthContext } from '../context/AuthContext';

const Analysis = () => {
  const { id } = useParams();
  const [analysis, setAnalysis] = useState(null);
  const [wsStatus, setWsStatus] = useState('Connecting...');
  const [progress, setProgress] = useState(0);
  const [currentFrame, setCurrentFrame] = useState(null);
  const [events, setEvents] = useState([]);
  const [allDetections, setAllDetections] = useState({});
  const [timelineData, setTimelineData] = useState([{time: 0, confidence: 0}]);
  const { token } = useContext(AuthContext);
  
  // Chat state
  const [messages, setMessages] = useState([{ role: 'assistant', content: 'Hello! I can answer questions about this specific video based on the processed knowledge. What would you like to know?' }]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const ws = useRef(null);
  const videoRef = useRef(null);
  const detectionsCacheRef = useRef({});

  useEffect(() => {
    let isMounted = true;
    
    const fetchStatus = async () => {
      try {
        const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
        const config = { headers: { Authorization: `Bearer ${token}` } };
        
        let res;
        try {
          res = await axios.get(`${API_URL}/api/v1/analysis/by-video/${id}`, config);
        } catch (err) {
          if (err.response?.status === 404) {
            if (isMounted) setAnalysis({ status: 'NOT_STARTED', video_id: id });
            return;
          }
          throw err;
        }
        
        if (res.data.status === 'completed') {
            try {
                const detRes = await axios.get(`${API_URL}/api/v1/analysis/${res.data.id}/detections`, config);
                detectionsCacheRef.current = detRes.data;
                setAllDetections(detRes.data);
            } catch(e) {
                console.error("Failed to fetch all detections", e);
            }
        }
        
        let video_url = null;
        if (res.data.video_id) {
            try {
                const urlRes = await axios.get(`${API_URL}/api/v1/videos/${res.data.video_id}/url`, config);
                let vUrl = urlRes.data.url;
                if (vUrl && vUrl.startsWith('/')) {
                    vUrl = API_URL + vUrl;
                }
                video_url = vUrl;
            } catch (err) {
                console.error("Failed to fetch video URL", err);
            }
        }
        
        if (isMounted) {
          setAnalysis({ ...res.data, video_url });
          setProgress(res.data.progress || 0);
        }
      } catch (err) {
        console.error("Failed to fetch analysis", err);
      }
    };
    fetchStatus();
  }, [id, token]);

  useEffect(() => {
    let isMounted = true;
    if (!analysis || !analysis.id || analysis.status === 'NOT_STARTED' || analysis.status === 'completed' || analysis.status === 'failed') return;

    const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    let wsUrl = '';
    if (API_URL.startsWith('http://')) {
        wsUrl = API_URL.replace('http://', 'ws://') + `/api/v1/analysis/ws/${analysis.id}`;
    } else if (API_URL.startsWith('https://')) {
        wsUrl = API_URL.replace('https://', 'wss://') + `/api/v1/analysis/ws/${analysis.id}`;
    } else {
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        wsUrl = `${wsProtocol}//${window.location.host}/api/v1/analysis/ws/${analysis.id}`;
    }
    
    const socket = new WebSocket(wsUrl);
    ws.current = socket;

    socket.onopen = () => {
      if (isMounted) setWsStatus('Connected (Live)');
    };
    
    socket.onerror = (error) => {
      if (isMounted) setWsStatus('Error connecting');
    };

    socket.onclose = () => {
      if (isMounted) setWsStatus('Disconnected');
    };
    
    socket.onmessage = (event) => {
      if (!isMounted) return;
      const data = JSON.parse(event.data);
      
      if (data.event === 'analysis_started') {
        setAnalysis(prev => ({ ...prev, status: 'processing' }));
      } else if (data.event === 'frame_processed') {
        setProgress(data.progress);
        setCurrentFrame(data.prediction);
        
        const ts = Math.round(data.prediction.timestamp * 10) / 10;
        if (data.prediction.detections && data.prediction.detections.length > 0) {
           detectionsCacheRef.current[ts] = data.prediction.detections;
        } else {
           detectionsCacheRef.current[ts] = [];
        }
        
        if (data.prediction.frame_id % 15 === 0) {
          setTimelineData(prev => [...prev, {
            time: Math.round(data.prediction.timestamp),
            confidence: data.prediction.phase?.confidence ? data.prediction.phase.confidence * 100 : 0
          }].slice(-50));
        }
        
      } else if (data.event === 'analysis_completed') {
        setAnalysis(prev => ({ ...prev, status: 'completed' }));
        setProgress(100);
        setAllDetections({...detectionsCacheRef.current});
      } else if (data.event === 'analysis_failed') {
        setAnalysis(prev => ({ ...prev, status: 'failed' }));
        setWsStatus('Analysis Failed: ' + data.error);
      }
    };

    return () => {
      isMounted = false;
      if (socket.readyState === WebSocket.OPEN) {
        socket.close();
      }
    };
  }, [analysis?.id, analysis?.status, token]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!chatInput.trim() || !analysis?.video_id) return;

    const userMessage = chatInput.trim();
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setChatInput('');
    setChatLoading(true);

    try {
      const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const res = await axios.post(`${API_URL}/api/v1/chat/`, {
        video_id: analysis.video_id,
        query: userMessage
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });

      let content = res.data.answer;
      if (res.data.evidence && res.data.evidence.length > 0) {
        const timestamps = [...new Set(res.data.evidence.map(e => Math.round(e.timestamp)))];
        content += `\n\n*(Evidence found at: ${timestamps.map(t => t + 's').join(', ')})*`;
      }

      setMessages(prev => [...prev, { role: 'assistant', content }]);
    } catch (err) {
      setMessages(prev => [...prev, { role: 'assistant', content: "Sorry, I couldn't process that query." }]);
    } finally {
      setChatLoading(false);
    }
  };

  const handleStartAnalysis = async (reanalyze = false) => {
    try {
      if (reanalyze && !window.confirm("This will rerun AI analysis and may take several minutes. Continue?")) return;
      
      const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const config = { headers: { Authorization: `Bearer ${token}` } };
      
      // Optimistic UI update
      setAnalysis(prev => ({ ...prev, status: 'processing' }));
      setProgress(0);
      setTimelineData([]);
      setCurrentFrame(null);
      setAllDetections({});
      detectionsCacheRef.current = {};
      
      const res = await axios.post(`${API_URL}/api/v1/analysis/?video_id=${id}&reanalyze=${reanalyze}`, null, config);
      setAnalysis(prev => ({ ...prev, id: res.data.analysis_id, status: res.data.status }));
      
    } catch (err) {
      console.error(err);
      alert("Failed to start analysis: " + (err.response?.data?.detail || err.message));
      setAnalysis(prev => ({ ...prev, status: reanalyze ? 'completed' : 'NOT_STARTED' }));
    }
  };
  
  const jumpToTime = (time) => {
    if (videoRef.current) {
        videoRef.current.currentTime = time;
        videoRef.current.play();
    }
  };

  const handleTimeUpdate = () => {
    if (!videoRef.current || analysis?.status !== 'completed') return;
    
    const ct = videoRef.current.currentTime;
    const cache = detectionsCacheRef.current;
    if (!cache || Object.keys(cache).length === 0) return;
    
    // Find closest timestamp
    const times = Object.keys(cache).map(Number).sort((a,b) => a - b);
    
    // Binary search or simple find closest
    let closest = times[0];
    let minDiff = Math.abs(ct - closest);
    
    for (let t of times) {
       const diff = Math.abs(ct - t);
       if (diff < minDiff) {
           minDiff = diff;
           closest = t;
       }
    }
    
    // Only show if we are within 0.5s of the frame
    if (minDiff < 0.5) {
       setCurrentFrame({
           timestamp: closest,
           detections: cache[closest] || []
       });
    } else {
       setCurrentFrame({
           timestamp: ct,
           detections: []
       });
    }
  };

  const BoundingBoxOverlay = () => {
    if (!currentFrame || !currentFrame.detections) return null;
    return (
      <div className="absolute inset-0 pointer-events-none">
        {currentFrame.detections.map((det, i) => {
          const scaleX = 100 / 640;
          const scaleY = 100 / 384;
          const left = det.bbox[0] * scaleX;
          const top = det.bbox[1] * scaleY;
          const width = (det.bbox[2] - det.bbox[0]) * scaleX;
          const height = (det.bbox[3] - det.bbox[1]) * scaleY;
          
          return (
            <div 
              key={i}
              className="absolute border-2 border-primary-500 rounded-sm bg-primary-500/10 transition-all duration-75"
              style={{ left: `${left}%`, top: `${top}%`, width: `${width}%`, height: `${height}%` }}
            >
              <div className="absolute -top-6 left-0 bg-primary-500 text-white text-xs px-2 py-0.5 rounded shadow whitespace-nowrap font-medium">
                {det.class} #{det.track_id} — {Math.round(det.confidence * 100)}%
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="flex h-full bg-dark-900">
      {/* Left Column - Video & Timeline */}
      <div className="flex-1 flex flex-col p-6 space-y-4 overflow-y-auto">
        <div className="flex justify-between items-center mb-2">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center">
              {analysis?.video_title || 'Loading Video Workspace...'}
            </h1>
            <div className="flex items-center space-x-4 mt-2 text-sm text-gray-400">
              <span className={`flex items-center ${wsStatus.includes('Connected') ? 'text-green-500' : 'text-gray-500'}`}>
                <Activity size={16} className="mr-1.5"/> {wsStatus}
              </span>
              <span className="flex items-center">
                <Clock size={16} className="mr-1.5"/> {Math.round(progress)}% Processed
              </span>
            </div>
          </div>
          <div className="flex flex-col items-end">
             {analysis?.status === 'completed' && (
                <div className="bg-green-500/10 text-green-400 px-3 py-1 rounded-full text-xs font-semibold border border-green-500/20 mb-2">
                  Analysis Complete
                </div>
             )}
          </div>
        </div>

        {/* Video Player Container */}
        <div className="bg-black rounded-2xl overflow-hidden relative border border-dark-700 shadow-xl aspect-video flex-shrink-0 group">
          {analysis?.video_url ? (
            <video 
              ref={videoRef}
              src={analysis.video_url} 
              controls 
              className="w-full h-full object-contain"
              crossOrigin="anonymous"
              onTimeUpdate={handleTimeUpdate}
            />
          ) : (
            <div className="w-full h-full flex flex-col items-center justify-center text-dark-600 space-y-4">
               <Loader2 className="animate-spin w-8 h-8" />
               <p>Loading Secure Video Stream...</p>
            </div>
          )}
          <BoundingBoxOverlay />
        </div>
        
        {/* Real YOLO Details / Tracking */}
        <div className="grid grid-cols-2 gap-4">
            <div className="bg-dark-800 rounded-xl border border-dark-700 p-5 shadow-sm">
                <div className="flex justify-between items-center mb-4">
                    <h3 className="font-semibold text-white flex items-center"><Target size={18} className="mr-2 text-primary-500"/> Live Detections (YOLO)</h3>
                    <span className="text-xs bg-dark-700 px-2 py-1 rounded text-gray-400">Current Frame</span>
                </div>
                <div className="space-y-3 max-h-48 overflow-y-auto pr-2">
                  {currentFrame?.detections?.map((det, i) => (
                    <div key={i} className="flex items-center justify-between bg-dark-900 p-3 rounded-lg border border-dark-700 hover:border-primary-500/30 transition-colors">
                      <div className="flex items-center space-x-3">
                        <div className="w-2.5 h-2.5 rounded-full bg-primary-500 animate-pulse"></div>
                        <span className="font-medium text-white">{det.class}</span>
                      </div>
                      <div className="text-right">
                        <span className="text-xs text-gray-400 block font-mono">Track #{det.track_id}</span>
                        <span className="text-sm font-semibold text-primary-400">{Math.round(det.confidence * 100)}%</span>
                      </div>
                    </div>
                  ))}
                  {(!currentFrame?.detections || currentFrame.detections.length === 0) && (
                    <div className="text-center text-gray-500 py-8 border border-dashed border-dark-600 rounded-lg">
                        No instruments detected in current frame.
                    </div>
                  )}
                </div>
            </div>

            <div className="bg-dark-800 rounded-xl border border-dark-700 p-5 shadow-sm flex flex-col">
                <h3 className="font-semibold text-white flex items-center mb-4"><Info size={18} className="mr-2 text-blue-500"/> Surgical Phase Recognition</h3>
                <div className="flex-1 flex flex-col items-center justify-center text-center p-6 bg-dark-900 border border-dark-700 border-dashed rounded-xl">
                    <AlertTriangle className="text-yellow-500 mb-3" size={32} />
                    <p className="text-gray-300 font-medium mb-1">Phase recognition unavailable</p>
                    <p className="text-sm text-gray-500">There is currently no validated surgical phase recognition model loaded for this deployment.</p>
                </div>
            </div>
        </div>

        {/* Pipeline Status */}
        <div className="bg-dark-800 rounded-xl border border-dark-700 p-5 shadow-sm flex flex-col mb-4">
            <h3 className="font-semibold text-white flex items-center mb-4"><Activity size={18} className="mr-2 text-green-500"/> AI Pipeline Status</h3>
            <div className="grid grid-cols-5 gap-2 text-sm text-center">
                <div className="flex flex-col items-center">
                    <span className="text-gray-400 mb-1">AI Engine</span>
                    <span className={analysis?.model_provider === 'real' ? 'text-green-400 font-semibold' : 'text-yellow-400 font-semibold'}>● {analysis?.model_provider === 'real' ? 'Ready' : 'Mock/Simulated'}</span>
                </div>
                <div className="flex flex-col items-center border-l border-dark-600">
                    <span className="text-gray-400 mb-1">Video Analysis</span>
                    <span className={analysis?.status === 'completed' ? 'text-green-400 font-semibold' : 'text-blue-400 font-semibold'}>● {analysis?.status === 'completed' ? 'Complete' : (analysis?.status === 'processing' ? `Processing ${Math.round(progress)}%` : 'Waiting')}</span>
                </div>
                <div className="flex flex-col items-center border-l border-dark-600">
                    <span className="text-gray-400 mb-1">Knowledge</span>
                    <span className={analysis?.status === 'completed' ? 'text-green-400 font-semibold' : 'text-gray-500 font-semibold'}>● {analysis?.status === 'completed' ? 'Ready' : 'Pending'}</span>
                </div>
                <div className="flex flex-col items-center border-l border-dark-600">
                    <span className="text-gray-400 mb-1">Embeddings</span>
                    <span className={analysis?.status === 'completed' ? 'text-green-400 font-semibold' : 'text-gray-500 font-semibold'}>● {analysis?.status === 'completed' ? 'Ready' : 'Pending'}</span>
                </div>
                <div className="flex flex-col items-center border-l border-dark-600">
                    <span className="text-gray-400 mb-1">Q&A</span>
                    <span className={analysis?.llm_provider === 'mock' ? 'text-yellow-400 font-semibold' : 'text-green-400 font-semibold'}>● {analysis?.llm_provider === 'mock' ? 'Mock Mode' : 'Ready'}</span>
                </div>
            </div>
        </div>

        {/* Timeline Chart */}
        <div className="h-48 bg-dark-800 rounded-xl border border-dark-700 p-5 shadow-sm flex-shrink-0">
          <h3 className="text-sm font-semibold text-white mb-4">Detection Confidence Timeline</h3>
          <div className="h-32 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={timelineData}>
                <defs>
                  <linearGradient id="colorConf" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.8}/>
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <XAxis dataKey="time" hide />
                <YAxis hide domain={[0, 100]} />
                <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px', color: '#f3f4f6' }}/>
                <Area type="monotone" dataKey="confidence" stroke="#3b82f6" strokeWidth={2} fillOpacity={1} fill="url(#colorConf)" isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Right Column - Q&A Workspace */}
      <div className="w-96 border-l border-dark-700 bg-dark-800 flex flex-col">
        <div className="p-4 border-b border-dark-700 bg-dark-800 flex items-center space-x-3">
          <div className="p-2 bg-accent-500/20 rounded-lg">
             <Brain className="text-accent-400" size={20} />
          </div>
          <div>
              <h2 className="font-bold text-white">SurgiVision AI Assistant</h2>
              <p className="text-xs text-gray-400">Context: This specific video</p>
          </div>
        </div>
        
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((msg, idx) => (
            <div key={idx} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
              <div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm shadow-sm ${
                msg.role === 'user' 
                  ? 'bg-primary-600 text-white rounded-br-none' 
                  : 'bg-dark-700 text-gray-100 rounded-bl-none border border-dark-600'
              }`}>
                {msg.content.split('\n').map((line, i) => {
                    // Render timestamp evidence as clickable links
                    if (line.startsWith('*(Evidence')) {
                        const parts = line.match(/\d+s/g) || [];
                        let rendered = line;
                        return (
                            <span key={i} className="block mt-2 text-accent-300 text-xs italic">
                                Evidence found at: {parts.map((p, j) => (
                                    <button key={j} onClick={() => jumpToTime(parseInt(p))} className="hover:underline text-accent-400 ml-1">{p}</button>
                                ))}
                            </span>
                        );
                    }
                    return <span key={i} className="block">{line}</span>;
                })}
              </div>
            </div>
          ))}
          {chatLoading && (
            <div className="flex items-start">
              <div className="bg-dark-700 text-gray-100 rounded-2xl rounded-bl-none px-4 py-3 text-sm flex items-center space-x-2 border border-dark-600">
                <Loader2 size={14} className="animate-spin text-accent-400" />
                <span className="text-gray-400">Retrieving video context...</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="p-4 bg-dark-900 border-t border-dark-700">
          <form onSubmit={handleSendMessage} className="relative">
            <input
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              placeholder="Ask about events in this video..."
              disabled={chatLoading || !analysis?.video_id}
              className="w-full bg-dark-800 border border-dark-600 rounded-full pl-4 pr-12 py-3 text-sm text-white focus:outline-none focus:border-accent-500 focus:ring-1 focus:ring-accent-500 transition-colors placeholder-gray-500"
            />
            <button 
              type="submit" 
              disabled={!chatInput.trim() || chatLoading || !analysis?.video_id}
              className="absolute right-1.5 top-1.5 p-1.5 bg-accent-600 hover:bg-accent-500 text-white rounded-full transition-colors disabled:bg-dark-600 disabled:text-gray-400"
            >
              <Send size={16} />
            </button>
          </form>
          <div className="mt-2 text-center">
            <span className="text-[10px] text-gray-500">AI answers are grounded exclusively in extracted knowledge from this recording.</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Analysis;
