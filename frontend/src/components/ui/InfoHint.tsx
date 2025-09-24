import React from 'react'
import InfoIcon from '../../assets/infoIcon.svg'

type InfoHintProps = {
    text: string;
    icon?: string;
    onClick?: () => any;
    position?: 'top' | 'bottom' | 'left' | 'right';
    gap?: number;
}

const InfoHint: React.FC<InfoHintProps> = ({ text, icon, onClick, position = 'top', gap = 2 }) => {
  const positionClasses = {
    bottom: `top-full mt-[${gap}px] left-1/2 -translate-x-1/2`,
    top: `bottom-full mb-[${gap}px] left-1/2 -translate-x-1/2`,
    right: `left-full ml-[${gap}px] top-1/2 -translate-y-1/2`,
    left: `right-full mr-[${gap}px] top-1/2 -translate-y-1/2`,
  }[position];

  return (
    <button onClick={onClick ? onClick : undefined} className="flex group items-center space-x-2 cursor-pointer relative">
      <img className='w-6' src={icon || InfoIcon} alt="" />
      <p
        className={`z-10 absolute ${positionClasses} w-64
            opacity-0 group-hover:opacity-100 pointer-events-none
            bg-black/80 text-white text-xs rounded px-2 py-1 wrap-break-word
            transition-opacity duration-200 whitespace-normal`}
        >
          {text}
        </p>
    </button>
  )
}

export default InfoHint