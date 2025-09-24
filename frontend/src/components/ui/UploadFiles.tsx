import { useState, useRef, useCallback } from "react";
import { Button } from "./Button";
import { useFileContext } from "../../hooks/useFileContext";
import type { UploadedFile } from "../../store/FileProvider";

// Parse CSV into array of objects
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
    // Ensure id is always an integer for backend validation
    if (typeof mapped.id !== "number") {
      // Try to extract a number from string, fallback to index
      const num = parseInt(mapped.id, 10);
      mapped.id = isNaN(num) ? index : num;
    }
    return mapped;
  };

  if (fileType === "json") return Array.isArray(data) ? data.map(normalize) : [normalize(data, 0)];
  if (fileType === "csv") return data.map((row: any, index: number) => normalize(row, index));
  if (fileType === "md" || fileType === "txt") return [{ id: 0, description: data }];
  return [{ id: 0, raw: data }];
};

interface UploadFilesProps {
  maxFiles?: number;
  supportedFileTypes?: string[];
  compact?: boolean;
  onFilesUploaded?: (files: UploadedFile[]) => void;
}

const UploadFiles = ({
  maxFiles,
  supportedFileTypes = [".json", ".md", ".csv", ".txt"],
  compact = false,
  onFilesUploaded,
}: UploadFilesProps) => {
  const [localFiles, setLocalFiles] = useState<UploadedFile[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { addFiles } = useFileContext();

  const isValidFileType = (file: File) => supportedFileTypes.includes("." + file.name.split(".").pop()?.toLowerCase());

  const readFileContent = (file: File) =>
    new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => resolve(e.target?.result as string);
      reader.onerror = reject;
      reader.readAsText(file);
    });

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
          alert(`Unsupported file type: ${file.name}`);
          continue;
        }

        const content = await readFileContent(file);
        // No parsed property in UploadedFile, just store content
        newFiles.push({
          id: `file-${Math.random().toString(36).substr(2, 9)}`,
          name: file.name,
          size: file.size,
          type: file.type,
          content,
          uploaded: false,
          uploadedAt: new Date(),
        });
      }

      setLocalFiles((prev) => [...prev, ...newFiles]);
    },
    [localFiles, maxFiles, supportedFileTypes]
  );

  const processFiles = async () => {
    if (!localFiles.length) return;
    setIsProcessing(true);

    try {
      let totalRecords = 0;

      for (const file of localFiles) {
        // Parse content on the fly before upload

        const ext = file.name.split(".").pop()?.toLowerCase();
        let parsed: any[] = [];
        const fileContent = file.content ?? "";
        try {
          if (ext === "json") parsed = mapSchema(JSON.parse(fileContent), "json");
          else if (ext === "csv") parsed = mapSchema(parseCSV(fileContent), "csv");
          else parsed = mapSchema(fileContent, "md");
        } catch (err) {
          console.error(`Error parsing ${file.name}:`, err);
          parsed = [{ id: 0, description: fileContent }];
        }

        const res = await fetch("http://localhost:8000/files/save", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ filename: file.name, content: parsed }),
        });

        if (!res.ok) throw new Error(`Failed to ingest file: ${file.name}`);

        const data = await res.json();
        totalRecords += data.inserted || parsed.length;
      }

      addFiles(localFiles);
      onFilesUploaded?.(localFiles);
      alert(`✅ Ingested ${totalRecords} records into Qdrant`);
    } catch (err) {
      console.error("Error ingesting files:", err);
      alert("❌ Error ingesting files. Check console for details.");
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className={compact ? "min-h-0 p-0 bg-transparent" : "min-h-screen bg-gray-50 p-6"}>
      <div className={compact ? "" : "max-w-4xl mx-auto"}>
        <div className="bg-white rounded-lg shadow-lg border-2 border-gray-300 p-5">
          <h1 className="text-xl text-black mb-4">Upload Files</h1>
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
            <Button variant="secondary" onClick={() => fileInputRef.current?.click()}>
              Browse Files
            </Button>
          </div>

          <input ref={fileInputRef} type="file" multiple accept={supportedFileTypes.join(",")} onChange={(e) => handleFileSelect(e.target.files)} className="hidden" />

          {localFiles.length > 0 && (
            <div className="mt-6">
              <ul>
                {localFiles.map((file) => (
                  <li key={file.id}>
                    {file.name} ({(file.size / 1024).toFixed(1)} KB)
                  </li>
                ))}
              </ul>
              <div className="mt-4 flex justify-end space-x-3">
                <Button variant="default" onClick={() => setLocalFiles([])}>Clear All</Button>
                <Button variant="primary" onClick={processFiles} disabled={isProcessing}>
                  {isProcessing ? "Processing..." : "Ingest into Qdrant"}
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
