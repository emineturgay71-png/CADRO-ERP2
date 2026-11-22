import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface MarkdownRendererProps {
    content: string,
    className?: string
}

/**
 * Renders Markdown content without raw HTML support.
 * rehypeRaw has been removed to prevent stored-XSS through user-controlled
 * fields such as bank account names and transaction descriptions.
 */
const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content }) => {
    return <ReactMarkdown
        remarkPlugins={[remarkGfm]}
    >
        {content}
    </ReactMarkdown>
}

export default MarkdownRenderer