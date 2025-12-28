import React, { useState } from 'react';
import { authApi } from '../../services/api';
import { useAuth } from '../../contexts/AuthContext';
import { ApiError } from '../../types';

interface RecruiterRegisterProps {
  onSuccess?: () => void;
  onSwitchToLogin?: () => void;
}

const RecruiterRegister: React.FC<RecruiterRegisterProps> = ({ onSuccess, onSwitchToLogin }) => {
  const { login } = useAuth();
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    company_name: '',
    job_title: '',
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
    
    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (formData.password.length < 8) {
      setError('Password must be at least 8 characters long');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await authApi.registerRecruiter({
        email: formData.email,
        password: formData.password,
        company_name: formData.company_name,
        job_title: formData.job_title,
      });

      // Store token first so getCurrentUser can use it
      localStorage.setItem('access_token', response.data.access_token);
      
      // Fetch full user info
      const userResponse = await authApi.getCurrentUser();
      login(response.data.access_token, userResponse.data);
      onSuccess?.();
    } catch (err: any) {
      const apiError = err.response?.data as ApiError;
      setError(apiError?.detail || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="register-form">
      <h2>Create Recruiter Account</h2>
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
          <label htmlFor="company_name">Company Name *</label>
          <input
            type="text"
            id="company_name"
            name="company_name"
            value={formData.company_name}
            onChange={handleChange}
            required
            aria-describedby="company_error"
          />
        </div>

        <div className="form-group">
          <label htmlFor="job_title">Job Title *</label>
          <input
            type="text"
            id="job_title"
            name="job_title"
            value={formData.job_title}
            onChange={handleChange}
            required
            aria-describedby="job_title_error"
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
            minLength={8}
            aria-describedby="password_help"
          />
          <small id="password_help">Password must be at least 8 characters long</small>
        </div>

        <div className="form-group">
          <label htmlFor="confirmPassword">Confirm Password *</label>
          <input
            type="password"
            id="confirmPassword"
            name="confirmPassword"
            value={formData.confirmPassword}
            onChange={handleChange}
            required
            aria-describedby="confirm_password_error"
          />
        </div>

        {error && (
          <div className="error-message" role="alert" aria-live="polite">
            {error}
          </div>
        )}

        <button type="submit" disabled={loading} className="submit-btn">
          {loading ? 'Creating Account...' : 'Create Account'}
        </button>
      </form>

      <div className="switch-form">
        <p>
          Already have an account?{' '}
          <button type="button" onClick={onSwitchToLogin} className="link-btn">
            Sign In
          </button>
        </p>
      </div>
    </div>
  );
};

export default RecruiterRegister;