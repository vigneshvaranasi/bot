import { useState, useRef, useCallback } from "react";
import { Button } from "./Button";
import { useFileContext } from "../../hooks/useFileContext";
import type { UploadedFile } from "../../store/FileProvider";
import { sup } from "motion/react-client";

interface UploadFilesProps {
  maxFiles?: number; // Optional prop to limit number of files (undefined = no limit)
  supportedFileTypes?: string[]; // Optional prop to specify supported file types
  // Usage Examples:
  // <UploadFiles /> - No limit (unlimited files)
  // <UploadFiles maxFiles={5} /> - Limit to 5 files
  // <UploadFiles maxFiles={1} /> - Single file upload only
  compact?: boolean;
}

const UploadFiles = ({
  maxFiles,
  supportedFileTypes = [".json", ".md", ".csv"],
  compact = false,
}: UploadFilesProps) => {
  const [localFiles, setLocalFiles] = useState<UploadedFile[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { addFiles } = useFileContext();

  // Calculate upload progress
  const uploadedCount = localFiles.filter((file) => file.uploaded).length;
  const totalCount = localFiles.length;

  // Format file size
  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  // Validate file type
  // TO CHANGE ACCEPTED FILE TYPES: Modify the allowedTypes array below
  // Currently accepts: .json and .md files only
  // Examples:
  // ['.json', '.md'] - JSON and Markdown files
  // ['.pdf', '.doc', '.docx'] - Document files
  // ['.jpg', '.png', '.gif'] - Image files
  // ['.json', '.csv', '.txt', '.md'] - Text-based files
  const isValidFileType = (file: File): boolean => {
    const allowedTypes = supportedFileTypes || [".json", ".md", ".csv"];
    const fileExtension = "." + file.name.split(".").pop()?.toLowerCase();
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
  const handleFileSelect = useCallback(
    async (selectedFiles: FileList | null) => {
      if (!selectedFiles) return;

      const newFiles: UploadedFile[] = [];

      for (const file of Array.from(selectedFiles)) {
        // FILE LIMIT CHECK: This enforces the maximum number of files allowed
        // The limit is set via the maxFiles prop when using the component
        if (maxFiles && localFiles.length + newFiles.length >= maxFiles) {
          alert(`Maximum ${maxFiles} files allowed. Cannot add more files.`);
          break; // Stop processing more files once limit is reached
        }

        if (isValidFileType(file)) {
          // Check if file already exists
          const fileExists = localFiles.some(
            (existingFile) =>
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
                content,
                uploaded: true,
                uploadedAt: new Date(),
              };
              newFiles.push(newFile);

              // Console log the uploaded file details with full content
              console.log("File uploaded:", {
                id: newFile.id,
                name: newFile.name,
                size: newFile.size,
                type: newFile.type,
                uploadedAt: newFile.uploadedAt,
              });

              // Log the complete file content
              console.log(
                "Full file content for",
                newFile.name,
                ":\n",
                content
              );
            } catch (error) {
              console.error("Error reading file:", error);
            }
          }
        }
      }

      setLocalFiles((prev) => [...prev, ...newFiles]);
    },
    [localFiles, maxFiles]
  );

  // Handle drag events
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      handleFileSelect(e.dataTransfer.files);
    },
    [handleFileSelect]
  );

  const handleBrowseClick = () => fileInputRef.current?.click();
  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) =>
    handleFileSelect(e.target.files);

  const removeFile = (fileId: string) =>
    setLocalFiles((prev) => prev.filter((file) => file.id !== fileId));

  const processFiles = async () => {
    setIsProcessing(true);
    try {
      console.log(
        "Processing files:",
        localFiles.map((file) => ({
          id: file.id,
          name: file.name,
          size: file.size,
          type: file.type,
        }))
      );

      addFiles(localFiles);
      console.log(`Successfully processed ${localFiles.length} files and added to global context`);
      alert(`Successfully processed ${localFiles.length} files!`);
    } catch (error) {
      console.error("Error processing files:", error);
      alert("Error processing files. Please try again.");
    } finally {
      setIsProcessing(false);
    }
  };

  // Outer wrappers → compact mode removes the big vertical space
  const outerWrap = compact ? "min-h-0 p-0 bg-transparent" : "min-h-screen bg-gray-50 p-6";
  const widthWrap = compact ? "" : "max-w-4xl mx-auto";

  const cardClasses = "bg-white rounded-lg shadow-lg border-2 border-gray-300 p-5";

  const Card = (
    <div className={cardClasses}>
      <h1 className="text-xl text-black mb-4">Upload files</h1>

      <p className="text-sm text-black mb-6">
        Please drag and drop file(s) in the below area; or browse files by using the button.
      </p>

      {/* Upload Area */}
      <div
        className={`border-2 border-dashed rounded-lg p-12 text-center transition-colors ${
          isDragOver ? "border-gray-400 bg-gray-50" : "border-gray-300 bg-gray-50"
        }`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <div className="mb-4 flex justify-center">
          <svg width="48px" height="48px" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12.5535 2.49392C12.4114 2.33852 12.2106 2.25 12 2.25C11.7894 2.25 11.5886 2.33852 11.4465 2.49392L7.44648 6.86892C7.16698 7.17462 7.18822 7.64902 7.49392 7.92852C7.79963 8.20802 8.27402 8.18678 8.55352 7.88108L11.25 4.9318V16C11.25 16.4142 11.5858 16.75 12 16.75C12.4142 16.75 12.75 16.4142 12.75 16V4.9318L15.4465 7.88108C15.726 8.18678 16.2004 8.20802 16.5061 7.92852C16.8118 7.64902 16.833 7.17462 16.5535 6.86892L12.5535 2.49392Z" fill="#b0b0b0"></path>
            <path d="M3.75 15C3.75 14.5858 3.41422 14.25 3 14.25C2.58579 14.25 2.25 14.5858 2.25 15V15.0549C2.24998 16.4225 2.24996 17.5248 2.36652 18.3918C2.48754 19.2919 2.74643 20.0497 3.34835 20.6516C3.95027 21.2536 4.70814 21.5125 5.60825 21.6335C6.47522 21.75 7.57754 21.75 8.94513 21.75H15.0549C16.4225 21.75 17.5248 21.75 18.3918 21.6335C19.2919 21.5125 20.0497 21.2536 20.6517 20.6516C21.2536 20.0497 21.5125 19.2919 21.6335 18.3918C21.75 17.5248 21.75 16.4225 21.75 15.0549V15C21.75 14.5858 21.4142 14.25 21 14.25C20.5858 14.25 20.25 14.5858 20.25 15C20.25 16.4354 20.2484 17.4365 20.1469 18.1919C20.0482 18.9257 19.8678 19.3142 19.591 19.591C19.3142 19.8678 18.9257 20.0482 18.1919 20.1469C17.4365 20.2484 16.4354 20.25 15 20.25H9C7.56459 20.25 6.56347 20.2484 5.80812 20.1469C5.07435 20.0482 4.68577 19.8678 4.40901 19.591C4.13225 19.3142 3.9518 18.9257 3.85315 18.1919C3.75159 17.4365 3.75 16.4354 3.75 15Z" fill="#b0b0b0"></path>
          </svg>
        </div>

        <p className="text-base text-black mb-4">Drop files here or</p>

        <Button variant="secondary" onClick={handleBrowseClick} className="mb-4">
          BROWSE FILES
        </Button>

        <p className="text-xs text-black">
          Files must be in
          {supportedFileTypes?.map((type: any, index: number) => (
            <span key={type} className="font-medium">
              {type.toUpperCase()}
              {index < supportedFileTypes.length - 1 && ", "}
            </span>
          ))}
          {maxFiles && <span className="block mt-1">Maximum {maxFiles} files allowed.</span>}
        </p>
      </div>

      {/* Hidden file input */}
          {/* 
            IMPORTANT: The accept attribute must match the allowedTypes in isValidFileType function
            Current: accepts .json and .md files
            To change: update both the accept attribute below AND the allowedTypes array above
          */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept={supportedFileTypes?.join(",")}
        onChange={handleFileInputChange}
        className="hidden"
      />

      {/* Upload Progress */}
      {totalCount > 0 && (
        <div className="mt-6">
          <p className="text-base text-black mb-4">
            {uploadedCount} out of {totalCount} files uploaded
            {maxFiles && ` (max ${maxFiles})`}
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
                      <svg className="h-5 w-5 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                        <path
                          fillRule="evenodd"
                          d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                          clipRule="evenodd"
                        />
                      </svg>
                    </div>
                  )}

                  <div>
                    <p className="text-sm text-black">{file.name}</p>
                    <p className="text-xs text-black">{formatFileSize(file.size)}</p>
                  </div>
                </div>

                    {/* Remove button */}
                <button
                  onClick={() => removeFile(file.id)}
                  className="text-gray-400 hover:text-red-500 transition-colors"
                  title="Remove file"
                >
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
            <Button variant="default" onClick={() => setLocalFiles([])} disabled={localFiles.length === 0}>
              Clear All
            </Button>
            <Button variant="primary" disabled={localFiles.length === 0 || isProcessing} onClick={processFiles}>
              {isProcessing ? "Processing..." : "Process Files"}
            </Button>
          </div>
        </div>
      )}
    </div>
  );

  if (compact) {
    // No full-page spacing
    return <div className={outerWrap}><div className={widthWrap}>{Card}</div></div>;
  }

  // Original full-page spacing
  return (
    <div className={outerWrap}>
      <div className={widthWrap}>{Card}</div>
    </div>
  );
};

export default UploadFiles;