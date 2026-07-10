import React from 'react';

const ScrollBar = ({ children, className = "" }) => {
  return (
    <div className={`h-screen overflow-y-auto custom-scrollbar ${className}`}>
      {children}

      <style>{`
        .custom-scrollbar {
          scrollbar-width: thin;
          scrollbar-color: #a2855a #dccaa0;
        }
        .custom-scrollbar::-webkit-scrollbar {
          width: 12px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: #dccaa0;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: #a2855a;
          border-radius: 6px;
          border: 3px solid #dccaa0;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: #6a4a26;
        }
      `}</style>
    </div>
  );
};

export default ScrollBar;