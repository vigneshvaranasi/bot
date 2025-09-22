export const markdownToText = (markdown: string): string => {
  if (!markdown) return '';

  let text = markdown;

  // Remove code blocks
  text = text.replace(/```[\s\S]*?```/g, ' code block ');
  text = text.replace(/`([^`]+)`/g, '$1');

  // Remove headers
  text = text.replace(/^#{1,6}\s+/gm, '');

  // Remove bold and italic combinations
  text = text.replace(/\*\*\*([^*]+)\*\*\*/g, '$1');
  text = text.replace(/\*\*([^*]+)\*\*/g, '$1');
  text = text.replace(/\*([^*]+)\*/g, '$1'); 
  text = text.replace(/___([^_]+)___/g, '$1');
  text = text.replace(/__([^_]+)__/g, '$1');
  text = text.replace(/_([^_]+)_/g, '$1');

  // Remove strikethrough
  text = text.replace(/~~([^~]+)~~/g, '$1');

  // Remove links but keep the text
  text = text.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
  text = text.replace(/\[([^\]]+)\]\[[^\]]*\]/g, '$1');

  // Remove images
  text = text.replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1 image');

  // Remove horizontal rules
  text = text.replace(/^[-*_]{3,}$/gm, '');

  // Remove blockquotes
  text = text.replace(/^>\s*/gm, '');

  // Convert lists to readable format
  text = text.replace(/^\s*[-*+]\s+/gm, '• ');
  text = text.replace(/^\s*\d+\.\s+/gm, '');

  // Remove HTML tags
  text = text.replace(/<[^>]*>/g, '');

  // Remove table formatting
  text = text.replace(/\|/g, ' ');
  text = text.replace(/^[-:| ]+$/gm, '');

  // Remove markdown special characters
  text = text.replace(/[#*_~`]/g, '');

  // Clean up multiple spaces and newlines
  text = text.replace(/\n{3,}/g, '\n\n');
  text = text.replace(/[ \t]{2,}/g, ' ');

  // Remove leading/trailing whitespace
  text = text.split('\n')
    .map(line => line.trim())
    .filter(line => line.length > 0)
    .join('. ');

  // Final cleanup
  text = text.replace(/\.\./g, '.');
  text = text.replace(/\s+/g, ' ');
  text = text.trim();

  return text;
};