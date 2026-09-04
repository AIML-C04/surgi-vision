import React from 'react';
import { Beaker, TrendingUp, Cpu, Database, AlertTriangle } from 'lucide-react';

const Research = () => {
  return (
    <div className="p-8 max-w-6xl mx-auto h-full flex flex-col">
      <div className="flex justify-between items-end mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Research & Evaluation</h1>
          <p className="text-gray-400 mt-1 text-lg">Model performance metrics and dataset evaluation.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-dark-800 p-6 rounded-2xl border border-dark-700 shadow-sm flex flex-col items-start">
          <div className="flex items-center space-x-3 text-primary-400 mb-4 bg-primary-500/10 px-3 py-1.5 rounded-full">
            <Cpu size={18} />
            <span className="font-semibold text-sm">Active Model</span>
          </div>
          <p className="text-xl font-bold text-white mb-1">YOLOv8s Cholec80</p>
          <p className="text-sm font-medium text-green-500 flex items-center">
            <div className="w-1.5 h-1.5 rounded-full bg-green-500 mr-1.5 animate-pulse"></div>
            REAL MODEL MOUNTED
          </p>
        </div>
        
        <div className="bg-dark-800 p-6 rounded-2xl border border-dark-700 shadow-sm flex flex-col items-start">
          <div className="flex items-center space-x-3 text-blue-400 mb-4 bg-blue-500/10 px-3 py-1.5 rounded-full">
            <Database size={18} />
            <span className="font-semibold text-sm">Tracking</span>
          </div>
          <p className="text-xl font-bold text-white mb-1">BoT-SORT</p>
          <p className="text-sm font-medium text-gray-400">Kinematic Tracking</p>
        </div>

        <div className="bg-dark-800 p-6 rounded-2xl border border-dark-700 shadow-sm flex flex-col items-start lg:col-span-2">
          <div className="flex items-center space-x-3 text-accent-400 mb-4 bg-accent-500/10 px-3 py-1.5 rounded-full">
            <Beaker size={18} />
            <span className="font-semibold text-sm">Knowledge Base</span>
          </div>
          <div className="flex justify-between w-full">
            <div>
              <p className="text-xl font-bold text-white mb-1">pgvector RAG Pipeline</p>
              <p className="text-sm font-medium text-gray-400">all-MiniLM-L6-v2 Embeddings</p>
            </div>
          </div>
        </div>
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
              { name: 'mAP@50 (Detection)', val: 'Evaluation Pending', note: 'Requires formal evaluation set run' },
              { name: 'mAP@50-95 (Detection)', val: 'Evaluation Pending', note: 'Requires formal evaluation set run' },
              { name: 'MOTA (Tracking)', val: 'Evaluation Pending', note: 'Requires ground truth bounding box trajectories' },
              { name: 'IDF1 (Tracking)', val: 'Evaluation Pending', note: 'ID assignment accuracy metrics' },
              { name: 'Inference Latency', val: '~45ms / frame', note: 'Local CPU measurement (varies by hardware)' },
              { name: 'RAG Hit Rate', val: 'Evaluation Pending', note: 'Requires Q&A dataset formulation' },
            ].map((m, i) => (
              <tr key={i} className="hover:bg-dark-700/30 transition-colors">
                <td className="px-6 py-4 font-medium text-white">{m.name}</td>
                <td className="px-6 py-4 text-gray-400">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${m.val === 'Evaluation Pending' ? 'bg-dark-700 text-gray-400' : 'bg-primary-500/10 text-primary-400 border border-primary-500/20'}`}>
                        {m.val}
                    </span>
                </td>
                <td className="px-6 py-4 text-gray-500">{m.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      
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
            No scientific evaluation metrics are fabricated; all metrics will remain "Evaluation Pending" until rigorous experimental evaluation is conducted on independent datasets.
            </p>
        </div>
      </div>
    </div>
  );
};

export default Research;
