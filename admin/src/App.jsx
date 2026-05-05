import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  LayoutDashboard, 
  Settings, 
  Play, 
  Database, 
  Search, 
  Plus, 
  Trash2, 
  Save, 
  ChevronUp, 
  ChevronDown,
  MapPin,
  Briefcase,
  ExternalLink,
  Building2,
  TrendingUp,
  TrendingDown,
  AlertCircle,
  CheckCircle2,
  TerminalSquare,
  LogOut,
  ToggleLeft,
  ToggleRight,
  RefreshCw,
  MoreVertical,
  Activity,
  Calendar
} from 'lucide-react';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, AreaChart, Area
} from 'recharts';

const App = () => {
  const [currentView, setCurrentView] = useState('dashboard');
  const [jobs, setJobs] = useState([]);
  const [totalJobs, setTotalJobs] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize] = useState(100);
  const [loading, setLoading] = useState(true);
  
  // API Filters
  const [apiFilters, setApiFilters] = useState({
    search: '',
    location: '',
    source: ''
  });
  
  const [stats, setStats] = useState({
    total_jobs: 0,
    companies: 0,
    cities: 0,
    locations_list: [],
    sources_list: []
  });
  
  // Auth state
  const [isLoggedIn, setIsLoggedIn] = useState(() => {
    const savedSession = localStorage.getItem('zapril_admin_session');
    if (savedSession) {
      try {
        const { token, expiresAt } = JSON.parse(savedSession);
        if (Date.now() < expiresAt) return true;
        localStorage.removeItem('zapril_admin_session');
      } catch (e) {
        localStorage.removeItem('zapril_admin_session');
      }
    }
    return false;
  });
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState('');

  // Config state
  const [citiesConfig, setCitiesConfig] = useState([]);
  const [jobTitlesConfig, setJobTitlesConfig] = useState([]);
  const [settings, setSettings] = useState({
    scraping_interval_hours: 24,
    lookback_period_hours: 48,
    max_results_per_scrape: 20,
    phased_scraping: true,
    jobs_per_phase: 3,
    cities_per_phase: 3,
    enabled_platforms: ['linkedin', 'indeed', 'naukri']
  });
  const [savingConfig, setSavingConfig] = useState(false);
  const [savingSettings, setSavingSettings] = useState(false);

  // Scraper Action state
  const [triggering, setTriggering] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testOutput, setTestOutput] = useState(null);
  const [systemLogs, setSystemLogs] = useState('');
  const [fetchingLogs, setFetchingLogs] = useState(false);

  // Modal state
  const [selectedJob, setSelectedJob] = useState(null);

  // Custom Trigger state
  const [customCity, setCustomCity] = useState('');
  const [customJobTitle, setCustomJobTitle] = useState('');
  const [customMaxResults, setCustomMaxResults] = useState(10);

  useEffect(() => {
    if (isLoggedIn) {
      fetchData();
      fetchConfig();
    }
  }, [isLoggedIn]);

  const handleLogin = async (e) => {
    e.preventDefault();
    try {
      const res = await axios.post('/api/auth/login', { password });
      if (res.data.token) {
        // Save session for 7 days
        const sessionData = {
          token: res.data.token,
          expiresAt: Date.now() + (7 * 24 * 60 * 60 * 1000)
        };
        localStorage.setItem('zapril_admin_session', JSON.stringify(sessionData));
        
        setIsLoggedIn(true);
        setLoginError('');
      } else {
        setLoginError('Invalid password');
      }
    } catch (error) {
      setLoginError('Login failed. Please check your password.');
    }
  };

  const fetchData = async (page = currentPage, filters = apiFilters) => {
    setLoading(true);
    try {
      const offset = (page - 1) * pageSize;
      const params = {
        limit: pageSize,
        offset: offset,
        search: filters.search,
        location: filters.location,
        source: filters.source
      };
      
      const [jobsRes, statsRes] = await Promise.all([
        axios.get('/api/jobs', { params }),
        axios.get('/api/stats')
      ]);
      
      if (jobsRes.data && jobsRes.data.jobs) {
        setJobs(jobsRes.data.jobs);
        setTotalJobs(jobsRes.data.total);
      } else {
        setJobs(Array.isArray(jobsRes.data) ? jobsRes.data : []);
      }

      if (statsRes.data) {
        setStats({
          total_jobs: statsRes.data.total_jobs || 0,
          companies: statsRes.data.companies || 0,
          cities: statsRes.data.cities || 0,
          locations_list: statsRes.data.locations_list || [],
          sources_list: statsRes.data.sources_list || []
        });
      }
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isLoggedIn) {
      fetchData();
      fetchConfig();
    }
  }, [isLoggedIn, currentPage, apiFilters]);

  const fetchConfig = async () => {
    try {
      const [citiesRes, jobTitlesRes, settingsRes] = await Promise.all([
        axios.get('/api/config/cities').catch(() => ({ data: { cities: [] } })),
        axios.get('/api/config/job-titles').catch(() => ({ data: { job_titles: [] } })),
        axios.get('/api/settings').catch(() => ({ data: null }))
      ]);
      
      const normalize = (items) => {
        if (!Array.isArray(items)) return [];
        return items
          .filter(item => item !== null && item !== undefined)
          .map(item => {
            if (typeof item === 'string') return { name: item, enabled: true };
            if (typeof item === 'object') {
              return { 
                name: item.name || item.label || String(item), 
                enabled: item.enabled !== undefined ? item.enabled : true 
              };
            }
            return { name: String(item), enabled: true };
          });
      };
      
      const cities = citiesRes.data?.cities || citiesRes.data || [];
      const titles = jobTitlesRes.data?.job_titles || jobTitlesRes.data || [];
      
      setCitiesConfig(normalize(cities));
      setJobTitlesConfig(normalize(titles));
      
      if (settingsRes.data) {
        setSettings(prev => ({ ...prev, ...settingsRes.data }));
      }
    } catch (error) {
      console.error('Error fetching config:', error);
    }
  };

  const saveSettings = async () => {
    setSavingSettings(true);
    try {
      await axios.post('/api/settings', settings);
      alert('Configuration updated successfully.');
    } catch (error) {
      alert('Failed to update settings');
    } finally {
      setSavingSettings(false);
    }
  };

  const saveCities = async () => {
    setSavingConfig(true);
    try {
      await axios.post('/api/config/cities', { cities: citiesConfig });
      alert('Cities configuration updated.');
    } catch (error) {
      alert('Error saving cities');
    } finally {
      setSavingConfig(false);
    }
  };

  const saveJobTitles = async () => {
    setSavingConfig(true);
    try {
      await axios.post('/api/config/job-titles', { job_titles: jobTitlesConfig });
      alert('Job roles updated.');
    } catch (error) {
      alert('Error saving roles');
    } finally {
      setSavingConfig(false);
    }
  };

  const addCity = (cityName) => {
    if (cityName.trim()) {
      setCitiesConfig([...citiesConfig, { name: cityName.trim(), enabled: true }]);
    }
  };

  const addJobTitle = (jobTitleName) => {
    if (jobTitleName.trim()) {
      setJobTitlesConfig([...jobTitlesConfig, { name: jobTitleName.trim(), enabled: true }]);
    }
  };

  const getSourceStats = () => {
    if (!Array.isArray(jobs)) return [];
    const counts = {};
    jobs.forEach(job => {
      if (job && job.source) {
        counts[job.source] = (counts[job.source] || 0) + 1;
      }
    });
    return Object.keys(counts).map(key => ({ name: key, value: counts[key] }));
  };

  const getCityStats = () => {
    if (!Array.isArray(jobs)) return [];
    const counts = {};
    jobs.forEach(job => {
      if (job && job.location) {
        const city = job.location.split(',')[0].trim();
        counts[city] = (counts[city] || 0) + 1;
      }
    });
    return Object.keys(counts)
      .map(key => ({ name: key, count: counts[key] }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10);
  };

  const handleTriggerScraper = async () => {
    setTriggering(true);
    try {
      await axios.post('/api/run-scraper');
      alert('Full scraping cycle initiated in background.');
    } catch (error) {
      alert('Error triggering scraper');
    } finally {
      setTriggering(false);
    }
  };

  const fetchLogs = async () => {
    setFetchingLogs(true);
    try {
      const res = await axios.get('/api/logs');
      setSystemLogs(res.data.logs);
    } catch (error) {
      console.error('Error fetching logs');
    } finally {
      setFetchingLogs(false);
    }
  };

  const testScraper = async () => {
    setTesting(true);
    try {
      const res = await axios.post('/api/test-scraper');
      setTestOutput(res.data);
    } catch (error) {
      alert('Scraper test failed');
    } finally {
      setTesting(false);
    }
  };

  if (!isLoggedIn) {
    return (
      <div className="login-screen">
        <div className="login-card animate-slide-in">
          <div className="login-icon">
            <LayoutDashboard size={32} color="white" />
          </div>
          <h2>Zapril Admin</h2>
          <p>Sign in to manage your automated job scraper</p>
          <form className="login-form" onSubmit={handleLogin}>
            <div className="form-group">
              <label>Administrator Password</label>
              <input 
                className="input-base w-full"
                type="password" 
                placeholder="••••••••••••" 
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoFocus
              />
            </div>
            {loginError && <div className="text-trend-down text-sm text-center">{loginError}</div>}
            <button type="submit" className="btn-base btn-solid w-full" style={{ padding: '0.875rem' }}>
              Access Dashboard
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="app-container">
      <Sidebar 
        currentView={currentView} 
        setCurrentView={setCurrentView} 
        handleLogout={() => { 
          localStorage.removeItem('zapril_admin_session');
          setIsLoggedIn(false); 
          setPassword(''); 
        }} 
      />
      <main className="main-content">
        {currentView === 'dashboard' && (
          <DashboardView 
            jobs={jobs}
            stats={stats}
            totalJobs={totalJobs}
            currentPage={currentPage}
            setCurrentPage={setCurrentPage}
            pageSize={pageSize}
            apiFilters={apiFilters}
            setApiFilters={setApiFilters}
            getSourceStats={getSourceStats}
            getCityStats={getCityStats}
            setSelectedJob={async (job) => {
              if (!job) {
                setSelectedJob(null);
                return;
              }
              // Set initial job data with loading state
              setSelectedJob({ ...job, loading: true });
              try {
                const res = await axios.get(`/api/jobs/${job.id}`);
                setSelectedJob({ ...res.data, loading: false });
              } catch (err) {
                console.error("Failed to fetch job details:", err);
                setSelectedJob({ ...job, loading: false, error: "Failed to load description" });
              }
            }}
            fetchData={fetchData}
          />
        )}
        {currentView === 'settings' && (
          <ConfigurationView 
            citiesConfig={citiesConfig}
            setCitiesConfig={setCitiesConfig}
            addCity={addCity}
            saveCities={saveCities}
            jobTitlesConfig={jobTitlesConfig}
            setJobTitlesConfig={setJobTitlesConfig}
            addJobTitle={addJobTitle}
            saveJobTitles={saveJobTitles}
            settings={settings}
            setSettings={setSettings}
            saveSettings={saveSettings}
            savingConfig={savingConfig}
            savingSettings={savingSettings}
          />
        )}
        {currentView === 'actions' && (
          <ActionsView 
            triggering={triggering}
            handleTriggerScraper={handleTriggerScraper}
            testing={testing}
            testScraper={testScraper}
            testOutput={testOutput}
            systemLogs={systemLogs}
            fetchLogs={fetchLogs}
            fetchingLogs={fetchingLogs}
            setSystemLogs={setSystemLogs}
            customCity={customCity}
            setCustomCity={setCustomCity}
            customJobTitle={customJobTitle}
            setCustomJobTitle={setCustomJobTitle}
            customMaxResults={customMaxResults}
            setCustomMaxResults={setCustomMaxResults}
          />
        )}
      </main>

      {/* Detail Modal */}
      {selectedJob && (
        <div className="modal-overlay" onClick={() => setSelectedJob(null)}>
          <div className="modal-window max-w-4xl h-[85vh] flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="modal-header shrink-0">
              <div className="flex justify-between items-start">
                <div className="flex-1 pr-8">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="badge badge-primary">{selectedJob.source}</span>
                    <span className="text-xs text-muted">ID: {selectedJob.id}</span>
                  </div>
                  <h2 className="text-2xl font-bold tracking-tight text-white mb-2 leading-tight">
                    {selectedJob.title}
                  </h2>
                  <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
                    <div className="flex items-center gap-1.5 font-medium text-white/90">
                      <Building2 size={16} className="text-accent-primary" /> 
                      {selectedJob.company}
                    </div>
                    <div className="flex items-center gap-1.5 text-white/70">
                      <MapPin size={16} className="text-accent-secondary" /> 
                      {selectedJob.location}
                    </div>
                    <div className="flex items-center gap-1.5 text-white/70">
                      <Calendar size={16} /> 
                      {(() => {
                        const dateStr = selectedJob.date_posted;
                        if (!dateStr || dateStr.toLowerCase() === 'nan') return 'Recently';
                        const d = new Date(dateStr);
                        return !isNaN(d.getTime()) ? d.toLocaleDateString() : 'Recently';
                      })()}
                    </div>
                  </div>
                </div>
                <button 
                  className="p-2 hover:bg-white/10 rounded-full text-white/60 hover:text-white transition-all hover:rotate-90 duration-300" 
                  onClick={() => setSelectedJob(null)}
                >
                  <LogOut size={22} />
                </button>
              </div>
            </div>
            
            <div className="modal-body flex-1 overflow-y-auto custom-scrollbar p-8">
              <div className="max-w-none prose prose-invert">
                <h4 className="text-xs font-bold text-accent-primary uppercase tracking-[0.2em] mb-6 flex items-center gap-2">
                  <TerminalSquare size={14} /> Job Description & Details
                </h4>
                
                {selectedJob.loading ? (
                  <div className="flex flex-col items-center justify-center py-20 gap-4">
                    <RefreshCw size={32} className="animate-spin text-accent-primary" />
                    <p className="text-muted text-sm">Fetching detailed description...</p>
                  </div>
                ) : (
                  <div className="job-desc-content whitespace-pre-wrap text-white/80 leading-relaxed font-light">
                    {selectedJob.description || 'No detailed description available for this role.'}
                  </div>
                )}
              </div>
            </div>

            <div className="modal-footer shrink-0 flex gap-4 p-6 bg-white/[0.02] border-t border-white/5">
              <a 
                href={selectedJob.job_url} 
                target="_blank" 
                rel="noopener noreferrer" 
                className="btn-base btn-solid flex-1 h-12 text-base font-semibold shadow-xl shadow-indigo-500/10 hover:shadow-indigo-500/20 transition-all"
              >
                Apply on {selectedJob.source.charAt(0).toUpperCase() + selectedJob.source.slice(1)} <ExternalLink size={18} />
              </a>
              <button 
                className="btn-base btn-ghost h-12 px-8 font-medium hover:bg-white/5" 
                onClick={() => setSelectedJob(null)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

/* --- Sub-Components (Defined Outside to Prevent Re-mounting) --- */

const Sidebar = ({ currentView, setCurrentView, handleLogout }) => (
  <aside className="sidebar">
    <div className="sidebar-logo">
      <div className="sidebar-logo-icon">
        <Database size={18} color="white" />
      </div>
      <span>Zapril AI</span>
    </div>

    <nav className="nav-section">
      <div 
        className={`nav-item ${currentView === 'dashboard' ? 'active' : ''}`}
        onClick={() => setCurrentView('dashboard')}
      >
        <LayoutDashboard size={20} />
        <span>Dashboard</span>
      </div>
      <div 
        className={`nav-item ${currentView === 'settings' ? 'active' : ''}`}
        onClick={() => setCurrentView('settings')}
      >
        <Settings size={20} />
        <span>Configuration</span>
      </div>
      <div 
        className={`nav-item ${currentView === 'actions' ? 'active' : ''}`}
        onClick={() => setCurrentView('actions')}
      >
        <Play size={20} />
        <span>Scraper Actions</span>
      </div>
    </nav>

    <div className="sidebar-footer">
      <button className="logout-btn" onClick={handleLogout}>
        <LogOut size={20} />
        <span>Logout</span>
      </button>
    </div>
  </aside>
);

const DashboardView = ({ 
  jobs, stats, getSourceStats, getCityStats, setSelectedJob, fetchData,
  totalJobs, currentPage, setCurrentPage, pageSize, apiFilters, setApiFilters 
}) => {
  const [localSearch, setLocalSearch] = useState(apiFilters.search);
  
  // Resizing logic
  const handleResize = (e, index) => {
    const th = e.target.parentElement.parentElement;
    const startX = e.pageX;
    const startWidth = th.offsetWidth;

    const onMouseMove = (moveEvent) => {
      const newWidth = startWidth + (moveEvent.pageX - startX);
      th.style.width = `${newWidth}px`;
    };

    const onMouseUp = () => {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    };

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  };
  
  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setApiFilters(prev => ({ ...prev, search: localSearch }));
      setCurrentPage(1); // Reset to first page on search
    }, 500);
    return () => clearTimeout(timer);
  }, [localSearch]);

  const handlePageChange = (newPage) => {
    setCurrentPage(newPage);
  };

  const handleFilterChange = (key, value) => {
    setApiFilters(prev => ({ ...prev, [key]: value }));
    setCurrentPage(1); // Reset to first page on filter change
  };

  const totalPages = Math.ceil(totalJobs / pageSize);

  return (
    <div className="space-y-6 animate-in">
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-card-header">
            <span className="stat-card-title">Total Jobs</span>
            <div className="stat-card-icon"><Briefcase size={18} /></div>
          </div>
          <div className="stat-card-value">{(totalJobs || 0).toLocaleString()}</div>
          <div className="stat-card-trend trend-up">
            <Activity size={14} /> <span>Live positions in database</span>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-card-header">
            <span className="stat-card-title">Companies</span>
            <div className="stat-card-icon"><Building2 size={18} /></div>
          </div>
          <div className="stat-card-value">{(stats.companies || 0).toLocaleString()}</div>
          <div className="stat-card-trend trend-up">
             <span>Across all sectors</span>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-card-header">
            <span className="stat-card-title">Coverage</span>
            <div className="stat-card-icon"><MapPin size={18} /></div>
          </div>
          <div className="stat-card-value">{(stats.cities || 0)} Cities</div>
          <div className="stat-card-trend">
            <Activity size={14} className="text-muted" /> <span>Targeted locations</span>
          </div>
        </div>
      </div>

      <div className="charts-grid">
        <div className="chart-container">
          <h3 className="chart-title">Distribution by Platform</h3>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={getSourceStats()}
                innerRadius={60}
                outerRadius={85}
                paddingAngle={8}
                dataKey="value"
              >
                {getSourceStats().map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={['#6366f1', '#06b6d4', '#10b981', '#f59e0b', '#ef4444'][index % 5]} />
                ))}
              </Pie>
              <Tooltip 
                contentStyle={{ background: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '12px', fontSize: '12px' }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-container">
          <h3 className="chart-title">Highest Volume Cities</h3>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={getCityStats()}>
              <XAxis dataKey="name" stroke="#64748b" fontSize={11} axisLine={false} tickLine={false} />
              <YAxis hide />
              <Tooltip 
                cursor={{fill: 'rgba(255,255,255,0.02)'}}
                contentStyle={{ background: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '12px' }}
              />
              <Bar dataKey="count" fill="#6366f1" radius={[6, 6, 0, 0]} barSize={32} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="table-wrapper">
        <div className="table-header">
          <h3 className="font-bold">Recent Listings <span className="text-muted text-xs font-normal ml-2">(Showing {jobs.length} of {totalJobs})</span></h3>
          <div className="flex flex-wrap gap-3">
            <div className="flex items-center bg-black/20 rounded-md px-3 border border-white/5">
              <Search size={16} className="text-muted mr-2" />
              <input 
                type="text" 
                placeholder="Search jobs..." 
                className="bg-transparent border-none text-sm text-white focus:outline-none py-2 w-40"
                value={localSearch}
                onChange={(e) => setLocalSearch(e.target.value)}
              />
            </div>
            
            <select 
              className="bg-black/20 border border-white/5 rounded-md px-2 text-xs text-white outline-none h-10"
              value={apiFilters.location}
              onChange={(e) => handleFilterChange('location', e.target.value)}
            >
              <option value="">All Locations</option>
              {stats.locations_list && stats.locations_list.map(loc => (
                <option key={loc} value={loc}>{loc}</option>
              ))}
            </select>

            <select 
              className="bg-black/20 border border-white/5 rounded-md px-2 text-xs text-white outline-none h-10"
              value={apiFilters.source}
              onChange={(e) => handleFilterChange('source', e.target.value)}
            >
              <option value="">All Sources</option>
              {stats.sources_list && stats.sources_list.map(src => (
                <option key={src} value={src}>{src.toUpperCase()}</option>
              ))}
            </select>

            <button className="btn-base btn-ghost" onClick={() => fetchData()}><RefreshCw size={14} /> Sync</button>
          </div>
        </div>
        
        <div className="table-content overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr>
                <th className="resizable-th" style={{ width: '30%' }}>
                  <div className="th-content">Title <div className="resizer" onMouseDown={(e) => handleResize(e, 0)}></div></div>
                </th>
                <th className="resizable-th" style={{ width: '20%' }}>
                  <div className="th-content">Company <div className="resizer" onMouseDown={(e) => handleResize(e, 1)}></div></div>
                </th>
                <th className="resizable-th" style={{ width: '20%' }}>
                  <div className="th-content">Location <div className="resizer" onMouseDown={(e) => handleResize(e, 2)}></div></div>
                </th>
                <th className="resizable-th" style={{ width: '15%' }}>
                  <div className="th-content">Date Posted <div className="resizer" onMouseDown={(e) => handleResize(e, 3)}></div></div>
                </th>
                <th className="resizable-th" style={{ width: '10%' }}>
                  <div className="th-content">Source <div className="resizer" onMouseDown={(e) => handleResize(e, 4)}></div></div>
                </th>
                <th className="w-10"></th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id}>
                  <td className="cell-primary">{job.title}</td>
                  <td>
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 bg-white/5 rounded-full flex items-center justify-center text-[10px] font-bold">
                        {job.company ? job.company.charAt(0) : '?'}
                      </div>
                      {job.company}
                    </div>
                  </td>
                  <td><div className="flex items-center gap-1.5"><MapPin size={12} className="text-muted" /> {job.location}</div></td>
                  <td>
                    <div className="flex items-center gap-1.5">
                      <Calendar size={12} className="text-muted" /> 
                      {(() => {
                        const dateStr = job.date_posted;
                        if (!dateStr || dateStr.toLowerCase() === 'nan') return 'Recently';
                        const d = new Date(dateStr);
                        return !isNaN(d.getTime()) ? d.toLocaleDateString() : 'Recently';
                      })()}
                    </div>
                  </td>
                  <td>
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium uppercase tracking-wider ${
                      job.source === 'linkedin' ? 'bg-blue-500/10 text-blue-400' : 
                      job.source === 'indeed' ? 'bg-indigo-500/10 text-indigo-400' : 
                      'bg-emerald-500/10 text-emerald-400'
                    }`}>
                      {job.source}
                    </span>
                  </td>
                  <td>
                    <button className="btn-base btn-ghost p-1.5" onClick={() => setSelectedJob(job)}>
                      <ExternalLink size={14} />
                    </button>
                  </td>
                </tr>
              ))}
              {jobs.length === 0 && (
                <tr>
                  <td colSpan="6" className="text-center py-10 text-muted">No jobs found matching your criteria.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div className="flex items-center justify-between p-4 border-t border-white/5">
            <div className="text-xs text-muted">
              Page {currentPage} of {totalPages}
            </div>
            <div className="flex gap-2">
              <button 
                className="btn-base btn-ghost text-xs px-3 py-1" 
                disabled={currentPage <= 1}
                onClick={() => handlePageChange(currentPage - 1)}
              >
                Previous
              </button>
              <button 
                className="btn-base btn-ghost text-xs px-3 py-1" 
                disabled={currentPage >= totalPages}
                onClick={() => handlePageChange(currentPage + 1)}
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

const ConfigurationView = ({ 
  citiesConfig, setCitiesConfig, addCity, saveCities,
  jobTitlesConfig, setJobTitlesConfig, addJobTitle, saveJobTitles,
  settings, setSettings, saveSettings, savingConfig, savingSettings
}) => {
  const [newCity, setNewCity] = useState('');
  const [newJobTitle, setNewJobTitle] = useState('');

  const handleAddCity = () => {
    if (newCity.trim()) {
      addCity(newCity);
      setNewCity('');
    }
  };

  const handleAddJobTitle = () => {
    if (newJobTitle.trim()) {
      addJobTitle(newJobTitle);
      setNewJobTitle('');
    }
  };

  const moveItem = (list, setList, index, direction) => {
    const newList = [...list];
    if (direction === 'up' && index > 0) {
      [newList[index], newList[index - 1]] = [newList[index - 1], newList[index]];
    } else if (direction === 'down' && index < newList.length - 1) {
      [newList[index], newList[index + 1]] = [newList[index + 1], newList[index]];
    }
    setList(newList);
  };

  const toggleItem = (list, setList, index) => {
    const newList = [...list];
    newList[index].enabled = !newList[index].enabled;
    setList(newList);
  };

  const removeItem = (list, setList, index) => {
    setList(list.filter((_, i) => i !== index));
  };

  return (
    <div className="animate-slide-in">
      <h1 className="page-title">Scraper Configuration</h1>

      <div className="charts-grid">
        {/* Cities Config */}
        <div className="chart-container" style={{ height: 'auto', minHeight: '500px' }}>
          <div className="flex justify-between items-center mb-6">
            <h3 className="chart-title mb-0">Target Cities</h3>
            <span className="text-xs bg-accent-primary-glow text-accent-primary px-2 py-1 rounded-md font-bold">{citiesConfig.length}</span>
          </div>
          
          <div className="flex gap-2 mb-6">
            <input 
              className="input-base flex-1"
              placeholder="Add city name..."
              value={newCity}
              onChange={(e) => setNewCity(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleAddCity()}
            />
            <button className="btn-base btn-solid" style={{ padding: '0 1rem' }} onClick={handleAddCity}><Plus size={18} /></button>
          </div>

          <div className="config-list mb-6">
            {citiesConfig.map((city, i) => (
              <div key={i} className={`config-item ${!city.enabled ? 'opacity-40' : ''}`}>
                <div className="flex items-center">
                  <div className="config-item-drag">
                    <button onClick={() => moveItem(citiesConfig, setCitiesConfig, i, 'up')}><ChevronUp size={14} /></button>
                    <button onClick={() => moveItem(citiesConfig, setCitiesConfig, i, 'down')}><ChevronDown size={14} /></button>
                  </div>
                  <span className="text-sm font-medium">{city.name}</span>
                </div>
                <div className="config-item-actions">
                  <button className={`action-icon-btn ${city.enabled ? 'success' : ''}`} onClick={() => toggleItem(citiesConfig, setCitiesConfig, i)}>
                    {city.enabled ? <ToggleRight size={24} /> : <ToggleLeft size={24} />}
                  </button>
                  <button className="action-icon-btn delete" onClick={() => removeItem(citiesConfig, setCitiesConfig, i)}><Trash2 size={16} /></button>
                </div>
              </div>
            ))}
          </div>
          <button className="btn-base btn-solid w-full mt-auto" onClick={saveCities} disabled={savingConfig}>
            <Save size={16} /> {savingConfig ? 'Saving...' : 'Sync Cities'}
          </button>
        </div>

        {/* Roles Config */}
        <div className="chart-container" style={{ height: 'auto', minHeight: '500px' }}>
          <div className="flex justify-between items-center mb-6">
            <h3 className="chart-title mb-0">Job Roles</h3>
            <span className="text-xs bg-accent-primary-glow text-accent-primary px-2 py-1 rounded-md font-bold">{jobTitlesConfig.length}</span>
          </div>
          
          <div className="flex gap-2 mb-6">
            <input 
              className="input-base flex-1"
              placeholder="Add job role..."
              value={newJobTitle}
              onChange={(e) => setNewJobTitle(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleAddJobTitle()}
            />
            <button className="btn-base btn-solid" style={{ padding: '0 1rem' }} onClick={handleAddJobTitle}><Plus size={18} /></button>
          </div>

          <div className="config-list mb-6">
            {jobTitlesConfig.map((role, i) => (
              <div key={i} className={`config-item ${!role.enabled ? 'opacity-40' : ''}`}>
                <div className="flex items-center">
                  <div className="config-item-drag">
                    <button onClick={() => moveItem(jobTitlesConfig, setJobTitlesConfig, i, 'up')}><ChevronUp size={14} /></button>
                    <button onClick={() => moveItem(jobTitlesConfig, setJobTitlesConfig, i, 'down')}><ChevronDown size={14} /></button>
                  </div>
                  <span className="text-sm font-medium">{role.name}</span>
                </div>
                <div className="config-item-actions">
                  <button className={`action-icon-btn ${role.enabled ? 'success' : ''}`} onClick={() => toggleItem(jobTitlesConfig, setJobTitlesConfig, i)}>
                    {role.enabled ? <ToggleRight size={24} /> : <ToggleLeft size={24} />}
                  </button>
                  <button className="action-icon-btn delete" onClick={() => removeItem(jobTitlesConfig, setJobTitlesConfig, i)}><Trash2 size={16} /></button>
                </div>
              </div>
            ))}
          </div>
          <button className="btn-base btn-solid w-full mt-auto" onClick={saveJobTitles} disabled={savingConfig}>
            <Save size={16} /> {savingConfig ? 'Saving...' : 'Sync Roles'}
          </button>
        </div>
      </div>

      <div className="stat-card mt-8">
        <h3 className="chart-title">Global Settings</h3>
        <div className="grid grid-cols-2 gap-8">
          <div className="flex flex-col gap-6">
            <div className="form-group">
              <label className="text-xs font-bold text-muted uppercase mb-2 block">Interval (Hours)</label>
              <input 
                type="number" 
                className="input-base w-full"
                value={settings.scraping_interval_hours || ''}
                onChange={(e) => {
                  const val = e.target.value === '' ? 0 : parseInt(e.target.value);
                  setSettings({...settings, scraping_interval_hours: isNaN(val) ? 0 : val});
                }}
              />
            </div>
            <div className="form-group">
              <label className="text-xs font-bold text-muted uppercase mb-2 block">Lookback (Hours)</label>
              <input 
                type="number" 
                className="input-base w-full"
                value={settings.lookback_period_hours || ''}
                onChange={(e) => {
                  const val = e.target.value === '' ? 0 : parseInt(e.target.value);
                  setSettings({...settings, lookback_period_hours: isNaN(val) ? 0 : val});
                }}
              />
            </div>
          </div>
          <div className="flex flex-col gap-6">
            <div className="form-group">
              <label className="text-xs font-bold text-muted uppercase mb-2 block">Max Results / Scrape</label>
              <input 
                type="number" 
                className="input-base w-full"
                value={settings.max_results_per_scrape || ''}
                onChange={(e) => {
                  const val = e.target.value === '' ? 0 : parseInt(e.target.value);
                  setSettings({...settings, max_results_per_scrape: isNaN(val) ? 0 : val});
                }}
              />
            </div>
            <button 
              className="btn-base btn-solid w-full mt-auto" 
              onClick={saveSettings}
              disabled={savingSettings}
            >
              <Save size={16} /> {savingSettings ? 'Saving...' : 'Save Global Settings'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

const ActionsView = ({ 
  triggering, handleTriggerScraper, testing, testScraper, testOutput, 
  systemLogs, fetchLogs, fetchingLogs, setSystemLogs,
  customCity, setCustomCity, customJobTitle, setCustomJobTitle, customMaxResults, setCustomMaxResults
}) => (
  <div className="animate-slide-in">
    <h1 className="page-title">Scraper Actions</h1>
    
    <div className="grid grid-cols-3 gap-6 mb-8">
      <div className="stat-card">
        <h3 className="text-sm font-bold text-muted uppercase mb-4">Run Full Scrape</h3>
        <p className="text-xs text-muted mb-6">Executes the scraper for all enabled cities and roles.</p>
        <button 
          className="btn-base btn-solid w-full" 
          onClick={handleTriggerScraper}
          disabled={triggering}
        >
          {triggering ? <RefreshCw size={16} className="animate-spin" /> : <Play size={16} />}
          {triggering ? 'Scraping...' : 'Start Full Cycle'}
        </button>
      </div>

      <div className="stat-card">
        <h3 className="text-sm font-bold text-muted uppercase mb-4">Quick Test</h3>
        <p className="text-xs text-muted mb-6">Test a single platform to verify connection.</p>
        <button 
          className="btn-base btn-ghost w-full" 
          onClick={testScraper}
          disabled={testing}
        >
          {testing ? <RefreshCw size={16} className="animate-spin" /> : <Activity size={16} />}
          {testing ? 'Testing...' : 'Run Diagnostics'}
        </button>
      </div>

      <div className="stat-card">
        <h3 className="text-sm font-bold text-muted uppercase mb-4">System Utilities</h3>
        <div className="flex flex-col gap-2">
          <div className="flex gap-2">
            <button className="btn-base btn-ghost flex-1" onClick={async () => {
              if(window.confirm('Clean old records?')) await axios.delete('/api/db/cleanup');
            }}>Cleanup</button>
            <button className="btn-base btn-ghost flex-1 text-accent-danger border-accent-danger/20" onClick={async () => {
              if(window.confirm('WIPE ALL DATA?')) await axios.post('/api/db/truncate');
            }}>Truncate</button>
          </div>
        </div>
      </div>
    </div>

    {testOutput && (
      <div className="stat-card mb-8 border-accent-secondary/30">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-sm font-bold text-accent-secondary uppercase">Test Results</h3>
          <button className="text-muted hover:text-white" onClick={() => setTestOutput(null)}><LogOut size={16} /></button>
        </div>
        <pre className="text-[11px] font-mono bg-black/40 p-4 rounded-lg overflow-x-auto text-accent-secondary">
          {JSON.stringify(testOutput, null, 2)}
        </pre>
      </div>
    )}

    <div className="stat-card" style={{ flex: 1 }}>
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-sm font-bold text-muted uppercase">System Logs</h3>
        <div className="flex gap-2">
          <button className="btn-base btn-ghost" onClick={fetchLogs} disabled={fetchingLogs}>
            <RefreshCw size={14} className={fetchingLogs ? 'animate-spin' : ''} /> Refresh
          </button>
          <button className="btn-base btn-ghost" onClick={async () => {
            if(window.confirm('Clear logs?')) await axios.delete('/api/logs/clear');
            setSystemLogs('');
          }}>Clear</button>
        </div>
      </div>
      <div className="bg-black/40 rounded-xl p-6 font-mono text-xs line-height-relaxed h-[400px] overflow-y-auto border border-white/5">
        {systemLogs ? (
          systemLogs.split('\n').map((log, i) => (
            <div key={i} className="mb-1">
              <span className="text-muted mr-2">[{i}]</span>
              <span className={log.includes('ERROR') ? 'text-accent-danger' : log.includes('SUCCESS') ? 'text-accent-success' : 'text-text-secondary'}>
                {log}
              </span>
            </div>
          ))
        ) : (
          <div className="text-muted text-center py-20 italic">No logs found. Click refresh to load.</div>
        )}
      </div>
    </div>
  </div>
);

export default App;
