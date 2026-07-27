import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X, FileText, Cpu, Loader2, AlertCircle, RotateCw } from 'lucide-react';
import { domainStyle } from '../utils/domainColors';
import ProjectDetailFields from './ProjectDetailFields';

const formatSize = (bytes) => (bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`);

// Opened from a Knowledge Map node — fetches the full project record (the
// graph itself only carries an abbreviated payload to stay light at scale)
// and renders it with the same fields as the Available Projects accordion.
export default function ProjectDetailModal({ projectId, onClose }) {
  const [project, setProject] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch(`/projects/${projectId}`)
      .then((res) => { if (!res.ok) throw new Error(); return res.json(); })
      .then((data) => { if (!cancelled) setProject(data); })
      .catch(() => { if (!cancelled) setError(true); });
    return () => { cancelled = true; };
  }, [projectId]);

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const meta = project?.metadata || {};
  const style = domainStyle(meta.domain);

  return createPortal(
    <div className="fixed inset-0 bg-gray-900/30 backdrop-blur-sm z-50 flex items-center justify-center p-6" onClick={onClose}>
      <div
        className="bg-white rounded-2xl w-full max-w-[720px] max-h-[85vh] flex flex-col shadow-2xl border border-gray-200 overflow-hidden anim-modal"
        style={{ borderTop: `3px solid ${style.hex}` }}
        onClick={(e) => e.stopPropagation()}
      >
        {!project && !error ? (
          <div className="flex items-center justify-center py-24">
            <Loader2 className="w-5 h-5 animate-spin text-blue-500 mr-3" />
            <span className="text-[14px] text-gray-400 font-medium">Loading project details...</span>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-24 px-8">
            <AlertCircle className="w-8 h-8 text-red-400 mb-3" />
            <p className="text-[14px] text-gray-500 text-center">Couldn't load this project. It may have been deleted.</p>
            <button onClick={onClose} className="mt-4 px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-lg text-[13px] font-semibold transition-all">
              Close
            </button>
          </div>
        ) : (
          <>
            {/* Header */}
            <div className="flex items-start gap-4 px-7 pt-7 pb-5 border-b border-gray-100 shrink-0">
              <div
                className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0"
                style={{ backgroundColor: `${style.hex}14` }}
              >
                <FileText className="w-5 h-5" style={{ color: style.hex }} />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="text-[19px] font-bold text-gray-900 leading-tight pr-8">{project.name}</h3>
                <div className="flex items-center gap-2 flex-wrap mt-2">
                  {meta.domain && (
                    <span className={`px-2.5 py-0.5 rounded-md text-[12px] font-semibold border ${style.chip}`}>
                      {meta.domain}
                    </span>
                  )}
                  {meta.ai_ml_components?.length > 0 && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-semibold bg-violet-50 text-violet-600">
                      <Cpu className="w-3 h-3" />AI/ML
                    </span>
                  )}
                  {project.processing_status === 'failed' && (
                    <span className="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-red-50 text-red-600">Failed</span>
                  )}
                </div>
              </div>
              <button onClick={onClose} className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-all shrink-0">
                <X className="w-4.5 h-4.5" />
              </button>
            </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto px-7 py-5">
              {project.processing_status === 'failed' ? (
                <div className="flex items-center gap-2.5 p-4 bg-red-50 border border-red-100 rounded-xl">
                  <RotateCw className="w-4 h-4 text-red-400 shrink-0" />
                  <p className="text-[13px] text-red-600">{project.processing_error || 'Processing failed for this document.'}</p>
                </div>
              ) : (
                <ProjectDetailFields meta={meta} />
              )}
            </div>

            {/* Footer */}
            <div className="px-7 py-4 border-t border-gray-100 shrink-0">
              <p className="text-[12px] text-gray-400">
                {project.file_name} · {formatSize(project.file_size)} · uploaded {new Date(project.created_at).toLocaleDateString()}
              </p>
            </div>
          </>
        )}
      </div>
    </div>,
    document.body
  );
}
