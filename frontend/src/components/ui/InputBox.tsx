import React from 'react'

type InputBoxProps = {
  value: string
  placeholder?: string
  onChange: (value: any) => void
  onKeyDown?: (e: React.KeyboardEvent<HTMLInputElement>) => void
  icon?: string | React.ReactNode
  className?: string
  variant: 'primary'
  backgroundColor?: string
  type?: 'text' | 'password' | 'email' | 'number'
}

const variantClasses: Record<'primary', string> = {
  primary: 'border-b border-gray-300'
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
  type = 'text'
}: InputBoxProps) => {
  const variantClass = variantClasses[variant]

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
      <input
        type={type}
        value={value}
        placeholder={placeholder}
        onChange={e => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        className={`w-full px-2 py-2 focus:outline-none transition ${
          icon ? 'pl-10' : ''
        } ${variantClass}`}
        style={{ backgroundColor: `#${backgroundColor}` }}
      />
    </div>
  )
}

export default InputBox
