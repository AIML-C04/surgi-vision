import React from 'react';
import { Beaker, TrendingUp, Cpu, Database } from 'lucide-react';

const Research = () => {
  return (
    <div className="p-8">
      <div className="flex justify-between items-end mb-8">
        <div>
          <h1 className="text-2xl font-bold">Research & Evaluation</h1>
          <p className="text-gray-400 mt-1">Model performance metrics and dataset evaluation.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-dark-800 p-6 rounded-xl border border-dark-700">
          <div className="flex items-center space-x-3 text-primary-400 mb-2">
            <Cpu size={20} />
            <span className="font-medium">Active Model</span>
          </div>
          <p className="text-xl font-bold">MockInferenceProvider</p>
          <p className="text-sm text-yellow-500 mt-2">DEMO MODE</p>
        </div>
        
        <div className="bg-dark-800 p-6 rounded-xl border border-dark-700">
          <div className="flex items-center space-x-3 text-primary-400 mb-2">
            <Database size={20} />
            <span className="font-medium">Dataset</span>
          </div>
          <p className="text-xl font-bold">Not Configured</p>
          <p className="text-sm text-gray-400 mt-2">Awaiting Cholec80</p>
        </div>
      </div>

      <h2 className="text-xl font-bold mb-4">Model Performance Metrics</h2>
      <div className="bg-dark-800 rounded-xl border border-dark-700 overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead className="bg-dark-900 border-b border-dark-700">
            <tr>
              <th className="px-6 py-4 font-medium text-gray-400">Metric</th>
              <th className="px-6 py-4 font-medium text-gray-400">Value</th>
              <th className="px-6 py-4 font-medium text-gray-400">Notes</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-dark-700">
            {[
              { name: 'Precision', val: 'Evaluation Pending', note: 'Requires real evaluation run' },
              { name: 'Recall', val: 'Evaluation Pending', note: 'Requires real evaluation run' },
              { name: 'mAP@50', val: 'Evaluation Pending', note: 'Requires real evaluation run' },
              { name: 'mAP@50-95', val: 'Evaluation Pending', note: 'Requires real evaluation run' },
              { name: 'FPS (Inference)', val: 'Evaluation Pending', note: 'Hardware dependent' },
              { name: 'Latency', val: 'Evaluation Pending', note: 'Hardware dependent' },
              { name: 'Tracking Accuracy (MOTA)', val: 'Evaluation Pending', note: 'Requires ground truth tracks' }
            ].map((m, i) => (
              <tr key={i} className="hover:bg-dark-700/50">
                <td className="px-6 py-4 font-medium">{m.name}</td>
                <td className="px-6 py-4 text-gray-400 italic">{m.val}</td>
                <td className="px-6 py-4 text-gray-500">{m.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      
      <div className="mt-8 bg-blue-500/10 border border-blue-500/50 p-6 rounded-xl">
        <h3 className="text-blue-400 font-medium flex items-center space-x-2 mb-2">
          <Beaker size={20} />
          <span>Research Integrity Notice</span>
        </h3>
        <p className="text-gray-300 text-sm">
          SurgiVision AI is a research and educational prototype. It is not intended for clinical diagnosis, treatment, or real-time medical decision-making. No scientific evaluation metrics are fabricated; all metrics will remain "Evaluation Pending" until rigorous experimental evaluation is conducted with the integrated model.
        </p>
      </div>
    </div>
  );
};

export default Research;
