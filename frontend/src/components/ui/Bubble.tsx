import { marked } from "marked";
import DOMPurify from "dompurify";
import { useEffect, useState } from "react";

type BubbleProps = {
  variant?: "bot" | "user";
  content: string;
};

const Bubble = ({ variant = "bot", content }: BubbleProps) => {
  const variantClasses = {
    bot: "border-none bg-transparent",
    user: "order border-gray-300 bg-bubblegray max-w-3/4",
  };
  const defaultClass = "border border-gray-300 text-gray-900";
  const [renderedContent, setRenderedContent] = useState("");

  useEffect(() => {
    const render = async () => {
      const htmlContent = await marked.parse(content);
      const sanitizedContent = DOMPurify.sanitize(htmlContent);
      setRenderedContent(sanitizedContent);
    };
    render();
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
        }`}
      >
        <div
          className="markdown-body"
          dangerouslySetInnerHTML={{ __html: renderedContent }}
        />
      </div>
    </div>
  );
};

export default Bubble;
