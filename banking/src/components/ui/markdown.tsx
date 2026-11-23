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
 *
 * Server messages (frappe.msgprint, frappe.bold) carry a few simple HTML tags. Those are
 * turned into the Markdown equivalent and any other tag is dropped, so the tags are never
 * shown as text and no HTML is ever rendered.
 */
export const htmlToMarkdown = (text: string): string => {
    if (typeof text !== 'string') return text
    return text
        .replace(/<\s*(strong|b)\s*>([\s\S]*?)<\s*\/\s*\1\s*>/gi, '**$2**')
        .replace(/<\s*(em|i)\s*>([\s\S]*?)<\s*\/\s*\1\s*>/gi, '*$2*')
        .replace(/<\s*br\s*\/?\s*>/gi, '\n\n')
        .replace(/<\/?[a-zA-Z][^>]*>/g, '')
}

const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content }) => {
    return <ReactMarkdown
        remarkPlugins={[remarkGfm]}
    >
        {htmlToMarkdown(content)}
    </ReactMarkdown>
}

export default MarkdownRenderer