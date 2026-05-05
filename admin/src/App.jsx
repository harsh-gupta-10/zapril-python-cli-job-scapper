import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import { 
  Briefcase, MapPin, Building2, LayoutDashboard, LogOut, Search, 
  ExternalLink, Database, Calendar, RefreshCw, Download, 
  TrendingUp, Play, Settings, TerminalSquare, Plus, Trash2, Save,
  GripVertical, ToggleLeft, ToggleRight, Eye, EyeOff
} from 'lucide-react';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, 
  Tooltip, ResponsiveContainer, Cell 
} from 'recharts';

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(localStorage.getItem('adminToken') === 'authenticated-session-token');
  const [password, setPassword] = useState('');
  const [currentView, setCurrentView] = useState('dashboard'); // dashboard, config, actions

  const [jobs, setJobs] = useState([]);
  const [stats, setStats] = useState({ total_jobs: 0, cities: 0, companies: 0 });
  const [loading, setLoading] = useState(false);
  
  const [search, setSearch] = useState('');
  const [cityFilter, setCityFilter] = useState('All Cities');
  const [platformFilter, setPlatformFilter] = useState('All Platforms');
  const [dateFilter, setDateFilter] = useState('All Time'); // All Time, Today, Last 3 Days, Last Week

  // Settings State
  const [settings, setSettings] = useState({
    scraping_interval_hours: 24,
    lookback_period_hours: 48,
    max_results_per_scrape: 20,
    phased_scraping: true,
    jobs_per_phase: 3,
    cities_per_phase: 3,
    enabled_platforms: ["linkedin", "indeed", "glassdoor", "naukri", "foundit", "internshala", "google"]
  });
  const [savingSettings, setSavingSettings] = useState(false);

  // Custom Trigger State
  const [customCity, setCustomCity] = useState('');
  const [customJobTitle, setCustomJobTitle] = useState('');
  const [customMaxResults, setCustomMaxResults] = useState(10);
  const [customHoursOld, setCustomHoursOld] = useState(48);

  // Logs State
  const [systemLogs, setSystemLogs] = useState('');
  const [fetchingLogs, setFetchingLogs] = useState(false);

  // Config State
  const [citiesConfig, setCitiesConfig] = useState([]);
  const [jobTitlesConfig, setJobTitlesConfig] = useState([]);
  const [newCity, setNewCity] = useState('');
  const [newJobTitle, setNewJobTitle] = useState('');
  const [savingConfig, setSavingConfig] = useState(false);

  // Actions State
  const [triggering, setTriggering] = useState(false);
  const [testOutput, setTestOutput] = useState(null);
  const [testing, setTesting] = useState(false);

  // Selected Job for Modal
  const [selectedJob, setSelectedJob] = useState(null);

  useEffect(() => {
    if (isLoggedIn) {
      fetchData();
      fetchConfig();
    }
  }, [isLoggedIn]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [jobsRes, statsRes] = await Promise.all([
        axios.get('/api/jobs'),
        axios.get('/api/stats')
      ]);
      setJobs(Array.isArray(jobsRes.data) ? jobsRes.data : []);
      if (statsRes.data && !statsRes.data.error) {
        setStats(statsRes.data);
      }
    } catch (error) {
      console.error('Error fetching data:', error);
      if (error.response && error.response.status === 401) {
        handleLogout();
      }
    } finally {
      setLoading(false);
    }
  };

  const fetchConfig = async () => {
    try {
      const [citiesRes, jobTitlesRes, settingsRes] = await Promise.all([
        axios.get('/api/config/cities'),
        axios.get('/api/config/job-titles'),
        axios.get('/api/settings')
      ]);
      setCitiesConfig(citiesRes.data.cities || []);
      setJobTitlesConfig(jobTitlesRes.data.job_titles || []);
      if (settingsRes.data) {
        setSettings(settingsRes.data);
      }
    } catch (error) {
      console.error('Error fetching config:', error);
    }
  };

  const saveSettings = async () => {
    setSavingSettings(true);
    try {
      await axios.post('/api/settings', settings);
      alert('Settings saved successfully!');
    } catch (error) {
      alert('Failed to save settings');
    } finally {
      setSavingSettings(false);
    }
  };

  const handleCustomTrigger = async () => {
    if (!customCity || !customJobTitle) return alert("Please select both city and job role.");
    setTriggering(true);
    try {
      const cityVal = typeof customCity === 'object' ? customCity.name : customCity;
      const jobVal = typeof customJobTitle === 'object' ? customJobTitle.name : customJobTitle;
      
      await axios.post('/api/scraper/trigger-custom', { 
        location: cityVal, 
        search: jobVal,
        max_results: customMaxResults,
        hours_old: customHoursOld
      });
      alert(`Scraping started for ${jobVal} in ${cityVal}!`);
    } catch(err) {
      alert("Failed to start custom scrape");
    } finally {
      setTriggering(false);
    }
  };

  const fetchLogs = async () => {
    setFetchingLogs(true);
    try {
      const res = await axios.get('/api/logs');
      setSystemLogs(res.data.logs);
    } catch (err) {
      setSystemLogs("Failed to fetch logs");
    } finally {
      setFetchingLogs(false);
    }
  };

  const handleCleanup = async () => {
    if (!window.confirm("Are you sure you want to delete jobs older than 30 days?")) return;
    try {
      const res = await axios.delete('/api/db/cleanup?days=30');
      alert(`Successfully deleted ${res.data.deleted_count} old jobs.`);
      fetchData();
    } catch(err) {
      const msg = err.response?.data?.error || err.message;
      alert(`Cleanup Failed: ${msg}`);
    }
  };

  const handleTruncate = async () => {
    if (!window.confirm("CRITICAL ACTION: Are you sure you want to delete ALL jobs from the database? This cannot be undone.")) return;
    const secondConfirm = window.prompt("Type 'DELETE ALL' to confirm:");
    if (secondConfirm !== 'DELETE ALL') return;

    try {
      await axios.post('/api/db/truncate');
      alert('All jobs cleared successfully.');
      fetchData();
    } catch(err) {
      const msg = err.response?.data?.error || err.message;
      alert(`Truncate Failed: ${msg}`);
    }
  };

  const saveConfig = async (type) => {
    setSavingConfig(true);
    try {
      if (type === 'cities') {
        await axios.post('/api/config/cities', { cities: citiesConfig });
        alert('Cities saved successfully!');
      } else {
        await axios.post('/api/config/job-titles', { job_titles: jobTitlesConfig });
        alert('Job roles saved successfully!');
      }
    } catch (error) {
      alert(`Failed to save ${type}`);
    } finally {
      setSavingConfig(false);
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    try {
      const res = await axios.post('/api/auth/login', { password });
      localStorage.setItem('adminToken', res.data.token);
      setIsLoggedIn(true);
    } catch (error) {
      alert('Invalid password');
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('adminToken');
    setIsLoggedIn(false);
  };

  const handleTriggerScraper = async () => {
    if (!window.confirm('Triggering a full scrape might take several minutes. Continue?')) return;
    setTriggering(true);
    try {
      await axios.post('/api/run-scraper');
      alert('Scraper triggered successfully! It will run in the background.');
      fetchData();
    } catch (error) {
      alert('Failed to trigger scraper');
    } finally {
      setTriggering(false);
    }
  };

  const handleRunTest = async () => {
    setTesting(true);
    setTestOutput(null);
    try {
      const res = await axios.get('/api/run-test');
      setTestOutput(res.data);
    } catch (error) {
      setTestOutput({ error: error.message });
    } finally {
      setTesting(false);
    }
  };

  const handleClearLogs = async () => {
    if (!window.confirm("Are you sure you want to clear all system logs?")) return;
    try {
      await axios.delete('/api/logs/clear');
      setSystemLogs("Logs cleared.");
    } catch(err) {
      alert("Failed to clear logs.");
    }
  };

  const handleExport = (format = 'csv') => {
    if (format === 'csv') {
      window.open('/api/db/export', '_blank');
    } else {
      const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(jobs));
      const downloadAnchorNode = document.createElement('a');
      downloadAnchorNode.setAttribute("href",     dataStr);
      downloadAnchorNode.setAttribute("download", "jobs_export.json");
      document.body.appendChild(downloadAnchorNode);
      downloadAnchorNode.click();
      downloadAnchorNode.remove();
    }
  };

  const uniqueCities = useMemo(() => ['All Cities', ...new Set(jobs.map(j => j.location))], [jobs]);
  const uniquePlatforms = useMemo(() => ['All Platforms', ...new Set(jobs.map(j => j.source || j.site))], [jobs]);

  const filteredJobs = jobs.filter(job => {
    const matchesSearch = job.title.toLowerCase().includes(search.toLowerCase()) || 
                          job.company.toLowerCase().includes(search.toLowerCase());
    const matchesCity = cityFilter === 'All Cities' || job.location === cityFilter;
    const matchesPlatform = platformFilter === 'All Platforms' || (job.source === platformFilter || job.site === platformFilter);
    
    let matchesDate = true;
    if (dateFilter !== 'All Time') {
      const postDate = new Date(job.date_posted);
      const now = new Date();
      const diffDays = (now - postDate) / (1000 * 60 * 60 * 24);
      if (dateFilter === 'Today') matchesDate = diffDays <= 1;
      else if (dateFilter === 'Last 3 Days') matchesDate = diffDays <= 3;
      else if (dateFilter === 'Last Week') matchesDate = diffDays <= 7;
    }

    return matchesSearch && matchesCity && matchesPlatform && matchesDate;
  });

  const cityChartData = useMemo(() => {
    const counts = {};
    jobs.forEach(j => {
      counts[j.location] = (counts[j.location] || 0) + 1;
    });
    return Object.entries(counts)
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 8);
  }, [jobs]);

  const roleChartData = useMemo(() => {
    const counts = {};
    jobs.forEach(j => {
      // Simple grouping by keywords
      const title = j.title.toLowerCase();
      let group = 'Other';
      if (title.includes('software') || title.includes('developer') || title.includes('engineer')) group = 'Engineering';
      else if (title.includes('data')) group = 'Data';
      else if (title.includes('product') || title.includes('manager')) group = 'Management';
      else if (title.includes('design') || title.includes('ui') || title.includes('ux')) group = 'Design';
      else if (title.includes('analyst')) group = 'Analysis';
      
      counts[group] = (counts[group] || 0) + 1;
    });
    return Object.entries(counts)
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count);
  }, [jobs]);

  if (!isLoggedIn) {
    return (
      <div className="login-container">
        <div className="glass-card" style={{ maxWidth: '400px', width: '100%', textAlign: 'center' }}>
          <div className="flex justify-center mb-6">
            <div className="p-4 bg-purple-500/20 rounded-2xl">
              <LayoutDashboard size={40} className="text-purple-400" />
            </div>
          </div>
          <h1 style={{ fontSize: '1.5rem', marginBottom: '0.5rem' }}>Zapril Admin</h1>
          <p style={{ color: 'var(--text-muted)', marginBottom: '2rem' }}>Enter password to access dashboard</p>
          <form onSubmit={handleLogin}>
            <div className="input-group" style={{ marginBottom: '1.5rem' }}>
              <input 
                type="password" 
                placeholder="Admin Password" 
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoFocus
              />
            </div>
            <button type="submit" className="btn btn-primary w-full justify-center">Login</button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="app-container">
      {/* Sidebar */}
      <div className="sidebar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
          <div className="p-2 bg-purple-500/20 rounded-xl">
            <Briefcase size={24} className="text-purple-400" />
          </div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: '700' }}>Zapril Admin</h2>
        </div>
        
        <div className="sidebar-nav">
          <div 
            className={`nav-item ${currentView === 'dashboard' ? 'active' : ''}`}
            onClick={() => setCurrentView('dashboard')}
          >
            <LayoutDashboard size={18} /> Dashboard
          </div>
          <div 
            className={`nav-item ${currentView === 'config' ? 'active' : ''}`}
            onClick={() => setCurrentView('config')}
          >
            <Settings size={18} /> Configuration
          </div>
          <div 
            className={`nav-item ${currentView === 'actions' ? 'active' : ''}`}
            onClick={() => setCurrentView('actions')}
          >
            <TerminalSquare size={18} /> Scraper Actions
          </div>
        </div>

        <div style={{ marginTop: 'auto' }}>
          <div className="nav-item" onClick={handleLogout} style={{ color: '#ef4444' }}>
            <LogOut size={18} /> Logout
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="main-content">
        <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2.5rem', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h1 style={{ fontSize: '1.8rem', fontWeight: '800' }}>
              {currentView === 'dashboard' && 'Dashboard Overview'}
              {currentView === 'config' && 'Scraper Settings'}
              {currentView === 'actions' && 'Manual Triggers'}
            </h1>
            <p style={{ color: 'var(--text-muted)' }}>
              {currentView === 'dashboard' && `Monitoring ${jobs.length} listings in India`}
              {currentView === 'config' && 'Manage target cities and job roles'}
              {currentView === 'actions' && 'Run scraper instances and preview output'}
            </p>
          </div>
          
          {currentView === 'dashboard' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div className="dropdown">
              <button className="btn btn-secondary">
                <Download size={18} /> Export Data
              </button>
              <div className="dropdown-content">
                <a onClick={() => handleExport('csv')} style={{ cursor: 'pointer' }}>CSV Format</a>
                <a onClick={() => handleExport('json')} style={{ cursor: 'pointer' }}>JSON Format</a>
              </div>
            </div>
            <button className="btn btn-primary" onClick={() => fetchData()}>
              <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
            </button>
            <button className="btn btn-secondary" onClick={handleLogout} title="Logout">
              <LogOut size={18} />
            </button>
            </div>
          )}
        </header>

        {currentView === 'dashboard' && (
          <>
            <div className="stats-grid">
              <div className="glass-card stat-item">
                <h3>Total Job Listings</h3>
                <div className="value">{stats.total_jobs}</div>
              </div>
              <div className="glass-card stat-item">
                <h3>Active Cities</h3>
                <div className="value">{stats.cities}</div>
              </div>
              <div className="glass-card stat-item">
                <h3>Hiring Companies</h3>
                <div className="value">{stats.companies}</div>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '2rem' }} className="stats-grid">
              <div className="glass-card">
                <h3 style={{ marginBottom: '1.5rem', fontSize: '1rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <TrendingUp size={18} /> Top Cities Distribution
                </h3>
                <div style={{ width: '100%', height: '200px' }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={cityChartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                      <XAxis dataKey="name" stroke="var(--text-muted)" fontSize={10} tickLine={false} axisLine={false} />
                      <YAxis stroke="var(--text-muted)" fontSize={10} tickLine={false} axisLine={false} />
                      <Tooltip 
                        contentStyle={{ background: '#1a1a1c', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}
                        itemStyle={{ color: '#8b5cf6' }}
                      />
                      <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                        {cityChartData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={index % 2 === 0 ? '#8b5cf6' : '#4ade80'} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
              
              <div className="glass-card">
                <h3 style={{ marginBottom: '1.5rem', fontSize: '1rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Briefcase size={18} /> Category Breakdown
                </h3>
                <div style={{ width: '100%', height: '220px' }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={roleChartData} layout="vertical">
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" horizontal={false} />
                      <XAxis type="number" hide />
                      <YAxis dataKey="name" type="category" stroke="var(--text-muted)" fontSize={10} tickLine={false} axisLine={false} width={80} />
                      <Tooltip 
                        contentStyle={{ background: '#1a1a1c', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}
                        itemStyle={{ color: '#22d3ee' }}
                      />
                      <Bar dataKey="count" radius={[0, 4, 4, 0]} fill="#22d3ee" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>

            <div className="glass-card" style={{ padding: '1rem' }}>
              <div className="filters-bar">
                <div className="input-group">
                  <Search size={18} style={{ position: 'absolute', left: '0.85rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                  <input 
                    type="text" 
                    placeholder="Search by role or company..." 
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </div>
                <div className="input-group" style={{ flex: '0 0 150px' }}>
                  <select value={cityFilter} onChange={(e) => setCityFilter(e.target.value)}>
                    {uniqueCities.map(city => <option key={city} value={city}>{city}</option>)}
                  </select>
                </div>
                <div className="input-group" style={{ flex: '0 0 150px' }}>
                  <select value={platformFilter} onChange={(e) => setPlatformFilter(e.target.value)}>
                    {uniquePlatforms.map(p => <option key={p} value={p}>{p}</option>)}
                  </select>
                </div>
                <div className="input-group" style={{ flex: '0 0 150px' }}>
                  <select value={dateFilter} onChange={(e) => setDateFilter(e.target.value)}>
                    {['All Time', 'Today', 'Last 3 Days', 'Last Week'].map(d => <option key={d} value={d}>{d}</option>)}
                  </select>
                </div>
              </div>

              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>Job Title & Type</th>
                      <th>Company</th>
                      <th>Location</th>
                      <th>Salary Range</th>
                      <th>Date Posted</th>
                      <th>Platform</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredJobs.length > 0 ? filteredJobs.map((job, idx) => (
                      <tr key={idx}>
                        <td data-label="Title">
                          <div style={{ fontWeight: '700', color: 'var(--text-main)', fontSize: '1rem' }}>{job.title}</div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                            {job.job_type || 'Full-time'}
                          </div>
                        </td>
                        <td data-label="Company">
                          <div className="flex items-center gap-2">
                            <Building2 size={14} className="text-gray-500" />
                            {job.company}
                          </div>
                        </td>
                        <td data-label="Location">
                          <div className="flex items-center gap-2">
                            <MapPin size={14} className="text-gray-500" />
                            {job.location}
                          </div>
                        </td>
                        <td data-label="Salary">
                          <div style={{ color: '#4ade80', fontWeight: '600' }}>
                            {job.salary || 'Not disclosed'}
                          </div>
                        </td>
                        <td data-label="Date">
                          <div style={{ fontSize: '0.85rem' }}>
                            {(() => {
                              const d = new Date(job.date_posted);
                              return isNaN(d.getTime()) 
                                ? (job.date_posted || 'N/A') 
                                : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
                            })()}
                          </div>
                        </td>
                        <td data-label="Platform">
                          <span className="badge">
                            {job.source || job.site}
                          </span>
                        </td>
                        <td data-label="Link">
                          <div className="flex items-center gap-3">
                            <button 
                              onClick={() => setSelectedJob(job)}
                              className="flex items-center gap-1 text-cyan-400 hover:text-cyan-300 transition-colors bg-transparent border-none cursor-pointer"
                              title="View Description"
                            >
                              <Eye size={14} /> View
                            </button>
                            <a href={job.job_url} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-purple-400 hover:text-purple-300 transition-colors">
                              Apply <ExternalLink size={14} />
                            </a>
                          </div>
                        </td>
                      </tr>
                    )) : (
                      <tr>
                        <td colSpan="7" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                          No jobs found matching your filters.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}

        {currentView === 'config' && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))', gap: '1.5rem' }}>
            
            {/* Cities Config */}
            <div className="glass-card flex flex-col">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                <h3 style={{ fontSize: '1.25rem', fontWeight: '600' }}>Target Cities</h3>
                <span className="badge">{citiesConfig.length} cities</span>
              </div>
              
              <div className="input-group" style={{ marginBottom: '1rem', display: 'flex', gap: '0.5rem' }}>
                <input 
                  type="text" 
                  placeholder="Add a new city..." 
                  value={newCity}
                  onChange={(e) => setNewCity(e.target.value)}
                  style={{ paddingLeft: '1rem' }}
                  onKeyPress={(e) => {
                    if (e.key === 'Enter' && newCity.trim()) {
                      setCitiesConfig([...citiesConfig, newCity.trim()]);
                      setCitiesConfig([...citiesConfig, { name: newCity.trim(), enabled: true }]);
                      setNewCity('');
                    }
                  }}
                />
                <button 
                  className="btn btn-primary" 
                  onClick={() => {
                    if (newCity.trim()) {
                      setCitiesConfig([...citiesConfig, { name: newCity.trim(), enabled: true }]);
                      setNewCity('');
                    }
                  }}
                  style={{ borderRadius: '0 8px 8px 0' }}
                >
                  <Plus size={18} />
                </button>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '1.5rem', maxHeight: '400px', overflowY: 'auto' }}>
                {citiesConfig.map((city, index) => (
                  <div key={index} className="flex items-center gap-3 p-2 rounded-xl bg-white/5 border border-white/5 hover:border-purple-500/30 transition-colors">
                    <div className="flex flex-col gap-1">
                      <button 
                        onClick={() => {
                          if (index === 0) return;
                          const newCities = [...citiesConfig];
                          [newCities[index-1], newCities[index]] = [newCities[index], newCities[index-1]];
                          setCitiesConfig(newCities);
                        }}
                        className="p-1 hover:text-purple-400 disabled:opacity-30"
                        disabled={index === 0}
                      >
                        <ChevronUp size={14} />
                      </button>
                      <button 
                        onClick={() => {
                          if (index === citiesConfig.length - 1) return;
                          const newCities = [...citiesConfig];
                          [newCities[index+1], newCities[index]] = [newCities[index], newCities[index+1]];
                          setCitiesConfig(newCities);
                        }}
                        className="p-1 hover:text-purple-400 disabled:opacity-30"
                        disabled={index === citiesConfig.length - 1}
                      >
                        <ChevronDown size={14} />
                      </button>
                    </div>
                    
                    <div className="flex-1 font-medium" style={{ opacity: city.enabled ? 1 : 0.5, textDecoration: city.enabled ? 'none' : 'line-through' }}>
                      {city.name || city}
                    </div>
                    
                    <button 
                      onClick={() => {
                        const newCities = [...citiesConfig];
                        newCities[index].enabled = !newCities[index].enabled;
                        setCitiesConfig(newCities);
                      }}
                      className={`p-1 transition-colors ${city.enabled ? 'text-green-400' : 'text-gray-500'}`}
                      title={city.enabled ? "Disable City" : "Enable City"}
                    >
                      {city.enabled ? <ToggleRight size={22} /> : <ToggleLeft size={22} />}
                    </button>
                    
                    <button 
                      onClick={() => {
                        const newCities = citiesConfig.filter((_, i) => i !== index);
                        setCitiesConfig(newCities);
                      }}
                      className="p-1 text-red-400 hover:bg-red-500/10 rounded"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
              </div>

              <button 
                className="btn btn-primary w-full justify-center" 
                onClick={() => saveConfig('cities')}
                disabled={savingConfig}
              >
                <Save size={18} /> {savingConfig ? 'Saving...' : 'Save Cities'}
              </button>
            </div>

            {/* Job Roles Config */}
            <div className="glass-card flex flex-col">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                <h3 style={{ fontSize: '1.25rem', fontWeight: '600' }}>Target Job Roles</h3>
                <span className="badge">{jobTitlesConfig.length} roles</span>
              </div>
              
              <div className="input-group" style={{ marginBottom: '1rem', display: 'flex', gap: '0.5rem' }}>
                <input 
                  type="text" 
                  placeholder="Add a new job role..." 
                  value={newJobTitle}
                  onChange={(e) => setNewJobTitle(e.target.value)}
                  style={{ paddingLeft: '1rem' }}
                  onKeyPress={(e) => {
                    if (e.key === 'Enter' && newJobTitle.trim()) {
                      setJobTitlesConfig([...jobTitlesConfig, { name: newJobTitle.trim(), enabled: true }]);
                      setNewJobTitle('');
                    }
                  }}
                />
                <button 
                  className="btn btn-secondary" 
                  style={{ padding: '0.8rem' }}
                  onClick={() => {
                    if (newJobTitle.trim()) {
                      setJobTitlesConfig([...jobTitlesConfig, { name: newJobTitle.trim(), enabled: true }]);
                      setNewJobTitle('');
                    }
                  }}
                >
                  <Plus size={18} />
                </button>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '1.5rem', maxHeight: '400px', overflowY: 'auto' }}>
                {jobTitlesConfig.map((role, index) => (
                  <div key={index} className="flex items-center gap-3 p-2 rounded-xl bg-white/5 border border-white/5 hover:border-purple-500/30 transition-colors">
                    <div className="flex flex-col gap-1">
                      <button 
                        onClick={() => {
                          if (index === 0) return;
                          const newRoles = [...jobTitlesConfig];
                          [newRoles[index-1], newRoles[index]] = [newRoles[index], newRoles[index-1]];
                          setJobTitlesConfig(newRoles);
                        }}
                        className="p-1 hover:text-purple-400 disabled:opacity-30"
                        disabled={index === 0}
                      >
                        <ChevronUp size={14} />
                      </button>
                      <button 
                        onClick={() => {
                          if (index === jobTitlesConfig.length - 1) return;
                          const newRoles = [...jobTitlesConfig];
                          [newRoles[index+1], newRoles[index]] = [newRoles[index], newRoles[index+1]];
                          setJobTitlesConfig(newRoles);
                        }}
                        className="p-1 hover:text-purple-400 disabled:opacity-30"
                        disabled={index === jobTitlesConfig.length - 1}
                      >
                        <ChevronDown size={14} />
                      </button>
                    </div>
                    
                    <div className="flex-1 font-medium" style={{ opacity: role.enabled ? 1 : 0.5, textDecoration: role.enabled ? 'none' : 'line-through' }}>
                      {role.name || role}
                    </div>

                    <button 
                      onClick={() => {
                        const newRoles = [...jobTitlesConfig];
                        newRoles[index].enabled = !newRoles[index].enabled;
                        setJobTitlesConfig(newRoles);
                      }}
                      className={`p-1 transition-colors ${role.enabled ? 'text-green-400' : 'text-gray-500'}`}
                      title={role.enabled ? "Disable Role" : "Enable Role"}
                    >
                      {role.enabled ? <ToggleRight size={22} /> : <ToggleLeft size={22} />}
                    </button>

                    <button 
                      onClick={() => {
                        const newRoles = jobTitlesConfig.filter((_, i) => i !== index);
                        setJobTitlesConfig(newRoles);
                      }}
                      className="p-1 text-red-400 hover:bg-red-500/10 rounded"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
              </div>

              <button 
                className="btn btn-primary w-full justify-center" 
                onClick={() => saveConfig('job_titles')}
                disabled={savingConfig}
              >
                <Save size={18} /> {savingConfig ? 'Saving...' : 'Save Job Roles'}
              </button>
            </div>

            {/* Advanced Settings */}
            <div className="glass-card flex flex-col" style={{ gridColumn: '1 / -1' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                <h3 style={{ fontSize: '1.25rem', fontWeight: '600' }}>Advanced Settings</h3>
              </div>
              
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1.5rem', marginBottom: '1.5rem' }}>
                <div className="input-group">
                  <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>Scraping Interval (Hours)</label>
                  <input 
                    type="number" 
                    value={settings.scraping_interval_hours}
                    onChange={(e) => setSettings({...settings, scraping_interval_hours: parseInt(e.target.value) || 24})}
                  />
                </div>
                <div className="input-group">
                  <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>Lookback Period (Hours)</label>
                  <input 
                    type="number" 
                    value={settings.lookback_period_hours}
                    onChange={(e) => setSettings({...settings, lookback_period_hours: parseInt(e.target.value) || 24})}
                  />
                </div>
                <div className="input-group">
                  <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>Max Results Per Combination</label>
                  <input 
                    type="number" 
                    value={settings.max_results_per_scrape}
                    onChange={(e) => setSettings({...settings, max_results_per_scrape: parseInt(e.target.value) || 10})}
                  />
                </div>
              </div>

              <div style={{ padding: '1.25rem', background: 'rgba(139, 92, 246, 0.05)', border: '1px solid rgba(139, 92, 246, 0.2)', borderRadius: '12px', marginBottom: '1.5rem' }}>
                <h4 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem', color: '#a78bfa' }}>
                  <TrendingUp size={18} /> Phased Scraping Strategy
                </h4>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1.5rem' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', cursor: 'pointer' }}>
                    <input 
                      type="checkbox" 
                      checked={settings.phased_scraping}
                      onChange={(e) => setSettings({...settings, phased_scraping: e.target.checked})}
                    />
                    <span>Enable Phased Execution</span>
                  </label>
                  <div className="input-group">
                    <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>Jobs per phase</label>
                    <input 
                      type="number" 
                      value={settings.jobs_per_phase}
                      onChange={(e) => setSettings({...settings, jobs_per_phase: parseInt(e.target.value) || 3})}
                      disabled={!settings.phased_scraping}
                      style={{ padding: '0.5rem' }}
                    />
                  </div>
                  <div className="input-group">
                    <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>Cities per phase</label>
                    <input 
                      type="number" 
                      value={settings.cities_per_phase}
                      onChange={(e) => setSettings({...settings, cities_per_phase: parseInt(e.target.value) || 3})}
                      disabled={!settings.phased_scraping}
                      style={{ padding: '0.5rem' }}
                    />
                  </div>
                </div>
                <p style={{ marginTop: '0.75rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Phased execution processes a small subset of job/city combinations per run to prevent server overload and anti-bot detection.
                </p>
              </div>

              <div style={{ marginBottom: '1.5rem' }}>
                <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>Enabled Platforms</label>
                <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                  {["linkedin", "indeed", "glassdoor", "naukri", "foundit", "internshala", "google"].map(platform => (
                    <label key={platform} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                      <input 
                        type="checkbox" 
                        checked={settings.enabled_platforms?.includes(platform)}
                        onChange={(e) => {
                          const enabled = e.target.checked 
                            ? [...(settings.enabled_platforms || []), platform] 
                            : (settings.enabled_platforms || []).filter(p => p !== platform);
                          setSettings({...settings, enabled_platforms: enabled});
                        }}
                      />
                      <span style={{ textTransform: 'capitalize' }}>{platform}</span>
                    </label>
                  ))}
                </div>
              </div>

              <button 
                className="btn btn-primary w-full justify-center" 
                onClick={saveSettings}
                disabled={savingSettings}
              >
                <Save size={18} /> {savingSettings ? 'Saving...' : 'Save Settings'}
              </button>
            </div>

          </div>
        )}

        {currentView === 'actions' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <div className="glass-card">
              <h3 style={{ fontSize: '1.25rem', fontWeight: '600', marginBottom: '1rem' }}>Run Full Scraper</h3>
              <p style={{ color: 'var(--text-muted)', marginBottom: '1.5rem' }}>
                Manually trigger the background scraping job. It will iterate through all configured cities and job roles. 
                Data will be inserted directly into the database.
              </p>
              <button className="btn btn-primary" onClick={handleTriggerScraper} disabled={triggering}>
                <Play size={18} /> {triggering ? 'Running in Background...' : 'Trigger Full Scrape'}
              </button>
            </div>

            <div className="glass-card">
              <h3 style={{ fontSize: '1.25rem', fontWeight: '600', marginBottom: '1rem' }}>Test / Preview Scraper</h3>
              <p style={{ color: 'var(--text-muted)', marginBottom: '1.5rem' }}>
                Run a small test scrape (Software Engineer in Mumbai, max 5 results) and view the logs in real-time. This helps verify if the scraping logic and database connections are working.
              </p>
              <button className="btn btn-secondary" onClick={handleRunTest} disabled={testing}>
                <TerminalSquare size={18} /> {testing ? 'Running Test...' : 'Run Preview Test'}
              </button>

              {testOutput && (
                <div style={{ marginTop: '1.5rem', background: '#000', padding: '1rem', borderRadius: '8px', border: '1px solid #333', overflowX: 'auto' }}>
                  <div style={{ marginBottom: '0.5rem', color: testOutput.returncode === 0 ? '#4ade80' : '#ef4444', fontWeight: 'bold' }}>
                    Status: {testOutput.error ? 'Error' : (testOutput.returncode === 0 ? 'Success' : `Failed (Exit Code ${testOutput.returncode})`)}
                  </div>
                  {testOutput.error && (
                     <pre style={{ color: '#ef4444', fontSize: '0.85rem' }}>{testOutput.error}</pre>
                  )}
                  {testOutput.stdout && (
                    <div style={{ marginBottom: '1rem' }}>
                      <div style={{ color: '#9ca3af', fontSize: '0.75rem', marginBottom: '0.25rem', textTransform: 'uppercase' }}>Standard Output</div>
                      <pre style={{ color: '#e5e7eb', fontSize: '0.85rem', whiteSpace: 'pre-wrap' }}>{testOutput.stdout}</pre>
                    </div>
                  )}
                  {testOutput.stderr && (
                    <div>
                      <div style={{ color: '#9ca3af', fontSize: '0.75rem', marginBottom: '0.25rem', textTransform: 'uppercase' }}>Standard Error</div>
                      <pre style={{ color: '#ef4444', fontSize: '0.85rem', whiteSpace: 'pre-wrap' }}>{testOutput.stderr}</pre>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Mini Custom Trigger */}
            <div className="glass-card">
              <h3 style={{ fontSize: '1.25rem', fontWeight: '600', marginBottom: '1rem' }}>Mini Target Trigger</h3>
              <p style={{ color: 'var(--text-muted)', marginBottom: '1.5rem' }}>
                Need to instantly scrape a specific combination? Select a city, job role, and parameters below to trigger a background job just for that pair.
              </p>
              <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
                <div className="input-group" style={{ flex: 1, minWidth: '200px' }}>
                  <select 
                    value={typeof customCity === 'object' ? customCity.name : customCity} 
                    onChange={e => setCustomCity(e.target.value)}
                  >
                    <option value="" disabled>Select City</option>
                    {citiesConfig.map((city, i) => (
                      <option key={i} value={city.name || city}>
                        {city.name || city}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="input-group" style={{ flex: 1, minWidth: '200px' }}>
                  <select 
                    value={typeof customJobTitle === 'object' ? customJobTitle.name : customJobTitle} 
                    onChange={e => setCustomJobTitle(e.target.value)}
                  >
                    <option value="" disabled>Select Job Role</option>
                    {jobTitlesConfig.map((role, i) => (
                      <option key={i} value={role.name || role}>
                        {role.name || role}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="input-group" style={{ flex: '0 0 120px' }}>
                  <input 
                    type="number" 
                    placeholder="Max Results"
                    title="Max Results per Platform"
                    value={customMaxResults}
                    onChange={e => setCustomMaxResults(parseInt(e.target.value) || 10)}
                  />
                </div>
                <div className="input-group" style={{ flex: '0 0 120px' }}>
                  <input 
                    type="number" 
                    placeholder="Hours Old"
                    title="Lookback Period (Hours)"
                    value={customHoursOld}
                    onChange={e => setCustomHoursOld(parseInt(e.target.value) || 48)}
                  />
                </div>
                <button className="btn btn-primary" onClick={handleCustomTrigger} disabled={triggering} style={{ flex: '0 0 auto', padding: '0 1.5rem' }}>
                  <Play size={18} /> {triggering ? 'Running...' : 'Run Custom Scrape'}
                </button>
              </div>
            </div>

            {/* Database & Logs Utilities */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.5rem' }}>
              <div className="glass-card">
                <h3 style={{ fontSize: '1.25rem', fontWeight: '600', marginBottom: '1rem' }}>Database Maintenance</h3>
                <p style={{ color: 'var(--text-muted)', marginBottom: '1.5rem' }}>
                  Clear outdated job postings from the database to save space and improve performance.
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  <button className="btn btn-secondary w-full justify-center" onClick={handleCleanup}>
                    <Trash2 size={18} /> Clean Jobs Older Than 30 Days
                  </button>
                  <button 
                    className="btn w-full justify-center" 
                    onClick={handleTruncate}
                    style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', border: '1px solid rgba(239, 68, 68, 0.2)' }}
                  >
                    <Trash2 size={18} /> Clear All Jobs (Truncate)
                  </button>
                </div>
              </div>
              
              <div className="glass-card">
                <h3 style={{ fontSize: '1.25rem', fontWeight: '600', marginBottom: '1rem' }}>System Logs</h3>
                <p style={{ color: 'var(--text-muted)', marginBottom: '1.5rem' }}>
                  View the recent background task logs for troubleshooting.
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  <button className="btn btn-secondary w-full justify-center" onClick={fetchLogs} disabled={fetchingLogs}>
                    <TerminalSquare size={18} /> {fetchingLogs ? 'Loading...' : 'View Recent Logs'}
                  </button>
                  <button className="btn w-full justify-center" onClick={handleClearLogs} style={{ background: 'rgba(239, 68, 68, 0.05)', color: '#ef4444', border: '1px solid rgba(239, 68, 68, 0.1)' }}>
                    <Trash2 size={16} /> Clear Logs
                  </button>
                </div>
              </div>
            </div>

            {/* Log Viewer Container */}
            {systemLogs && (
              <div className="glass-card" style={{ background: '#000' }}>
                <h4 style={{ color: '#9ca3af', marginBottom: '1rem', textTransform: 'uppercase', fontSize: '0.85rem' }}>Live System Logs (Last 100 Lines)</h4>
                <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
                  <pre style={{ color: '#4ade80', fontSize: '0.85rem', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                    {systemLogs}
                  </pre>
                </div>
              </div>
            )}
            
          </div>
        )}

      </div>

      {/* Job Description Modal */}
      {selectedJob && (
        <div className="modal-overlay" onClick={() => setSelectedJob(null)}>
          <div className="glass-card modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: '800px', width: '90%', maxHeight: '85vh', overflowY: 'auto' }}>
            <div className="flex justify-between items-start mb-6">
              <div>
                <h2 style={{ fontSize: '1.5rem', fontWeight: '800', color: 'var(--text-main)' }}>{selectedJob.title}</h2>
                <div className="flex items-center gap-4 mt-2">
                  <div className="flex items-center gap-1 text-purple-400">
                    <Building2 size={16} /> {selectedJob.company}
                  </div>
                  <div className="flex items-center gap-1 text-muted">
                    <MapPin size={16} /> {selectedJob.location}
                  </div>
                  <span className="badge">{selectedJob.source || selectedJob.site}</span>
                </div>
              </div>
              <button 
                onClick={() => setSelectedJob(null)}
                className="p-2 hover:bg-white/10 rounded-full transition-colors"
                style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
              >
                <Plus size={24} style={{ transform: 'rotate(45deg)' }} />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-4 mb-8">
              <div className="p-4 bg-white/5 rounded-xl border border-white/10">
                <div className="text-xs uppercase text-muted mb-1">Salary Range</div>
                <div className="text-green-400 font-bold">{selectedJob.salary || 'Not Disclosed'}</div>
              </div>
              <div className="p-4 bg-white/5 rounded-xl border border-white/10">
                <div className="text-xs uppercase text-muted mb-1">Date Posted</div>
                <div className="text-main font-bold">
                  {(() => {
                    const d = new Date(selectedJob.date_posted);
                    return isNaN(d.getTime()) 
                      ? (selectedJob.date_posted || 'Recently') 
                      : d.toLocaleDateString(undefined, { month: 'long', day: 'numeric', year: 'numeric' });
                  })()}
                </div>
              </div>
            </div>

            <div className="mb-8">
              <h3 className="text-sm uppercase text-muted mb-4 border-b border-white/10 pb-2">Job Description</h3>
              <div 
                className="description-text"
                style={{ 
                  color: 'var(--text-main)', 
                  lineHeight: '1.6', 
                  fontSize: '0.95rem',
                  whiteSpace: 'pre-wrap'
                }}
                dangerouslySetInnerHTML={{ __html: selectedJob.description || 'No description available for this listing.' }}
              />
            </div>

            <div className="flex gap-4 sticky bottom-0 bg-black/80 backdrop-blur-md p-4 -mx-6 -mb-6 border-t border-white/10">
              <a 
                href={selectedJob.job_url} 
                target="_blank" 
                rel="noreferrer" 
                className="btn btn-primary flex-1 justify-center"
              >
                Apply on {selectedJob.source || selectedJob.site} <ExternalLink size={18} />
              </a>
              <button onClick={() => setSelectedJob(null)} className="btn btn-secondary">
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
