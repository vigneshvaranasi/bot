import { useState, useRef, useCallback } from 'react';
import { Button } from './Button';
import { useFileContext } from '../../hooks/useFileContext';
import type { UploadedFile } from '../../store/FileProvider';

const UploadFiles = () => {
  const [localFiles, setLocalFiles] = useState<UploadedFile[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { addFiles } = useFileContext();

  // Calculate upload progress
  const uploadedCount = localFiles.filter(file => file.uploaded).length;
  const totalCount = localFiles.length;

  // Format file size
  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  // Validate file type
  const isValidFileType = (file: File): boolean => {
    const allowedTypes = ['.json', '.md'];
    const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase();
    return allowedTypes.includes(fileExtension);
  };

  // Read file content
  const readFileContent = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => resolve(e.target?.result as string);
      reader.onerror = reject;
      reader.readAsText(file);
    });
  };

  // Handle file selection
  const handleFileSelect = useCallback(async (selectedFiles: FileList | null) => {
    if (!selectedFiles) return;

    const newFiles: UploadedFile[] = [];
    
    for (const file of Array.from(selectedFiles)) {
      if (isValidFileType(file)) {
        // Check if file already exists
        const fileExists = localFiles.some(existingFile => 
          existingFile.name === file.name && existingFile.size === file.size
        );
        
        if (!fileExists) {
          try {
            const content = await readFileContent(file);
            const newFile: UploadedFile = {
              id: Math.random().toString(36).substr(2, 9),
              name: file.name,
              size: file.size,
              type: file.type,
              content: content,
              uploaded: true,
              uploadedAt: new Date()
            };
            newFiles.push(newFile);
            
            // Console log the uploaded file details with full content
            console.log('File uploaded:', {
              id: newFile.id,
              name: newFile.name,
              size: newFile.size,
              type: newFile.type,
              uploadedAt: newFile.uploadedAt
            });
            
            // Log the complete file content
            console.log('Full file content for', newFile.name, ':\n', content);
          } catch (error) {
            console.error('Error reading file:', error);
          }
        }
      }
    }

    setLocalFiles(prev => [...prev, ...newFiles]);
  }, [localFiles]);

  // Handle drag events
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    handleFileSelect(e.dataTransfer.files);
  }, [handleFileSelect]);

  // Handle browse button click
  const handleBrowseClick = () => {
    fileInputRef.current?.click();
  };

  // Handle file input change
  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleFileSelect(e.target.files);
  };

  // Remove file
  const removeFile = (fileId: string) => {
    setLocalFiles(prev => prev.filter(file => file.id !== fileId));
  };

  // Process files - add to global context
  const processFiles = async () => {
    setIsProcessing(true);
    try {
      console.log('Processing files:', localFiles.map(file => ({
        id: file.id,
        name: file.name,
        size: file.size,
        type: file.type
      })));
      
      addFiles(localFiles);
      
      console.log(`Successfully processed ${localFiles.length} files and added to global context`);
      // Optionally clear local files after processing
      // setLocalFiles([]);
      alert(`Successfully processed ${localFiles.length} files!`);
    } catch (error) {
      console.error('Error processing files:', error);
      alert('Error processing files. Please try again.');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-4xl mx-auto">
        <div className="bg-white rounded-lg shadow-lg p-6">
          <h1 className="text-2xl font-semibold text-gray-800 mb-6">Upload files</h1>
          
          <p className="text-gray-600 mb-6">
            Please drag and drop file(s) in the below area or browse files by using the button.
          </p>

          {/* Upload Area */}
          <div
            className={`border-2 border-dashed rounded-lg p-12 text-center transition-colors ${
              isDragOver
                ? 'border-blue-400 bg-blue-50'
                : 'border-gray-300 bg-gray-50'
            }`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            {/* Upload Icon */}
            <div className="mb-4">
              <svg
                className="mx-auto h-12 w-12 text-gray-400"
                stroke="currentColor"
                fill="none"
                viewBox="0 0 48 48"
                aria-hidden="true"
              >
                <path
                  d="M24 8v24m8-12l-8-8-8 8"
                  strokeWidth={2}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path
                  d="M40 32v8a2 2 0 01-2 2H10a2 2 0 01-2-2v-8"
                  strokeWidth={2}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>

            <p className="text-lg text-gray-700 mb-4">Drop files here or</p>
            
            <Button
              variant="secondary"
              onClick={handleBrowseClick}
              className="mb-4"
            >
              BROWSE FILES
            </Button>

            <p className="text-sm text-gray-500">
              Files must be in .JSON or .MD format.
            </p>
          </div>

          {/* Hidden file input */}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".json,.md"
            onChange={handleFileInputChange}
            className="hidden"
          />

          {/* Upload Progress */}
          {totalCount > 0 && (
            <div className="mt-6">
              <p className="text-lg font-medium text-gray-800 mb-4">
                {uploadedCount} out of {totalCount} files uploaded
              </p>

              {/* File List */}
              <div className="space-y-3">
                {localFiles.map((file) => (
                  <div
                    key={file.id}
                    className="flex items-center justify-between p-3 border border-gray-200 rounded-lg bg-gray-50"
                  >
                    <div className="flex items-center space-x-3">
                      {/* Success checkmark */}
                      {file.uploaded && (
                        <div className="flex-shrink-0">
                          <svg
                            className="h-5 w-5 text-green-500"
                            fill="currentColor"
                            viewBox="0 0 20 20"
                          >
                            <path
                              fillRule="evenodd"
                              d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                              clipRule="evenodd"
                            />
                          </svg>
                        </div>
                      )}
                      
                      <div>
                        <p className="text-sm font-medium text-gray-900">
                          {file.name}
                        </p>
                        <p className="text-sm text-gray-500">
                          {formatFileSize(file.size)}
                        </p>
                      </div>
                    </div>

                    {/* Remove button */}
                    <button
                      onClick={() => removeFile(file.id)}
                      className="text-gray-400 hover:text-red-500 transition-colors"
                      title="Remove file"
                    >
                      <svg
                        className="h-5 w-5"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                        />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>



              {/* Action Buttons */}
              <div className="mt-6 flex justify-end space-x-3">
                <Button
                  variant="default"
                  onClick={() => setLocalFiles([])}
                  disabled={localFiles.length === 0}
                >
                  Clear All
                </Button>
                <Button
                  variant="primary"
                  disabled={localFiles.length === 0 || isProcessing}
                  onClick={processFiles}
                >
                  {isProcessing ? 'Processing...' : 'Process Files'}
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default UploadFiles;
