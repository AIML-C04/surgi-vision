import React, { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { Activity, Clock, Play, Pause, AlertTriangle } from 'lucide-react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip } from 'recharts';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const Analysis = () => {
  const { id } = useParams();
  const [analysis, setAnalysis] = useState(null);
  const [wsStatus, setWsStatus] = useState('Connecting...');
  const [progress, setProgress] = useState(0);
  const [currentFrame, setCurrentFrame] = useState(null);
  const [events, setEvents] = useState([]);
  const [timelineData, setTimelineData] = useState([{time: 0, confidence: 0}]);
  
  const ws = useRef(null);

  useEffect(() => {
    let isMounted = true;
    
    // Fetch initial status
      const fetchStatus = async () => {
      try {
        const token = localStorage.getItem('token');
        const config = { headers: { Authorization: `Bearer ${token}` } };
        const res = await axios.get(`${API_URL}/api/v1/analysis/${id}`, config);
        
        let video_url = null;
        if (res.data.video_id) {
            try {
                const urlRes = await axios.get(`${API_URL}/api/v1/videos/${res.data.video_id}/url`, config);
                video_url = `${API_URL}${urlRes.data.url}`;
            } catch (err) {
                console.error("Failed to fetch video URL", err);
            }
        }
        
        if (isMounted) {
          setAnalysis({ ...res.data, video_url });
          setProgress(res.data.progress);
        }
      } catch (err) {
        console.error("Failed to fetch analysis", err);
      }
    };
    fetchStatus();

    // Connect WebSocket
    const wsUrl = API_URL.replace('http', 'ws');
    const socket = new WebSocket(`${wsUrl}/api/v1/analysis/ws/${id}`);
    ws.current = socket;

    socket.onopen = () => {
      if (!isMounted) {
        socket.close();
        return;
      }
      setWsStatus('Connected (Live)');
    };
    
    socket.onerror = (error) => {
      if (isMounted) setWsStatus('Error connecting');
      console.error("WebSocket error:", error);
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
        
        // Add to timeline data periodically
        if (data.prediction.frame_id % 15 === 0) {
          setTimelineData(prev => [...prev, {
            time: Math.round(data.prediction.timestamp),
            confidence: data.prediction.phase.confidence * 100
          }].slice(-50)); // keep last 50 points
        }
        
        // Fake events
        if (Math.random() > 0.95) {
          setEvents(prev => [{
            id: Date.now(),
            time: new Date().toLocaleTimeString(),
            message: `Detected ${data.prediction.detections[0]?.class || 'instrument'} activity`
          }, ...prev].slice(0, 10));
        }
        
      } else if (data.event === 'analysis_completed') {
        setAnalysis(prev => ({ ...prev, status: 'completed' }));
        setProgress(100);
      }
    };

    return () => {
      isMounted = false;
      if (socket.readyState === WebSocket.OPEN) {
        socket.close();
      } else if (socket.readyState === WebSocket.CONNECTING) {
        // Prevent it from throwing an error if it's still connecting
        socket.onopen = () => socket.close();
      }
    };
  }, [id]);

  const BoundingBoxOverlay = () => {
    if (!currentFrame || !currentFrame.detections) return null;
    
    return (
      <div className="absolute inset-0 pointer-events-none">
        {currentFrame.detections.map((det, i) => {
          // Standardizes to typical video resolution, fallback 640x384 from demo
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
              <div className="absolute -top-6 left-0 bg-primary-500 text-white text-xs px-2 py-0.5 rounded shadow whitespace-nowrap">
                {det.class} #{det.track_id} — {Math.round(det.confidence * 100)}%
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="p-6 h-full flex flex-col space-y-6">
      {/* Header */}
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-bold">{analysis?.video_title || 'Loading...'}</h1>
          <div className="flex items-center space-x-4 mt-2 text-sm text-gray-400">
            <span className="flex items-center"><Activity size={16} className="mr-1 text-primary-500"/> {wsStatus}</span>
            <span className="flex items-center"><Clock size={16} className="mr-1"/> {Math.round(progress)}% Processed</span>
          </div>
        </div>
        <div className="flex flex-col items-end">
          {['local', 'real'].includes(analysis?.model_provider) ? (
            <div className="bg-blue-500/20 text-blue-400 px-4 py-1.5 rounded-full text-sm font-semibold border border-blue-500/50 flex items-center mb-2">
              <Activity size={16} className="mr-2" />
              REAL MODEL — YOLOv8s Cholec80
            </div>
          ) : (
            <div className="bg-yellow-500/20 text-yellow-500 px-4 py-1.5 rounded-full text-sm font-semibold border border-yellow-500/50 flex items-center mb-2">
              <AlertTriangle size={16} className="mr-2" />
              DEMO MODE — SIMULATED AI OUTPUT
            </div>
          )}
          <span className="text-xs text-gray-500 italic max-w-sm text-right">
            Research & Educational Prototype — Not intended for clinical diagnosis, treatment, or real-time medical decision-making.
          </span>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6 flex-1 min-h-0">
        
        {/* Main Video Area */}
        {/* Main Video Area */}
        <div className="col-span-2 flex flex-col space-y-6">
          <div className="bg-black rounded-xl overflow-hidden relative border border-dark-700 flex-1 flex flex-col">
            {/* Real Video Player */}
            <div className="flex-1 relative flex items-center justify-center bg-black">
              {analysis?.video_url ? (
                <video 
                  id="surgical-video"
                  src={analysis.video_url} 
                  controls 
                  className="w-full h-full object-contain"
                  crossOrigin="anonymous"
                />
              ) : (
                <p className="text-dark-700">Loading Video...</p>
              )}
              {/* <BoundingBoxOverlay /> */} 
            </div>
            
            {/* Processing Status */}
            <div className="bg-dark-800 p-4 border-t border-dark-700">
              <div className="flex justify-between text-xs text-gray-400 mb-1">
                <span>AI Processing Progress</span>
                <span>{Math.round(progress)}%</span>
              </div>
              <div className="w-full bg-dark-900 rounded-full h-1.5 mb-2">
                <div className="bg-primary-500 h-1.5 rounded-full transition-all duration-300" style={{ width: `${progress}%` }}></div>
              </div>
              <div className="flex justify-between text-xs text-gray-400">
                <span>{analysis?.status === 'processing' ? 'Processing...' : 'Completed'}</span>
              </div>
            </div>
          </div>
          
          {/* Timeline Chart */}
          <div className="h-48 bg-dark-800 rounded-xl border border-dark-700 p-4">
            <h3 className="text-sm font-medium text-gray-300 mb-4">Phase Confidence Timeline</h3>
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
                  <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: 'none', borderRadius: '8px' }}/>
                  <Area type="monotone" dataKey="confidence" stroke="#3b82f6" fillOpacity={1} fill="url(#colorConf)" isAnimationActive={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Right Sidebar */}
        <div className="col-span-1 flex flex-col space-y-6">
          
          {/* Current Phase */}
          <div className="bg-dark-800 rounded-xl border border-dark-700 p-6">
            <h3 className="text-gray-400 text-sm font-medium mb-1">Current Surgical Phase</h3>
            <div className="flex items-end justify-between">
              <p className={`text-2xl font-bold ${currentFrame?.phase?.name === 'Not available' ? 'text-gray-500' : 'text-primary-400'}`}>
                {currentFrame?.phase?.name || 'Unknown'}
              </p>
              <div className="text-right">
                <p className="text-xs text-gray-400">Confidence</p>
                <p className="text-lg font-semibold">{Math.round((currentFrame?.phase?.confidence || 0) * 100)}%</p>
              </div>
            </div>
            {currentFrame?.phase?.name === 'Not available' && (
              <p className="text-xs text-yellow-500 mt-2">Phase model not yet connected.</p>
            )}
          </div>

          {/* Detected Instruments */}
          <div className="bg-dark-800 rounded-xl border border-dark-700 flex-1 flex flex-col">
            <div className="p-4 border-b border-dark-700">
              <h3 className="font-medium">Detected Instruments</h3>
            </div>
            <div className="p-4 space-y-4 overflow-y-auto flex-1">
              {currentFrame?.detections?.map((det, i) => (
                <div key={i} className="flex items-center justify-between bg-dark-900 p-3 rounded-lg border border-dark-700">
                  <div className="flex items-center space-x-3">
                    <div className="w-2 h-2 rounded-full bg-green-500"></div>
                    <span className="font-medium">{det.class}</span>
                  </div>
                  <div className="text-right">
                    <span className="text-xs text-gray-400 block">Track #{det.track_id}</span>
                    <span className="text-sm">{Math.round(det.confidence * 100)}%</span>
                  </div>
                </div>
              ))}
              {(!currentFrame?.detections || currentFrame.detections.length === 0) && (
                <p className="text-center text-gray-500 py-8">No instruments detected in current frame.</p>
              )}
            </div>
          </div>

          {/* Event Log */}
          <div className="bg-dark-800 rounded-xl border border-dark-700 h-64 flex flex-col">
            <div className="p-4 border-b border-dark-700">
              <h3 className="font-medium">Event Alerts</h3>
            </div>
            <div className="p-4 overflow-y-auto space-y-3 flex-1">
              {events.map((evt) => (
                <div key={evt.id} className="flex space-x-3 text-sm">
                  <span className="text-gray-500 whitespace-nowrap">{evt.time}</span>
                  <span className="text-gray-300">{evt.message}</span>
                </div>
              ))}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
};

export default Analysis;
