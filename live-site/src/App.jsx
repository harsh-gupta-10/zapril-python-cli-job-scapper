import { useCallback, useEffect, useMemo, useState } from 'react';
import { createClient } from '@supabase/supabase-js';
import { useLocation, useNavigate } from 'react-router-dom';
import { ArrowRight, Briefcase, Building2, Calendar, CircleDollarSign, MapPin, Search, Sparkles, X } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;
const supabase = createClient(supabaseUrl, supabaseAnonKey);

const JOBS_PER_PAGE = 50;

const LOCATION_GROUPS = {
  Remote: ['Remote', 'Work from home', 'WFH', 'Anywhere'],
  Maharashtra: ['Maharashtra', 'Mumbai', 'Pune', 'Nagpur', 'Nashik', 'Thane', 'Navi Mumbai', 'Andheri', 'Bandra', 'Borivali', 'Dadar', 'Goregaon', 'Juhu', 'Kurla', 'Malad', 'Powai', 'Vashi', 'Worli', 'Hinjewadi', 'Kharadi', 'Baner', 'Aundh', 'Viman Nagar', 'Magarpatta', 'Kalyani Nagar', 'Wakad'],
  Mumbai: ['Mumbai', 'Andheri', 'Bandra', 'Borivali', 'Dadar', 'Goregaon', 'Juhu', 'Kurla', 'Malad', 'Navi Mumbai', 'Thane', 'Powai', 'Vashi', 'Worli'],
  'Delhi NCR': ['Delhi', 'New Delhi', 'Gurgaon', 'Gurugram', 'Noida', 'Faridabad', 'Ghaziabad'],
  Bangalore: ['Bangalore', 'Bengaluru', 'Koramangala', 'Indiranagar', 'Whitefield', 'Electronic City', 'HSR Layout', 'Jayanagar', 'JP Nagar', 'Bellandur', 'Marathahalli'],
  Hyderabad: ['Hyderabad', 'Secunderabad', 'HITEC City', 'Gachibowli', 'Madhapur', 'Banjara Hills', 'Jubilee Hills', 'Kondapur'],
  Chennai: ['Chennai', 'Adyar', 'Anna Nagar', 'T Nagar', 'Velachery', 'Guindy', 'OMR', 'Porur', 'Tambaram'],
  Pune: ['Pune', 'Hinjewadi', 'Kharadi', 'Baner', 'Aundh', 'Viman Nagar', 'Magarpatta', 'Kalyani Nagar', 'Wakad'],
};

const formatDate = (dateStr, createdAt) => {
  let date;
  if (!dateStr || dateStr.toLowerCase() === 'nan') {
    date = new Date(createdAt);
  } else {
    date = new Date(dateStr);
    if (Number.isNaN(date.getTime())) {
      date = new Date(createdAt);
    }
  }

  const now = new Date();
  const diffHours = (now - date) / (1000 * 60 * 60);
  if (diffHours <= 24) {
    return 'Today';
  }

  return formatDistanceToNow(date, { addSuffix: true });
};

const App = () => {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [locationFilter, setLocationFilter] = useState('');
  const [aiOnly, setAiOnly] = useState(false);
  const [appliedSearchTerm, setAppliedSearchTerm] = useState('');
  const [appliedLocationFilter, setAppliedLocationFilter] = useState('');
  const [selectedJob, setSelectedJob] = useState(null);
  const [locations, setLocations] = useState([]);
  const [page, setPage] = useState(1);
  const [totalJobs, setTotalJobs] = useState(0);

  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    if (location.pathname === '/ai-improved') {
      setAiOnly(true);
    } else {
      setAiOnly(false);
    }
    setPage(1);
  }, [location.pathname]);

  const fetchJobs = useCallback(async (search = '', loc = '', pageNum = 1, isAiOnly = false) => {
    setLoading(true);
    try {
      let query = supabase.from('jobs').select('*', { count: 'exact' }).order('date_posted', { ascending: false });

      if (isAiOnly) {
        // More robust check: not null, not '[]', and has at least one skill or takeaway
        query = query.not('skills', 'is', null).neq('skills', '[]');
      }

      if (search) {
        query = query.or(`title.ilike.%${search}%,company.ilike.%${search}%`);
      }

      if (loc) {
        const matchingGroupKey = Object.keys(LOCATION_GROUPS).find(
          (key) => key.toLowerCase() === loc.toLowerCase()
        );

        if (matchingGroupKey) {
          const subLocations = LOCATION_GROUPS[matchingGroupKey];
          const orQuery = subLocations.map((subLoc) => `location.ilike.%${subLoc}%`).join(',');
          query = query.or(orQuery);
        } else {
          query = query.ilike('location', `%${loc}%`);
        }
      }

      const from = (pageNum - 1) * JOBS_PER_PAGE;
      const to = from + JOBS_PER_PAGE - 1;
      const { data, error, count } = await query.range(from, to);

      if (error) {
        throw error;
      }

      setJobs(data || []);
      if (count !== null) {
        setTotalJobs(count);
      }
    } catch (error) {
      console.error('Error fetching jobs:', error.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchLocations = useCallback(async () => {
    try {
      const { data, error } = await supabase.from('jobs').select('location').not('location', 'is', null);

      if (error) {
        throw error;
      }

      const uniqueLocations = [...new Set(
        (data || [])
          .map((item) => item.location?.split(',')[0]?.trim())
          .filter(Boolean)
      )].sort((a, b) => a.localeCompare(b));

      const filteredLocations = uniqueLocations.filter(
        (loc) => !Object.keys(LOCATION_GROUPS).some((group) => group.toLowerCase() === loc.toLowerCase())
      );

      setLocations(filteredLocations);
    } catch (error) {
      console.error('Error fetching locations:', error.message);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchLocations();
  }, [fetchLocations]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchJobs(appliedSearchTerm, appliedLocationFilter, page, aiOnly);
  }, [appliedSearchTerm, appliedLocationFilter, fetchJobs, page, aiOnly]);

  useEffect(() => {
    if (!selectedJob) {
      return undefined;
    }

    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setSelectedJob(null);
      }
    };

    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [selectedJob]);

  const handleSearch = (event) => {
    event.preventDefault();
    const normalizedSearch = searchTerm.trim();

    setAppliedSearchTerm(normalizedSearch);
    setAppliedLocationFilter(locationFilter);

    if (page !== 1) {
      setPage(1);
      return;
    }

    fetchJobs(normalizedSearch, locationFilter, 1, aiOnly);
  };

  const clearFilters = () => {
    setSearchTerm('');
    setLocationFilter('');
    setAppliedSearchTerm('');
    setAiOnly(false);
    navigate('/');
    fetchJobs('', '', 1, false);
  };

  const totalPages = useMemo(() => Math.max(1, Math.ceil(totalJobs / JOBS_PER_PAGE)), [totalJobs]);

  const activeFilterLabel = useMemo(() => {
    const baseLabel = aiOnly ? 'AI-Improved' : 'Latest';
    
    if (!appliedSearchTerm && !appliedLocationFilter) {
      return `${baseLabel} opportunities`;
    }

    if (appliedSearchTerm && appliedLocationFilter) {
      return `${baseLabel} results for "${appliedSearchTerm}" in ${appliedLocationFilter}`;
    }

    if (appliedSearchTerm) {
      return `${baseLabel} results for "${appliedSearchTerm}"`;
    }

    return `${baseLabel} results in ${appliedLocationFilter}`;
  }, [appliedLocationFilter, appliedSearchTerm, aiOnly]);

  return (
    <div className="app">
      <header className="header">
        <div className="container nav">
          <a href="/" className="logo">
            <span className="logo-icon" aria-hidden="true">
              <Briefcase size={18} color="white" />
            </span>
            <span className="logo-wordmark">zapril</span>
          </a>
          <div className="header-actions">
            <button 
              className={`ai-toggle-pill ${aiOnly ? 'active' : ''}`}
              onClick={() => {
                const newValue = !aiOnly;
                setAiOnly(newValue);
                navigate(newValue ? '/ai-improved' : '/');
              }}
            >
              <Sparkles size={14} />
              AI Enhanced
            </button>
            <div className="job-count-pill">{totalJobs.toLocaleString()} active listings</div>
          </div>
        </div>
      </header>

      <main className="main-content">
        <section className="hero">
          <div className="container">
            <div className="hero-eyebrow">AI & Software jobs in India</div>
            <h1>Search jobs and filter by role or location</h1>
            <p>Use the filters below to quickly find relevant openings and open detailed role descriptions.</p>

            <form className="search-container" onSubmit={handleSearch}>
              <div className="search-input-group">
                <label htmlFor="search-input" className="sr-only">
                  Search by title, company, or keyword
                </label>
                <Search size={18} className="input-icon" aria-hidden="true" />
                <input
                  id="search-input"
                  type="text"
                  placeholder="Job title, keywords, or company"
                  className="search-input"
                  value={searchTerm}
                  onChange={(event) => setSearchTerm(event.target.value)}
                  autoComplete="off"
                />
              </div>

              <div className="search-input-group">
                <label htmlFor="location-filter" className="sr-only">
                  Filter by location
                </label>
                <MapPin size={18} className="input-icon" aria-hidden="true" />
                <select
                  id="location-filter"
                  className="search-input"
                  value={locationFilter}
                  onChange={(event) => setLocationFilter(event.target.value)}
                >
                  <option value="">All Locations</option>
                  <optgroup label="Major Regions & Cities">
                    {Object.keys(LOCATION_GROUPS).map((locationName) => (
                      <option key={locationName} value={locationName}>
                        {locationName}
                      </option>
                    ))}
                  </optgroup>
                  <optgroup label="Specific Areas">
                    {locations.map((locationName) => (
                      <option key={locationName} value={locationName}>
                        {locationName}
                      </option>
                    ))}
                  </optgroup>
                </select>
              </div>

              <button type="submit" className="search-btn" disabled={loading}>
                {loading ? 'Searching...' : 'Find jobs'}
              </button>
            </form>
          </div>
        </section>

        <section className="container results-section" aria-live="polite">
          <div className="results-header">
            <div>
              <h2>{activeFilterLabel}</h2>
              <p className="results-subtitle">
                {totalJobs.toLocaleString()} jobs found · page {page} of {totalPages}
              </p>
            </div>

            {(appliedSearchTerm || appliedLocationFilter) && (
              <button type="button" className="secondary-btn" onClick={clearFilters}>
                Clear filters
              </button>
            )}
          </div>

          {loading ? (
            <div className="loading-state">
              <div className="loading-spinner"></div>
              <span>Loading roles...</span>
            </div>
          ) : (
            <>
              {jobs.length > 0 && (
                <div className="job-grid">
                  {jobs.map((job) => (
                    <button key={job.id} type="button" className="job-card" onClick={() => setSelectedJob(job)}>
                      <div className="job-source">{job.source}</div>
                      <h3 className="job-title">{job.title}</h3>
                      <div className="job-company">
                        <Building2 size={16} aria-hidden="true" />
                        <span>{job.company}</span>
                      </div>
                      <div className="job-meta">
                        <div className="meta-item">
                          <MapPin size={14} aria-hidden="true" />
                          <span>{job.location || 'Location unavailable'}</span>
                        </div>
                        <div className="meta-item">
                          <Calendar size={14} aria-hidden="true" />
                          <span>{formatDate(job.date_posted, job.created_at)}</span>
                        </div>
                        {((job.salary && job.salary !== 'nan') || (job.salary_expectation && job.salary_expectation !== 'Not specified')) && (
                          <div className="meta-item salary-meta">
                            <CircleDollarSign size={14} aria-hidden="true" />
                            <span>{job.salary_expectation && job.salary_expectation !== 'Not specified' ? job.salary_expectation : job.salary}</span>
                          </div>
                        )}
                      </div>
                      <div className="card-action-row">
                        <span>View details</span>
                        <ArrowRight size={16} aria-hidden="true" />
                      </div>
                    </button>
                  ))}
                </div>
              )}

              {jobs.length > 0 && totalJobs > JOBS_PER_PAGE && (
                <nav className="pagination" aria-label="Pagination">
                  <button
                    type="button"
                    className="secondary-btn"
                    onClick={() => setPage((current) => Math.max(1, current - 1))}
                    disabled={page === 1}
                  >
                    Previous
                  </button>
                  <div className="page-indicator">
                    Page <strong>{page}</strong> of <strong>{totalPages}</strong>
                  </div>
                  <button
                    type="button"
                    className="secondary-btn"
                    onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
                    disabled={page >= totalPages}
                  >
                    Next
                  </button>
                </nav>
              )}

              {jobs.length === 0 && (
                <div className="empty-state">
                  <h3>No jobs matched your filters</h3>
                  <p>Try a broader keyword or another location group to discover more listings.</p>
                  <button type="button" className="search-btn" onClick={clearFilters}>
                    Reset search
                  </button>
                </div>
              )}
            </>
          )}
        </section>
      </main>

      {selectedJob && (
        <div className="modal-overlay" onClick={() => setSelectedJob(null)}>
          <div
            className="modal-content"
            role="dialog"
            aria-modal="true"
            aria-labelledby="job-modal-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="modal-header">
              <div className="modal-title-wrap">
                <div className="job-source">{selectedJob.source}</div>
                <h2 id="job-modal-title">{selectedJob.title}</h2>
                <div className="modal-company-row">
                  <div className="job-company">
                    <Building2 size={16} aria-hidden="true" />
                    <span>{selectedJob.company}</span>
                  </div>
                  <div className="meta-item">
                    <MapPin size={14} aria-hidden="true" />
                    <span>{selectedJob.location || 'Location unavailable'}</span>
                  </div>
                  {((selectedJob.salary && selectedJob.salary !== 'nan') || (selectedJob.salary_expectation && selectedJob.salary_expectation !== 'Not specified')) && (
                    <div className="meta-item salary-badge">
                      <CircleDollarSign size={14} aria-hidden="true" />
                      <span>
                        {selectedJob.salary_expectation && selectedJob.salary_expectation !== 'Not specified' 
                          ? selectedJob.salary_expectation 
                          : selectedJob.salary}
                      </span>
                      {selectedJob.salary_expectation && selectedJob.salary_expectation !== 'Not specified' && (
                        <span className="ai-tag">AI Est.</span>
                      )}
                    </div>
                  )}
                </div>
              </div>

              <button
                type="button"
                className="icon-btn"
                onClick={() => setSelectedJob(null)}
                aria-label="Close job details"
              >
                <X size={20} />
              </button>
            </div>

            <div className="modal-body">
              {selectedJob.skills && (Array.isArray(selectedJob.skills) || typeof selectedJob.skills === 'string') && (
                (() => {
                  let skillsArray = [];
                  try {
                    skillsArray = Array.isArray(selectedJob.skills) 
                      ? selectedJob.skills 
                      : JSON.parse(selectedJob.skills);
                  } catch (e) {
                    return null;
                  }
                  
                  if (skillsArray.length === 0) return null;

                  return (
                    <div className="ai-enhanced-section">
                      <div className="ai-badge">
                        <Sparkles size={14} /> AI Extracted Skills
                      </div>
                      <div className="skills-container">
                        {skillsArray.map((skill, index) => (
                          <span key={index} className="skill-chip">{skill}</span>
                        ))}
                      </div>
                    </div>
                  );
                })()
              )}

              {selectedJob.key_takeaways && (Array.isArray(selectedJob.key_takeaways) || typeof selectedJob.key_takeaways === 'string') && (
                (() => {
                  let takeawaysArray = [];
                  try {
                    takeawaysArray = Array.isArray(selectedJob.key_takeaways) 
                      ? selectedJob.key_takeaways 
                      : JSON.parse(selectedJob.key_takeaways);
                  } catch (e) {
                    return null;
                  }

                  if (takeawaysArray.length === 0) return null;

                  return (
                    <div className="ai-enhanced-section">
                      <div className="ai-badge">
                        <Sparkles size={14} /> Key Takeaways
                      </div>
                      <ul className="takeaways-list">
                        {takeawaysArray.map((takeaway, index) => (
                          <li key={index}>{takeaway}</li>
                        ))}
                      </ul>
                    </div>
                  );
                })()
              )}

              <h3 className="section-title">Job description</h3>
              <p className="job-desc-content">
                {selectedJob.description || 'No detailed description provided by the source. Please visit the job page for more information.'}
              </p>
            </div>

            <div className="modal-footer">
              <a href={selectedJob.job_url} target="_blank" rel="noopener noreferrer" className="search-btn apply-btn">
                Apply for this position <ArrowRight size={18} aria-hidden="true" />
              </a>
              <button type="button" className="secondary-btn" onClick={() => setSelectedJob(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      <footer className="container footer">
        <p>© 2026 Zapril AI · Aggregating high-quality roles for engineers and AI professionals.</p>
      </footer>
    </div>
  );
};

export default App;
