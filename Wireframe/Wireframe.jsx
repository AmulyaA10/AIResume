import React, { useState } from 'react';
import { 
  Layout, 
  User, 
  Briefcase, 
  Settings, 
  Search, 
  FileText, 
  Linkedin, 
  Mail, 
  ShieldCheck, 
  BarChart3, 
  AlertCircle, 
  CheckCircle2, 
  ArrowRight,
  Download,
  Filter,
  LogOut,
  Cpu,
  Plus,
  History,
  Database,
  X,
  PieChart,
  FileDown
} from 'lucide-react';

// --- Mock Data ---
const MOCK_CANDIDATES = [
  { id: 1, name: "Alex Chen", role: "Senior Frontend Engineer", score: 94, category: "Shortlist", match: "95%", risk: "Low", skills: ["React", "TypeScript", "Node.js"] },
  { id: 2, name: "Sarah Miller", role: "Fullstack Developer", score: 82, category: "Review", match: "82%", risk: "Medium", skills: ["React", "Python", "AWS"] },
  { id: 3, name: "Jordan Smith", role: "Frontend Developer", score: 45, category: "Reject", match: "40%", risk: "High", skills: ["HTML/CSS", "Basic JS"] },
];

const PROVIDERS = ["OpenAI (GPT-4o)", "Anthropic (Claude 3.5 Sonnet)", "Gemini 1.5 Pro", "Groq (Llama 3)", "OpenRouter"];

// --- Shared Components ---

const Sidebar = ({ persona, activeTab, setActiveTab, onLogout }) => {
  const menus = {
    jobseeker: [
      { id: 'dashboard', label: 'My Applications', icon: Layout },
      { id: 'refine', label: 'Resume Refiner', icon: FileText },
      { id: 'settings', label: 'Profile Settings', icon: User },
    ],
    recruiter: [
      { id: 'config', label: 'LLM Settings', icon: Settings },
      { id: 'jd', label: 'Job Definitions', icon: Briefcase },
      { id: 'candidates', label: 'Candidate Corpus', icon: Search },
    ],
    manager: [
      { id: 'rankings', label: 'Active Rankings', icon: BarChart3 },
      { id: 'analytics', label: 'Skill Analysis', icon: Cpu },
      { id: 'reports', label: 'Final Reports', icon: ShieldCheck },
    ]
  };

  return (
    <div className="w-64 bg-slate-900 text-slate-300 flex flex-col h-full border-r border-slate-800">
      <div className="p-6">
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <ShieldCheck className="text-blue-500" /> RESUME.AI
        </h1>
      </div>
      
      <nav className="flex-1 px-4 space-y-2">
        <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-4 px-2">
          {persona === 'jobseeker' ? 'Candidate Portal' : 'Enterprise Portal'}
        </div>
        {menus[persona].map((item) => (
          <button
            key={item.id}
            onClick={() => setActiveTab(item.id)}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all ${
              activeTab === item.id ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/20' : 'hover:bg-slate-800'
            }`}
          >
            <item.icon size={18} />
            <span className="text-sm font-medium">{item.label}</span>
          </button>
        ))}
      </nav>

      <div className="p-4 border-t border-slate-800">
        <button 
          onClick={onLogout}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-red-900/20 text-red-400 transition-colors"
        >
          <LogOut size={18} />
          <span className="text-sm font-semibold">Sign Out</span>
        </button>
      </div>
    </div>
  );
};

// --- JobSeeker Specific Views ---

const JobSeekerDashboard = () => (
  <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
    <div className="bg-gradient-to-r from-blue-600 to-indigo-700 rounded-2xl p-8 text-white shadow-xl relative overflow-hidden">
      <div className="relative z-10">
        <h2 className="text-3xl font-bold mb-2">Elevate Your Profile.</h2>
        <p className="opacity-90 max-w-md">Our AI engine has analyzed your profile. You have a 92% match for Senior roles.</p>
        <div className="mt-6 flex gap-3">
          <button className="bg-white text-blue-700 px-6 py-2 rounded-lg font-semibold flex items-center gap-2 hover:bg-slate-100 transition-all shadow-lg">
            <Linkedin size={18} /> Sync LinkedIn
          </button>
        </div>
      </div>
      <div className="absolute right-[-20px] top-[-20px] opacity-10">
        <User size={240} />
      </div>
    </div>

    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
        <h3 className="text-lg font-bold mb-4 flex items-center gap-2"><History size={20} className="text-blue-600" /> Recent Applications</h3>
        <div className="space-y-4">
          <div className="flex justify-between items-center p-3 hover:bg-slate-50 rounded-lg border border-transparent hover:border-slate-200 transition-all">
            <div>
              <p className="text-sm font-bold">Google - Frontend</p>
              <p className="text-xs text-slate-500">Match Score: 94%</p>
            </div>
            <span className="bg-green-100 text-green-700 text-[10px] px-2 py-1 rounded-full font-bold uppercase">Shortlisted</span>
          </div>
          <div className="flex justify-between items-center p-3 hover:bg-slate-50 rounded-lg border border-transparent hover:border-slate-200 transition-all">
            <div>
              <p className="text-sm font-bold">Stripe - Product Eng</p>
              <p className="text-xs text-slate-500">Match Score: 88%</p>
            </div>
            <span className="bg-blue-100 text-blue-700 text-[10px] px-2 py-1 rounded-full font-bold uppercase">Under Review</span>
          </div>
        </div>
      </div>
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
        <h3 className="text-lg font-bold mb-4 flex items-center gap-2"><AlertCircle size={20} className="text-amber-500" /> Optimization Alerts</h3>
        <div className="p-4 bg-amber-50 rounded-lg border-l-4 border-amber-400 text-sm text-amber-800">
          "Consider adding <strong>GraphQL</strong> to your skills list. It appears in 40% of the roles you're targeting."
        </div>
      </div>
    </div>
  </div>
);

const ResumeRefiner = () => (
  <div className="h-[calc(100vh-160px)] flex gap-6 animate-in fade-in duration-500">
    <div className="flex-1 bg-white rounded-xl border border-slate-200 shadow-sm p-6 flex flex-col">
      <div className="flex justify-between items-center mb-4 pb-4 border-b">
        <h3 className="font-bold flex items-center gap-2"><FileText className="text-blue-600" /> Smart Editor</h3>
        <div className="flex gap-2">
          <button className="text-xs bg-slate-100 px-3 py-1.5 rounded font-bold hover:bg-slate-200">Import</button>
          <button className="text-xs bg-blue-600 text-white px-3 py-1.5 rounded font-bold hover:bg-blue-700">Save Draft</button>
        </div>
      </div>
      <textarea 
        className="flex-1 w-full bg-slate-50/50 p-4 text-sm font-mono outline-none resize-none rounded-lg"
        placeholder="Paste your resume content here for real-time AI optimization..."
        defaultValue="Experienced Software Engineer with a focus on React and Node.js..."
      />
    </div>
    <div className="w-80 space-y-4 overflow-y-auto pr-2">
      <div className="bg-blue-900 text-white p-4 rounded-xl shadow-lg">
        <h4 className="text-xs font-bold uppercase opacity-60 mb-2">Live AI Score</h4>
        <div className="text-4xl font-black">74<span className="text-lg opacity-40">/100</span></div>
        <p className="text-[10px] mt-2 leading-relaxed opacity-80">Score based on alignment with 'Senior Software Engineer' benchmarks.</p>
      </div>
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
        <h4 className="text-xs font-bold text-slate-500 uppercase mb-3">Suggested Edits</h4>
        <div className="space-y-3">
          <div className="p-2.5 rounded bg-slate-50 text-[11px] border-l-2 border-blue-500">
            <strong>Stronger Action Verbs:</strong> Replace "Worked on" with "Architected" in section 2.
          </div>
          <div className="p-2.5 rounded bg-slate-50 text-[11px] border-l-2 border-blue-500">
            <strong>Metrics:</strong> AI detected missing quantitative results in your Meta role.
          </div>
        </div>
      </div>
    </div>
  </div>
);

// --- Recruiter Specific Views ---

const RecruiterConfig = () => {
  const [status, setStatus] = useState('idle');
  return (
    <div className="max-w-2xl space-y-6">
      <div className="bg-white p-8 rounded-2xl border border-slate-200 shadow-sm space-y-6">
        <div>
          <h3 className="text-xl font-bold text-slate-900 mb-1">Provider Configuration</h3>
          <p className="text-sm text-slate-500">Select the LLM engine for processing your current candidate batch.</p>
        </div>
        <div className="space-y-4">
          <div>
            <label className="text-xs font-bold text-slate-500 block mb-2 uppercase tracking-wider">Target Model</label>
            <select className="w-full border p-3 rounded-xl text-sm bg-slate-50 focus:ring-2 focus:ring-blue-500 outline-none transition-all">
              {PROVIDERS.map(p => <option key={p}>{p}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs font-bold text-slate-500 block mb-2 uppercase tracking-wider">API Access Key</label>
            <input 
              type="password" 
              placeholder="sk-••••••••••••••••"
              className="w-full border p-3 rounded-xl text-sm bg-slate-50 focus:ring-2 focus:ring-blue-500 outline-none" 
            />
          </div>
          <button 
            onClick={() => { setStatus('testing'); setTimeout(() => setStatus('success'), 1000); }}
            className="w-full bg-slate-900 text-white py-3 rounded-xl font-bold hover:bg-slate-800 transition-all flex items-center justify-center gap-2"
          >
            {status === 'testing' ? <Cpu className="animate-spin" size={18} /> : <ShieldCheck size={18} />}
            {status === 'testing' ? 'Verifying Pipeline...' : 'Validate & Save Configuration'}
          </button>
          {status === 'success' && (
            <div className="p-3 bg-green-50 text-green-700 rounded-lg text-xs font-bold flex items-center gap-2">
              <CheckCircle2 size={16} /> Connection stable. Gemini 1.5 Pro is ready for ingestion.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const RecruiterJD = () => {
  const [isAdding, setIsAdding] = useState(false);
  const [jobs, setJobs] = useState([
    { id: 1, title: 'Senior React Lead', category: 'Engineering', applicants: 14, threshold: 90, desc: 'Focus on performance optimization and large-scale state management.' }
  ]);

  const [newJob, setNewJob] = useState({ title: '', category: 'Engineering', desc: '' });

  const handleAddJob = () => {
    if (!newJob.title) return;
    setJobs([{ ...newJob, id: Date.now(), applicants: 0, threshold: 85 }, ...jobs]);
    setIsAdding(false);
    setNewJob({ title: '', category: 'Engineering', desc: '' });
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="flex justify-between items-center">
        <h3 className="text-xl font-bold">Active Job Definitions</h3>
        <button 
          onClick={() => setIsAdding(true)}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 hover:bg-blue-700 shadow-lg shadow-blue-200"
        >
          <Plus size={18} /> New Definition
        </button>
      </div>

      {isAdding && (
        <div className="bg-white p-6 rounded-2xl border-2 border-blue-500 shadow-xl space-y-4 animate-in zoom-in-95">
          <div className="flex justify-between items-center mb-2">
            <h4 className="font-bold text-slate-900">Define New Role</h4>
            <button onClick={() => setIsAdding(false)} className="text-slate-400 hover:text-slate-600"><X size={20}/></button>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-[10px] font-bold text-slate-500 uppercase">Role Title</label>
              <input 
                type="text" 
                value={newJob.title}
                onChange={(e) => setNewJob({...newJob, title: e.target.value})}
                placeholder="e.g. Senior Backend Architect"
                className="w-full border p-2 rounded-lg text-sm bg-slate-50 outline-none focus:ring-2 focus:ring-blue-500" 
              />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] font-bold text-slate-500 uppercase">Department</label>
              <select 
                value={newJob.category}
                onChange={(e) => setNewJob({...newJob, category: e.target.value})}
                className="w-full border p-2 rounded-lg text-sm bg-slate-50 outline-none"
              >
                <option>Engineering</option>
                <option>Product</option>
                <option>Design</option>
                <option>Sales</option>
              </select>
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-[10px] font-bold text-slate-500 uppercase">Description / Requirements</label>
            <textarea 
              rows={4}
              value={newJob.desc}
              onChange={(e) => setNewJob({...newJob, desc: e.target.value})}
              placeholder="Paste raw JD here for semantic extraction..."
              className="w-full border p-2 rounded-lg text-sm bg-slate-50 outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button onClick={() => setIsAdding(false)} className="px-4 py-2 text-sm font-bold text-slate-500">Cancel</button>
            <button onClick={handleAddJob} className="bg-blue-600 text-white px-6 py-2 rounded-lg text-sm font-bold shadow-lg shadow-blue-200">Save & Analyze</button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {jobs.map(job => (
          <div key={job.id} className="p-5 bg-white border border-slate-200 rounded-xl shadow-sm hover:border-blue-300 transition-all cursor-pointer">
            <div className="flex justify-between items-start mb-3">
              <h4 className="font-bold text-slate-900">{job.title}</h4>
              <span className="bg-blue-100 text-blue-700 text-[10px] px-2 py-1 rounded font-bold uppercase tracking-wider">{job.category}</span>
            </div>
            <p className="text-sm text-slate-500 line-clamp-2 mb-4">{job.desc}</p>
            <div className="flex gap-4 text-[11px] font-bold text-slate-400">
              <span className="flex items-center gap-1"><User size={12}/> {job.applicants} Applicants</span>
              <span className="flex items-center gap-1"><Cpu size={12}/> {job.threshold}% Match Threshold</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

// --- Manager Specific Views ---

const ManagerRankings = () => {
  const [selected, setSelected] = useState(null);
  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 animate-in fade-in duration-500">
      <div className="xl:col-span-2 space-y-3">
        {MOCK_CANDIDATES.map(c => (
          <div 
            key={c.id} 
            onClick={() => setSelected(c)}
            className={`p-4 bg-white border rounded-xl cursor-pointer transition-all hover:shadow-md ${selected?.id === c.id ? 'border-blue-500 ring-2 ring-blue-50' : 'border-slate-200'}`}
          >
            <div className="flex justify-between items-center">
              <div className="flex gap-3 items-center">
                <div className="w-10 h-10 bg-slate-100 rounded-lg flex items-center justify-center font-bold text-slate-500">{c.name.charAt(0)}</div>
                <div>
                  <h4 className="text-sm font-bold text-slate-900">{c.name}</h4>
                  <p className="text-[10px] text-slate-500 font-medium uppercase tracking-wider">{c.role}</p>
                </div>
              </div>
              <div className="text-right">
                <div className="text-xl font-black text-blue-600 leading-none">{c.score}</div>
                <div className="text-[9px] font-bold text-slate-400 uppercase">Match Score</div>
              </div>
            </div>
          </div>
        ))}
      </div>
      <div className="bg-slate-900 text-white rounded-2xl overflow-hidden shadow-2xl h-fit sticky top-6">
        {selected ? (
          <div className="p-6 space-y-6">
            <div>
              <h3 className="text-xl font-bold">{selected.name}</h3>
              <p className="text-slate-400 text-xs">Full Intelligence Breakdown</p>
            </div>
            <div className="space-y-4">
              <div className="p-4 bg-slate-800 rounded-xl border border-slate-700">
                <h5 className="text-[10px] font-bold text-blue-400 uppercase mb-2">Skill Gap Summary</h5>
                <div className="text-xs space-y-2">
                  <div className="flex items-center gap-2"><CheckCircle2 size={12} className="text-green-400"/> Strong Domain Expertise</div>
                  <div className="flex items-center gap-2"><AlertCircle size={12} className="text-amber-400"/> Missing: Cloud Architecture</div>
                </div>
              </div>
              <button className="w-full bg-blue-600 hover:bg-blue-700 py-3 rounded-xl font-bold text-sm transition-all">Approve for Interview</button>
            </div>
          </div>
        ) : (
          <div className="p-12 text-center text-slate-500 italic text-sm">Select a candidate for deep-dive analysis.</div>
        )}
      </div>
    </div>
  );
};

const ManagerSkillAnalysis = () => (
  <div className="space-y-6 animate-in fade-in duration-500">
    <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
      {[
        { label: 'Avg. Skill Match', value: '84%', trend: '+5%', color: 'blue' },
        { label: 'Risk Flag Density', value: '12%', trend: '-2%', color: 'green' },
        { label: 'Top Skill: React', value: '92%', trend: 'High', color: 'indigo' },
        { label: 'Gap: Kubernetes', value: '15%', trend: 'Critical', color: 'red' },
      ].map((stat, i) => (
        <div key={i} className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">{stat.label}</p>
          <div className="flex items-end justify-between mt-1">
            <h4 className="text-2xl font-black text-slate-900">{stat.value}</h4>
            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${stat.color === 'green' ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'}`}>
              {stat.trend}
            </span>
          </div>
        </div>
      ))}
    </div>

    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2 bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <h3 className="text-lg font-bold mb-6 flex items-center gap-2">
          <BarChart3 className="text-blue-600" /> Skill Frequency Distribution
        </h3>
        <div className="space-y-6">
          {[
            { skill: 'React.js', val: 95, color: 'bg-blue-500' },
            { skill: 'TypeScript', val: 82, color: 'bg-blue-400' },
            { skill: 'Node.js', val: 74, color: 'bg-indigo-500' },
            { skill: 'AWS / Cloud', val: 55, color: 'bg-slate-400' },
            { skill: 'Python', val: 42, color: 'bg-slate-300' },
          ].map(s => (
            <div key={s.skill}>
              <div className="flex justify-between text-xs font-bold mb-2">
                <span>{s.skill}</span>
                <span className="text-slate-400">{s.val}% Candidate Presence</span>
              </div>
              <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                <div className={`h-full ${s.color} transition-all duration-1000`} style={{ width: `${s.val}%` }}></div>
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="bg-slate-900 p-6 rounded-2xl text-white shadow-xl relative overflow-hidden">
        <h3 className="text-lg font-bold mb-4 relative z-10 flex items-center gap-2">
          <PieChart className="text-blue-400" /> Sentiment Analysis
        </h3>
        <p className="text-xs text-slate-400 mb-6 relative z-10">AI-detected career progression sentiment across the corpus.</p>
        <div className="space-y-4 relative z-10">
          <div className="flex items-center justify-between text-sm">
            <span className="flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-green-400" /> Growth Mindset</span>
            <span className="font-bold">68%</span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-blue-400" /> Domain Specialist</span>
            <span className="font-bold">22%</span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-amber-400" /> Risk/Transition</span>
            <span className="font-bold">10%</span>
          </div>
        </div>
        <div className="absolute bottom-[-20px] right-[-20px] opacity-10">
          <Cpu size={140} />
        </div>
      </div>
    </div>
  </div>
);

const ManagerReports = () => (
  <div className="space-y-6 animate-in fade-in duration-500">
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="p-6 border-b border-slate-100 flex justify-between items-center">
        <div>
          <h3 className="text-lg font-bold">Final Evaluation Reports</h3>
          <p className="text-xs text-slate-500">Comprehensive summaries ready for executive review.</p>
        </div>
        <button className="text-xs bg-slate-900 text-white px-4 py-2 rounded-lg font-bold flex items-center gap-2">
          <Download size={14} /> Batch Download
        </button>
      </div>
      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-slate-500 text-left">
          <tr>
            <th className="px-6 py-3 font-bold uppercase text-[10px]">Candidate</th>
            <th className="px-6 py-3 font-bold uppercase text-[10px]">Final Score</th>
            <th className="px-6 py-3 font-bold uppercase text-[10px]">Gen Date</th>
            <th className="px-6 py-3 font-bold uppercase text-[10px]">Status</th>
            <th className="px-6 py-3 font-bold uppercase text-[10px] text-right">Action</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {[
            { name: 'Alex Chen', score: 94, date: 'Oct 24, 2023', status: 'Ready' },
            { name: 'Sarah Miller', score: 82, date: 'Oct 23, 2023', status: 'Pending Review' },
          ].map((report, i) => (
            <tr key={i} className="hover:bg-slate-50 transition-colors">
              <td className="px-6 py-4 font-bold text-slate-900">{report.name}</td>
              <td className="px-6 py-4">
                <span className="text-blue-600 font-black">{report.score}</span>
                <span className="text-[10px] text-slate-400">/100</span>
              </td>
              <td className="px-6 py-4 text-slate-500">{report.date}</td>
              <td className="px-6 py-4">
                <span className={`text-[10px] font-bold px-2 py-1 rounded-full ${report.status === 'Ready' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'}`}>
                  {report.status.toUpperCase()}
                </span>
              </td>
              <td className="px-6 py-4 text-right">
                <button className="text-blue-600 hover:text-blue-800 font-bold flex items-center gap-1 ml-auto">
                  <FileDown size={16} /> <span className="text-xs">PDF</span>
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </div>
);

// --- Settings & Placeholder Views ---

const PlaceholderView = ({ title, desc, icon: Icon }) => (
  <div className="h-[calc(100vh-200px)] flex flex-col items-center justify-center text-center space-y-4 animate-in fade-in zoom-in-95 duration-300">
    <div className="w-20 h-20 bg-slate-100 rounded-3xl flex items-center justify-center text-slate-400">
      <Icon size={40} />
    </div>
    <div>
      <h3 className="text-xl font-bold text-slate-900">{title}</h3>
      <p className="text-sm text-slate-500 max-w-xs mx-auto">{desc}</p>
    </div>
    <button className="bg-slate-900 text-white px-6 py-2 rounded-lg text-sm font-bold">Refresh Data</button>
  </div>
);

// --- Main App Component ---

const App = () => {
  const [auth, setAuth] = useState({ isAuthenticated: false, persona: null, user: null });
  const [activeTab, setActiveTab] = useState('dashboard');

  const handleLogin = (method) => {
    let persona = 'jobseeker';
    let user = { name: 'Alex Chen', email: 'alex@gmail.com' };
    let initialTab = 'dashboard';

    if (method === 'corporate') {
      persona = 'recruiter';
      user = { name: 'Recruiter Pro', email: 'admin@company.com' };
      initialTab = 'config';
    } else if (method === 'manager') {
       persona = 'manager';
       user = { name: 'Hiring Lead', email: 'lead@company.com' };
       initialTab = 'rankings';
    }

    setAuth({ isAuthenticated: true, persona, user });
    setActiveTab(initialTab);
  };

  const handleLogout = () => {
    setAuth({ isAuthenticated: false, persona: null, user: null });
    setActiveTab('dashboard');
  };

  // Content Routing Logic
  const renderContent = () => {
    if (auth.persona === 'jobseeker') {
      switch (activeTab) {
        case 'dashboard': return <JobSeekerDashboard />;
        case 'refine': return <ResumeRefiner />;
        case 'settings': return <PlaceholderView title="Profile Settings" desc="Manage your personal information and privacy preferences." icon={User} />;
        default: return <JobSeekerDashboard />;
      }
    }
    if (auth.persona === 'recruiter') {
      switch (activeTab) {
        case 'config': return <RecruiterConfig />;
        case 'jd': return <RecruiterJD />;
        case 'candidates': return <PlaceholderView title="Candidate Corpus" desc="Access the full LanceDB vector store of your applicants." icon={Database} />;
        default: return <RecruiterConfig />;
      }
    }
    if (auth.persona === 'manager') {
      switch (activeTab) {
        case 'rankings': return <ManagerRankings />;
        case 'analytics': return <ManagerSkillAnalysis />;
        case 'reports': return <ManagerReports />;
        default: return <ManagerRankings />;
      }
    }
  };

  if (!auth.isAuthenticated) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center p-6 font-sans">
        <div className="max-w-md w-full space-y-8 bg-slate-900 border border-slate-800 p-8 rounded-2xl shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 right-0 w-32 h-32 bg-blue-600/10 blur-3xl -mr-16 -mt-16"></div>
          <div className="text-center relative z-10">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-600 rounded-2xl shadow-lg shadow-blue-500/30 mb-6">
              <ShieldCheck className="text-white" size={32} />
            </div>
            <h1 className="text-3xl font-black text-white tracking-tight">RESUME.AI</h1>
            <p className="mt-2 text-slate-400 text-sm">Intelligence Platform for Modern Talent</p>
          </div>

          <div className="space-y-4 relative z-10">
            <button onClick={() => handleLogin('gmail')} className="w-full flex items-center justify-center gap-3 bg-white text-slate-900 py-3.5 rounded-xl font-bold hover:bg-slate-100 transition-all active:scale-[0.98]">
              <Mail className="text-red-500" size={20} /> Login with Gmail
            </button>
            <button onClick={() => handleLogin('linkedin')} className="w-full flex items-center justify-center gap-3 bg-[#0077b5] text-white py-3.5 rounded-xl font-bold hover:bg-[#006699] transition-all active:scale-[0.98]">
              <Linkedin size={20} /> Login with LinkedIn
            </button>
            
            <div className="relative py-4">
              <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-slate-800"></div></div>
              <div className="relative flex justify-center text-[10px] uppercase font-bold tracking-widest"><span className="bg-slate-900 px-3 text-slate-500">Internal Access</span></div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <button onClick={() => handleLogin('corporate')} className="bg-slate-800 text-white p-3 rounded-xl font-bold hover:bg-slate-700 transition-all border border-slate-700 text-xs">Recruiter SSO</button>
              <button onClick={() => handleLogin('manager')} className="bg-slate-800 text-white p-3 rounded-xl font-bold hover:bg-slate-700 transition-all border border-slate-700 text-xs">Manager SSO</button>
            </div>
          </div>
          <p className="text-center text-[9px] text-slate-600 uppercase tracking-widest font-bold">Secure Session • Audit Logging Enabled</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-slate-50 text-slate-900 overflow-hidden font-sans">
      <Sidebar persona={auth.persona} activeTab={activeTab} setActiveTab={setActiveTab} onLogout={handleLogout} />
      
      <main className="flex-1 flex flex-col overflow-hidden">
        <header className="h-16 bg-white border-b border-slate-200 px-8 flex items-center justify-between z-20 shadow-sm">
          <div className="flex items-center gap-4">
            <span className="text-xs font-black text-blue-600 bg-blue-50 px-2.5 py-1 rounded tracking-widest">
              {auth.persona.toUpperCase()} MODE
            </span>
            <div className="h-4 w-px bg-slate-200"></div>
            <span className="text-xs font-semibold text-slate-400">Environment: <span className="text-slate-900">PROD-LLM-01</span></span>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right hidden sm:block">
              <p className="text-xs font-bold leading-none">{auth.user.name}</p>
              <p className="text-[10px] text-slate-400 mt-1">{auth.user.email}</p>
            </div>
            <div className="w-9 h-9 bg-slate-900 rounded-xl flex items-center justify-center text-white text-xs font-bold ring-2 ring-white shadow-md">
              {auth.user.name.split(' ').map(n => n[0]).join('')}
            </div>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto p-8 bg-slate-50/50">
          <div className="max-w-7xl mx-auto">
            {renderContent()}
          </div>
        </div>
      </main>
    </div>
  );
};

export default App;