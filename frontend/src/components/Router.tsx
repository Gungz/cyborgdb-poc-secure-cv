import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import Layout from './common/Layout';
import Loading from './common/Loading';

// Candidate components
import CandidateLogin from './candidate/CandidateLogin';
import CandidateRegister from './candidate/CandidateRegister';
import CandidateDashboard from './candidate/CandidateDashboard';

// Recruiter components
import RecruiterLogin from './recruiter/RecruiterLogin';
import RecruiterRegister from './recruiter/RecruiterRegister';
import RecruiterDashboard from './recruiter/RecruiterDashboard';

type UserType = 'candidate' | 'recruiter';
type AuthMode = 'login' | 'register';

const Router: React.FC = () => {
  const { user, isAuthenticated, loading } = useAuth();
  const [selectedUserType, setSelectedUserType] = useState<UserType>('candidate');
  const [authMode, setAuthMode] = useState<AuthMode>('login');

  if (loading) {
    return (
      <Layout>
        <Loading message="Loading application..." size="large" />
      </Layout>
    );
  }

  // If user is authenticated, show appropriate dashboard
  if (isAuthenticated && user) {
    if (user.role === 'candidate') {
      return (
        <Layout title="SecureHR - Candidate Dashboard">
          <CandidateDashboard />
        </Layout>
      );
    } else if (user.role === 'recruiter') {
      return (
        <Layout title="SecureHR - Recruiter Dashboard">
          <RecruiterDashboard />
        </Layout>
      );
    }
  }

  // Show authentication interface
  return (
    <Layout title="SecureHR - Sign In">
      <div className="auth-container">
        <div className="auth-card">
          {/* User type selection */}
          <div className="user-type-selection">
            <h1>SecureHR</h1>
            <p>Privacy-preserving talent matching platform</p>
            
            <div className="user-type-tabs" role="tablist">
              <button
                role="tab"
                aria-selected={selectedUserType === 'candidate'}
                aria-controls="candidate-panel"
                className={`user-type-tab ${selectedUserType === 'candidate' ? 'active' : ''}`}
                onClick={() => setSelectedUserType('candidate')}
              >
                I'm a Candidate
              </button>
              <button
                role="tab"
                aria-selected={selectedUserType === 'recruiter'}
                aria-controls="recruiter-panel"
                className={`user-type-tab ${selectedUserType === 'recruiter' ? 'active' : ''}`}
                onClick={() => setSelectedUserType('recruiter')}
              >
                I'm a Recruiter
              </button>
            </div>
          </div>

          {/* Authentication forms */}
          <div className="auth-forms">
            {selectedUserType === 'candidate' && (
              <div id="candidate-panel" role="tabpanel">
                {authMode === 'login' ? (
                  <CandidateLogin
                    onSwitchToRegister={() => setAuthMode('register')}
                  />
                ) : (
                  <CandidateRegister
                    onSwitchToLogin={() => setAuthMode('login')}
                  />
                )}
              </div>
            )}

            {selectedUserType === 'recruiter' && (
              <div id="recruiter-panel" role="tabpanel">
                {authMode === 'login' ? (
                  <RecruiterLogin
                    onSwitchToRegister={() => setAuthMode('register')}
                  />
                ) : (
                  <RecruiterRegister
                    onSwitchToLogin={() => setAuthMode('login')}
                  />
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default Router;