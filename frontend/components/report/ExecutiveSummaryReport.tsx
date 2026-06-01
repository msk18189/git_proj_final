import React from 'react';
import { Database } from 'lucide-react';

export function ExecutiveSummaryReport({ status }: { status: any }) {
  return (
    <header className="mb-10 pb-6 border-b border-slate-200 avoid-break">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 mb-2">
            Engineering Intelligence Report
          </h1>
          <div className="flex items-center gap-2 text-slate-500 font-medium">
            <Database className="w-4 h-4" />
            <span>{status?.owner}/{status?.name}</span>
          </div>
        </div>
        <div className="text-right">
          <div className="text-sm font-medium text-slate-400 mb-1">Generated On</div>
          <div className="text-sm text-slate-600 font-mono">
            {new Date().toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' })}
          </div>
        </div>
      </div>
      <p className="mt-4 text-sm text-slate-500 uppercase tracking-widest font-semibold">
        Cycle Time · Review Turnaround · Throughput · Bottlenecks
      </p>
    </header>
  );
}
