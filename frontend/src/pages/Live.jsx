import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Activity, Camera, Link, XCircle, PlaySquare } from 'lucide-react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const Live = () => {
  const [role, setRole] = useState(null); // 'host' (laptop) or 'client' (mobile)
  const [sessionData, setSessionData] = useState(null);
  const [pairingCode, setPairingCode] = useState('');
  const [status, setStatus] = useState('Idle');
  
  const ws = useRef(null);
  const peerConnection = useRef(null);
  const localVideoRef = useRef(null);
  const remoteVideoRef = useRef(null);
  
  // Create Session (Host)
  const createSession = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await axios.post(`${API_URL}/api/v1/live/create`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSessionData(res.data);
      setRole('host');
      connectWebSocket(res.data.session_id, 'host');
    } catch (err) {
      alert('Failed to create live session');
    }
  };

  // Join Session (Client)
  const joinSession = async (e) => {
    e.preventDefault();
    try {
      // Basic demo verification without user auth required on mobile
      const res = await axios.post(`${API_URL}/api/v1/live/verify?code=${pairingCode}`);
      setSessionData(res.data);
      setRole('client');
      connectWebSocket(res.data.session_id, 'client');
      startClientMedia();
    } catch (err) {
      alert('Invalid or expired code');
    }
  };

  const [detections, setDetections] = useState([]);

  // ...

  const connectWebSocket = (sessionId, userRole) => {
      let wsUrl = '';
      if (API_URL.startsWith('http://')) {
          wsUrl = API_URL.replace('http://', 'ws://') + `/api/v1/live/ws/${sessionId}/${userRole}`;
      } else if (API_URL.startsWith('https://')) {
          wsUrl = API_URL.replace('https://', 'wss://') + `/api/v1/live/ws/${sessionId}/${userRole}`;
      } else {
          const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
          wsUrl = `${wsProtocol}//${window.location.host}/api/v1/live/ws/${sessionId}/${userRole}`;
      }
      
      const socket = new WebSocket(wsUrl);
      ws.current = socket;
    
    socket.onopen = () => setStatus('Connected to Signaling');
    socket.onmessage = async (event) => {
      // Handle blobs if any are received (though backend sends text JSON for detections)
      let data = event.data;
      if (data instanceof Blob) {
          const text = await data.text();
          data = text;
      }
      
      const message = JSON.parse(data);
      
      // If it's detection data from backend inference
      if (message.type === 'detections' && userRole === 'host') {
          setDetections(message.detections);
          return;
      }
      
      if (!peerConnection.current) setupPeerConnection();
      
      if (message.type === 'offer' && userRole === 'host') {
        await peerConnection.current.setRemoteDescription(new RTCSessionDescription(message));
        const answer = await peerConnection.current.createAnswer();
        await peerConnection.current.setLocalDescription(answer);
        socket.send(JSON.stringify(peerConnection.current.localDescription));
      } else if (message.type === 'answer' && userRole === 'client') {
        await peerConnection.current.setRemoteDescription(new RTCSessionDescription(message));
      } else if (message.candidate) {
        await peerConnection.current.addIceCandidate(new RTCIceCandidate(message));
      }
    };
  };

  const startInferenceLoop = () => {
      if (role !== 'host' || !remoteVideoRef.current) return;
      
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      
      setInterval(() => {
          if (remoteVideoRef.current.readyState === remoteVideoRef.current.HAVE_ENOUGH_DATA) {
              canvas.width = remoteVideoRef.current.videoWidth;
              canvas.height = remoteVideoRef.current.videoHeight;
              ctx.drawImage(remoteVideoRef.current, 0, 0, canvas.width, canvas.height);
              
              // Convert canvas to blob and send to backend
              canvas.toBlob((blob) => {
                  if (ws.current && ws.current.readyState === WebSocket.OPEN) {
                      ws.current.send(blob);
                  }
              }, 'image/jpeg', 0.8);
          }
      }, 200); // 5 FPS
  };

  useEffect(() => {
      if (status === 'Receiving Stream') {
          startInferenceLoop();
      }
  }, [status]);

  const mediaRecorderRef = useRef(null);
  const recordedChunks = useRef([]);
  const [isRecording, setIsRecording] = useState(false);

  const startRecording = (stream) => {
    const mediaRecorder = new MediaRecorder(stream, { mimeType: 'video/webm' });
    mediaRecorderRef.current = mediaRecorder;
    recordedChunks.current = [];
    
    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        recordedChunks.current.push(event.data);
      }
    };
    
    mediaRecorder.start(1000);
    setIsRecording(true);
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const saveRecording = async () => {
    stopRecording();
    const blob = new Blob(recordedChunks.current, { type: 'video/webm' });
    
    const formData = new FormData();
    formData.append('title', `Live Session ${new Date().toLocaleString()}`);
    formData.append('file', blob, 'live_recording.webm');
    
    try {
      const token = localStorage.getItem('token');
      await axios.post(`${API_URL}/api/v1/videos/upload`, formData, {
        headers: { 
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data'
        }
      });
      alert('Recording saved to Video Library!');
      window.location.href = '/';
    } catch (err) {
      alert('Failed to save recording');
    }
  };

  const discardRecording = () => {
    stopRecording();
    recordedChunks.current = [];
    if (ws.current) ws.current.close();
    window.location.reload();
  };

  const setupPeerConnection = () => {
    const pc = new RTCPeerConnection({
      iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
    });
    
    pc.onicecandidate = (event) => {
      if (event.candidate && ws.current) {
        ws.current.send(JSON.stringify(event.candidate));
      }
    };
    
    pc.ontrack = (event) => {
      if (remoteVideoRef.current) {
        remoteVideoRef.current.srcObject = event.streams[0];
        setStatus('Receiving Stream');
        if (role === 'host') startRecording(event.streams[0]);
      }
    };
    
    peerConnection.current = pc;
    return pc;
  };

  const startClientMedia = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      if (localVideoRef.current) {
        localVideoRef.current.srcObject = stream;
      }
      
      const pc = setupPeerConnection();
      stream.getTracks().forEach(track => pc.addTrack(track, stream));
      
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      ws.current.send(JSON.stringify(pc.localDescription));
      setStatus('Streaming');
    } catch (err) {
      alert('Camera access denied');
      setStatus('Camera Error');
    }
  };

  const BoundingBoxOverlay = () => {
    if (!detections || detections.length === 0) return null;
    
    return (
      <div className="absolute inset-0 pointer-events-none">
        {detections.map((det, i) => {
          // Assuming 640x384 for now, would need actual video dims from ref
          const scaleX = 100 / (remoteVideoRef.current?.videoWidth || 640);
          const scaleY = 100 / (remoteVideoRef.current?.videoHeight || 384);
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
    <div className="p-8 h-full max-w-6xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white tracking-tight">Live Broadcast Studio</h1>
        <p className="text-gray-400 mt-1">Connect a remote camera device for real-time surgical inference.</p>
      </div>
      
      {!role && (
        <div className="grid md:grid-cols-2 gap-8">
          <div className="bg-dark-800 p-8 rounded-2xl border border-dark-700 shadow-sm hover:border-primary-500/50 transition-all flex flex-col items-start group">
            <div className="bg-primary-500/10 p-4 rounded-xl mb-6 group-hover:scale-105 transition-transform">
              <PlaySquare size={32} className="text-primary-400"/>
            </div>
            <h2 className="text-2xl font-bold text-white mb-2">Host Analysis Session</h2>
            <p className="text-gray-400 mb-8 leading-relaxed">
              Create a secure P2P WebRTC session on this machine. You will generate a pairing code to stream video from a mobile device and process the inference locally.
            </p>
            <button onClick={createSession} className="w-full bg-primary-600 hover:bg-primary-500 text-white px-6 py-3 rounded-xl font-medium flex items-center justify-center space-x-2 transition-colors mt-auto shadow-lg shadow-primary-600/20">
              <PlaySquare size={20} /> 
              <span>Create Session</span>
            </button>
          </div>
          
          <div className="bg-dark-800 p-8 rounded-2xl border border-dark-700 shadow-sm hover:border-blue-500/50 transition-all flex flex-col items-start group">
             <div className="bg-blue-500/10 p-4 rounded-xl mb-6 group-hover:scale-105 transition-transform">
              <Camera size={32} className="text-blue-400"/>
            </div>
            <h2 className="text-2xl font-bold text-white mb-2">Join as Camera Client</h2>
            <p className="text-gray-400 mb-6 leading-relaxed">
              Use this device as the sterile field camera. Enter the 6-digit pairing code from the host machine to begin streaming securely.
            </p>
            <form onSubmit={joinSession} className="w-full flex flex-col mt-auto space-y-4">
              <input 
                type="text" 
                placeholder="Enter 6-digit code" 
                value={pairingCode}
                onChange={e => setPairingCode(e.target.value)}
                className="bg-dark-900 border border-dark-600 rounded-xl px-4 py-3 text-white text-center text-xl tracking-widest font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all placeholder:text-dark-600 placeholder:text-base placeholder:font-sans placeholder:tracking-normal"
                maxLength={6}
                required
              />
              <button type="submit" className="w-full bg-blue-600 hover:bg-blue-500 text-white px-6 py-3 rounded-xl font-medium flex items-center justify-center space-x-2 transition-colors shadow-lg shadow-blue-600/20">
                <Camera size={20} /> 
                <span>Start Camera Stream</span>
              </button>
            </form>
          </div>
        </div>
      )}

      {role === 'host' && sessionData && (
        <div className="flex flex-col space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
          <div className="bg-dark-800 p-6 rounded-2xl border border-primary-500/30 flex justify-between items-center shadow-sm">
            <div>
              <p className="text-sm text-gray-400 font-medium mb-1">Pairing Code (Enter on mobile)</p>
              <p className="text-4xl font-mono tracking-[0.3em] font-bold text-primary-400">{sessionData.pairing_code}</p>
            </div>
            <div className="text-right">
              <span className={`flex items-center text-sm font-medium px-4 py-2 rounded-full border ${
                  status.includes('Receiving') ? 'bg-green-500/10 text-green-400 border-green-500/30' : 'bg-yellow-500/10 text-yellow-500 border-yellow-500/30'
              }`}>
                  <Activity size={16} className="mr-2"/> {status.toUpperCase()}
              </span>
            </div>
          </div>
          
          <div className="bg-black rounded-2xl overflow-hidden relative border border-dark-700 flex items-center justify-center aspect-video shadow-xl">
            <video ref={remoteVideoRef} autoPlay playsInline className="w-full h-full object-contain"></video>
            {status !== 'Receiving Stream' && (
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-dark-900/80 backdrop-blur-sm">
                   <div className="w-16 h-16 border-4 border-dark-700 border-t-primary-500 rounded-full animate-spin mb-4"></div>
                   <p className="text-gray-400 font-medium tracking-wide">WAITING FOR SECURE P2P CONNECTION...</p>
                </div>
            )}
            {status === 'Receiving Stream' && <BoundingBoxOverlay />}
            {isRecording && (
                <div className="absolute top-4 right-4 bg-red-500/90 backdrop-blur text-white px-3 py-1.5 rounded-full text-xs font-bold flex items-center shadow-lg animate-pulse">
                    <div className="w-2 h-2 bg-white rounded-full mr-2"></div>
                    REC
                </div>
            )}
          </div>
          
          <div className="flex justify-end space-x-4">
             <button onClick={discardRecording} className="bg-dark-700 hover:bg-dark-600 text-white px-6 py-3 rounded-xl font-medium transition-colors border border-dark-600">
              Discard & End Session
            </button>
            <button onClick={saveRecording} className="bg-green-600 hover:bg-green-500 text-white px-6 py-3 rounded-xl font-medium flex items-center space-x-2 transition-colors shadow-lg shadow-green-600/20">
              <span>Save Recording to Library</span>
            </button>
          </div>
        </div>
      )}

      {role === 'client' && (
        <div className="flex flex-col max-w-2xl mx-auto space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
          <div className="bg-dark-800 p-6 rounded-2xl border border-dark-700 shadow-sm">
            <div className="flex justify-between items-center mb-6">
                <h2 className="text-xl font-bold text-white flex items-center"><Camera className="mr-2 text-blue-400" size={24}/> Secure Camera Link</h2>
                <span className="bg-green-500/10 text-green-400 px-3 py-1 rounded-full text-xs font-bold border border-green-500/30 flex items-center">
                    <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse mr-1.5"></div>
                    {status.toUpperCase()}
                </span>
            </div>
            
            <div className="bg-black rounded-xl overflow-hidden relative border border-dark-700 flex items-center justify-center aspect-video shadow-inner">
              <video ref={localVideoRef} autoPlay playsInline muted className="w-full h-full object-cover transform -scale-x-100"></video>
            </div>
            
            <button onClick={() => window.location.reload()} className="w-full mt-6 bg-red-600/90 hover:bg-red-500 text-white px-4 py-3.5 rounded-xl font-medium transition-colors flex items-center justify-center space-x-2">
              <XCircle size={20} />
              <span>End Transmission</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default Live;
