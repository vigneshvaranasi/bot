"use client";

import { useState, useRef, useCallback } from "react";
import { Button } from "./Button";
import { useFileContext } from "../../hooks/useFileContext";
import type { UploadedFile } from "../../store/FileProvider";

// --------------------------
// CSV Parsing Utility
// --------------------------
const parseCSV = (text: string): any[] => {
  const [headerLine, ...rows] = text.split("\n").filter(Boolean);
  const headers = headerLine.split(",").map((h) => h.trim());
  return rows.map((row) => {
    const values = row.split(",").map((v) => v.trim());
    return headers.reduce((obj: any, header, i) => {
      obj[header] = values[i] || "";
      return obj;
    }, {});
  });
};

// --------------------------
// Key-Value Text Parsing Utility
// --------------------------
const parseKeyValueText = (text: string): Record<string, string> => {
  const lines = text.split("\n").filter(Boolean);
  const result: Record<string, string> = {};
  for (const line of lines) {
    const [key, ...rest] = line.split(":");
    if (!key || rest.length === 0) continue;
    result[key.trim()] = rest.join(":").trim();
  }
  return result;
};

// --------------------------
// Normalize Data Schema
// --------------------------
const normalizeSchema = (data: any, fileType: string): any[] => {
  const FIELD_ALIASES = {
    id: ["Incident ID", "id", "incidentId"],
    name: ["Main Issue", "name", "issue", "problem"],
    description: ["text", "description", "details"],
  };

  const mapEntry = (record: any, index: number) => {
    const normalized: any = {};
    for (const [field, aliases] of Object.entries(FIELD_ALIASES)) {
      for (const alias of aliases) {
        if (record[alias] !== undefined) {
          normalized[field] = record[alias];
          break;
        }
      }
      if (normalized[field] === undefined)
        normalized[field] = field === "id" ? index : "";
    }

    // Ensure numeric IDs
    normalized.id = Number.isInteger(normalized.id)
      ? normalized.id
      : (() => {
          const parsedId = parseInt(normalized.id, 10);
          return isNaN(parsedId) ? record["Incident ID"] || index : parsedId;
        })();

    // Parse key-value data in description
    if (normalized.description) {
      const extra = parseKeyValueText(normalized.description);
      Object.assign(normalized, extra);
    }

    return normalized;
  };

  if (fileType === "json")
    return Array.isArray(data) ? data.map(mapEntry) : [mapEntry(data, 0)];
  if (fileType === "csv")
    return data.map((row: any, i: number) => mapEntry(row, i));

  if (fileType === "md" || fileType === "txt") {
    if (typeof data !== "string") return [{ id: 0, description: "" }];

    const lines = data.split(/\r?\n/);
    const sections: string[] = [];
    let current: string[] = [];
    let foundStart = false;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      if (/^[=]{2,}\s*$/.test(line) && i + 1 < lines.length && lines[i + 1].trim().startsWith("Incident ID:")) {
        if (current.length > 0) sections.push(current.join("\n").trim());
        current = [];
        foundStart = true;
        continue;
      }
      if (foundStart) current.push(line);
    }

    if (current.length > 0) sections.push(current.join("\n").trim());

    return sections.map((block, idx) => ({ id: idx, description: block }));
  }

  return [{ id: 0, raw: data }];
};

// --------------------------
// UploadFiles Component Props
// --------------------------
interface UploadFilesProps {
  maxFiles?: number; // Optional: max number of files
  supportedFileTypes?: string[]; // Optional: supported file types
  compact?: boolean; // Optional: compact display
  onFilesUploaded?: (files: UploadedFile[]) => void; // Callback after successful upload
}

// --------------------------
// UploadFiles Component
// --------------------------
const UploadFiles = ({
  maxFiles,
  supportedFileTypes = [".json", ".md", ".csv", ".txt"],
  compact = false,
  onFilesUploaded,
}: UploadFilesProps) => {
  const [pendingFiles, setPendingFiles] = useState<UploadedFile[]>([]);
  const [dragActive, setDragActive] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { addFiles } = useFileContext();

  // --------------------------
  // Format file size for display
  // --------------------------
  const formatSize = (bytes: number): string => {
    if (bytes === 0) return "0 Bytes";
    const units = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(2)} ${units[i]}`;
  };

  // --------------------------
  // Validate supported file type
  // --------------------------
  const isSupportedFile = (file: File) =>
    supportedFileTypes.includes("." + file.name.split(".").pop()?.toLowerCase());

  // --------------------------
  // Read file as text
  // --------------------------
  const readFileAsText = (file: File) =>
    new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => resolve(e.target?.result as string);
      reader.onerror = reject;
      reader.readAsText(file);
    });

  // --------------------------
  // Handle file selection / drag-and-drop
  // --------------------------
  const handleFileSelection = useCallback(
    async (selected: FileList | null) => {
      if (!selected) return;
      const newUploads: UploadedFile[] = [];

      for (const file of Array.from(selected)) {
        // Enforce file limit
        if (maxFiles && pendingFiles.length + newUploads.length >= maxFiles) {
          alert(`You can only upload up to ${maxFiles} files.`);
          break;
        }

        if (!isSupportedFile(file)) {
          alert(`Unsupported file type: ${file.name}`);
          continue;
        }

        const content = await readFileAsText(file);

        // --------------------------
        // Create local file object
        // --------------------------
        newUploads.push({
          id: `file-${Math.random().toString(36).substr(2, 9)}`,
          name: file.name,
          size: file.size,
          type: file.type,
          content,
          uploaded: false, // backend upload status
          ready: true, // UI-ready status
          uploadedAt: new Date(),
        });

        // --------------------------
        // Log file content
        // --------------------------
        console.log("File selected:", file.name, formatSize(file.size));
        console.log("Full content:\n", content);
      }

      setPendingFiles((prev) => [...prev, ...newUploads]);
    },
    [pendingFiles, maxFiles, supportedFileTypes]
  );

  // --------------------------
  // Remove a pending file
  // --------------------------
  const removePendingFile = (id: string) =>
    setPendingFiles((prev) => prev.filter((f) => f.id !== id));

  // --------------------------
  // Upload files to backend and add to global context
  // --------------------------
  const uploadFiles = async () => {
    if (!pendingFiles.length) return;
    setIsUploading(true);

    try {
      const results = await Promise.all(
        pendingFiles.map(async (file) => {
          const ext = file.name.split(".").pop()?.toLowerCase();
          let parsed: any[] = [];
          const content = file.content ?? "";

          try {
            if (ext === "json") parsed = normalizeSchema(JSON.parse(content), "json");
            else if (ext === "csv") parsed = normalizeSchema(parseCSV(content), "csv");
            else parsed = normalizeSchema(content, "md");
          } catch {
            parsed = [{ id: 0, description: content }];
          }

          const response = await fetch("http://localhost:8000/files/save", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ filename: file.name, content: parsed }),
          });

          if (!response.ok) throw new Error(`Upload failed for ${file.name}`);
          const data = await response.json();
          return data.inserted || parsed.length;
        })
      );

      const completed = pendingFiles.map((f) => ({ ...f, uploaded: true }));
      addFiles(completed);
      onFilesUploaded?.(completed);
      setPendingFiles([]);
      alert(`✅ Uploaded ${results.reduce((a, b) => a + b, 0)} records.`);
    } catch (e) {
      console.error(e);
      alert("❌ Upload failed. Check console.");
    } finally {
      setIsUploading(false);
    }
  };

  const outerWrap = compact ? "min-h-0 p-0 bg-transparent" : "min-h-screen bg-gray-50 p-6";
  const widthWrap = compact ? "" : "max-w-4xl mx-auto";
  const cardClasses = "bg-white rounded-lg shadow-lg border-2 border-gray-300 p-5";

  const readyCount = pendingFiles.filter((f) => f.ready).length;
  const totalCount = pendingFiles.length;

  // --------------------------
  // Main JSX
  // --------------------------
  return (
    <div className={outerWrap}>
      <div className={widthWrap}>
        <div className={cardClasses}>
          <h1 className="text-xl text-black mb-4">Upload files</h1>
          <p className="text-sm text-black mb-6">
            Please drag and drop file(s) below, or browse manually.
          </p>

          <div
            className={`border-2 border-dashed rounded-lg p-12 text-center transition-colors ${
              dragActive ? "border-gray-400 bg-gray-50" : "border-gray-300 bg-gray-50"
            }`}
            onDragOver={(e) => {
              e.preventDefault();
              setDragActive(true);
            }}
            onDragLeave={(e) => {
              e.preventDefault();
              setDragActive(false);
            }}
            onDrop={(e) => {
              e.preventDefault();
              setDragActive(false);
              handleFileSelection(e.dataTransfer.files);
            }}
          >
            <div className="mb-4 flex justify-center">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
                <path
                  d="M12.5535 2.49392C12.4114 2.33852 12.2106 2.25 12 2.25C11.7894 2.25 11.5886 2.33852 11.4465 2.49392L7.44648 6.86892C7.16698 7.17462 7.18822 7.64902 7.49392 7.92852C7.79963 8.20802 8.27402 8.18678 8.55352 7.88108L11.25 4.9318V16C11.25 16.4142 11.5858 16.75 12 16.75C12.4142 16.75 12.75 16.4142 12.75 16V4.9318L15.4465 7.88108C15.726 8.18678 16.2004 8.20802 16.5061 7.92852C16.8118 7.64902 16.833 7.17462 16.5535 6.86892L12.5535 2.49392Z"
                  fill="#b0b0b0"
                />
                <path
                  d="M3.75 15C3.75 14.5858 3.41422 14.25 3 14.25C2.58579 14.25 2.25 14.5858 2.25 15V15.0549C2.24998 16.4225 2.24996 17.5248 2.36652 18.3918C2.48754 19.2919 2.74643 20.0497 3.34835 20.6516C3.95027 21.2536 4.70814 21.5125 5.60825 21.6335C6.47522 21.75 7.57754 21.75 8.94513 21.75H15.0549C16.4225 21.75 17.5248 21.75 18.3918 21.6335C19.2919 21.5125 20.0497 21.2536 20.6517 20.6516C21.2536 20.0497 21.5125 19.2919 21.6335 18.3918C21.75 17.5248 21.75 16.4225 21.75 15.0549V15C21.75 14.5858 21.4142 14.25 21 14.25C20.5858 14.25 20.25 14.5858 20.25 15Z"
                  fill="#b0b0b0"
                />
              </svg>
            </div>

            <p className="text-base text-black mb-4">Drop files here or</p>
            <Button variant="secondary" onClick={() => fileInputRef.current?.click()} className="mb-4">
              BROWSE FILES
            </Button>

            <p className="text-xs text-black">
              Supported:
              {supportedFileTypes.map((type, i) => (
                <span key={type} className="font-medium">
                  {" "}
                  {type.toUpperCase()}
                  {i < supportedFileTypes.length - 1 && ","}
                </span>
              ))}
              {maxFiles && <span className="block mt-1">Maximum {maxFiles} files allowed.</span>}
            </p>
          </div>

          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept={supportedFileTypes.join(",")}
            onChange={(e) => handleFileSelection(e.target.files)}
            className="hidden"
          />

          {totalCount > 0 && (
            <div className="mt-6">
              <p className="text-base text-black mb-4">
                {readyCount} of {totalCount} ready to upload
              </p>

              <div className="space-y-3">
                {pendingFiles.map((file) => (
                  <div
                    key={file.id}
                    className="flex items-center justify-between p-3 border border-gray-200 rounded-lg bg-gray-50"
                  >
                    <div className="flex items-center space-x-3">
                      {/* Tick mark for ready files */}
                      {file.ready && (
                        <svg className="h-5 w-5 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                          <path
                            fillRule="evenodd"
                            d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                            clipRule="evenodd"
                          />
                        </svg>
                      )}
                      <div>
                        <p className="text-sm text-black">{file.name}</p>
                        <p className="text-xs text-black">{formatSize(file.size)}</p>
                      </div>
                    </div>

                    <button
                      onClick={() => removePendingFile(file.id)}
                      className="text-gray-400 hover:text-red-500 transition-colors"
                      title="Remove"
                    >
                      ✖
                    </button>
                  </div>
                ))}
              </div>

              <div className="mt-6 flex justify-end space-x-3">
                <Button variant="default" onClick={() => setPendingFiles([])} disabled={isUploading}>
                  Clear All
                </Button>
                <Button variant="primary" onClick={uploadFiles} disabled={isUploading}>
                  {isUploading ? "Uploading..." : "Upload Files"}
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
