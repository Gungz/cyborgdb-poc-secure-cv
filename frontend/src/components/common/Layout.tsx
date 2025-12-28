import React, { ReactNode } from 'react';

interface LayoutProps {
  children: ReactNode;
  title?: string;
  showSkipLink?: boolean;
}

const Layout: React.FC<LayoutProps> = ({ 
  children, 
  title = 'SecureHR - Privacy-preserving talent matching', 
  showSkipLink = true 
}) => {
  React.useEffect(() => {
    document.title = title;
  }, [title]);

  return (
    <div className="app-layout">
      {showSkipLink && (
        <a href="#main-content" className="skip-link">
          Skip to main content
        </a>
      )}
      
      <main id="main-content" role="main">
        {children}
      </main>
    </div>
  );
};

export default Layout;