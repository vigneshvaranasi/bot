export type Model = "gemma3:1b" | "gemma3:4b" | "gemini-2.0-flash" | "gemini-2.5-flash" | "gemini-2.0-flash-lite-001" | "gemini-2.5-pro";

export type Settings = {
  deny_words: string;
  model: Model;
  temperature: string;
  langfuse_enabled: boolean;
}

export type FileRecord = {
  fileName: string;
  fileType: string;
  size: string;
  lastUpdated: string;
  id: string;
}

export type DenyWordRecord ={
  id: string;
  word: string;
}