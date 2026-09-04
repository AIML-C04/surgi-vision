import React, { useState, useEffect, useContext, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Activity, Clock, FileText, AlertTriangle, Printer, ChevronLeft, Target, Eye, BarChart2 } from 'lucide-react';
import { AuthContext } from '../context/AuthContext';

const Report = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { token } = useContext(AuthContext);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let isMounted = true;
    const fetchReport = async () => {
      try {
        const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
        const res = await axios.get(`${API_URL}/api/v1/videos/${id}/report`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (isMounted) {
          if (!res.data.available) {
            setError(res.data.message || "Report is unavailable for this video.");
          } else {
            setReport(res.data);
          }
          setLoading(false);
        }
      } catch (err) {
        if (isMounted) {
          setError(err.response?.data?.detail || "Failed to load surgical intelligence report.");
          setLoading(false);
        }
      }
    };
    fetchReport();
    return () => { isMounted = false; };
  }, [id, token]);

  const handlePrint = () => {
    window.print();
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = (seconds % 60).toFixed(1);
    return `${mins}:${secs.padStart(4, '0')}`;
  };

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center bg-dark-900 text-white flex-col space-y-4">
         <Activity className="animate-spin text-primary-500 w-10 h-10" />
         <p>Aggregating Surgical Intelligence...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full items-center justify-center bg-dark-900 p-6">
        <div className="bg-dark-800 p-8 rounded-xl border border-red-500/30 text-center max-w-md">
           <AlertTriangle className="text-red-500 w-12 h-12 mx-auto mb-4" />
           <h2 className="text-xl font-bold text-white mb-2">Report Unavailable</h2>
           <p className="text-gray-400 mb-6">{error}</p>
           <button onClick={() => navigate(-1)} className="bg-dark-700 hover:bg-dark-600 text-white px-4 py-2 rounded-lg">Go Back</button>
        </div>
      </div>
    );
  }

  if (!report) return null;

  return (
    <div className="bg-dark-900 min-h-full text-gray-200 overflow-y-auto">
      {/* Top action bar (Hidden on print) */}
      <div className="sticky top-0 bg-dark-900/90 backdrop-blur-sm border-b border-dark-700 p-4 flex justify-between items-center z-10 print:hidden">
        <button onClick={() => navigate(`/analysis/${id}`)} className="flex items-center text-gray-400 hover:text-white transition-colors">
           <ChevronLeft size={20} className="mr-1" /> Back to Analysis
        </button>
        <button onClick={handlePrint} className="flex items-center bg-primary-600 hover:bg-primary-500 text-white px-4 py-2 rounded-lg font-semibold transition-colors">
           <Printer size={16} className="mr-2" /> Export to PDF / Print
        </button>
      </div>

      {/* Printable Report Container */}
      <div className="max-w-4xl mx-auto p-8 print:p-0 print:bg-white print:text-black space-y-8">
        
        {/* Header */}
        <div className="border-b-2 border-dark-600 print:border-gray-300 pb-6">
           <div className="flex items-center text-primary-500 print:text-black font-bold text-xl mb-4">
              <Activity className="mr-2" /> SurgiVision AI
           </div>
           <h1 className="text-3xl font-bold text-white print:text-black mb-2">Surgical Intelligence Report</h1>
           <p className="text-xl text-gray-300 print:text-gray-700 mb-4">{report.procedure_overview.video_title}</p>
           
           <div className="flex flex-wrap gap-4 text-sm text-gray-400 print:text-gray-600">
              <span className="flex items-center"><Clock size={14} className="mr-1" /> {formatTime(report.procedure_overview.duration)}</span>
              <span>•</span>
              <span>Analysis Version: v{report.procedure_overview.analysis_version}</span>
              <span>•</span>
              <span>Model: {report.procedure_overview.model_version}</span>
              <span>•</span>
              <span>Processed: {new Date(report.procedure_overview.processed_at).toLocaleString()}</span>
           </div>
        </div>

        {/* Executive Overview */}
        <section>
          <h2 className="text-xl font-bold text-white print:text-black mb-4 border-b border-dark-700 print:border-gray-200 pb-2">1. Procedure Overview</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-dark-800 print:bg-gray-50 p-4 rounded-lg border border-dark-700 print:border-gray-200">
               <div className="text-gray-400 print:text-gray-500 text-xs uppercase tracking-wider mb-1">Detections</div>
               <div className="text-2xl font-semibold text-white print:text-black">{report.procedure_overview.total_detections.toLocaleString()}</div>
            </div>
            <div className="bg-dark-800 print:bg-gray-50 p-4 rounded-lg border border-dark-700 print:border-gray-200">
               <div className="text-gray-400 print:text-gray-500 text-xs uppercase tracking-wider mb-1">Total Tracks</div>
               <div className="text-2xl font-semibold text-white print:text-black">{report.procedure_overview.total_tracks.toLocaleString()}</div>
            </div>
            <div className="bg-dark-800 print:bg-gray-50 p-4 rounded-lg border border-dark-700 print:border-gray-200">
               <div className="text-gray-400 print:text-gray-500 text-xs uppercase tracking-wider mb-1">Persisted Events</div>
               <div className="text-2xl font-semibold text-white print:text-black">{report.procedure_overview.total_events.toLocaleString()}</div>
            </div>
            <div className="bg-dark-800 print:bg-gray-50 p-4 rounded-lg border border-dark-700 print:border-gray-200">
               <div className="text-gray-400 print:text-gray-500 text-xs uppercase tracking-wider mb-1">Instrument Classes</div>
               <div className="text-2xl font-semibold text-white print:text-black">{report.procedure_overview.instrument_class_count}</div>
            </div>
          </div>
          
          {report.ai_summary && (
            <div className="bg-primary-900/20 print:bg-blue-50 border border-primary-800 print:border-blue-200 p-5 rounded-lg mb-4">
              <h3 className="text-sm font-semibold text-primary-400 print:text-blue-800 mb-2 flex items-center">
                 <FileText size={16} className="mr-2" /> AI-Generated Executive Summary
              </h3>
              <p className="text-gray-300 print:text-gray-800 text-sm leading-relaxed">
                 {report.ai_summary}
              </p>
            </div>
          )}
        </section>

        {/* Instrument Intelligence */}
        <section>
          <h2 className="text-xl font-bold text-white print:text-black mb-4 border-b border-dark-700 print:border-gray-200 pb-2 flex items-center">
            <Target size={20} className="mr-2 text-primary-500 print:text-black" /> 2. Instrument Intelligence
          </h2>
          {report.instrument_intelligence.length > 0 ? (
            <div className="overflow-x-auto rounded-lg border border-dark-700 print:border-gray-200">
              <table className="w-full text-left text-sm">
                <thead className="bg-dark-800 print:bg-gray-100 text-gray-300 print:text-gray-700">
                  <tr>
                    <th className="px-4 py-3 font-semibold">Instrument</th>
                    <th className="px-4 py-3 font-semibold">Detections</th>
                    <th className="px-4 py-3 font-semibold">Tracks</th>
                    <th className="px-4 py-3 font-semibold">Visible Time</th>
                    <th className="px-4 py-3 font-semibold">Avg. Confidence</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-dark-700 print:divide-gray-200">
                  {report.instrument_intelligence.map((inst, i) => (
                    <tr key={i} className="bg-dark-900 print:bg-white text-gray-300 print:text-gray-800">
                      <td className="px-4 py-3 font-medium text-white print:text-black">{inst.class_name}</td>
                      <td className="px-4 py-3">{inst.detection_count.toLocaleString()}</td>
                      <td className="px-4 py-3">{inst.track_count}</td>
                      <td className="px-4 py-3">{formatTime(inst.visible_duration)}</td>
                      <td className="px-4 py-3">{inst.average_confidence ? (inst.average_confidence * 100).toFixed(1) + '%' : 'N/A'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-gray-500 italic">No instrument intelligence is available.</p>
          )}
        </section>

        {/* Event Summary */}
        <section>
          <h2 className="text-xl font-bold text-white print:text-black mb-4 border-b border-dark-700 print:border-gray-200 pb-2 flex items-center">
            <BarChart2 size={20} className="mr-2 text-primary-500 print:text-black" /> 3. Surgical Event Summary
          </h2>
          {Object.keys(report.event_summary).length > 0 ? (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
               {Object.entries(report.event_summary).map(([eventType, count], i) => (
                  <div key={i} className="bg-dark-800 print:bg-gray-50 p-4 rounded-lg border border-dark-700 print:border-gray-200 flex justify-between items-center">
                     <span className="text-sm font-medium text-gray-300 print:text-gray-700">{eventType.replace("INSTRUMENT_", "").replace("_", " ")}</span>
                     <span className="text-lg font-bold text-white print:text-black bg-dark-900 print:bg-white px-2 py-0.5 rounded border border-dark-600 print:border-gray-300">{count}</span>
                  </div>
               ))}
            </div>
          ) : (
            <p className="text-gray-500 italic">No persisted surgical events are available.</p>
          )}
        </section>

        <section>
          <h2 className="text-xl font-bold text-white print:text-black mb-4 border-b border-dark-700 print:border-gray-200 pb-2">4. Phase Recognition</h2>
          {report.phase_recognition?.available && report.phase_recognition.phases?.length ? <div className="overflow-x-auto rounded-lg border border-dark-700 print:border-gray-200"><table className="w-full text-left text-sm"><thead className="bg-dark-800 print:bg-gray-100"><tr><th className="px-4 py-3">Phase</th><th className="px-4 py-3">Start</th><th className="px-4 py-3">End</th><th className="px-4 py-3">Duration</th><th className="px-4 py-3">Confidence</th></tr></thead><tbody>{report.phase_recognition.phases.map((phase) => <tr key={phase.id} className="border-t border-dark-700 print:border-gray-200"><td className="px-4 py-3">{phase.phase_name}</td><td className="px-4 py-3">{formatTime(phase.start_time)}</td><td className="px-4 py-3">{formatTime(phase.end_time)}</td><td className="px-4 py-3">{formatTime(phase.duration)}</td><td className="px-4 py-3">{phase.confidence === null ? 'Not available' : `${(phase.confidence * 100).toFixed(1)}%`}</td></tr>)}</tbody></table></div> : <div className="border border-dashed border-dark-600 p-5 text-gray-500">Phase Recognition<br />Unavailable<br /><span className="text-sm">No validated phase recognition model is configured for this analysis.</span></div>}
        </section>

        {/* Key Moments */}
        <section>
          <h2 className="text-xl font-bold text-white print:text-black mb-4 border-b border-dark-700 print:border-gray-200 pb-2 flex items-center">
            <Eye size={20} className="mr-2 text-primary-500 print:text-black" /> 4. Key Moments & Evidence
          </h2>
          {report.key_moments.length > 0 ? (
            <div className="space-y-3">
              {report.key_moments.map((moment, i) => (
                <div key={i} className="flex items-start bg-dark-800 print:bg-gray-50 p-3 rounded-lg border border-dark-700 print:border-gray-200">
                  <div className="font-mono text-sm text-primary-400 print:text-blue-600 font-semibold w-24 flex-shrink-0 pt-0.5">
                    {formatTime(moment.timestamp)}
                  </div>
                  <div className="flex-1">
                    <p className="text-white print:text-black font-medium">{moment.label}</p>
                    <p className="text-xs text-gray-500 mt-1 print:text-gray-600">
                      Evidence ID: {moment.id}
                      {moment.confidence && ` • Conf: ${(moment.confidence * 100).toFixed(1)}%`}
                    </p>
                  </div>
                  <div className="print:hidden">
                     <button 
                       onClick={() => navigate(`/analysis/${id}?time=${moment.timestamp}`)}
                       className="text-xs bg-dark-700 hover:bg-dark-600 text-white px-3 py-1.5 rounded transition-colors"
                     >
                       Watch
                     </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 italic">No key moments available for this video.</p>
          )}
        </section>

        {/* Limitations Footer */}
        <div className="mt-12 pt-6 border-t border-dark-700 print:border-gray-300 text-xs text-gray-500 print:text-gray-500 space-y-2">
           <p className="font-bold uppercase text-gray-400 print:text-gray-600">Important Limitations & Disclaimer</p>
           <ul className="list-disc pl-4 space-y-1">
              <li>This report reflects model-detected video intelligence and computer vision events.</li>
              <li>It does not establish clinical diagnosis or medical outcomes.</li>
              <li>Instrument co-occurrence does not establish physical or medical interaction.</li>
              <li>Clinical interpretation is outside current system scope.</li>
           </ul>
        </div>
      </div>
    </div>
  );
};

export default Report;
