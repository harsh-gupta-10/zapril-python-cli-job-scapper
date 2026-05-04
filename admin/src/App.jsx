import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  Briefcase, 
  MapPin, 
  Building2, 
  LayoutDashboard, 
  LogOut, 
  Search, 
  ExternalLink, 
  Database,
  Calendar,
  AlertCircle,
  Loader2
} from 'lucide-react';

const API_BASE = window.location.origin === 'http://localhost:5173' 
  ? 'http://localhost:8080' 
  : '';

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(localStorage.getItem('adminToken') === 'authenticated-session-token');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [jobs, setJobs] = useState([]);
  const [stats, setStats] = useState({ total_jobs: 0, cities: 0, companies: 0 });
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    if (isLoggedIn) {
      fetchData();
    }
  }, [isLoggedIn]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [jobsRes, statsRes] = await Promise.all([
        axios.get(`${API_BASE}/api/jobs`),
        axios.get(`${API_BASE}/api/stats`)
      ]);
      setJobs(jobsRes.data);
      setStats(statsRes.data);
    } catch (err) {
      console.error('Fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await axios.post(`${API_BASE}/api/auth/login`, { password });
      localStorage.setItem('adminToken', res.data.token);
      setIsLoggedIn(true);
    } catch (err) {
      setError(err.response?.data?.error || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('adminToken');
    setIsLoggedIn(false);
  };

  const filteredJobs = jobs.filter(job => 
    job.title?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    job.company?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    job.location?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (!isLoggedIn) {
    return (
      <div className="login-screen">
        <div className="login-card glass animate-fade">
          <div className="stat-icon" style={{ margin: '0 auto 1.5rem', width: '64px', height: '64px' }}>
            <Briefcase size={32} />
          </div>
          <h1>Zapril Admin</h1>
          <p style={{ color: 'var(--text-muted)', marginTop: '0.5rem' }}>Secure Dashboard Access</p>
          
          <form onSubmit={handleLogin}>
            <div className="input-group">
              <label>Administrator Password</label>
              <input 
                type="password" 
                value={password} 
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
              />
            </div>
            {error && <div className="error-msg flex items-center gap-2"><AlertCircle size={16} /> {error}</div>}
            <button type="submit" disabled={loading}>
              {loading ? <Loader2 className="animate-spin inline mr-2" /> : 'Login to Dashboard'}
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="admin-container animate-fade">
      {/* Header */}
      <div className="flex justify-between items-center mb-8 glass" style={{ padding: '1rem 2rem' }}>
        <div className="flex items-center gap-3">
          <div className="stat-icon" style={{ width: '40px', height: '40px' }}>
            <Database size={20} />
          </div>
          <div>
            <h2 style={{ fontSize: '1.2rem', fontWeight: '700' }}>Zapril Console</h2>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Database Management & Monitoring</p>
          </div>
        </div>
        <button onClick={handleLogout} className="flex items-center gap-2" style={{ width: 'auto', background: 'rgba(255, 82, 82, 0.1)', color: '#ff5252', padding: '0.5rem 1rem', border: '1px solid rgba(255, 82, 82, 0.2)' }}>
          <LogOut size={16} /> Logout
        </button>
      </div>

      {/* Stats */}
      <div className="dashboard-grid">
        <div className="stat-card glass">
          <div className="stat-icon">
            <Briefcase size={24} />
          </div>
          <div className="stat-info">
            <h3>Total Job Postings</h3>
            <p>{stats.total_jobs.toLocaleString()}</p>
          </div>
        </div>
        <div className="stat-card glass">
          <div className="stat-icon" style={{ color: 'var(--accent-secondary)', background: 'rgba(0, 229, 255, 0.1)' }}>
            <MapPin size={24} />
          </div>
          <div className="stat-info">
            <h3>Cities Covered</h3>
            <p>{stats.cities}</p>
          </div>
        </div>
        <div className="stat-card glass">
          <div className="stat-icon" style={{ color: '#ffbd2e', background: 'rgba(255, 189, 46, 0.1)' }}>
            <Building2 size={24} />
          </div>
          <div className="stat-info">
            <h3>Companies Listed</h3>
            <p>{stats.companies}</p>
          </div>
        </div>
      </div>

      {/* Controls & Table */}
      <div className="glass" style={{ padding: '1.5rem' }}>
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-6">
          <div className="relative w-full md:w-96">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
            <input 
              type="text" 
              placeholder="Search by title, company, or city..." 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{ paddingLeft: '2.8rem' }}
            />
          </div>
          <div className="flex items-center gap-3">
             <button onClick={fetchData} className="flex items-center gap-2" style={{ width: 'auto', background: 'rgba(255, 255, 255, 0.05)', marginTop: 0 }}>
               Refresh Data
             </button>
          </div>
        </div>

        <div className="table-container">
          {loading ? (
            <div className="flex flex-col items-center justify-center p-20 gap-4">
              <Loader2 className="animate-spin text-purple-500" size={48} />
              <p className="text-muted">Querying Cloud SQL Database...</p>
            </div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Job Title & Type</th>
                  <th>Company</th>
                  <th>Location</th>
                  <th>Salary Range</th>
                  <th>Date Posted</th>
                  <th>Description</th>
                  <th>Platform</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredJobs.length > 0 ? filteredJobs.map((job, idx) => (
                  <tr key={idx}>
                    <td>
                      <div style={{ fontWeight: '700', color: 'var(--text-main)', fontSize: '1rem' }}>{job.title}</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                        {job.job_type || 'Full-time'}
                      </div>
                    </td>
                    <td>
                      <div className="flex items-center gap-2">
                        <Building2 size={14} className="text-gray-500" />
                        {job.company}
                      </div>
                    </td>
                    <td>
                      <div className="flex items-center gap-2">
                        <MapPin size={14} className="text-gray-500" />
                        {job.location}
                      </div>
                    </td>
                    <td>
                      <div style={{ color: '#4ade80', fontWeight: '600' }}>
                        {job.salary || 'Not disclosed'}
                      </div>
                    </td>
                    <td>
                      <div style={{ fontSize: '0.85rem' }}>
                        {new Date(job.date_posted).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                      </div>
                    </td>
                    <td>
                      <div style={{ 
                        fontSize: '0.75rem', 
                        color: 'var(--text-muted)', 
                        maxWidth: '200px', 
                        whiteSpace: 'nowrap', 
                        overflow: 'hidden', 
                        textOverflow: 'ellipsis' 
                      }} title={job.description}>
                        {job.description || 'No description available'}
                      </div>
                    </td>
                    <td>
                      <span className="badge" style={{ 
                        background: 'rgba(255, 255, 255, 0.05)', 
                        color: 'white', 
                        border: '1px solid rgba(255,255,255,0.1)',
                        textTransform: 'uppercase',
                        letterSpacing: '1px'
                      }}>
                        {job.site || job.source}
                      </span>
                    </td>
                    <td>
                      <a href={job.job_url} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-purple-400 hover:text-purple-300 transition-colors">
                         View <ExternalLink size={14} />
                      </a>
                    </td>
                  </tr>
                )) : (
                  <tr>
                    <td colSpan="6" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                      No jobs found matching your search criteria.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
