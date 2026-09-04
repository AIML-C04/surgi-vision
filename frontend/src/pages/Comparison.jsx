import React, { useEffect, useState, useContext } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { AlertTriangle, ArrowRight, BarChart3, ChevronLeft, GitCompare, Loader2, Video } from 'lucide-react';
import { AuthContext } from '../context/AuthContext';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const formatTime = (seconds) => {
  if (seconds === null || seconds === undefined) return 'Not available';
  const total = Math.max(0, Math.round(Number(seconds)));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const remainder = total % 60;
  return hours ? `${hours}:${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}` : `${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}`;
};

const formatMetric = (value, type = 'number') => {
  if (value === null || value === undefined) return 'Not available';
  if (type === 'time') return formatTime(value);
  if (type === 'confidence') return `${(value * 100).toFixed(1)}%`;
  if (type === 'rate') return `${Number(value).toFixed(2)} / min`;
  return Number.isInteger(value) ? value.toLocaleString() : Number(value).toFixed(2);
};

const Comparison = () => {
  const { token } = useContext(AuthContext);
  const [searchParams, setSearchParams] = useSearchParams();
  const [videos, setVideos] = useState([]);
  const [videoA, setVideoA] = useState(searchParams.get('a') || '');
  const [videoB, setVideoB] = useState(searchParams.get('b') || '');
  const [comparison, setComparison] = useState(null);
  const [loadingVideos, setLoadingVideos] = useState(true);
  const [loadingComparison, setLoadingComparison] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadVideos = async () => {
      try {
        const response = await axios.get(`${API_URL}/api/v1/videos/`, { headers: { Authorization: `Bearer ${token}` } });
        setVideos(Array.isArray(response.data) ? response.data : []);
      } catch (err) {
        setError(err.response?.data?.detail || 'Unable to load procedures.');
      } finally {
        setLoadingVideos(false);
      }
    };
    loadVideos();
  }, [token]);

  const runComparison = async (event) => {
    event.preventDefault();
    if (!videoA || !videoB || videoA === videoB) {
      setError('Choose two different procedures.');
      return;
    }
    setLoadingComparison(true);
    setError('');
    setComparison(null);
    setSearchParams({ a: videoA, b: videoB });
    try {
      const response = await axios.get(`${API_URL}/api/v1/compare`, {
        params: { video_a_id: videoA, video_b_id: videoB },
        headers: { Authorization: `Bearer ${token}` },
      });
      setComparison(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Unable to compare these procedures.');
    } finally {
      setLoadingComparison(false);
    }
  };

  const overviewMetrics = comparison ? [
    ['Duration', 'duration', 'time'],
    ['Detections', 'total_detections'],
    ['Tracks', 'total_tracks'],
    ['Events', 'total_events'],
    ['Instrument classes', 'instrument_classes'],
    ['Co-occurrences', 'co_occurrences'],
    ['Average confidence', 'average_detection_confidence', 'confidence'],
  ] : [];

  return (
    <div className="min-h-full bg-dark-900 text-gray-200 p-6 lg:p-8">
      <div className="max-w-7xl mx-auto">
        <div className="flex flex-wrap items-start justify-between gap-4 mb-8">
          <div>
            <Link to="/" className="text-sm text-gray-500 hover:text-white flex items-center mb-3"><ChevronLeft size={16} className="mr-1"/> Video Workspace</Link>
            <h1 className="text-3xl font-bold text-white flex items-center"><GitCompare size={28} className="mr-3 text-primary-400"/> Procedure Comparison</h1>
            <p className="text-gray-400 mt-2">Compare observable, model-derived video intelligence. This is not a clinical performance assessment.</p>
          </div>
        </div>

        <form onSubmit={runComparison} className="bg-dark-800 border border-dark-700 rounded-xl p-5 flex flex-col lg:flex-row gap-4 lg:items-end">
          <label className="flex-1 text-sm text-gray-400">Procedure A
            <select value={videoA} onChange={(event) => setVideoA(event.target.value)} disabled={loadingVideos} className="mt-2 w-full bg-dark-900 border border-dark-600 rounded-lg px-3 py-3 text-white">
              <option value="">Select procedure A</option>
              {videos.map((video) => <option key={video.id} value={video.id}>{video.title}</option>)}
            </select>
          </label>
          <ArrowRight className="hidden lg:block text-gray-600 mb-3" size={20}/>
          <label className="flex-1 text-sm text-gray-400">Procedure B
            <select value={videoB} onChange={(event) => setVideoB(event.target.value)} disabled={loadingVideos} className="mt-2 w-full bg-dark-900 border border-dark-600 rounded-lg px-3 py-3 text-white">
              <option value="">Select procedure B</option>
              {videos.map((video) => <option key={video.id} value={video.id}>{video.title}</option>)}
            </select>
          </label>
          <button type="submit" disabled={loadingComparison || loadingVideos} className="bg-primary-600 hover:bg-primary-500 disabled:bg-dark-600 text-white px-5 py-3 rounded-lg font-semibold flex items-center justify-center gap-2">
            {loadingComparison ? <Loader2 size={18} className="animate-spin"/> : <BarChart3 size={18}/>} Compare
          </button>
        </form>

        {error && <div className="mt-5 p-4 rounded-lg border border-red-500/30 bg-red-500/10 text-red-300 flex items-center gap-2"><AlertTriangle size={18}/>{error}</div>}
        {loadingComparison && <div className="py-20 flex items-center justify-center gap-3 text-gray-400"><Loader2 className="animate-spin text-primary-400"/> Aggregating persisted intelligence...</div>}

        {comparison && !loadingComparison && (
          <div className="mt-6 space-y-6">
            {comparison.model_versions_differ && <div className="p-4 rounded-lg border border-yellow-500/30 bg-yellow-500/10 text-yellow-200 text-sm">Model versions differ. Comparison metrics may not be directly equivalent.</div>}
            {comparison.analysis_versions_differ && <div className="p-4 rounded-lg border border-yellow-500/30 bg-yellow-500/10 text-yellow-200 text-sm">Analysis versions differ. Values reflect each procedure's latest completed analysis.</div>}

            <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {[comparison.procedure_a, comparison.procedure_b].map((procedure, index) => (
                <div key={procedure.video_id} className="bg-dark-800 border border-dark-700 rounded-xl p-5">
                  <div className="flex items-start justify-between gap-3">
                    <div><p className="text-xs uppercase tracking-wider text-gray-500">Procedure {index === 0 ? 'A' : 'B'}</p><h2 className="text-xl font-semibold text-white mt-1">{procedure.title}</h2></div>
                    <Link to={`/analysis/${procedure.video_id}`} className="text-primary-400 hover:text-primary-300 text-sm">Open workspace</Link>
                  </div>
                  <div className="grid grid-cols-2 gap-4 mt-5 text-sm">
                    <div><span className="text-gray-500 block">Duration</span><span className="text-gray-200">{formatTime(procedure.duration)}</span></div>
                    <div><span className="text-gray-500 block">Processed</span><span className="text-gray-200">{procedure.processed_at ? new Date(procedure.processed_at).toLocaleString() : 'Not available'}</span></div>
                    <div><span className="text-gray-500 block">Analysis version</span><span className="text-gray-200">v{procedure.analysis_version}</span></div>
                    <div><span className="text-gray-500 block">Model version</span><span className="text-gray-200 break-all">{procedure.model_version || 'Not available'}</span></div>
                  </div>
                </div>
              ))}
            </section>

            <section className="bg-dark-800 border border-dark-700 rounded-xl overflow-hidden">
              <div className="p-5 border-b border-dark-700"><h2 className="text-lg font-semibold text-white">Overall Intelligence</h2><p className="text-xs text-gray-500 mt-1">Absolute values and normalized rates per minute</p></div>
              <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="bg-dark-900 text-gray-400"><tr><th className="px-5 py-3">Metric</th><th className="px-5 py-3">Procedure A</th><th className="px-5 py-3">Procedure B</th><th className="px-5 py-3">Difference B - A</th></tr></thead><tbody className="divide-y divide-dark-700">{overviewMetrics.map(([label, key, type]) => { const metric = comparison.overview[key]; return <tr key={key}><td className="px-5 py-3 text-gray-300">{label}</td><td className="px-5 py-3 text-gray-200">{formatMetric(metric.a, type)}</td><td className="px-5 py-3 text-gray-200">{formatMetric(metric.b, type)}</td><td className="px-5 py-3 text-primary-300">{formatMetric(metric.difference.absolute, type)}</td></tr>; })}</tbody></table></div>
            </section>

            <section className="bg-dark-800 border border-dark-700 rounded-xl overflow-hidden"><div className="p-5 border-b border-dark-700"><h2 className="text-lg font-semibold text-white">Phase Recognition</h2></div>{comparison.phases?.available ? <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 p-5">{[['A', comparison.phases.a], ['B', comparison.phases.b]].map(([label, phases]) => <div key={label}><p className="text-xs uppercase text-gray-500 mb-2">Procedure {label}</p>{phases.length ? phases.map((phase) => <div key={phase.id} className="border-b border-dark-700 py-2 text-sm"><span className="text-gray-200">{phase.phase_name}</span><span className="float-right text-gray-500">{formatTime(phase.duration)}</span></div>) : <p className="text-gray-500">No phase segments.</p>}</div>)}</div> : <p className="p-5 text-gray-500">{comparison.phases?.reason || 'Phase comparison unavailable because the phase model/taxonomy differs.'}</p>}</section>

            <section className="bg-dark-800 border border-dark-700 rounded-xl overflow-hidden">
              <div className="p-5 border-b border-dark-700"><h2 className="text-lg font-semibold text-white">Instrument Intelligence</h2></div>
              <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="bg-dark-900 text-gray-400"><tr><th className="px-5 py-3">Instrument</th><th className="px-5 py-3">A detections</th><th className="px-5 py-3">B detections</th><th className="px-5 py-3">Visible duration A / B</th><th className="px-5 py-3">Tracks A / B</th><th className="px-5 py-3">Avg confidence A / B</th></tr></thead><tbody className="divide-y divide-dark-700">{comparison.instruments.map((row) => <tr key={row.class_name}><td className="px-5 py-3 font-medium text-white">{row.class_name}</td><td className="px-5 py-3">{formatMetric(row.detection_count.a)}</td><td className="px-5 py-3">{formatMetric(row.detection_count.b)}</td><td className="px-5 py-3">{formatTime(row.visible_duration.a)} / {formatTime(row.visible_duration.b)}</td><td className="px-5 py-3">{formatMetric(row.track_count.a)} / {formatMetric(row.track_count.b)}</td><td className="px-5 py-3">{formatMetric(row.average_confidence.a, 'confidence')} / {formatMetric(row.average_confidence.b, 'confidence')}</td></tr>)}</tbody></table></div>
              {comparison.instruments.length === 0 && <p className="p-5 text-gray-500">No common or unique instrument classes are available.</p>}
            </section>

              <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="bg-dark-800 border border-dark-700 rounded-xl overflow-hidden"><div className="p-5 border-b border-dark-700"><h2 className="text-lg font-semibold text-white">Event Intelligence</h2></div><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="bg-dark-900 text-gray-400"><tr><th className="px-5 py-3">Event type</th><th className="px-5 py-3">A</th><th className="px-5 py-3">B</th><th className="px-5 py-3">B - A</th></tr></thead><tbody className="divide-y divide-dark-700">{comparison.events.map((row) => <tr key={row.event_type}><td className="px-5 py-3 text-gray-300">{row.event_type.replaceAll('_', ' ')}</td><td className="px-5 py-3">{formatMetric(row.count.a.a)}</td><td className="px-5 py-3">{formatMetric(row.count.b.a)}</td><td className="px-5 py-3 text-primary-300">{formatMetric(row.count.difference.absolute)}</td></tr>)}</tbody></table></div></div>
              <div className="bg-dark-800 border border-dark-700 rounded-xl overflow-hidden"><div className="p-5 border-b border-dark-700"><h2 className="text-lg font-semibold text-white">Simultaneous Model Detection</h2><p className="text-xs text-gray-500 mt-1">Co-occurrence pairs, not interaction or exchange claims</p></div>{comparison.co_occurrences.length ? <div className="divide-y divide-dark-700">{comparison.co_occurrences.map((row) => <div key={row.instruments.join('+')} className="p-5 flex items-start justify-between gap-4"><div><p className="font-medium text-white">{row.instruments.join(' + ')}</p><p className="text-xs text-gray-500 mt-1">A: {row.timestamps.a.map(formatTime).join(', ') || 'None'}</p><p className="text-xs text-gray-500">B: {row.timestamps.b.map(formatTime).join(', ') || 'None'}</p></div><span className="text-sm text-primary-300">{row.count.a.a} / {row.count.b.a}</span></div>)}</div> : <p className="p-5 text-gray-500">No co-occurrence pairs are available.</p>}</div>
            </section>

            <section className="bg-dark-800 border border-dark-700 rounded-xl p-5"><h2 className="text-lg font-semibold text-white mb-4">Timeline Comparison</h2>{[['A', comparison.timeline.a], ['B', comparison.timeline.b]].map(([label, timeline]) => <div key={label} className="mb-5 last:mb-0"><div className="flex items-center gap-3 mb-2"><span className="w-7 text-xs font-semibold text-gray-400">{label}</span><span className="text-xs text-gray-500">{timeline.events.length} event markers</span><Link to={`/analysis/${label === 'A' ? comparison.procedure_a.video_id : comparison.procedure_b.video_id}`} className="ml-auto text-xs text-primary-400">View events</Link></div><div className="relative h-9 bg-dark-900 rounded border border-dark-700">{timeline.activity.flatMap((item) => item.segments.map((segment, index) => <span key={`${item.instrument}-${segment.start_time}-${index}`} title={`${item.instrument} ${formatTime(segment.start_time)}-${formatTime(segment.end_time)}`} className="absolute top-2 h-5 rounded-sm bg-primary-500/70" style={{ left: `${(segment.start_time / (label === 'A' ? comparison.procedure_a.duration : comparison.procedure_b.duration || 1)) * 100}%`, width: `${Math.max(0.8, ((segment.end_time - segment.start_time) / (label === 'A' ? comparison.procedure_a.duration : comparison.procedure_b.duration || 1)) * 100)}%` }} />))}</div></div>)}</section>

            <section className="grid grid-cols-1 lg:grid-cols-2 gap-6"><div className="bg-dark-800 border border-dark-700 rounded-xl p-5"><h2 className="text-lg font-semibold text-white mb-4">Key Differences</h2>{comparison.highlights.length ? <ul className="space-y-3">{comparison.highlights.map((highlight) => <li key={highlight} className="text-sm text-gray-300 flex gap-2"><span className="text-primary-400">•</span>{highlight}</li>)}</ul> : <p className="text-sm text-gray-500">No factual differences were identified in the returned metrics.</p>}</div><div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-5"><h2 className="text-lg font-semibold text-blue-200 mb-3">Interpretation Limits</h2>{comparison.limitations.map((limitation) => <p key={limitation} className="text-sm text-blue-100/70 mb-2">{limitation}</p>)}</div></section>
          </div>
        )}
        {!comparison && !loadingComparison && !error && <div className="py-20 text-center text-gray-500"><Video size={40} className="mx-auto mb-4 text-gray-600"/><p>Select two completed procedures to begin.</p></div>}
      </div>
    </div>
  );
};

export default Comparison;
