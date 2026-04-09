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
  primary: 'border-b border-border-strong',
  multiline:'border border-border-default rounded-xl shadow-sm'
}

const resolveBackgroundColor = (color: string) => {
  if (color === 'transparent') return color
  if (
    color.startsWith('#') ||
    color.startsWith('var(') ||
    color.startsWith('rgb') ||
    color.startsWith('hsl')
  ) {
    return color
  }
  if (/^[0-9a-fA-F]{3,8}$/.test(color)) {
    return `#${color}`
  }
  return `var(--color-${color})`
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
  backgroundColor = 'surface-primary',
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
  const resolvedBackgroundColor = resolveBackgroundColor(backgroundColor)

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
        <div className='absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary'>
          {typeof icon === 'string' ? (
            <img src={icon} className='w-4 icon-adaptive' alt='' />
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
          className={`w-full px-3 py-2.5 leading-6 text-text-primary placeholder-text-tertiary focus:outline-none transition ${
            icon ? 'pl-10' : ''
          } ${variantClass} resize-none min-h-[44px] ${autoGrow ? (isOverflowing ? 'overflow-y-auto' : 'overflow-y-hidden') : ''} ${isNonEditable ? 'cursor-not-allowed' : ''}`}
          style={{
            backgroundColor: resolvedBackgroundColor,
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
          className={`w-full px-2 py-2 text-text-primary placeholder-text-tertiary focus:outline-none transition ${icon ? 'pl-10' : ''} ${variantClass} ${isNonEditable ? 'cursor-not-allowed' : ''}`}
          style={{ backgroundColor: resolvedBackgroundColor }}
        />
      )}
    </div>
  )
}

export default InputBox
