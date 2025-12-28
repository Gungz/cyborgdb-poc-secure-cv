import React, { useState, useMemo } from 'react';
import { recruiterApi } from '../../services/api';
import { SearchResult } from '../../types';

interface SearchResultsProps {
  results: SearchResult[];
  loading?: boolean;
}

interface CVModalState {
  isOpen: boolean;
  candidateId: string;
  candidateName: string;
  cvContent: string;
  loading: boolean;
  error: string;
}

const SearchResults: React.FC<SearchResultsProps> = ({ results, loading }) => {
  const [sortBy, setSortBy] = useState<'similarity' | 'experience'>('similarity');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [minSimilarity, setMinSimilarity] = useState(0);
  const [experienceFilter, setExperienceFilter] = useState<string>('');
  const [cvModal, setCvModal] = useState<CVModalState>({
    isOpen: false,
    candidateId: '',
    candidateName: '',
    cvContent: '',
    loading: false,
    error: ''
  });

  const filteredAndSortedResults = useMemo(() => {
    let filtered = results.filter(result => {
      if (result.similarity_score < minSimilarity / 100) {
        return false;
      }
      if (experienceFilter && result.experience_level !== experienceFilter) {
        return false;
      }
      return true;
    });

    filtered.sort((a, b) => {
      let comparison = 0;
      if (sortBy === 'similarity') {
        comparison = a.similarity_score - b.similarity_score;
      } else if (sortBy === 'experience') {
        const experienceLevels = ['entry', 'mid', 'senior', 'lead'];
        const aLevel = experienceLevels.indexOf(a.experience_level || '');
        const bLevel = experienceLevels.indexOf(b.experience_level || '');
        comparison = aLevel - bLevel;
      }
      return sortOrder === 'desc' ? -comparison : comparison;
    });

    return filtered;
  }, [results, sortBy, sortOrder, minSimilarity, experienceFilter]);

  const handleViewDetails = async (result: SearchResult) => {
    const candidateName = result.first_name && result.last_name 
      ? `${result.first_name} ${result.last_name}`
      : `Candidate ${result.candidate_id.substring(0, 8)}`;

    setCvModal({
      isOpen: true,
      candidateId: result.candidate_id,
      candidateName,
      cvContent: '',
      loading: true,
      error: ''
    });

    try {
      const response = await recruiterApi.getCandidateCV(result.candidate_id);
      setCvModal(prev => ({
        ...prev,
        cvContent: response.data.cv_content,
        loading: false
      }));
    } catch (err: any) {
      setCvModal(prev => ({
        ...prev,
        loading: false,
        error: err.response?.data?.detail || 'Failed to load CV content'
      }));
    }
  };

  const closeModal = () => {
    setCvModal({
      isOpen: false,
      candidateId: '',
      candidateName: '',
      cvContent: '',
      loading: false,
      error: ''
    });
  };

  const getScoreColor = (score: number) => {
    if (score >= 0.8) return 'excellent';
    if (score >= 0.6) return 'good';
    if (score >= 0.4) return 'fair';
    return 'poor';
  };

  const formatScore = (score: number) => {
    return Math.round(score * 100);
  };

  const getExperienceLabel = (level?: string) => {
    switch (level) {
      case 'entry': return 'Entry Level';
      case 'mid': return 'Mid Level';
      case 'senior': return 'Senior Level';
      case 'lead': return 'Lead/Principal';
      default: return 'Not specified';
    }
  };

  if (loading) {
    return (
      <div className="search-results loading" role="status" aria-live="polite">
        <p>Searching for candidates...</p>
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <div className="search-results empty">
        <h3>No Results</h3>
        <p>No candidates match your search criteria. Try adjusting your requirements or filters.</p>
      </div>
    );
  }

  return (
    <div className="search-results">
      <div className="results-header">
        <h3>Search Results ({filteredAndSortedResults.length} of {results.length})</h3>
        
        <div className="results-controls">
          <div className="filter-controls">
            <div className="control-group">
              <label htmlFor="min-similarity">Min Similarity:</label>
              <input
                type="range"
                id="min-similarity"
                min="0"
                max="100"
                value={minSimilarity}
                onChange={(e) => setMinSimilarity(parseInt(e.target.value))}
                aria-describedby="similarity-value"
              />
              <span id="similarity-value">{minSimilarity}%</span>
            </div>

            <div className="control-group">
              <label htmlFor="experience-filter">Experience:</label>
              <select
                id="experience-filter"
                value={experienceFilter}
                onChange={(e) => setExperienceFilter(e.target.value)}
              >
                <option value="">All Levels</option>
                <option value="entry">Entry Level</option>
                <option value="mid">Mid Level</option>
                <option value="senior">Senior Level</option>
                <option value="lead">Lead/Principal</option>
              </select>
            </div>
          </div>

          <div className="sort-controls">
            <div className="control-group">
              <label htmlFor="sort-by">Sort by:</label>
              <select
                id="sort-by"
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as 'similarity' | 'experience')}
              >
                <option value="similarity">Similarity Score</option>
                <option value="experience">Experience Level</option>
              </select>
            </div>

            <div className="control-group">
              <label htmlFor="sort-order">Order:</label>
              <select
                id="sort-order"
                value={sortOrder}
                onChange={(e) => setSortOrder(e.target.value as 'asc' | 'desc')}
              >
                <option value="desc">High to Low</option>
                <option value="asc">Low to High</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      <div className="results-list">
        {filteredAndSortedResults.map((result, index) => (
          <div key={result.candidate_id} className="result-item">
            <div className="result-header">
              <div className="result-id">
                <h4>
                  {result.first_name && result.last_name 
                    ? `${result.first_name} ${result.last_name}`
                    : `Candidate #${index + 1}`}
                </h4>
                {result.email && (
                  <span className="candidate-email">{result.email}</span>
                )}
                <span className="candidate-id">ID: {result.candidate_id.substring(0, 8)}...</span>
              </div>
              
              <div className={`similarity-score ${getScoreColor(result.similarity_score)}`}>
                <span className="score-value">{formatScore(result.similarity_score)}%</span>
                <span className="score-label">Match</span>
              </div>
            </div>

            <div className="result-details">
              {result.experience_level && (
                <div className="detail-item">
                  <label>Experience Level:</label>
                  <span>{getExperienceLabel(result.experience_level)}</span>
                </div>
              )}

              {result.matched_skills && result.matched_skills.length > 0 && (
                <div className="detail-item">
                  <label>Matched Skills:</label>
                  <div className="skills-list">
                    {result.matched_skills.map((skill, skillIndex) => (
                      <span key={skillIndex} className="skill-tag">
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="result-actions">
              <button 
                className="view-details-btn"
                onClick={() => handleViewDetails(result)}
              >
                View Details
              </button>
              
              <button 
                className="contact-btn"
                onClick={() => {
                  alert(`Contact process for candidate ${result.candidate_id} would start here`);
                }}
              >
                Express Interest
              </button>
            </div>
          </div>
        ))}
      </div>

      {filteredAndSortedResults.length === 0 && results.length > 0 && (
        <div className="no-filtered-results">
          <p>No candidates match your current filters. Try adjusting the similarity threshold or experience level filter.</p>
        </div>
      )}

      {/* CV Content Modal */}
      {cvModal.isOpen && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal-content cv-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>CV - {cvModal.candidateName}</h3>
              <button className="modal-close" onClick={closeModal} aria-label="Close modal">
                &times;
              </button>
            </div>
            <div className="modal-body">
              {cvModal.loading && (
                <div className="modal-loading">
                  <p>Loading CV content...</p>
                </div>
              )}
              {cvModal.error && (
                <div className="modal-error">
                  <p>{cvModal.error}</p>
                </div>
              )}
              {!cvModal.loading && !cvModal.error && (
                <div className="cv-content-wrapper">
                  <pre className="cv-content">{cvModal.cvContent}</pre>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SearchResults;
