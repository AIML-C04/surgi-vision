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
    const wsUrl = API_URL.replace('http', 'ws');
    const socket = new WebSocket(`${wsUrl}/api/v1/live/ws/${sessionId}/${userRole}`);
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
    <div className="p-6 h-full">
      <h1 className="text-2xl font-bold mb-6">Live Session</h1>
      
      {!role && (
        <div className="flex gap-8">
          <div className="bg-dark-800 p-6 rounded-xl border border-dark-700 w-1/2">
            <h2 className="text-lg font-bold mb-4">Start as Host (Laptop)</h2>
            <p className="text-gray-400 mb-4 text-sm">Create a session and generate a pairing code for your mobile device.</p>
            <button onClick={createSession} className="bg-primary-600 hover:bg-primary-500 text-white px-4 py-2 rounded font-medium flex items-center">
              <PlaySquare size={18} className="mr-2"/> Create Session
            </button>
          </div>
          
          <div className="bg-dark-800 p-6 rounded-xl border border-dark-700 w-1/2">
            <h2 className="text-lg font-bold mb-4">Join as Client (Mobile Camera)</h2>
            <form onSubmit={joinSession} className="flex flex-col space-y-4">
              <input 
                type="text" 
                placeholder="6-digit Pairing Code" 
                value={pairingCode}
                onChange={e => setPairingCode(e.target.value)}
                className="bg-dark-900 border border-dark-600 rounded p-2 text-white"
                maxLength={6}
                required
              />
              <button type="submit" className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded font-medium flex items-center justify-center">
                <Camera size={18} className="mr-2"/> Start Camera Stream
              </button>
            </form>
          </div>
        </div>
      )}

      {role === 'host' && sessionData && (
        <div className="flex flex-col space-y-4">
          <div className="bg-dark-800 p-4 rounded-xl border border-primary-500/30 flex justify-between items-center">
            <div>
              <p className="text-sm text-gray-400">Pairing Code (Enter on mobile)</p>
              <p className="text-3xl font-mono tracking-widest font-bold text-primary-400">{sessionData.pairing_code}</p>
            </div>
            <div className="text-right">
              <span className="flex items-center text-sm text-gray-400"><Activity size={16} className="mr-2"/> Status: {status}</span>
            </div>
          </div>
          
          <div className="bg-black rounded-xl overflow-hidden relative border border-dark-700 flex items-center justify-center h-[60vh]">
            <video ref={remoteVideoRef} autoPlay playsInline className="w-full h-full object-contain"></video>
            {status !== 'Receiving Stream' && <p className="text-dark-600 text-xl font-bold">WAITING FOR CAMERA STREAM...</p>}
            {status === 'Receiving Stream' && <BoundingBoxOverlay />}
          </div>
          
          <div className="flex space-x-4">
            <button onClick={saveRecording} className="bg-green-600 hover:bg-green-500 text-white px-4 py-2 rounded font-medium flex items-center">
              Save Recording {isRecording ? '(Recording...)' : ''}
            </button>
            <button onClick={discardRecording} className="bg-red-600 hover:bg-red-500 text-white px-4 py-2 rounded font-medium flex items-center">
              Discard & End
            </button>
          </div>
        </div>
      )}

      {role === 'client' && (
        <div className="flex flex-col space-y-4">
          <div className="bg-dark-800 p-4 rounded-xl border border-dark-700">
            <p className="text-sm text-center mb-2 font-bold text-green-400">{status}</p>
            <div className="bg-black rounded-xl overflow-hidden relative border border-dark-600 flex items-center justify-center h-[50vh]">
              <video ref={localVideoRef} autoPlay playsInline muted className="w-full h-full object-cover"></video>
            </div>
            <button onClick={() => window.location.reload()} className="w-full mt-4 bg-red-600 hover:bg-red-500 text-white px-4 py-3 rounded font-medium">
              Disconnect
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default Live;
