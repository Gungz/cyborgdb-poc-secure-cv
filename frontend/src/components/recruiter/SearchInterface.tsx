import React, { useState } from 'react';
import { recruiterApi } from '../../services/api';
import { SearchRequest, SearchResult, ApiError } from '../../types';

interface SearchInterfaceProps {
  onSearchResults?: (results: SearchResult[], criteria?: SearchRequest) => void;
}

const SearchInterface: React.FC<SearchInterfaceProps> = ({ onSearchResults }) => {
  const [searchData, setSearchData] = useState<SearchRequest>({
    requirements: '',
    filters: {},
    limit: 10,
  });
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string>('');
  const [showAdvanced, setShowAdvanced] = useState(false);

  const handleRequirementsChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setSearchData({
      ...searchData,
      requirements: e.target.value,
    });
    setError('');
  };

  const handleFilterChange = (filterKey: string, value: string) => {
    setSearchData({
      ...searchData,
      filters: {
        ...searchData.filters,
        [filterKey]: value || undefined,
      },
    });
  };

  const handleLimitChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSearchData({
      ...searchData,
      limit: parseInt(e.target.value),
    });
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!searchData.requirements.trim()) {
      setError('Please enter job requirements');
      return;
    }

    setSearching(true);
    setError('');

    try {
      const response = await recruiterApi.search(searchData);
      onSearchResults?.(response.data.results, searchData);
    } catch (err: any) {
      const apiError = err.response?.data as ApiError;
      setError(apiError?.detail || 'Search failed. Please try again.');
    } finally {
      setSearching(false);
    }
  };

  const handleSaveSearch = async () => {
    const name = prompt('Enter a name for this search:');
    if (!name) return;

    try {
      await recruiterApi.saveSearch(name, searchData);
      alert('Search saved successfully!');
    } catch (err: any) {
      const apiError = err.response?.data as ApiError;
      setError(apiError?.detail || 'Failed to save search');
    }
  };

  return (
    <div className="search-interface">
      <h2>Find Candidates</h2>
      
      <form onSubmit={handleSearch}>
        <div className="form-group">
          <label htmlFor="requirements">Job Requirements *</label>
          <textarea
            id="requirements"
            name="requirements"
            value={searchData.requirements}
            onChange={handleRequirementsChange}
            placeholder="Describe the skills, experience, and qualifications you're looking for..."
            rows={6}
            required
            aria-describedby="requirements_help"
          />
          <small id="requirements_help">
            Be specific about skills, experience level, and qualifications to get better matches
          </small>
        </div>

        <div className="advanced-filters">
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="toggle-advanced"
            aria-expanded={showAdvanced}
            aria-controls="advanced-filters"
          >
            {showAdvanced ? 'Hide' : 'Show'} Advanced Filters
          </button>

          {showAdvanced && (
            <div id="advanced-filters" className="advanced-filters-content">
              <div className="filter-row">
                <div className="form-group">
                  <label htmlFor="experience_level">Experience Level</label>
                  <select
                    id="experience_level"
                    value={searchData.filters?.experience_level || ''}
                    onChange={(e) => handleFilterChange('experience_level', e.target.value)}
                  >
                    <option value="">Any</option>
                    <option value="entry">Entry Level (0-2 years)</option>
                    <option value="mid">Mid Level (3-5 years)</option>
                    <option value="senior">Senior Level (6-10 years)</option>
                    <option value="lead">Lead/Principal (10+ years)</option>
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor="location">Location</label>
                  <input
                    type="text"
                    id="location"
                    value={searchData.filters?.location || ''}
                    onChange={(e) => handleFilterChange('location', e.target.value)}
                    placeholder="e.g., San Francisco, Remote"
                  />
                </div>
              </div>

              <div className="filter-row">
                <div className="form-group">
                  <label htmlFor="skills">Specific Skills</label>
                  <input
                    type="text"
                    id="skills"
                    value={searchData.filters?.skills || ''}
                    onChange={(e) => handleFilterChange('skills', e.target.value)}
                    placeholder="e.g., Python, React, AWS (comma-separated)"
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="limit">Number of Results</label>
                  <select
                    id="limit"
                    value={searchData.limit}
                    onChange={handleLimitChange}
                  >
                    <option value={3}>3 results</option>
                    <option value={5}>5 results</option>
                    <option value={10}>10 results</option>
                    <option value={15}>15 results</option>
                    <option value={20}>20 results</option>
                    <option value={25}>25 results</option>
                    <option value={30}>30 results</option>
                    <option value={40}>40 results</option>
                    <option value={50}>50 results</option>
                  </select>
                </div>
              </div>
            </div>
          )}
        </div>

        {error && (
          <div className="error-message" role="alert" aria-live="polite">
            {error}
          </div>
        )}

        <div className="search-actions">
          <button type="submit" disabled={searching} className="search-btn">
            {searching ? 'Searching...' : 'Search Candidates'}
          </button>
          
          {searchData.requirements.trim() && (
            <button 
              type="button" 
              onClick={handleSaveSearch}
              disabled={searching}
              className="save-search-btn"
            >
              Save Search
            </button>
          )}
        </div>
      </form>
    </div>
  );
};

export default SearchInterface;