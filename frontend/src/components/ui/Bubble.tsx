import { marked } from "marked";
import DOMPurify from "dompurify";
import { useEffect, useState } from "react";

type BubbleProps = {
  variant?: "bot" | "user";
  content: string;
  streaming?: boolean;
  stopped?: boolean;
  statusMessage?: string;
};

const Bubble = ({ variant = "bot", content, streaming = false, stopped = false, statusMessage }: BubbleProps) => {
  const variantClasses = {
    bot: "border-none bg-transparent max-w-[95%] min-w-0",
    user: "border border-0.5 border-gray-200 bg-bubblegray max-w-[75%] px-4 py-2.5 rounded-3xl rounded-br-none",
  };
  const defaultClass = "border border-gray-300 text-gray-900";
  const [renderedContent, setRenderedContent] = useState("");

  marked.setOptions({
    breaks: true,
    gfm: true
  });

  const prepareMarkdownForStreaming = (text: string): string => {
    let t = text;

  t = t.replace(/^(#{1,6})([^#\s])/gm, (_match, hashes, rest) => `${hashes} ${rest}`);

    if (!t.endsWith("\n")) t += "\n";

    const fenceCount = (t.match(/```/g) || []).length;
    if (fenceCount % 2 !== 0) t += "\n```\n";

    const inlineTicks = (t.match(/(?<!`)`(?!`)/g) || []).length;
    if (inlineTicks % 2 !== 0) t += "`";

    t = t.replace(/(:|\.|\?|!|:)\s+(\d+\.)\s/g, "$1\n\n$2 ");
    t = t.replace(/(:|\.|\?|!|:)\s+([*-])\s/g, "$1\n\n$2 ");

    // If a heading line starts with # and is followed by bold text or list markers on the same line,
    // insert a paragraph break so the heading doesn't swallow the following content while streaming.
    // Examples handled:
    // "## Title **Immediate Steps:** 1. ..." -> "## Title\n\n**Immediate Steps:** 1. ..."
    // "### Title 1. Do X" -> "### Title\n\n1. Do X"
    t = t.replace(/^((?:#{1,6})\s[^\n]+?)\s+(?=(\d+\.\s|\*\s|-\s|\*\*))/gm, '$1\n\n');

    return t;
  };

  useEffect(() => {
  if (!content && !streaming) return;
    try {
      const source = streaming ? prepareMarkdownForStreaming(content) : content;
      const htmlContent = marked.parse(source) as string;
      
      const sanitizedContent = DOMPurify.sanitize(htmlContent, {
        ALLOWED_TAGS: [
          'p','h1','h2','h3','h4','h5','h6','ul','ol','li','code','pre','strong','em','blockquote','br','a',
          'table','thead','tbody','tr','th','td'
        ],
        ADD_ATTR: ['class','href','target','rel'],
      });
      setRenderedContent(sanitizedContent);
    } catch (error) {
      console.error('Markdown parsing error:', error);
      setRenderedContent(content);
    }
  }, [content, streaming, variant]);

  const isLoadingStatus = streaming && statusMessage && !content;

  return (
    <div
      className={`flex ${
        variant === "user" ? "justify-end" : "justify-start"
      } ${variant === "user" ? "mb-3" : "mb-1"}`}
    >
      <div
        className={`${
          variantClasses[variant] || defaultClass
        }`}
      >
        {isLoadingStatus ? (
          <div className="flex items-center gap-2">
            <span className="shimmer-text text-base">{statusMessage}</span>
          </div>
        ) : stopped && !content ? (
          <div className="flex items-center gap-1.5 text-gray-400 text-sm italic">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2" /></svg>
            Response stopped
          </div>
        ) : (
          <>
            <div
              className="markdown-body"
              dangerouslySetInnerHTML={{ __html: renderedContent }}
            />
            {stopped && content && (
              <div className="mt-2 pt-2 border-t border-gray-200 text-gray-400 text-xs italic">
                — Response stopped
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default Bubble;
