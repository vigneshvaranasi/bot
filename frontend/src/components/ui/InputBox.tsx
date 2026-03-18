import React, { useEffect, useRef, useState } from 'react'

type InputBoxProps = {
  value: string
  placeholder?: string
  onChange: (value: string) => void
  onKeyDown?: (e: React.KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>) => void
  onFocus?: (e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement>) => void
  inputRef?: React.RefObject<HTMLInputElement | HTMLTextAreaElement | null>
  icon?: string | React.ReactNode
  className?: string
  variant: 'primary' | 'multiline'
  backgroundColor?: string
  type?: 'text' | 'password' | 'email' | 'number'
  rows?: number
  autoGrow?: boolean
  maxHeight?: number
  min?: number
  max?: number
  step?: number
  disabled?: boolean
  readOnly?: boolean
}

const variantClasses: Record<'primary' | 'multiline', string> = {
  primary: 'border-b border-gray-300',
  multiline:'border border-gray-200 rounded-xl shadow-sm'
}

const InputBox = ({
  value,
  placeholder = '',
  onChange,
  onKeyDown,
  onFocus,
  inputRef,
  icon,
  className = '',
  variant = 'primary',
  backgroundColor = 'fff',
  type = 'text',
  rows = 1,
  autoGrow = true,
  maxHeight = 200,
  min,
  max,
  step,
  disabled = false,
  readOnly = false
}: InputBoxProps) => {
  const variantClass = variantClasses[variant]
  const textAreaRef = useRef<HTMLTextAreaElement | null>(null)
  const [isOverflowing, setIsOverflowing] = useState(false)
  const isNonEditable = disabled || readOnly

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
    if (isNonEditable) {
      e.preventDefault()
      return
    }
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
          ref={(node) => {
            textAreaRef.current = node
            if (inputRef) inputRef.current = node
          }}
          value={value}
          placeholder={placeholder}
          onChange={e => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={onFocus as React.FocusEventHandler<HTMLTextAreaElement>}
          rows={rows}
          readOnly={readOnly}
          disabled={disabled}
          aria-readonly={readOnly}
          aria-disabled={disabled}
          className={`w-full px-3 py-2.5 leading-6 placeholder-gray-400 focus:outline-none transition ${
            icon ? 'pl-10' : ''
          } ${variantClass} resize-none min-h-[44px] ${autoGrow ? (isOverflowing ? 'overflow-y-auto' : 'overflow-y-hidden') : ''} ${isNonEditable ? 'cursor-not-allowed' : ''} ${backgroundColor === 'surface-secondary' ? 'bg-surface-secondary' : ''}`}
          style={{
            ...(backgroundColor !== 'surface-secondary' ? { backgroundColor: `#${backgroundColor}` } : {}),
            maxHeight: autoGrow ? `${maxHeight}px` : undefined
          }}
        />
      ) : (
        <input
          ref={(node) => {
            if (inputRef) inputRef.current = node
          }}
          type={type}
          value={value}
          placeholder={placeholder}
          onChange={e => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={onFocus as React.FocusEventHandler<HTMLInputElement>}
          step={step}
          min={min}
          max={max}
          readOnly={readOnly}
          disabled={disabled}
          aria-readonly={readOnly}
          aria-disabled={disabled}
          className={`w-full px-2 py-2 focus:outline-none transition ${icon ? 'pl-10' : ''} ${variantClass} ${isNonEditable ? 'cursor-not-allowed' : ''} ${backgroundColor === 'surface-secondary' ? 'bg-surface-secondary' : ''}`}
          style={backgroundColor !== 'surface-secondary' ? { backgroundColor: `#${backgroundColor}` } : undefined}
        />
      )}
    </div>
  )
}

export default InputBox
