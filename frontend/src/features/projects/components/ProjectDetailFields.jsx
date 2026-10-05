import { Cpu, Layers } from 'lucide-react';

// Shared with ProjectsPanel's Available Projects accordion and the Knowledge
// Map's project modal — one source of truth for how project metadata renders.
export default function ProjectDetailFields({ meta }) {
  const stack = meta.tech_stack || {};
  const stackGroups = [
    ['Frontend', stack.frontend], ['Backend', stack.backend],
    ['Database', stack.database], ['Cloud / DevOps', stack.cloud_devops], ['Other', stack.other],
  ].filter(([, v]) => v?.length > 0);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-x-8 gap-y-5">
      {meta.summary && (
        <div className="lg:col-span-2">
          <p className="text-[11px] font-bold uppercase tracking-wider text-gray-400 mb-1.5">Summary</p>
          <p className="text-[14px] text-gray-600 leading-relaxed">{meta.summary}</p>
        </div>
      )}
      {meta.business_problem && (
        <div>
          <p className="text-[11px] font-bold uppercase tracking-wider text-gray-400 mb-1.5">Business Problem</p>
          <p className="text-[14px] text-gray-600 leading-relaxed">{meta.business_problem}</p>
        </div>
      )}
      {meta.solution_provided && (
        <div>
          <p className="text-[11px] font-bold uppercase tracking-wider text-gray-400 mb-1.5">Solution Provided</p>
          <p className="text-[14px] text-gray-600 leading-relaxed">{meta.solution_provided}</p>
        </div>
      )}
      {meta.key_features?.length > 0 && (
        <div>
          <p className="text-[11px] font-bold uppercase tracking-wider text-gray-400 mb-1.5">Key Features</p>
          <ul className="space-y-1">
            {meta.key_features.map((f, i) => (
              <li key={i} className="text-[14px] text-gray-600 flex items-start gap-2">
                <span className="w-1 h-1 rounded-full bg-blue-400 mt-2 shrink-0" />{f}
              </li>
            ))}
          </ul>
        </div>
      )}
      {meta.ai_ml_components?.length > 0 && (
        <div>
          <p className="text-[11px] font-bold uppercase tracking-wider text-gray-400 mb-1.5 flex items-center gap-1.5">
            <Cpu className="w-3 h-3 text-violet-500" />AI / ML Components
          </p>
          <ul className="space-y-1">
            {meta.ai_ml_components.map((c, i) => (
              <li key={i} className="text-[14px] text-gray-600 flex items-start gap-2">
                <span className="w-1 h-1 rounded-full bg-violet-400 mt-2 shrink-0" />{c}
              </li>
            ))}
          </ul>
        </div>
      )}
      {stackGroups.length > 0 && (
        <div className="lg:col-span-2">
          <p className="text-[11px] font-bold uppercase tracking-wider text-gray-400 mb-2 flex items-center gap-1.5">
            <Layers className="w-3 h-3" />Tech Stack
          </p>
          <div className="flex flex-wrap gap-x-6 gap-y-2">
            {stackGroups.map(([label, items]) => (
              <div key={label} className="flex items-center gap-2 flex-wrap">
                <span className="text-[12px] font-semibold text-gray-400">{label}:</span>
                {items.map((t, i) => (
                  <span key={i} className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded-md text-[12px] font-medium">{t}</span>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
      {meta.technologies?.length > 0 && stackGroups.length === 0 && (
        <div className="lg:col-span-2">
          <p className="text-[11px] font-bold uppercase tracking-wider text-gray-400 mb-2">Technologies</p>
          <div className="flex flex-wrap gap-1.5">
            {meta.technologies.map((t, i) => (
              <span key={i} className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded-md text-[12px] font-medium">{t}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
