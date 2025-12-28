import React from 'react';

interface LoadingProps {
  message?: string;
  size?: 'small' | 'medium' | 'large';
  inline?: boolean;
}

const Loading: React.FC<LoadingProps> = ({ 
  message = 'Loading...', 
  size = 'medium',
  inline = false 
}) => {
  const sizeClasses = {
    small: 'loading-small',
    medium: 'loading-medium',
    large: 'loading-large',
  };

  const containerClass = inline ? 'loading-inline' : 'loading-container';

  return (
    <div 
      className={`${containerClass} ${sizeClasses[size]}`}
      role="status" 
      aria-live="polite"
      aria-label={message}
    >
      <div className="loading-spinner" aria-hidden="true">
        <div className="spinner-circle"></div>
      </div>
      <span className="loading-text">{message}</span>
    </div>
  );
};

export default Loading;