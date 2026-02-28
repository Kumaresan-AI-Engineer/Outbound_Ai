import { useState } from 'react';
import { Cpu, Key, Check, Shield } from 'lucide-react';

export default function SettingsPanel() {
  const [provider, setProvider] = useState('groq');

  return (
    <div className="py-8 max-w-2xl anim-enter">
      <div className="mb-8">
        <h2 className="text-[26px] font-extrabold text-gray-900">Settings</h2>
        <p className="text-gray-400 text-[14px] mt-1">Configure your call assistant</p>
      </div>

      <div className="space-y-4">
        <div className="card hover-glow p-6 anim-enter delay-1">
          <div className="flex items-center gap-2.5 mb-5">
            <div className="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center">
              <Cpu className="w-4 h-4 text-blue-600" />
            </div>
            <h3 className="text-[16px] font-bold text-gray-900">AI Provider</h3>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {[
              { id: 'groq', name: 'Groq', desc: 'Ultra-fast inference', sub: 'Llama 3.1 70B' },
              { id: 'openai', name: 'OpenAI', desc: 'High quality output', sub: 'GPT-4o' },
            ].map((p) => (
              <button
                key={p.id}
                onClick={() => setProvider(p.id)}
                className={`relative p-4 rounded-xl border text-left transition-all ${
                  provider === p.id
                    ? 'bg-blue-50 border-blue-200 shadow-sm shadow-blue-100'
                    : 'bg-white border-gray-200 hover:border-gray-300'
                }`}
              >
                {provider === p.id && (
                  <div className="absolute top-3 right-3 w-5 h-5 rounded-full bg-blue-600 flex items-center justify-center">
                    <Check className="w-3 h-3 text-white" />
                  </div>
                )}
                <p className={`text-[14px] font-bold ${provider === p.id ? 'text-blue-700' : 'text-gray-800'}`}>{p.name}</p>
                <p className="text-[13px] text-gray-400 mt-0.5">{p.desc}</p>
                <p className={`text-[12px] font-mono mt-1 ${provider === p.id ? 'text-blue-400' : 'text-gray-300'}`}>{p.sub}</p>
              </button>
            ))}
          </div>
        </div>

        <div className="card hover-glow p-6 anim-enter delay-2">
          <div className="flex items-center gap-2.5 mb-4">
            <div className="w-8 h-8 rounded-lg bg-amber-50 flex items-center justify-center">
              <Key className="w-4 h-4 text-amber-500" />
            </div>
            <h3 className="text-[16px] font-bold text-gray-900">API Keys</h3>
          </div>
          <p className="text-[14px] text-gray-500 leading-relaxed">
            Keys are configured in the backend <code className="text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded text-[13px] font-mono">.env</code> file.
            Update Twilio, OpenAI, and Groq keys there.
          </p>
        </div>

        <div className="card hover-glow p-6 anim-enter delay-3">
          <div className="flex items-center gap-2.5 mb-4">
            <div className="w-8 h-8 rounded-lg bg-emerald-50 flex items-center justify-center">
              <Shield className="w-4 h-4 text-emerald-500" />
            </div>
            <h3 className="text-[16px] font-bold text-gray-900">Transcription</h3>
          </div>
          <p className="text-[14px] text-gray-500 leading-relaxed">
            Using <span className="font-semibold text-gray-700">Groq Whisper Large V3</span> for real-time speech-to-text. Audio is processed via Twilio Media Streams.
          </p>
        </div>
      </div>
    </div>
  );
}
