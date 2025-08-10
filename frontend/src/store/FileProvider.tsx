import { createContext, useState } from 'react';
import type { ReactNode } from 'react';

export interface UploadedFile {
  id: string;
  name: string;
  size: number;
  type: string;
  content?: string;
  uploaded: boolean;
  uploadedAt: Date;
}

export interface FileContextType {
  files: UploadedFile[];
  addFiles: (files: UploadedFile[]) => void;
  removeFile: (fileId: string) => void;
  clearAllFiles: () => void;
  getFileById: (fileId: string) => UploadedFile | undefined;
  getFileContent: (fileId: string) => Promise<string | null>;
}

export const FileContext = createContext<FileContextType | undefined>(undefined);

interface FileProviderProps {
  children: ReactNode;
}

export const FileProvider = ({ children }: FileProviderProps) => {
  const [files, setFiles] = useState<UploadedFile[]>([]);

  const addFiles = (newFiles: UploadedFile[]) => {
    setFiles(prev => {
      const filtered = newFiles.filter(newFile => 
        !prev.some(existingFile => 
          existingFile.name === newFile.name && existingFile.size === newFile.size
        )
      );
      return [...prev, ...filtered];
    });
  };

  const removeFile = (fileId: string) => {
    setFiles(prev => prev.filter(file => file.id !== fileId));
  };

  const clearAllFiles = () => {
    setFiles([]);
  };

  const getFileById = (fileId: string): UploadedFile | undefined => {
    return files.find(file => file.id === fileId);
  };

  const getFileContent = async (fileId: string): Promise<string | null> => {
    const file = getFileById(fileId);
    if (!file || !file.content) return null;
    return file.content;
  };

  const value: FileContextType = {
    files,
    addFiles,
    removeFile,
    clearAllFiles,
    getFileById,
    getFileContent,
  };

  return (
    <FileContext.Provider value={value}>
      {children}
    </FileContext.Provider>
  );
};
