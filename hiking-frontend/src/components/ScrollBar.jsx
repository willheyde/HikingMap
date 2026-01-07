import React from 'react';

const ScrollBar = ({ children, className = "" }) => {
  return (
    <div className={`h-screen overflow-y-auto custom-scrollbar ${className}`}>
      {children}

      <style>{`
        .custom-scrollbar {
          scrollbar-width: thin;
          scrollbar-color: #475569 #0f172a;
        }
        .custom-scrollbar::-webkit-scrollbar {
          width: 12px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: #0f172a;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: #475569;
          border-radius: 6px;
          border: 3px solid #0f172a;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: #64748b;
        }
      `}</style>
    </div>
  );
};

export default ScrollBar;