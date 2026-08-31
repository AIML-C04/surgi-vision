import React from 'react';

const Dashboard = () => {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-6">Dashboard</h1>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        {[
          { label: 'Total Analyses', value: '0' },
          { label: 'Videos Processed', value: '0' },
          { label: 'Instruments Detected', value: '0' },
          { label: 'Avg. Processing Time', value: '0s' },
        ].map((stat, i) => (
          <div key={i} className="bg-dark-800 p-6 rounded-xl border border-dark-700">
            <h3 className="text-gray-400 text-sm font-medium">{stat.label}</h3>
            <p className="text-3xl font-bold mt-2">{stat.value}</p>
          </div>
        ))}
      </div>
    </div>
  );
};

export default Dashboard;
