import React, { useState, useEffect } from 'react';
import { recruiterApi } from '../../services/api';
import { useAuth } from '../../contexts/AuthContext';
import { Recruiter, SearchResult, SearchRequest, ApiError } from '../../types';
import SearchInterface from './SearchInterface';
import SearchResults from './SearchResults';

const RecruiterDashboard: React.FC = () => {
  const { logout } = useAuth();
  const [profile, setProfile] = useState<Recruiter | null>(null);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [lastSearchCriteria, setLastSearchCriteria] = useState<SearchRequest | null>(null);
  const [savedSearches, setSavedSearches] = useState<Array<{ id: string; name: string; criteria: any }>>([]);
  const [loading, setLoading] = useState(true);
  const [searchLoading, setSearchLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [activeTab, setActiveTab] = useState<'search' | 'results' | 'saved'>('search');

  useEffect(() => {
    loadProfile();
    loadSavedSearches();
  }, []);

  const loadProfile = async () => {
    try {
      const response = await recruiterApi.getProfile();
      setProfile(response.data);
    } catch (err: any) {
      const apiError = err.response?.data as ApiError;
      setError(apiError?.detail || 'Failed to load profile');
    } finally {
      setLoading(false);
    }
  };

  const loadSavedSearches = async () => {
    try {
      const response = await recruiterApi.getSavedSearches();
      setSavedSearches(response.data.searches || []);
    } catch (err: any) {
      // Saved searches are optional, don't show error if they fail to load
      console.warn('Failed to load saved searches:', err);
      setSavedSearches([]);
    }
  };

  const handleSearchResults = (results: SearchResult[], criteria?: SearchRequest) => {
    setSearchResults(results);
    if (criteria) {
      setLastSearchCriteria(criteria);
    }
    setActiveTab('results');
  };

  const handleSaveCurrentSearch = async () => {
    if (!lastSearchCriteria) return;
    
    const name = prompt('Enter a name for this search:');
    if (!name) return;

    try {
      await recruiterApi.saveSearch(name, lastSearchCriteria);
      alert('Search saved successfully!');
      loadSavedSearches(); // Refresh the saved searches list
    } catch (err: any) {
      const apiError = err.response?.data as ApiError;
      setError(apiError?.detail || 'Failed to save search');
    }
  };

  const handleRunSavedSearch = async (criteria: any) => {
    setSearchLoading(true);
    setError('');
    
    try {
      const response = await recruiterApi.search(criteria);
      setSearchResults(response.data.results);
      setActiveTab('results');
    } catch (err: any) {
      const apiError = err.response?.data as ApiError;
      setError(apiError?.detail || 'Search failed. Please try again.');
    } finally {
      setSearchLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="dashboard-loading" role="status" aria-live="polite">
        <p>Loading dashboard...</p>
      </div>
    );
  }

  return (
    <div className="recruiter-dashboard">
      <header className="dashboard-header">
        <div className="header-info">
          <h1>Welcome, {profile?.job_title || 'Recruiter'}</h1>
          <p>{profile?.company_name}</p>
        </div>
        <button onClick={logout} className="logout-btn">
          Sign Out
        </button>
      </header>

      {error && (
        <div className="error-message" role="alert" aria-live="polite">
          {error}
        </div>
      )}

      <nav className="dashboard-nav">
        <button
          className={`nav-tab ${activeTab === 'search' ? 'active' : ''}`}
          onClick={() => setActiveTab('search')}
          aria-pressed={activeTab === 'search'}
        >
          New Search
        </button>
        <button
          className={`nav-tab ${activeTab === 'results' ? 'active' : ''}`}
          onClick={() => setActiveTab('results')}
          aria-pressed={activeTab === 'results'}
          disabled={searchResults.length === 0}
        >
          Results ({searchResults.length})
        </button>
        <button
          className={`nav-tab ${activeTab === 'saved' ? 'active' : ''}`}
          onClick={() => setActiveTab('saved')}
          aria-pressed={activeTab === 'saved'}
        >
          Saved Searches ({savedSearches.length})
        </button>
      </nav>

      <div className="dashboard-content">
        {activeTab === 'search' && (
          <div className="search-tab">
            <SearchInterface onSearchResults={handleSearchResults} />
          </div>
        )}

        {activeTab === 'results' && (
          <div className="results-tab">
            {lastSearchCriteria && (
              <div className="results-actions">
                <button 
                  onClick={handleSaveCurrentSearch}
                  className="save-search-btn"
                >
                  Save This Search
                </button>
              </div>
            )}
            <SearchResults results={searchResults} loading={searchLoading} />
          </div>
        )}

        {activeTab === 'saved' && (
          <div className="saved-tab">
            <h2>Saved Searches</h2>
            
            {savedSearches.length === 0 ? (
              <div className="empty-saved-searches">
                <p>No saved searches yet. Create a search and save it for future use.</p>
                <button 
                  onClick={() => setActiveTab('search')}
                  className="create-search-btn"
                >
                  Create New Search
                </button>
              </div>
            ) : (
              <div className="saved-searches-list">
                {savedSearches.map((savedSearch) => (
                  <div key={savedSearch.id} className="saved-search-item">
                    <div className="saved-search-info">
                      <h3>{savedSearch.name}</h3>
                      <p className="search-preview">
                        {savedSearch.criteria.requirements.substring(0, 100)}
                        {savedSearch.criteria.requirements.length > 100 ? '...' : ''}
                      </p>
                      
                      <div className="search-filters">
                        {savedSearch.criteria.filters?.experience_level && (
                          <span className="filter-tag">
                            Experience: {savedSearch.criteria.filters.experience_level}
                          </span>
                        )}
                        {savedSearch.criteria.filters?.location && (
                          <span className="filter-tag">
                            Location: {savedSearch.criteria.filters.location}
                          </span>
                        )}
                        <span className="filter-tag">
                          Limit: {savedSearch.criteria.limit || 10} results
                        </span>
                      </div>
                    </div>
                    
                    <div className="saved-search-actions">
                      <button
                        onClick={() => handleRunSavedSearch(savedSearch.criteria)}
                        disabled={searchLoading}
                        className="run-search-btn"
                      >
                        {searchLoading ? 'Running...' : 'Run Search'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default RecruiterDashboard;