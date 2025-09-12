import React, { useEffect, useRef, useState } from 'react'

type InputBoxProps = {
  value: string
  placeholder?: string
  onChange: (value: any) => void
  onKeyDown?: (e: React.KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>) => void
  icon?: string | React.ReactNode
  className?: string
  variant: 'primary' | 'multiline'
  backgroundColor?: string
  type?: 'text' | 'password' | 'email' | 'number'
  rows?: number
  autoGrow?: boolean
  maxHeight?: number
}

const variantClasses: Record<'primary' | 'multiline', string> = {
  primary: 'border-b border-gray-300',
  multiline:'border border-gray-200 rounded-xl bg-white shadow-sm focus:ring-1 focus:ring-gray-300 focus:border-gray-300'
}

const InputBox = ({
  value,
  placeholder = '',
  onChange,
  onKeyDown,
  icon,
  className = '',
  variant = 'primary',
  backgroundColor = 'fff',
  type = 'text',
  rows = 1,
  autoGrow = true,
  maxHeight = 200
}: InputBoxProps) => {
  const variantClass = variantClasses[variant]
  const textAreaRef = useRef<HTMLTextAreaElement | null>(null)
  const [isOverflowing, setIsOverflowing] = useState(false)

  // Auto resize textarea height based on content
  useEffect(() => {
    if (variant !== 'multiline' || !autoGrow) return
    const el = textAreaRef.current
    if (!el) return
    el.style.height = 'auto'
    const newHeight = Math.min(el.scrollHeight, maxHeight)
    el.style.height = `${newHeight}px`
  setIsOverflowing(el.scrollHeight > maxHeight)
  }, [value, variant, autoGrow, maxHeight])

  const handleKeyDown = (
    e: React.KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    if (variant === 'multiline' && e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      onKeyDown?.(e)
      return
    }
    onKeyDown?.(e)
  }

  return (
    <div className={`relative w-full ${className}`}>
      {icon && (
        <div className='absolute left-3 top-1/2 -translate-y-1/2 text-gray-500'>
          {typeof icon === 'string' ? (
            <img src={icon} className='w-4' alt='' />
          ) : (
            icon
          )}
        </div>
      )}
    {variant === 'multiline' ? (
        <textarea
          ref={textAreaRef}
          value={value}
          placeholder={placeholder}
          onChange={e => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={rows}
          className={`w-full px-3 py-2.5 leading-6 placeholder-gray-400 focus:outline-none transition ${
            icon ? 'pl-10' : ''
          } ${variantClass} resize-none min-h-[44px] ${autoGrow ? (isOverflowing ? 'overflow-y-auto' : 'overflow-y-hidden') : ''}`}
          style={{
            backgroundColor: `#${backgroundColor}`,
            maxHeight: autoGrow ? `${maxHeight}px` : undefined
          }}
        />
      ) : (
        <input
          type={type}
          value={value}
          placeholder={placeholder}
          onChange={e => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          className={`w-full px-2 py-2 focus:outline-none transition ${icon ? 'pl-10' : ''} ${variantClass}`}
          style={{ backgroundColor: `#${backgroundColor}` }}
        />
      )}
    </div>
  )
}

export default InputBox
