import { marked } from "marked";
import DOMPurify from "dompurify";
import { useEffect, useState } from "react";

type BubbleProps = {
  variant?: "bot" | "user";
  content: string;
  streaming?: boolean;
};

const Bubble = ({ variant = "bot", content }: BubbleProps) => {
  const variantClasses = {
    bot: "border-none bg-transparent",
    user: "order border-gray-300 bg-bubblegray max-w-3/4",
  };
  const defaultClass = "border border-gray-300 text-gray-900";
  const [renderedContent, setRenderedContent] = useState("");
  const [isProcessing, setIsProcessing] = useState(variant === "bot" && !content);

  marked.setOptions({
    breaks: true,
    gfm: true
  });

  useEffect(() => {
    if (!content) return;

    setIsProcessing(false);
    try {
      const htmlContent = marked.parse(content) as string;
      
      const sanitizedContent = DOMPurify.sanitize(htmlContent, {
        ALLOWED_TAGS: ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 
                      'code', 'pre', 'strong', 'em', 'blockquote', 'br'],
        ADD_ATTR: ['class'],
      });

      setRenderedContent(sanitizedContent);
    } catch (error) {
      console.error('Markdown parsing error:', error);
      setRenderedContent(content);
    }
  }, [content]);

  return (
    <div
      className={`flex ${
        variant === "user" ? "justify-end" : "justify-start"
      } mb-2`}
    >
      <div
        className={`p-2 rounded-lg ${
          variantClasses[variant] || defaultClass
        } ${isProcessing && variant === 'bot' ? 'animate-pulse' : ''}`}
      >
        <div
          className="markdown-body prose prose-sm max-w-none dark:prose-invert"
          dangerouslySetInnerHTML={{ __html: renderedContent }}
        />
      </div>
    </div>
  );
};

export default Bubble;
