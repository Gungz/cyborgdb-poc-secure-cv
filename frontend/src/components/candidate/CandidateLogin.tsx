import React, { useState } from 'react';
import { authApi } from '../../services/api';
import { useAuth } from '../../contexts/AuthContext';
import { ApiError } from '../../types';

interface CandidateLoginProps {
  onSuccess?: () => void;
  onSwitchToRegister?: () => void;
}

const CandidateLogin: React.FC<CandidateLoginProps> = ({ onSuccess, onSwitchToRegister }) => {
  const { login } = useAuth();
  const [formData, setFormData] = useState({
    email: '',
    password: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
    setError('');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await authApi.login(formData.email, formData.password);
      
      // Verify user is a candidate
      if (response.data.user_role !== 'candidate') {
        setError('Invalid credentials for candidate login');
        return;
      }

      // Store token first so getCurrentUser can use it
      localStorage.setItem('access_token', response.data.access_token);
      
      // Fetch full user info
      const userResponse = await authApi.getCurrentUser();
      login(response.data.access_token, userResponse.data);
      onSuccess?.();
    } catch (err: any) {
      console.log(err);
      const apiError = err.response?.data as ApiError;
      setError(apiError?.detail || 'Login failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-form">
      <h2>Candidate Sign In</h2>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="email">Email *</label>
          <input
            type="email"
            id="email"
            name="email"
            value={formData.email}
            onChange={handleChange}
            required
            aria-describedby="email_error"
          />
        </div>

        <div className="form-group">
          <label htmlFor="password">Password *</label>
          <input
            type="password"
            id="password"
            name="password"
            value={formData.password}
            onChange={handleChange}
            required
            aria-describedby="password_error"
          />
        </div>

        {error && (
          <div className="error-message" role="alert" aria-live="polite">
            {error}
          </div>
        )}

        <button type="submit" disabled={loading} className="submit-btn">
          {loading ? 'Signing In...' : 'Sign In'}
        </button>
      </form>

      <div className="switch-form">
        <p>
          Don't have an account?{' '}
          <button type="button" onClick={onSwitchToRegister} className="link-btn">
            Create Account
          </button>
        </p>
      </div>
    </div>
  );
};

export default CandidateLogin;