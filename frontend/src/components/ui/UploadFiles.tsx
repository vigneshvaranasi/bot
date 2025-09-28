import { useState, useRef, useCallback } from "react";
import { Button } from "./Button";
import { useFileContext } from "../../hooks/useFileContext";
import type { UploadedFile } from "../../store/FileProvider";

// --- CSV parser ---
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

// --- Parse text block like Markdown or TXT ---
const parseTextBlock = (text: string): Record<string, string> => {
  const lines = text.split("\n").filter(Boolean);
  const obj: Record<string, string> = {};
  for (const line of lines) {
    const [key, ...rest] = line.split(":");
    if (!key || rest.length === 0) continue;
    obj[key.trim()] = rest.join(":").trim();
  }
  return obj;
};

// --- Schema mapper ---
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

    mapped.id = Number.isInteger(mapped.id)
      ? mapped.id
      : (() => {
          const num = parseInt(mapped.id, 10);
          return isNaN(num) ? item["Incident ID"] || index : num;
        })();

    if (mapped.description) {
      const parsedDetails = parseTextBlock(mapped.description);
      Object.assign(mapped, parsedDetails);
    }

    return mapped;
  };

  if (fileType === "json") return Array.isArray(data) ? data.map(normalize) : [normalize(data, 0)];
  if (fileType === "csv") return data.map((row: any, index: number) => normalize(row, index));
  if (fileType === "md" || fileType === "txt") {
    if (typeof data !== "string") return [{ id: 0, description: "" }];
    const lines = data.split(/\r?\n/);
    const incidents: string[] = [];
    let current: string[] = [];
    let foundFirst = false;
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      if (/^[=]{2,}\s*$/.test(line) && i + 1 < lines.length && lines[i + 1].trim().startsWith("Incident ID:")) {
        if (current.length > 0) {
          incidents.push(current.join("\n").trim());
        }
        current = [];
        foundFirst = true;
        continue;
      }
      if (foundFirst) {
        current.push(line);
      }
    }
    if (current.length > 0) {
      incidents.push(current.join("\n").trim());
    }
    return incidents.filter((block) => block.length > 0).map((block, idx) => ({ id: idx, description: block }));
  }
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

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  const isValidFileType = (file: File) =>
    supportedFileTypes.includes("." + file.name.split(".").pop()?.toLowerCase());

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

  const removeFile = (fileId: string) =>
    setLocalFiles((prev) => prev.filter((file) => file.id !== fileId));

  const processFiles = async () => {
    if (!localFiles.length) return;
    setIsProcessing(true);

    try {
      let totalRecords = 0;

      const results = await Promise.all(
        localFiles.map(async (file) => {
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

          console.log("👉 Sending payload:", { filename: file.name, content: parsed });

          const res = await fetch("http://localhost:8000/files/save", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ filename: file.name, content: parsed }),
          });

          if (!res.ok) {
            const errorText = await res.text();
            throw new Error(`Failed to ingest file: ${file.name}. Server says: ${errorText}`);
          }

          const data = await res.json();
          return data.inserted || parsed.length;
        })
      );

      totalRecords = results.reduce((sum, n) => sum + n, 0);

      addFiles(localFiles);
      onFilesUploaded?.(localFiles);
      alert(`✅ Ingested ${totalRecords} records into Qdrant`);
    } catch (err) {
      console.error("❌ Error ingesting files:", err);
      alert("❌ Error ingesting files. Check console for details.");
    } finally {
      setIsProcessing(false);
    }
  };

  // --- UI ---
  const outerWrap = compact ? "min-h-0 p-0 bg-transparent" : "min-h-screen bg-gray-50 p-6";
  const widthWrap = compact ? "" : "max-w-4xl mx-auto";
  const cardClasses = "bg-white rounded-lg shadow-lg border-2 border-gray-300 p-5";

  return (
    <div className={outerWrap}>
      <div className={widthWrap}>
        <div className={cardClasses}>
          <h1 className="text-xl text-black mb-4">Upload Files</h1>
          <p className="text-sm text-black mb-6">
            Please drag and drop file(s) or browse to upload. Supports{" "}
            {supportedFileTypes.join(", ")}
          </p>

          {/* Drop Area */}
          <div
            className={`border-2 border-dashed rounded-lg p-12 text-center transition-colors ${
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
              <p className="text-base text-black mb-4">
                {localFiles.length} file(s) ready for ingestion
              </p>

              {/* File List */}
              <div className="space-y-3">
                {localFiles.map((file) => (
                  <div
                    key={file.id}
                    className="flex items-center justify-between p-3 border border-gray-200 rounded-lg bg-gray-50"
                  >
                    <div>
                      <p className="text-sm text-black">{file.name}</p>
                      <p className="text-xs text-black">{formatFileSize(file.size)}</p>
                    </div>
                    <button
                      onClick={() => removeFile(file.id)}
                      className="text-gray-400 hover:text-red-500 transition-colors"
                      title="Remove file"
                    >
                      ✖
                    </button>
                  </div>
                ))}
              </div>

              {/* Actions */}
              <div className="mt-6 flex justify-end space-x-3">
                <Button variant="default" onClick={() => setLocalFiles([])} disabled={isProcessing}>
                  Clear All
                </Button>
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
