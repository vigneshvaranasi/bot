import { useContext } from 'react';
import { FileContext } from '../store/FileProvider';
import type { FileContextType } from '../store/FileProvider';

export const useFileContext = (): FileContextType => {
  const context = useContext(FileContext);
  if (!context) {
    throw new Error('useFileContext must be used within a FileProvider');
  }
  return context;
};
