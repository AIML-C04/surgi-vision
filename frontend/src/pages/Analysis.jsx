import React, { useState, useEffect, useRef, useContext } from 'react';
import { useParams, Link, useLocation } from 'react-router-dom';
import axios from 'axios';
import { Activity, Clock, Play, Pause, AlertTriangle, MessageSquare, Send, Brain, Target, Info, Loader2, ZoomIn, ZoomOut, Maximize2, Crosshair, GitCompare } from 'lucide-react';
import { AuthContext } from '../context/AuthContext';

const formatSeconds = (seconds) => {
  if (seconds === null || seconds === undefined || Number.isNaN(Number(seconds))) return 'Not available';
  const total = Math.max(0, Math.round(Number(seconds)));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const remainder = total % 60;
  return hours > 0
    ? `${hours}:${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}`
    : `${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}`;
};

const formatChatError = (error) => {
  if (!error.response) return 'Copilot could not connect to the backend.';
  if (error.response.status === 401) return 'Your session expired. Please sign in again.';
  if (error.response.status === 404) return 'The requested video or conversation was not found.';
  if (error.response.status === 422) return 'The Copilot request was invalid.';
  if (error.response.status === 503) return error.response.data?.detail || 'Copilot is temporarily unavailable.';
  if (error.response.status === 500) return 'Copilot is unavailable because the configured Hugging Face LLM provider failed.';
  return error.response.data?.detail || 'Copilot could not process this request.';
};

const Analysis = () => {
  const { id } = useParams();
  const location = useLocation();
  const [analysis, setAnalysis] = useState(null);
  const [videoError, setVideoError] = useState(null);
  const [wsStatus, setWsStatus] = useState('Not connected');
  const [progress, setProgress] = useState(0);
  const [currentFrame, setCurrentFrame] = useState(null);
  const [events, setEvents] = useState([]);
  const [phaseStatus, setPhaseStatus] = useState(null);
  const [phases, setPhases] = useState([]);
  const [allDetections, setAllDetections] = useState({});
  const [instrumentIntelligence, setInstrumentIntelligence] = useState(null);
  const [expandedInstrument, setExpandedInstrument] = useState(null);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [timelineError, setTimelineError] = useState(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [videoDuration, setVideoDuration] = useState(0);
  const [timelineFilter, setTimelineFilter] = useState('all');
  const [instrumentFilter, setInstrumentFilter] = useState('all');
  const [eventFilter, setEventFilter] = useState('all');
  const [confidenceThreshold, setConfidenceThreshold] = useState(0);
  const [timelineZoom, setTimelineZoom] = useState(1);
  const [selectedTimelineItem, setSelectedTimelineItem] = useState(null);
  const timelineScrollRef = useRef(null);
  const { token } = useContext(AuthContext);
  
  // Chat state
  const [messages, setMessages] = useState([{ role: 'assistant', content: 'Hello! I can answer questions about this specific video based on the processed knowledge. What would you like to know?' }]);
  const [conversationId, setConversationId] = useState(null);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const videoContainerRef = useRef(null);

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
          setTimelineLoading(true);
          setTimelineError(null);
            try {
                const detRes = await axios.get(`${API_URL}/api/v1/analysis/${res.data.id}/detections`, config);
                detectionsCacheRef.current = detRes.data;
                setAllDetections(detRes.data);
            } catch(e) {
                console.error("Failed to fetch all detections", e);
            }
          try {
            const instrumentRes = await axios.get(`${API_URL}/api/v1/videos/${res.data.video_id}/instruments`, config);
            setInstrumentIntelligence(instrumentRes.data);
          } catch(e) {
            console.error("Failed to fetch instrument intelligence", e);
          }
          try {
            const eventRes = await axios.get(`${API_URL}/api/v1/videos/${res.data.video_id}/events?limit=1000`, config);
            setEvents(eventRes.data.events || []);
          } catch(e) {
            console.error("Failed to fetch surgical events", e);
            if (isMounted) setTimelineError(e.response?.data?.detail || 'Unable to load surgical intelligence.');
          } finally {
            if (isMounted) setTimelineLoading(false);
          }
          try {
            const phaseRes = await axios.get(`${API_URL}/api/v1/videos/${res.data.video_id}/phases`, config);
            if (isMounted) {
              setPhaseStatus(phaseRes.data);
              setPhases(phaseRes.data.phases || []);
            }
          } catch (e) {
            if (isMounted) setPhaseStatus({ available: false, status: 'failed', reason: 'Unable to load phase recognition status.' });
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
                const detail = err.response?.data?.detail || "Failed to fetch secure video URL.";
                if (isMounted) setVideoError(detail);
            }
        }
        
        if (isMounted) {
          setAnalysis({ ...res.data, video_url });
          setProgress(res.data.progress || 0);
        }
      } catch (err) {
        console.error("Failed to fetch analysis", err);
        if (isMounted) setVideoError("Failed to load analysis session.");
      }
    };
    fetchStatus();
  }, [id, token]);

  useEffect(() => {
    let isMounted = true;
    if (!analysis || !analysis.id || analysis.status === 'NOT_STARTED' || analysis.status === 'completed' || analysis.status === 'error') return;

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
    
    setWsStatus('Connecting...');
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
        
      } else if (data.event === 'analysis_completed') {
        setAnalysis(prev => ({ ...prev, status: 'completed' }));
        setProgress(100);
        setAllDetections({...detectionsCacheRef.current});
      } else if (data.event === 'analysis_failed') {
        setAnalysis(prev => ({ ...prev, status: 'error', error: data.error }));
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

  useEffect(() => {
    if (analysis?.status === 'completed' && videoRef.current) {
      const params = new URLSearchParams(location.search);
      const timeParam = params.get('time');
      if (timeParam) {
        const targetTime = parseFloat(timeParam);
        if (!isNaN(targetTime)) {
          // A slight delay ensures the video element has loaded its metadata
          setTimeout(() => {
            if (videoRef.current) {
              const duration = Number.isFinite(videoRef.current.duration) ? videoRef.current.duration : videoDuration;
              const nextTime = Math.max(0, Math.min(targetTime, duration || targetTime));
              videoRef.current.currentTime = nextTime;
              setCurrentTime(nextTime);
              videoContainerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
          }, 500);
        }
      }
    }
  }, [location.search, analysis?.status]);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!chatInput.trim() || !analysis?.video_id) return;

    const userMessage = chatInput.trim();
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setChatInput('');
    setChatLoading(true);

    try {
      const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const selectedContext = selectedTimelineItem?.kind === 'event'
        ? { type: 'event', event_id: selectedTimelineItem.value.id }
        : selectedTimelineItem?.kind === 'segment'
          ? { type: 'segment', instrument: selectedTimelineItem.value.class_name, start_time: selectedTimelineItem.value.segment.start_time, end_time: selectedTimelineItem.value.segment.end_time }
          : null;
      const res = await axios.post(`${API_URL}/api/v1/chat/`, {
        video_id: analysis.video_id,
        query: userMessage,
        conversation_id: conversationId,
        selected_context: selectedContext
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });

      setConversationId(res.data.conversation_id);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: res.data.answer,
        evidence: res.data.evidence || [],
        support: res.data.support || 'insufficient_evidence',
      }]);
    } catch (err) {
      setMessages(prev => [...prev, { role: 'assistant', content: formatChatError(err) }]);
    } finally {
      setChatLoading(false);
    }
  };

  const selectCopilotEvidence = (evidence) => {
    const timestamp = evidence.start_time ?? evidence.timestamp ?? 0;
    const matchingEvent = evidence.event_id ? events.find((event) => event.id === evidence.event_id) : null;
    if (matchingEvent) {
      setSelectedTimelineItem({ kind: 'event', value: matchingEvent });
    } else if (evidence.instrument && instrumentIntelligence) {
      const item = instrumentIntelligence.instruments.find((instrument) => instrument.class_name === evidence.instrument);
      const segment = item?.activity_segments.find((candidate) => candidate.start_time <= timestamp && candidate.end_time >= timestamp) || item?.activity_segments[0];
      if (item && segment) {
        setSelectedTimelineItem({ kind: 'segment', value: { class_name: item.class_name, segment, track: item.tracks.find((track) => track.first_seen <= segment.start_time && track.last_seen >= segment.start_time) } });
      }
    }
    seekTo(timestamp, true);
  };

  const handleStartAnalysis = async (reanalyze = false) => {
    try {
      if (reanalyze && !window.confirm("This will rerun AI analysis and may take several minutes. Continue?")) return;
      
      const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const config = { headers: { Authorization: `Bearer ${token}` } };
      
      // Optimistic UI update
      setAnalysis(prev => ({ ...prev, status: 'processing' }));
      setProgress(0);
      setCurrentFrame(null);
      setAllDetections({});
      setInstrumentIntelligence(null);
      setEvents([]);
      setConversationId(null);
      setTimelineError(null);
      setSelectedTimelineItem(null);
      setCurrentTime(0);
      setVideoDuration(0);
      setExpandedInstrument(null);
      detectionsCacheRef.current = {};
      
      const res = await axios.post(`${API_URL}/api/v1/analysis/?video_id=${id}&reanalyze=${reanalyze}`, null, config);
      setAnalysis(prev => ({ ...prev, id: res.data.analysis_id, status: res.data.status }));
      
    } catch (err) {
      console.error(err);
      alert("Failed to start analysis: " + (err.response?.data?.detail || err.message));
      setAnalysis(prev => ({ ...prev, status: reanalyze ? 'completed' : 'NOT_STARTED' }));
    }
  };
  
  const seekTo = (time, shouldPlay = true) => {
    if (videoRef.current) {
        const duration = Number.isFinite(videoRef.current.duration) ? videoRef.current.duration : videoDuration;
        const nextTime = Math.max(0, Math.min(Number(time) || 0, duration || Number(time) || 0));
        videoRef.current.currentTime = nextTime;
        setCurrentTime(nextTime);
        const bounds = videoContainerRef.current?.getBoundingClientRect();
        if (bounds && (bounds.top < 0 || bounds.bottom > window.innerHeight)) {
          videoContainerRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        if (shouldPlay) videoRef.current.play().catch(() => {});
    }
  };

  const jumpToTime = (time) => seekTo(time, true);

  const centerTimelineOnCurrentTime = () => {
    const container = timelineScrollRef.current;
    if (!container) return;
    const contentWidth = container.firstElementChild?.scrollWidth || container.scrollWidth;
    container.scrollLeft = Math.max(0, (currentTime / timelineDuration) * contentWidth - container.clientWidth / 2);
  };

  const generateTimelineIntelligence = async () => {
    if (!analysis?.video_id) return;
    setTimelineLoading(true);
    setTimelineError(null);
    try {
      const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const config = { headers: { Authorization: `Bearer ${token}` } };
      await axios.post(`${API_URL}/api/v1/videos/${analysis.video_id}/events/generate`, null, config);
      const eventRes = await axios.get(`${API_URL}/api/v1/videos/${analysis.video_id}/events?limit=1000`, config);
      setEvents(eventRes.data.events || []);
    } catch (err) {
      // The event endpoint can report an in-progress analysis with 409. Always
      // check for persisted events before showing a fatal timeline error.
      if (err.response?.status === 409) {
        try {
          const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
          const eventRes = await axios.get(`${API_URL}/api/v1/videos/${analysis.video_id}/events?limit=1000`, { headers: { Authorization: `Bearer ${token}` } });
          if (eventRes.data.events?.length) {
            setEvents(eventRes.data.events);
            return;
          }
        } catch (_) {
          // Preserve the original backend error below if persisted events cannot be read.
        }
      }
      setTimelineError(err.response?.data?.detail || 'Unable to generate surgical intelligence.');
    } finally {
      setTimelineLoading(false);
    }
  };

  const handleTimeUpdate = () => {
    if (!videoRef.current) return;
    
    const ct = videoRef.current.currentTime;
    setCurrentTime(ct);
    if (Number.isFinite(videoRef.current.duration)) setVideoDuration(videoRef.current.duration);
    if (analysis?.status !== 'completed') return;
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

  const timelineDuration = videoDuration || Math.max(
    1,
    ...events.map((event) => event.end_time || event.start_time || 0),
    ...phases.map((phase) => phase.end_time || phase.start_time || 0),
    ...(instrumentIntelligence?.instruments || []).flatMap((item) => item.activity_segments.map((segment) => segment.end_time || 0)),
  );
  const timelineWidth = `${Math.max(100, timelineZoom * 100)}%`;
  const tickStep = timelineDuration <= 60 ? 10 : timelineDuration <= 300 ? 30 : timelineDuration <= 900 ? 60 : timelineDuration <= 1800 ? 300 : 600;
  const ticks = Array.from({ length: Math.floor(timelineDuration / tickStep) + 1 }, (_, index) => Math.min(index * tickStep, timelineDuration));
  const availableInstruments = instrumentIntelligence?.instruments || [];
  const visibleInstruments = instrumentFilter === 'all'
    ? availableInstruments
    : availableInstruments.filter((item) => item.class_name === instrumentFilter);
  const confidenceInstruments = confidenceThreshold === 0
    ? visibleInstruments
    : visibleInstruments.filter((item) => item.average_confidence !== null && item.average_confidence >= confidenceThreshold);
  const visibleEvents = events.filter((event) => {
    const eventInstrument = event.metadata?.instrument || '';
    const eventInstruments = event.metadata?.instruments || [];
    const matchesInstrument = instrumentFilter === 'all' || eventInstrument === instrumentFilter || eventInstruments.includes(instrumentFilter);
    const matchesEvent = eventFilter === 'all' || event.event_type === eventFilter;
    const matchesConfidence = confidenceThreshold === 0 || (event.confidence !== null && event.confidence >= confidenceThreshold);
    return matchesInstrument && matchesEvent && matchesConfidence;
  });
  const timelineEvents = timelineFilter === 'instruments' ? visibleEvents.filter((event) => event.event_type.startsWith('INSTRUMENT_')) :
    timelineFilter === 'events' ? visibleEvents.filter((event) => !['INSTRUMENT_ACTIVITY', 'INSTRUMENT_CO_OCCURRENCE'].includes(event.event_type)) :
    timelineFilter === 'cooccurrence' ? visibleEvents.filter((event) => event.event_type === 'INSTRUMENT_CO_OCCURRENCE') : visibleEvents;
  const keyMoments = [...visibleEvents].sort((left, right) => {
    const priority = { INSTRUMENT_ENTERED: 1, INSTRUMENT_REMOVED: 2, INSTRUMENT_CO_OCCURRENCE: 3, INSTRUMENT_ACTIVITY: 4 };
    return (priority[left.event_type] || 9) - (priority[right.event_type] || 9) || left.start_time - right.start_time;
  }).slice(0, 6);
  const position = (time) => `${Math.max(0, Math.min(100, (Number(time) / timelineDuration) * 100))}%`;
  const eventLabel = (event) => {
    if (event.event_type === 'INSTRUMENT_CO_OCCURRENCE') return (event.metadata?.instruments || []).join(' + ') || 'Simultaneous detection';
    return event.metadata?.instrument || event.event_type.replaceAll('_', ' ').toLowerCase();
  };
  const selectedEvent = selectedTimelineItem?.kind === 'event' ? selectedTimelineItem.value : null;
  const selectedSegment = selectedTimelineItem?.kind === 'segment' ? selectedTimelineItem.value : null;
  const selectedPhase = selectedTimelineItem?.kind === 'phase' ? selectedTimelineItem.value : null;

  return (
    <div className="flex h-full min-h-0 flex-col lg:flex-row bg-dark-900">
      {/* Left Column - Video & Timeline */}
      <div className="min-w-0 w-full lg:flex-1 min-h-0 flex flex-col p-6 space-y-4 overflow-hidden">
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
          <div className="flex flex-col items-end space-y-2">
             {analysis?.status === 'completed' && (
                <div className="flex items-center space-x-3">
                   <div className="bg-green-500/10 text-green-400 px-3 py-1 rounded-full text-xs font-semibold border border-green-500/20">
                     Analysis Complete
                   </div>
                   <Link
                     to={`/report/${id}`}
                     className="text-xs bg-primary-600 hover:bg-primary-500 text-white px-3 py-1 rounded-full transition-colors font-medium flex items-center"
                   >
                     View Report
                   </Link>
                   <button 
                     onClick={() => handleStartAnalysis(true)} 
                     className="text-xs bg-dark-700 hover:bg-dark-600 text-white px-3 py-1 rounded-full border border-dark-600 transition-colors"
                   >
                     Re-analyze
                   </button>
                   <Link to={`/compare?a=${id}`} className="text-xs bg-dark-700 hover:bg-dark-600 text-white px-3 py-1 rounded-full border border-dark-600 transition-colors flex items-center gap-1">
                     <GitCompare size={12} /> Compare
                   </Link>
                </div>
             )}
             {analysis?.status === 'NOT_STARTED' && (
                <button 
                  onClick={() => handleStartAnalysis(false)} 
                  className="text-sm bg-primary-600 hover:bg-primary-500 text-white px-4 py-2 rounded-lg font-semibold transition-colors flex items-center shadow-lg"
                >
                  <Play size={16} className="mr-2" /> Start AI Analysis
                </button>
             )}
          </div>
        </div>

        {/* Video Player Container */}
        <div ref={videoContainerRef} className="bg-black rounded-2xl overflow-hidden relative border border-dark-700 shadow-xl aspect-video flex-shrink-0 group lg:h-[min(42vh,32rem)] lg:aspect-auto">
          {analysis?.video_url ? (
            <video 
              ref={videoRef}
              src={analysis.video_url} 
              controls 
              className="w-full h-full object-contain"
              crossOrigin="anonymous"
              onLoadedMetadata={(event) => setVideoDuration(event.currentTarget.duration || 0)}
              onTimeUpdate={handleTimeUpdate}
            />
          ) : (
            <div className="w-full h-full flex flex-col items-center justify-center text-dark-600 space-y-4">
               {videoError ? (
                  <>
                     <AlertTriangle className="text-red-500 w-10 h-10 mb-2" />
                     <p className="text-red-400 font-medium">{videoError}</p>
                  </>
               ) : (
                  <>
                     <Loader2 className="animate-spin w-8 h-8" />
                     <p>Loading Secure Video Stream...</p>
                  </>
               )}
            </div>
          )}
          <BoundingBoxOverlay />
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto space-y-4 pr-1">

        <div className="bg-dark-800 rounded-xl border border-dark-700 p-5 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-semibold text-white flex items-center"><Target size={18} className="mr-2 text-primary-500"/> Instrument Intelligence</h3>
              <p className="text-xs text-gray-500 mt-1">Derived from persisted detections, tracks, and activity events</p>
            </div>
            {instrumentIntelligence?.instrument_intelligence_available && (
              <span className="text-xs text-gray-400">{instrumentIntelligence.track_count} track instances</span>
            )}
          </div>
          {!instrumentIntelligence?.instrument_intelligence_available ? (
            <div className="text-center text-gray-500 py-8 border border-dashed border-dark-600 rounded-lg">
              Instrument intelligence is not available for this analysis.
            </div>
          ) : (
            <div className="space-y-3">
              {instrumentIntelligence.instruments.map((item) => (
                <div key={item.class_name} className="bg-dark-900 border border-dark-700 rounded-lg overflow-hidden">
                  <button
                    type="button"
                    onClick={() => setExpandedInstrument(expandedInstrument === item.class_name ? null : item.class_name)}
                    className="w-full text-left p-4 hover:bg-dark-800 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="w-2.5 h-2.5 rounded-full bg-primary-500"></span>
                          <span className="font-semibold text-white">{item.class_name}</span>
                        </div>
                        <p className="text-xs text-gray-500 mt-1">{item.track_count} track instance{item.track_count === 1 ? '' : 's'} · {item.activity_segment_count} activity segment{item.activity_segment_count === 1 ? '' : 's'}</p>
                      </div>
                      <div className="text-right">
                        <span className="text-lg font-semibold text-primary-400">{Math.round(item.latest_confidence * 100)}%</span>
                        <span className="text-xs text-gray-500 block">latest confidence</span>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-4 text-xs">
                      <div><span className="text-gray-500 block">Visible duration</span><span className="text-gray-200">{formatSeconds(item.visible_duration)}</span></div>
                      <div><span className="text-gray-500 block">Detections</span><span className="text-gray-200">{item.detection_count}</span></div>
                      <div><span className="text-gray-500 block">Average</span><span className="text-gray-200">{Math.round(item.average_confidence * 100)}%</span></div>
                      <div><span className="text-gray-500 block">Peak</span><span className="text-gray-200">{Math.round(item.peak_confidence * 100)}%</span></div>
                      <div><span className="text-gray-500 block">First / last</span><span className="text-gray-200">{formatSeconds(item.first_seen)} / {formatSeconds(item.last_seen)}</span></div>
                    </div>
                  </button>
                  {expandedInstrument === item.class_name && (
                    <div className="border-t border-dark-700 p-4 space-y-4">
                      <div>
                        <p className="text-xs uppercase tracking-wide text-gray-500 mb-2">Track instances</p>
                        <div className="space-y-2">
                          {item.tracks.length === 0 ? <p className="text-sm text-gray-500">Track details not available.</p> : item.tracks.map((track) => (
                            <button
                              type="button"
                              key={track.track_id}
                              onClick={() => jumpToTime(track.first_seen)}
                              className="w-full text-left flex items-center justify-between bg-dark-800 hover:bg-dark-700 rounded-md px-3 py-2 text-sm"
                            >
                              <span className="text-gray-200">Track #{track.track_id}</span>
                              <span className="text-gray-400">{formatSeconds(track.first_seen)} - {formatSeconds(track.last_seen)} · {track.detection_count} detections</span>
                            </button>
                          ))}
                        </div>
                      </div>
                      <div>
                        <p className="text-xs uppercase tracking-wide text-gray-500 mb-2">Activity segments</p>
                        <div className="flex flex-wrap gap-2">
                          {item.activity_segments.map((segment, index) => (
                            <button
                              type="button"
                              key={`${segment.start_time}-${index}`}
                              onClick={() => jumpToTime(segment.start_time)}
                              className="text-xs px-2.5 py-1.5 rounded-md bg-primary-500/10 border border-primary-500/20 text-primary-300 hover:bg-primary-500/20"
                            >
                              {formatSeconds(segment.start_time)} - {formatSeconds(segment.end_time)}
                            </button>
                          ))}
                        </div>
                      </div>
                      {item.co_occurrences.length > 0 && (
                        <div>
                          <p className="text-xs uppercase tracking-wide text-gray-500 mb-2">Co-occurrences</p>
                          <p className="text-sm text-gray-300">{item.co_occurrences.length} simultaneous detection interval{item.co_occurrences.length === 1 ? '' : 's'} with other instruments.</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
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
                <h3 className="font-semibold text-white flex items-center mb-4"><Info size={18} className="mr-2 text-blue-500"/> Phase Recognition</h3>
                <div className="flex-1 flex flex-col items-center justify-center text-center p-6 bg-dark-900 border border-dark-700 border-dashed rounded-xl">
                    <AlertTriangle className="text-yellow-500 mb-3" size={32} />
                    {phaseStatus?.status === 'completed' && phases.length > 0 ? <div className="w-full text-left"><p className="text-gray-300 font-medium mb-3">Model-predicted phases</p>{phases.map((phase) => <button type="button" key={phase.id} onClick={() => { setSelectedTimelineItem({ kind: 'phase', value: phase }); seekTo(phase.start_time, false); }} className="w-full text-left border-b border-dark-700 py-2 text-sm text-gray-300"><span>{phase.phase_name}</span><span className="float-right text-gray-500">{formatSeconds(phase.start_time)} - {formatSeconds(phase.end_time)}</span></button>)}</div> : <><p className="text-gray-300 font-medium mb-1">{phaseStatus?.status === 'processing' ? 'Phase recognition is being processed.' : 'Phase recognition unavailable'}</p><p className="text-sm text-gray-500">{phaseStatus?.reason || 'No validated phase recognition model is configured for this analysis.'}</p></>}
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

        {/* Surgical Intelligence Timeline */}
        <section className="bg-dark-800 rounded-xl border border-dark-700 p-5 shadow-sm flex-shrink-0">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h3 className="text-sm font-semibold text-white flex items-center"><Crosshair size={17} className="mr-2 text-primary-400"/> Surgical Intelligence Timeline</h3>
              <p className="text-xs text-gray-500 mt-1">Evidence-linked activity from this analysis</p>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs">
              {['all', 'instruments', 'events', 'cooccurrence'].map((filter) => (
                <button key={filter} type="button" onClick={() => setTimelineFilter(filter)} className={`px-2.5 py-1.5 rounded-md border ${timelineFilter === filter ? 'bg-primary-500/15 border-primary-500/40 text-primary-300' : 'bg-dark-900 border-dark-600 text-gray-400 hover:text-white'}`}>
                  {filter === 'all' ? 'All' : filter === 'cooccurrence' ? 'Co-occurrence' : filter[0].toUpperCase() + filter.slice(1)}
                </button>
              ))}
              <button type="button" title="Zoom out" aria-label="Zoom out" onClick={() => setTimelineZoom((value) => Math.max(0.5, value / 2))} className="p-1.5 rounded-md border border-dark-600 text-gray-400 hover:text-white"><ZoomOut size={15}/></button>
              <button type="button" title="Fit timeline to video" aria-label="Fit timeline to video" onClick={() => setTimelineZoom(1)} className="p-1.5 rounded-md border border-dark-600 text-gray-400 hover:text-white"><Maximize2 size={15}/></button>
              <button type="button" title="Zoom in" aria-label="Zoom in" onClick={() => setTimelineZoom((value) => Math.min(8, value * 2))} className="p-1.5 rounded-md border border-dark-600 text-gray-400 hover:text-white"><ZoomIn size={15}/></button>
              <button type="button" title="Center timeline on current time" aria-label="Center timeline on current time" onClick={centerTimelineOnCurrentTime} className="p-1.5 rounded-md border border-dark-600 text-gray-400 hover:text-white"><Crosshair size={15}/></button>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 mt-4 text-xs">
            <label className="flex items-center gap-2 text-gray-400">Instrument
              <select value={instrumentFilter} onChange={(event) => setInstrumentFilter(event.target.value)} className="bg-dark-900 border border-dark-600 rounded-md px-2 py-1.5 text-gray-200">
                <option value="all">All instruments</option>
                {availableInstruments.map((item) => <option key={item.class_name} value={item.class_name}>{item.class_name}</option>)}
              </select>
            </label>
            <label className="flex items-center gap-2 text-gray-400">Event
              <select value={eventFilter} onChange={(event) => setEventFilter(event.target.value)} className="bg-dark-900 border border-dark-600 rounded-md px-2 py-1.5 text-gray-200">
                <option value="all">All events</option>
                {[...new Set(events.map((event) => event.event_type))].map((type) => <option key={type} value={type}>{type.replaceAll('_', ' ')}</option>)}
              </select>
            </label>
            <label className="flex items-center gap-2 text-gray-400">Confidence ≥ {Math.round(confidenceThreshold * 100)}%
              <input aria-label="Minimum confidence" type="range" min="0" max="0.95" step="0.05" value={confidenceThreshold} onChange={(event) => setConfidenceThreshold(Number(event.target.value))} className="accent-blue-500" />
            </label>
            <span className="ml-auto text-gray-500">{formatSeconds(currentTime)} / {formatSeconds(videoDuration)}</span>
          </div>

          {timelineLoading ? (
            <div className="mt-5 h-56 flex items-center justify-center text-gray-400">Loading surgical intelligence...</div>
          ) : timelineError ? (
            <div className="mt-5 h-56 flex flex-col items-center justify-center gap-3 text-center border border-dashed border-red-500/30 rounded-lg">
              <p className="text-red-300">Unable to load surgical intelligence.</p>
              <button type="button" onClick={() => window.location.reload()} className="px-3 py-1.5 rounded-md bg-dark-700 text-gray-200 hover:bg-dark-600">Retry</button>
            </div>
          ) : !events.length && !availableInstruments.length ? (
            <div className="mt-5 h-56 flex flex-col items-center justify-center gap-2 text-center border border-dashed border-dark-600 rounded-lg">
              <p className="text-gray-300">No event intelligence is available for this analysis.</p>
              <p className="text-xs text-gray-500">Generate event intelligence from the existing detections to populate this timeline.</p>
              <button type="button" onClick={generateTimelineIntelligence} className="px-3 py-1.5 rounded-md bg-primary-600 text-white hover:bg-primary-500">Generate Intelligence</button>
            </div>
          ) : (
            <div ref={timelineScrollRef} className="mt-5 overflow-x-auto pb-2">
              <div className="relative min-w-[680px]" style={{ width: timelineWidth }}>
                <div className="relative h-8 border-b border-dark-600 text-[10px] text-gray-500">
                  {ticks.map((tick) => <button type="button" key={tick} onClick={() => seekTo(tick, false)} className="absolute bottom-1 -translate-x-1/2 hover:text-white" style={{ left: position(tick) }}>{formatSeconds(tick)}</button>)}
                </div>
                <button type="button" aria-label={`Seek to ${formatSeconds(currentTime)}`} onClick={() => seekTo(currentTime, false)} className="absolute top-0 bottom-0 z-20 w-px bg-accent-400" style={{ left: position(currentTime) }}>
                  <span className="absolute -top-1 -translate-x-1/2 border-4 border-transparent border-t-accent-400" />
                </button>

                <div className="py-3 space-y-3">
                  <div className="text-[10px] uppercase tracking-wider text-gray-500">Instrument activity</div>
                  {confidenceInstruments.map((item) => (
                    <div key={item.class_name} className="flex items-center gap-3 h-7">
                      <span className="w-20 shrink-0 text-xs text-gray-300 truncate">{item.class_name}</span>
                      <div className="relative h-5 flex-1 bg-dark-900 rounded border border-dark-700">
                        {item.activity_segments.map((segment, index) => {
                          const selected = selectedSegment?.class_name === item.class_name && selectedSegment?.segment.start_time === segment.start_time;
                          return <button type="button" key={`${segment.start_time}-${index}`} title={`${item.class_name} ${formatSeconds(segment.start_time)}-${formatSeconds(segment.end_time)}`} onClick={() => { setSelectedTimelineItem({ kind: 'segment', value: { class_name: item.class_name, segment, track: item.tracks.find((track) => track.first_seen <= segment.start_time && track.last_seen >= segment.start_time) } }); seekTo(segment.start_time, false); }} className={`absolute top-0.5 h-4 rounded-sm border ${selected ? 'bg-accent-400 border-white' : 'bg-primary-500/70 border-primary-300/40 hover:bg-primary-400'}`} style={{ left: position(segment.start_time), width: `${Math.max(0.6, ((segment.end_time - segment.start_time) / timelineDuration) * 100)}%` }} />;
                        })}
                      </div>
                    </div>
                  ))}

                  {phases.length > 0 && <><div className="text-[10px] uppercase tracking-wider text-gray-500 pt-2">Phase recognition</div><div className="relative h-7 bg-dark-900 rounded border border-dark-700">{phases.map((phase) => <button type="button" key={`phase-${phase.id}`} title={`${phase.phase_name} ${formatSeconds(phase.start_time)}-${formatSeconds(phase.end_time)}`} onClick={() => { setSelectedTimelineItem({ kind: 'phase', value: phase }); seekTo(phase.start_time, false); }} className={`absolute top-1 h-5 rounded-sm border text-[10px] truncate px-1 ${selectedPhase?.id === phase.id ? 'bg-accent-400 border-white text-dark-900' : 'bg-blue-500/70 border-blue-300/50 text-white hover:bg-blue-400'}`} style={{ left: position(phase.start_time), width: `${Math.max(1, ((phase.end_time - phase.start_time) / timelineDuration) * 100)}%` }}>{phase.phase_name}</button>)}</div></>}

                  <div className="text-[10px] uppercase tracking-wider text-gray-500 pt-2">Events</div>
                  <div className="relative h-12 bg-dark-900 rounded border border-dark-700">
                    {timelineEvents.filter((event) => event.event_type !== 'INSTRUMENT_ACTIVITY').map((event) => {
                      const selected = selectedEvent?.id === event.id;
                      const isRange = event.end_time > event.start_time;
                      return <button type="button" key={event.id} title={`${eventLabel(event)} at ${formatSeconds(event.start_time)}`} onClick={() => { setSelectedTimelineItem({ kind: 'event', value: event }); seekTo(event.start_time, false); }} className={`absolute top-3 h-5 ${isRange ? 'rounded-sm border' : 'w-3 -translate-x-1/2 rounded-full'} ${selected ? 'bg-accent-400 border-white' : event.event_type === 'INSTRUMENT_CO_OCCURRENCE' ? 'bg-orange-400/80 border-orange-300/60' : 'bg-primary-400 border-primary-200/60'}`} style={{ left: position(event.start_time), width: isRange ? `${Math.max(0.8, ((event.end_time - event.start_time) / timelineDuration) * 100)}%` : undefined }} />;
                    })}
                  </div>

                  <div className="text-[10px] uppercase tracking-wider text-gray-500 pt-2">Confidence evidence</div>
                  <div className="relative h-10 bg-dark-900 rounded border border-dark-700">
                    {visibleEvents.filter((event) => event.confidence !== null).map((event) => <button type="button" key={`confidence-${event.id}`} aria-label={`${Math.round(event.confidence * 100)} percent confidence at ${formatSeconds(event.start_time)}`} onClick={() => { setSelectedTimelineItem({ kind: 'event', value: event }); seekTo(event.start_time, false); }} className="absolute bottom-0 w-1.5 bg-blue-400/80 hover:bg-white" style={{ left: position(event.start_time), height: `${Math.max(8, event.confidence * 100)}%` }} />)}
                  </div>
                </div>
                <div className="flex items-center gap-4 pt-2 text-[10px] text-gray-500">
                  <span><i className="inline-block w-3 h-2 rounded-sm bg-primary-500/70 mr-1"/>Instrument activity</span>
                  <span><i className="inline-block w-2 h-2 rounded-full bg-primary-400 mr-1"/>Event</span>
                  <span><i className="inline-block w-2 h-2 rounded-full bg-orange-400 mr-1"/>Co-occurrence</span>
                  <span><i className="inline-block w-px h-3 bg-accent-400 mr-1"/>Playhead</span>
                </div>
              </div>
            </div>
          )}

          <div className="mt-4 min-h-20 bg-dark-900 border border-dark-700 rounded-lg p-4">
            {!selectedEvent && !selectedSegment && !selectedPhase ? (
              <p className="text-sm text-gray-500">Select an event or timeline segment to inspect evidence.</p>
            ) : selectedEvent ? (
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-xs">
                <div><span className="text-gray-500 block">Event</span><span className="text-gray-200">{selectedEvent.event_type.replaceAll('_', ' ')}</span></div>
                <div><span className="text-gray-500 block">Subject</span><span className="text-gray-200">{eventLabel(selectedEvent)}</span></div>
                <div><span className="text-gray-500 block">Time</span><span className="text-gray-200">{formatSeconds(selectedEvent.start_time)} - {formatSeconds(selectedEvent.end_time)}</span></div>
                <div><span className="text-gray-500 block">Confidence</span><span className="text-gray-200">{selectedEvent.confidence === null ? 'Not available' : `${Math.round(selectedEvent.confidence * 100)}%`}</span></div>
                <div><span className="text-gray-500 block">Evidence</span><span className="text-gray-200">{selectedEvent.evidence?.frame_ids?.length || 0} frames</span></div>
                <button type="button" onClick={() => seekTo(selectedEvent.start_time, true)} className="col-span-2 md:col-span-1 px-3 py-2 rounded-md bg-primary-600 text-white hover:bg-primary-500">Watch evidence</button>
              </div>
            ) : selectedPhase ? (
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-xs"><div><span className="text-gray-500 block">Phase</span><span className="text-gray-200">{selectedPhase.phase_name}</span></div><div><span className="text-gray-500 block">Time</span><span className="text-gray-200">{formatSeconds(selectedPhase.start_time)} - {formatSeconds(selectedPhase.end_time)}</span></div><div><span className="text-gray-500 block">Duration</span><span className="text-gray-200">{formatSeconds(selectedPhase.duration)}</span></div><div><span className="text-gray-500 block">Confidence</span><span className="text-gray-200">{selectedPhase.confidence === null ? 'Not available' : `${Math.round(selectedPhase.confidence * 100)}%`}</span></div><div><span className="text-gray-500 block">Model</span><span className="text-gray-200">{selectedPhase.phase_model_version || 'Not available'}</span></div><button type="button" onClick={() => seekTo(selectedPhase.start_time, true)} className="col-span-2 md:col-span-1 px-3 py-2 rounded-md bg-primary-600 text-white hover:bg-primary-500">Watch evidence</button></div>
            ) : (
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-xs">
                <div><span className="text-gray-500 block">Instrument</span><span className="text-gray-200">{selectedSegment.class_name}</span></div>
                <div><span className="text-gray-500 block">Time</span><span className="text-gray-200">{formatSeconds(selectedSegment.segment.start_time)} - {formatSeconds(selectedSegment.segment.end_time)}</span></div>
                <div><span className="text-gray-500 block">Duration</span><span className="text-gray-200">{formatSeconds(selectedSegment.segment.duration)}</span></div>
                <div><span className="text-gray-500 block">Track</span><span className="text-gray-200">{selectedSegment.track ? `#${selectedSegment.track.track_id}` : 'Not available'}</span></div>
                <button type="button" onClick={() => seekTo(selectedSegment.segment.start_time, true)} className="px-3 py-2 rounded-md bg-primary-600 text-white hover:bg-primary-500">Play segment</button>
              </div>
            )}
          </div>
          {keyMoments.length > 0 && (
            <div className="mt-4">
              <p className="text-[10px] uppercase tracking-wider text-gray-500 mb-2">Key moments</p>
              <div className="flex flex-wrap gap-2">
                {keyMoments.map((event) => <button type="button" key={`moment-${event.id}`} onClick={() => { setSelectedTimelineItem({ kind: 'event', value: event }); seekTo(event.start_time, false); }} className="text-left px-3 py-2 rounded-md bg-dark-900 border border-dark-700 hover:border-primary-500/50">
                  <span className="text-xs text-primary-300 font-mono">{formatSeconds(event.start_time)}</span>
                  <span className="block text-xs text-gray-300 mt-1">{eventLabel(event)}</span>
                </button>)}
              </div>
            </div>
          )}
        </section>
        </div>
      </div>

      {/* Right Column - Q&A Workspace */}
      <div className="w-full lg:w-96 min-h-[32rem] lg:min-h-0 border-t lg:border-t-0 lg:border-l border-dark-700 bg-dark-800 flex flex-col flex-1 lg:flex-none">
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
                {msg.role === 'assistant' && msg.support && (
                  <span className={`block mt-3 text-[10px] uppercase tracking-wide ${msg.support === 'supported' ? 'text-green-400' : msg.support === 'partially_supported' ? 'text-yellow-400' : 'text-gray-400'}`}>
                    {msg.support.replaceAll('_', ' ')}
                  </span>
                )}
                {msg.role === 'assistant' && msg.evidence?.length > 0 && (
                  <div className="mt-3 space-y-2 border-t border-dark-600 pt-2">
                    <span className="block text-[10px] uppercase tracking-wide text-gray-500">Evidence</span>
                    {msg.evidence.map((evidence) => (
                      <button
                        type="button"
                        key={evidence.evidence_id || `${evidence.start_time}-${evidence.text}`}
                        onClick={() => selectCopilotEvidence(evidence)}
                        className="w-full text-left rounded-md border border-dark-600 bg-dark-800/70 px-2.5 py-2 hover:border-accent-400/60"
                      >
                        <span className="text-xs text-accent-300 font-mono">{formatSeconds(evidence.start_time ?? evidence.timestamp)}{evidence.end_time !== undefined && evidence.end_time !== evidence.start_time ? ` - ${formatSeconds(evidence.end_time)}` : ''}</span>
                        <span className="block text-xs text-gray-300 mt-1">{evidence.event_type?.replaceAll('_', ' ') || evidence.instrument || evidence.type || 'Video evidence'}</span>
                        {evidence.confidence !== null && evidence.confidence !== undefined && <span className="block text-[10px] text-gray-500 mt-1">Confidence {Math.round(evidence.confidence * 100)}% · {evidence.frame_ids?.length || 0} frames</span>}
                        <span className="block text-[10px] text-accent-400 mt-1">Watch evidence</span>
                      </button>
                    ))}
                  </div>
                )}
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
