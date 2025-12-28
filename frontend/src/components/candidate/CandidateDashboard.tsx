import React, { useState, useEffect } from 'react';
import { candidateApi } from '../../services/api';
import { useAuth } from '../../contexts/AuthContext';
import { Candidate, ApiError } from '../../types';
import CVUpload from './CVUpload';

const CandidateDashboard: React.FC = () => {
  const { user, logout } = useAuth();
  const [profile, setProfile] = useState<Candidate | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    loadProfile();
  }, []);

  const loadProfile = async () => {
    try {
      const response = await candidateApi.getProfile();
      setProfile(response.data);
    } catch (err: any) {
      const apiError = err.response?.data as ApiError;
      setError(apiError?.detail || 'Failed to load profile');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteProfile = async () => {
    setDeleting(true);
    try {
      await candidateApi.deleteProfile();
      logout();
    } catch (err: any) {
      const apiError = err.response?.data as ApiError;
      setError(apiError?.detail || 'Failed to delete profile');
      setDeleting(false);
      setShowDeleteConfirm(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'green';
      case 'processing': return 'orange';
      case 'failed': return 'red';
      case 'pending':
      default: return 'gray';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'completed': return 'CV Processed Successfully';
      case 'processing': return 'Processing CV...';
      case 'failed': return 'Processing Failed';
      case 'pending':
      default: return 'No CV Uploaded';
    }
  };

  if (loading) {
    return (
      <div className="dashboard-loading" role="status" aria-live="polite">
        <p>Loading profile...</p>
      </div>
    );
  }

  return (
    <div className="candidate-dashboard">
      <header className="dashboard-header">
        <h1>Welcome, {profile?.first_name || user?.email}</h1>
        <button onClick={logout} className="logout-btn">
          Sign Out
        </button>
      </header>

      {error && (
        <div className="error-message" role="alert" aria-live="polite">
          {error}
        </div>
      )}

      <div className="dashboard-content">
        <section className="profile-section">
          <h2>Profile Information</h2>
          <div className="profile-info">
            <div className="info-item">
              <label>Name:</label>
              <span>{profile?.first_name} {profile?.last_name}</span>
            </div>
            <div className="info-item">
              <label>Email:</label>
              <span>{profile?.email}</span>
            </div>
            <div className="info-item">
              <label>Account Created:</label>
              <span>{profile?.created_at ? new Date(profile.created_at).toLocaleDateString() : 'N/A'}</span>
            </div>
            <div className="info-item">
              <label>Last Login:</label>
              <span>{profile?.last_login_at ? new Date(profile.last_login_at).toLocaleDateString() : 'N/A'}</span>
            </div>
          </div>
        </section>

        <section className="cv-section">
          <h2>CV Status</h2>
          <div className="cv-status">
            <div className="status-indicator">
              <span 
                className={`status-dot ${getStatusColor(profile?.cv_processing_status || 'none')}`}
                aria-label={`CV status: ${getStatusText(profile?.cv_processing_status || 'none')}`}
              ></span>
              <span className="status-text">
                {getStatusText(profile?.cv_processing_status || 'none')}
              </span>
            </div>
            
            {profile?.cv_uploaded_at && (
              <div className="upload-info">
                {profile?.cv_filename && (
                  <p>File: {profile.cv_filename}</p>
                )}
                <p>Last uploaded: {new Date(profile.cv_uploaded_at).toLocaleString()}</p>
              </div>
            )}
          </div>

          <CVUpload onUploadSuccess={loadProfile} />
        </section>

        <section className="account-actions">
          <h2>Account Management</h2>
          <div className="danger-zone">
            <h3>Danger Zone</h3>
            <p>Permanently delete your account and all associated data. This action cannot be undone.</p>
            
            {!showDeleteConfirm ? (
              <button 
                onClick={() => setShowDeleteConfirm(true)}
                className="delete-btn"
              >
                Delete Account
              </button>
            ) : (
              <div className="delete-confirm">
                <p><strong>Are you sure?</strong> This will permanently delete your account and CV data.</p>
                <div className="confirm-actions">
                  <button 
                    onClick={handleDeleteProfile}
                    disabled={deleting}
                    className="confirm-delete-btn"
                  >
                    {deleting ? 'Deleting...' : 'Yes, Delete My Account'}
                  </button>
                  <button 
                    onClick={() => setShowDeleteConfirm(false)}
                    disabled={deleting}
                    className="cancel-btn"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
};

export default CandidateDashboard;