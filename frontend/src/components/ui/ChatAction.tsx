import { useEffect, useRef, useState } from 'react'
import retryIcon from '../../assets/chat-actions/retry.svg'
import thumbsUpIcon from '../../assets/chat-actions/thumbsUp.svg'
import thumbsUpFilledIcon from '../../assets/chat-actions/thumbsUpfill.svg'
import thumbsDownIcon from '../../assets/chat-actions/thumbsDown.svg'
import thumbsDownFilledIcon from '../../assets/chat-actions/thumbsDownfill.svg'
import copyIcon from '../../assets/chat-actions/copy.svg'
import tickIcon from '../../assets/chat-actions/tick.svg'
import speakerIcon from '../../assets/chat-actions/speaker.svg'
import stopIcon from '../../assets/chat-actions/stop.svg'
import type { ResponseMetrics } from '../../utils/metrics'

import { formatDuration } from '../../utils/metrics'

interface ChatActionButtonProps {
  type: 'retry' | 'thumbsUp' | 'thumbsDown' | 'metrics' | 'copy' | 'speaker'
  active?: boolean
  loading?: boolean
  onClick?: () => void
  responseMetrics?: ResponseMetrics
  content?: string
  isSpeaking?: boolean
  onSpeakToggle?: () => void
}

const icons: Record<string, { default?: string; active?: string }> = {
  retry: { default: retryIcon },
  thumbsUp: { default: thumbsUpIcon, active: thumbsUpFilledIcon },
  thumbsDown: { default: thumbsDownIcon, active: thumbsDownFilledIcon },
  copy: { default: copyIcon, active: tickIcon },
  metrics: { default: retryIcon },
  speaker: { default: speakerIcon, active: stopIcon}
}

const tooltips: Record<string, { default: string; active?: string }> = {
  retry: { default: 'Retry' },
  thumbsUp: { default: 'Like' },
  thumbsDown: { default: 'Dislike' },
  copy: { default: 'Copy' },
  metrics: { default: 'Metrics' },
  speaker: { default: 'Read Aloud', active: 'Stop Reading' },
}

export const ChatAction: React.FC<ChatActionButtonProps> = ({
  type,
  active: activeProp,
  loading,
  onClick,
  responseMetrics,
  content,
  isSpeaking,
  onSpeakToggle
}) => {
  const [active, setActive] = useState(false)
  const resetTimerRef = useRef<number | null>(null)

  const iconSet = icons[type]
  const tooltipSet = tooltips[type]

  const isActive = type === 'retry' ? false : type === 'speaker' ? (isSpeaking ?? false) : activeProp ?? active

  const tooltip = type === 'speaker' && isActive && tooltipSet.active ? tooltipSet.active : tooltipSet.default

  const icon =
    type === 'retry'
      ? iconSet.default
      : isActive && iconSet.active
      ? iconSet.active
      : iconSet.default

  function handleClick () {
    if (type === 'copy') {
      setActive(true)
      if (content) {
        navigator.clipboard.writeText(content)
      }
      if (resetTimerRef.current) window.clearTimeout(resetTimerRef.current)
      resetTimerRef.current = window.setTimeout(() => setActive(false), 2000)
    } else if (type === 'speaker') {
      if (onSpeakToggle) {
        onSpeakToggle()
      }
    } else if (type !== 'retry') {
      setActive(prev => !prev)
    }
    if (onClick) onClick()
  }

  useEffect(() => {
    return () => {
      if (resetTimerRef.current) window.clearTimeout(resetTimerRef.current)
    }
  }, [])

  return (
    <div className='relative group inline-flex'>
      <button
        onClick={handleClick}
        disabled={loading && type === 'retry'}
        aria-label={tooltip}
        className='flex items-center justify-center p-1.5
             text-text-tertiary hover:text-text-primary hover:bg-surface-tertiary
             disabled:opacity-50 disabled:cursor-not-allowed
             rounded-md cursor-pointer transition-colors'
      >
        {type === 'metrics' && responseMetrics?.timeToFirstToken ? (
          <p>{formatDuration(responseMetrics.timeToFirstToken)}</p>
        ) : (
          <img
            src={icon}
            alt={tooltip}
            className={`h-5 w-5 icon-adaptive ${
              loading && type === 'retry' ? 'animate-spin' : ''
            }`}
          />
        )}
      </button>

      {/* Tooltip */}
      {type === 'metrics' ? (
        <div
          className='absolute left-full ml-2 top-1/2 -translate-y-1/2
             opacity-0 group-hover:opacity-100 pointer-events-none
             bg-surface-tertiary text-text-primary text-xs rounded px-2 py-1
             transition-opacity duration-200 whitespace-nowrap'
        >
          {responseMetrics &&
          (responseMetrics.timeToFirstToken !== undefined ||
            responseMetrics.totalResponseTime !== undefined ||
            responseMetrics.modelId ||
            responseMetrics.providerType) ? (
            <div className='flex flex-col gap-1'>
              {responseMetrics.timeToFirstToken !== undefined && (
                <p>
                  Time To First Token:{' '}
                  <span className='opacity-75 font-semibold'>
                    {formatDuration(responseMetrics.timeToFirstToken)}
                  </span>
                </p>
              )}
              {responseMetrics.totalResponseTime !== undefined && (
                <p>
                  Response Time:{' '}
                  <span className='opacity-75 font-semibold'>
                    {formatDuration(responseMetrics.totalResponseTime)}
                  </span>
                </p>
              )}
              {responseMetrics.providerType && (
                <p>
                  Provider:{' '}
                  <span className='opacity-75 font-semibold capitalize'>
                    {responseMetrics.providerType}
                  </span>
                </p>
              )}
              {responseMetrics.modelId && (
                <p>
                  Model:{' '}
                  <span className='opacity-75 font-semibold'>
                    {responseMetrics.modelId}
                  </span>
                </p>
              )}
            </div>
          ) : (
            'No metrics available'
          )}
        </div>
      ) : (
        <div
          className='absolute top-full mt-2 left-1/2 -translate-x-1/2
             opacity-0 group-hover:opacity-100 pointer-events-none
             bg-surface-tertiary text-text-primary text-xs rounded px-2 py-1
             transition-opacity duration-200 whitespace-nowrap'
        >
          {loading && type === 'retry' ? 'Retrying...' : tooltip}
        </div>
      )}
    </div>
  )
}
