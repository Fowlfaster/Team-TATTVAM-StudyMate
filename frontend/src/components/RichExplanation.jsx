import DOMPurify from 'dompurify'

const allowedTags = ['h2', 'h3', 'h4', 'p', 'ul', 'ol', 'li', 'strong', 'em', 'mark', 'br', 'blockquote', 'code']

export default function RichExplanation({ html = '', className = '' }) {
  const safeHtml = DOMPurify.sanitize(html, {
    ALLOWED_TAGS: allowedTags,
    ALLOWED_ATTR: [],
  })

  return <div className={`rich-explanation ${className}`.trim()} dangerouslySetInnerHTML={{ __html: safeHtml }} />
}
