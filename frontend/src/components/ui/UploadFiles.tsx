import { useState, useRef, useCallback } from "react";
import { Button } from "./Button";
import { useFileContext } from "../../hooks/useFileContext";
import type { UploadedFile } from "../../store/FileProvider";

// Parse CSV text into array of objects
const parseCSV = (text: string): any[] => {
  const [headerLine, ...lines] = text.split("\n").filter(Boolean);
  const headers = headerLine.split(",").map((h) => h.trim());

  return lines.map((line) => {
    const values = line.split(",").map((v) => v.trim());
    return headers.reduce((obj: any, header, i) => {
      obj[header] = values[i] || "";
      return obj;
    }, {});
  });
};

// Schema Mapper
const mapSchema = (data: any, fileType: string): any[] => {
  const SCHEMA = {
    id: ["Incident ID", "id", "incidentId"],
    name: ["Main Issue", "name", "issue", "problem"],
    description: ["text", "description", "details"],
  };

  const normalize = (item: any, index: number) => {
    const mapped: any = {};
    for (const [key, aliases] of Object.entries(SCHEMA)) {
      for (const alias of aliases) {
        if (item[alias] !== undefined) {
          mapped[key] = item[alias];
          break;
        }
      }
      if (mapped[key] === undefined) {
        mapped[key] = key === "id" ? index : "";
      }
    }
    return mapped;
  };

  if (fileType === "json") {
    return Array.isArray(data) ? data.map(normalize) : [normalize(data, 0)];
  }

  if (fileType === "csv") {
    return data.map((row: any, index: number) => normalize(row, index));
  }

  if (fileType === "md" || fileType === "txt") {
    return [{ id: Date.now(), description: data }];
  }

  return [{ id: Date.now(), raw: data }];
};

interface UploadFilesProps {
  maxFiles?: number;
  supportedFileTypes?: string[];
  compact?: boolean;
  onFilesUploaded?: (files: UploadedFile[]) => void;
}

const UploadFiles = ({
  maxFiles,
  supportedFileTypes = [".json", ".md", ".csv"],
  compact = false,
  onFilesUploaded,
}: UploadFilesProps) => {
  const [localFiles, setLocalFiles] = useState<UploadedFile[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { addFiles } = useFileContext();

  const isValidFileType = (file: File): boolean => {
    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    return supportedFileTypes.includes(ext);
  };

  const readFileContent = (file: File): Promise<string> =>
    new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => resolve(e.target?.result as string);
      reader.onerror = reject;
      reader.readAsText(file);
    });

  // Handle file selection
  const handleFileSelect = useCallback(
    async (selectedFiles: FileList | null) => {
      if (!selectedFiles) return;

      const newFiles: UploadedFile[] = [];

      for (const file of Array.from(selectedFiles)) {
        if (maxFiles && localFiles.length + newFiles.length >= maxFiles) {
          alert(`Maximum ${maxFiles} files allowed.`);
          break;
        }

        if (!isValidFileType(file)) {
          alert(`File type not supported: ${file.name}`);
          continue;
        }

        const content = await readFileContent(file);
        let parsed: any[] = [];
        const ext = file.name.split(".").pop()?.toLowerCase();

        try {
          if (ext === "json") parsed = mapSchema(JSON.parse(content), "json");
          else if (ext === "csv") parsed = mapSchema(parseCSV(content), "csv");
          else if (ext === "md" || ext === "txt") parsed = mapSchema(content, "md");
        } catch (err) {
          console.error(`Error parsing ${file.name}:`, err);
          parsed = [{ id: Date.now(), raw: content }];
        }

        newFiles.push({
          id: Math.random().toString(36).substr(2, 9),
          name: file.name,
          size: file.size,
          type: file.type,
          content,
          parsed,
          uploaded: true,
          uploadedAt: new Date(),
        });
      }

      setLocalFiles((prev) => [...prev, ...newFiles]);
    },
    [localFiles, maxFiles, supportedFileTypes]
  );

  // Save parsed files to FastAPI backend
  const processFiles = async () => {
    setIsProcessing(true);
    try {
      for (const file of localFiles) {
        const response = await fetch("http://localhost:5000/save-file", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            filename: file.name.replace(/\.[^/.]+$/, ".json"),
            content: file.parsed,
          }),
        });

        if (!response.ok) throw new Error("Failed to save file");
      }

      addFiles(localFiles);
      onFilesUploaded?.(localFiles);

      alert(`Saved ${localFiles.length} files into /data/`);
    } catch (err) {
      console.error("Error saving files:", err);
      alert("Error saving files. Please try again.");
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className={compact ? "min-h-0 p-0 bg-transparent" : "min-h-screen bg-gray-50 p-6"}>
      <div className={compact ? "" : "max-w-4xl mx-auto"}>
        <div className="bg-white rounded-lg shadow-lg border-2 border-gray-300 p-5">
          <h1 className="text-xl text-black mb-4">Upload Files</h1>
          <p className="text-sm text-black mb-6">Drag & drop or browse files below.</p>

          <div
            className={`border-2 border-dashed rounded-lg p-12 text-center ${
              isDragOver ? "border-gray-400 bg-gray-50" : "border-gray-300 bg-gray-50"
            }`}
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragOver(true);
            }}
            onDragLeave={(e) => {
              e.preventDefault();
              setIsDragOver(false);
            }}
            onDrop={(e) => {
              e.preventDefault();
              setIsDragOver(false);
              handleFileSelect(e.dataTransfer.files);
            }}
          >
            <p className="text-base text-black mb-4">Drop files here or</p>
            <Button variant="secondary" onClick={() => fileInputRef.current?.click()} className="mb-4">
              Browse Files
            </Button>
            <p className="text-xs text-black">
              Supported: {supportedFileTypes.join(", ")}
              {maxFiles && <span className="block mt-1">Max {maxFiles} files</span>}
            </p>
          </div>

          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept={supportedFileTypes.join(",")}
            onChange={(e) => handleFileSelect(e.target.files)}
            className="hidden"
          />

          {localFiles.length > 0 && (
            <div className="mt-6">
              <p className="text-base text-black mb-4">{localFiles.length} file(s) ready</p>
              <ul className="space-y-2">
                {localFiles.map((file) => (
                  <li key={file.id} className="flex justify-between bg-gray-100 p-2 rounded">
                    <span>
                      {file.name} ({(file.size / 1024).toFixed(1)} KB)
                    </span>
                    <Button
                      variant="ghost"
                      onClick={() => setLocalFiles((prev) => prev.filter((f) => f.id !== file.id))}
                    >
                      Remove
                    </Button>
                  </li>
                ))}
              </ul>
              <div className="mt-4 flex justify-end space-x-3">
                <Button variant="default" onClick={() => setLocalFiles([])}>
                  Clear All
                </Button>
                <Button variant="primary" disabled={isProcessing} onClick={processFiles}>
                  {isProcessing ? "Processing..." : "Save"}
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