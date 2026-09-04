import React, { useContext, useEffect, useState } from 'react';
import axios from 'axios';
import { AlertTriangle, Beaker, CheckCircle2, Cpu, Database, Download, Loader2, Play, TrendingUp } from 'lucide-react';
import { AuthContext } from '../context/AuthContext';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const unavailable = 'Unavailable';

const formatNumber = (value) => value === null || value === undefined ? unavailable : Number(value).toLocaleString();
const formatSeconds = (value) => value === null || value === undefined ? unavailable : `${Number(value).toFixed(2)} s`;

const Research = () => {
  const { token } = useContext(AuthContext);
  const [overview, setOverview] = useState(null);
  const [datasets, setDatasets] = useState([]);
  const [runs, setRuns] = useState([]);
  const [videos, setVideos] = useState([]);
  const [selectedVideo, setSelectedVideo] = useState('');
  const [selectedDataset, setSelectedDataset] = useState('');
  const [datasetName, setDatasetName] = useState('Evaluation dataset');
  const [datasetVersion, setDatasetVersion] = useState('1.0');
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState('');
  const config = { headers: { Authorization: `Bearer ${token}` } };

  const load = async () => {
    setLoading(true);
    try {
      const [overviewResponse, datasetsResponse, runsResponse, videosResponse] = await Promise.all([
        axios.get(`${API_URL}/api/v1/research/overview`, config),
        axios.get(`${API_URL}/api/v1/research/datasets`, config),
        axios.get(`${API_URL}/api/v1/research/runs`, config),
        axios.get(`${API_URL}/api/v1/videos/`, config),
      ]);
      setOverview(overviewResponse.data);
      setDatasets(datasetsResponse.data);
      setRuns(runsResponse.data);
      setVideos(videosResponse.data || []);
      if (!selectedVideo && videosResponse.data?.length) setSelectedVideo(videosResponse.data[0].id);
      if (!selectedDataset && datasetsResponse.data?.length) setSelectedDataset(datasetsResponse.data[0].id);
    } catch (err) {
      setError(err.response?.data?.detail || 'Unable to load research data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [token]);

  const createDataset = async (event) => {
    event.preventDefault();
    setWorking(true);
    setError('');
    try {
      const response = await axios.post(`${API_URL}/api/v1/research/datasets`, { name: datasetName, version: datasetVersion, annotation_format: 'json-manifest', annotations: [] }, config);
      setDatasets((current) => [response.data, ...current]);
      setSelectedDataset(response.data.id);
    } catch (err) {
      setError(err.response?.data?.detail || 'Unable to create dataset reference.');
    } finally {
      setWorking(false);
    }
  };

  const createRun = async () => {
    if (!selectedDataset || !selectedVideo) return;
    setWorking(true);
    setError('');
    try {
      await axios.post(`${API_URL}/api/v1/research/runs`, { dataset_id: selectedDataset, video_id: selectedVideo }, config);
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Unable to start evaluation.');
    } finally {
      setWorking(false);
    }
  };

  const downloadRun = async (runId, format) => {
    try {
      const response = await axios.get(`${API_URL}/api/v1/research/runs/${runId}/export?format=${format}`, { ...config, responseType: 'blob' });
      const url = URL.createObjectURL(response.data);
      const link = document.createElement('a');
      link.href = url;
      link.download = `evaluation-${runId}.${format}`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.response?.data?.detail || 'Unable to export evaluation run.');
    }
  };

  const latest = runs[0];
  const detection = latest?.metrics?.detection;
  const performance = latest?.metrics?.performance;

  if (loading) return <div className="h-full flex items-center justify-center bg-dark-900 text-gray-300"><Loader2 className="animate-spin mr-3" /> Loading research data...</div>;

  return (
    <div className="p-8 max-w-6xl mx-auto h-full flex flex-col">
      <div className="flex justify-between items-end mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Research & Evaluation</h1>
          <p className="text-gray-400 mt-1 text-lg">Reproducible evaluation of persisted model outputs.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-dark-800 p-6 rounded-2xl border border-dark-700 shadow-sm flex flex-col items-start">
          <div className="flex items-center space-x-3 text-primary-400 mb-4 bg-primary-500/10 px-3 py-1.5 rounded-full">
            <Cpu size={18} />
            <span className="font-semibold text-sm">Active Model</span>
          </div>
            <p className="text-xl font-bold text-white mb-1">{overview?.model?.provider || unavailable}</p>
          <p className="text-sm font-medium text-gray-400">Version: {overview?.model?.version || unavailable}</p>
        </div>
        
        <div className="bg-dark-800 p-6 rounded-2xl border border-dark-700 shadow-sm flex flex-col items-start">
          <div className="flex items-center space-x-3 text-blue-400 mb-4 bg-blue-500/10 px-3 py-1.5 rounded-full">
            <Database size={18} />
            <span className="font-semibold text-sm">Tracking</span>
          </div>
            <p className="text-xl font-bold text-white mb-1">Ground truth</p>
            <p className="text-sm font-medium text-gray-400">Required for accuracy metrics</p>
        </div>

        <div className="bg-dark-800 p-6 rounded-2xl border border-dark-700 shadow-sm flex flex-col items-start lg:col-span-2">
          <div className="flex items-center space-x-3 text-accent-400 mb-4 bg-accent-500/10 px-3 py-1.5 rounded-full">
            <Beaker size={18} />
            <span className="font-semibold text-sm">Knowledge Base</span>
          </div>
          <div className="flex justify-between w-full">
            <div>
              <p className="text-xl font-bold text-white mb-1">{formatNumber(overview?.analyses?.length)} analyses</p>
              <p className="text-sm font-medium text-gray-400">Persisted outputs available for evaluation</p>
            </div>
          </div>
        </div>
      </div>

      {error && <div className="mb-5 p-4 rounded-lg border border-red-500/30 bg-red-500/10 text-red-300">{error}</div>}

      <form onSubmit={createDataset} className="bg-dark-800 rounded-2xl border border-dark-700 p-5 mb-5 flex flex-wrap gap-3 items-end">
        <label className="text-sm text-gray-400">Dataset name<input value={datasetName} onChange={(event) => setDatasetName(event.target.value)} className="block mt-1 bg-dark-900 border border-dark-600 rounded px-3 py-2 text-white" /></label>
        <label className="text-sm text-gray-400">Version<input value={datasetVersion} onChange={(event) => setDatasetVersion(event.target.value)} className="block mt-1 bg-dark-900 border border-dark-600 rounded px-3 py-2 text-white" /></label>
        <button disabled={working} className="bg-primary-600 hover:bg-primary-500 disabled:bg-dark-600 text-white px-4 py-2 rounded flex items-center gap-2"><Database size={16} /> Register dataset</button>
        <p className="w-full text-xs text-gray-500">This creates an annotation manifest reference. Accuracy remains unavailable until real ground-truth annotations are imported.</p>
      </form>

      <div className="bg-dark-800 rounded-2xl border border-dark-700 p-5 mb-5 flex flex-wrap gap-3 items-end">
        <label className="text-sm text-gray-400">Dataset<select value={selectedDataset} onChange={(event) => setSelectedDataset(event.target.value)} className="block mt-1 bg-dark-900 border border-dark-600 rounded px-3 py-2 text-white"><option value="">Select dataset</option>{datasets.map((dataset) => <option key={dataset.id} value={dataset.id}>{dataset.name} v{dataset.version} {dataset.ground_truth_available ? '(ground truth)' : '(no ground truth)'}</option>)}</select></label>
        <label className="text-sm text-gray-400">Completed analysis<select value={selectedVideo} onChange={(event) => setSelectedVideo(event.target.value)} className="block mt-1 bg-dark-900 border border-dark-600 rounded px-3 py-2 text-white"><option value="">Select video</option>{videos.map((video) => <option key={video.id} value={video.id}>{video.title}</option>)}</select></label>
        <button type="button" onClick={createRun} disabled={working || !selectedDataset || !selectedVideo} className="bg-blue-600 hover:bg-blue-500 disabled:bg-dark-600 text-white px-4 py-2 rounded flex items-center gap-2"><Play size={16} /> Run evaluation</button>
      </div>

      <div className="bg-dark-800 rounded-2xl border border-dark-700 overflow-hidden shadow-sm flex-grow">
        <div className="p-5 border-b border-dark-700 bg-dark-900/50">
           <h2 className="text-lg font-bold text-white flex items-center"><TrendingUp size={18} className="mr-2 text-gray-400"/> Scientific Evaluation Metrics</h2>
        </div>
        <table className="w-full text-left text-sm">
          <thead className="bg-dark-900/80 border-b border-dark-700">
            <tr>
              <th className="px-6 py-4 font-semibold text-gray-300 w-1/3">Metric Name</th>
              <th className="px-6 py-4 font-semibold text-gray-300 w-1/4">Current Value</th>
              <th className="px-6 py-4 font-semibold text-gray-300">Methodology / Notes</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-dark-700/50">
            {[
              { name: 'Precision', val: detection?.overall?.precision, note: detection?.reason || 'Computed only from real ground-truth annotations.' },
              { name: 'Recall', val: detection?.overall?.recall, note: detection?.reason || 'Computed only from real ground-truth annotations.' },
              { name: 'F1 score', val: detection?.overall?.f1, note: detection?.reason || 'Computed only from real ground-truth annotations.' },
              { name: 'Model confidence mean', val: latest?.metrics?.model_confidence?.mean, note: 'Model confidence, not prediction correctness.' },
              { name: 'Processing duration', val: performance?.processing_duration_seconds, note: 'Measured recorded-analysis pipeline time.' },
              { name: 'Effective FPS', val: performance?.effective_fps, note: 'Measured processed frames divided by processing duration.' },
            ].map((m, i) => (
              <tr key={i} className="hover:bg-dark-700/30 transition-colors">
                <td className="px-6 py-4 font-medium text-white">{m.name}</td>
                <td className="px-6 py-4 text-gray-400">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${m.val === null || m.val === undefined ? 'bg-dark-700 text-gray-400' : 'bg-primary-500/10 text-primary-400 border border-primary-500/20'}`}>
                        {m.name.includes('confidence') || m.name === 'Precision' || m.name === 'Recall' || m.name === 'F1 score' ? m.val === null || m.val === undefined ? unavailable : `${(m.val * 100).toFixed(1)}%` : m.name.includes('duration') ? formatSeconds(m.val) : formatNumber(m.val)}
                    </span>
                </td>
                <td className="px-6 py-4 text-gray-500">{m.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {latest?.metrics?.detection?.per_class && <section className="mt-5 bg-dark-800 rounded-2xl border border-dark-700 overflow-hidden"><div className="p-5 border-b border-dark-700"><h2 className="text-lg font-bold text-white">Per-instrument detection performance</h2><p className="text-xs text-gray-500 mt-1">Only classes present in the evaluation data are shown.</p></div><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="bg-dark-900/80"><tr><th className="px-5 py-3">Instrument</th><th className="px-5 py-3">TP</th><th className="px-5 py-3">FP</th><th className="px-5 py-3">FN</th><th className="px-5 py-3">Precision</th><th className="px-5 py-3">Recall</th><th className="px-5 py-3">F1</th></tr></thead><tbody>{Object.entries(latest.metrics.detection.per_class).map(([name, metric]) => <tr key={name} className="border-t border-dark-700"><td className="px-5 py-3 text-white">{name}</td><td className="px-5 py-3">{metric.tp}</td><td className="px-5 py-3">{metric.fp}</td><td className="px-5 py-3">{metric.fn}</td><td className="px-5 py-3">{metric.precision === null ? unavailable : `${(metric.precision * 100).toFixed(1)}%`}</td><td className="px-5 py-3">{metric.recall === null ? unavailable : `${(metric.recall * 100).toFixed(1)}%`}</td><td className="px-5 py-3">{metric.f1 === null ? unavailable : `${(metric.f1 * 100).toFixed(1)}%`}</td></tr>)}</tbody></table></div></section>}
      
      <div className="mt-8 bg-blue-500/10 border border-blue-500/30 p-6 rounded-2xl flex space-x-4 items-start shadow-sm">
        <div className="bg-blue-500/20 p-2 rounded-lg shrink-0">
          <AlertTriangle size={24} className="text-blue-400" />
        </div>
        <div>
            <h3 className="text-blue-400 font-bold text-lg mb-1">
            Research Integrity Declaration
            </h3>
            <p className="text-blue-100/70 text-sm leading-relaxed max-w-4xl">
            SurgiVision AI is a research and educational prototype. It is not intended for clinical diagnosis, treatment, or real-time medical decision-making. 
            No scientific evaluation metrics are fabricated. Accuracy remains unavailable until this user registers real ground-truth annotations. Phase evaluation is unavailable while PHASE_MODEL_PROVIDER=none.
            </p>
        </div>
      </div>
      <section className="mt-8 bg-dark-800 rounded-2xl border border-dark-700 overflow-hidden">
        <div className="p-5 border-b border-dark-700 flex items-center justify-between"><h2 className="text-lg font-bold text-white">Historical evaluation runs</h2><span className="text-xs text-gray-500">Runs are never overwritten</span></div>
        {runs.length ? <div className="divide-y divide-dark-700">{runs.map((run) => <div key={run.id} className="p-4 flex flex-wrap items-center gap-3 text-sm"><CheckCircle2 size={16} className="text-green-400" /><span className="text-gray-200">{run.id}</span><span className="text-gray-500">{run.model_provider || unavailable} / {run.model_version || unavailable}</span><span className="text-gray-500">{run.sample_counts?.predictions ?? 0} predictions</span><button type="button" className="ml-auto text-primary-300 flex items-center gap-1" onClick={() => downloadRun(run.id, 'json')}><Download size={14} /> JSON</button><button type="button" className="text-primary-300" onClick={() => downloadRun(run.id, 'csv')}>CSV</button></div>)}</div> : <p className="p-5 text-gray-500">No evaluation runs have been created.</p>}
      </section>
    </div>
  );
};

export default Research;
