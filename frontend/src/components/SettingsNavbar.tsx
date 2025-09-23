import React from 'react';
import InputBox from './ui/InputBox';

interface SettingsNavbarProps {
  searchValue?: string;
  onSearchChange?: (value: string) => void;
  searchPlaceholder?: string;
}

const SettingsNavbar: React.FC<SettingsNavbarProps> = ({
  searchValue = "",
  onSearchChange = () => {},
  searchPlaceholder = "Search"
}) => {
  return (
    <div className="px-4 md:px-6 py-4 bg-gray-100">
      <div className="max-w-screen-2xl mx-auto flex flex-col md:grid md:grid-cols-[1.5fr_1.5fr] gap-4 md:gap-0">
        {/* Logo */}
        <div className="bg-white px-6 md:px-8 py-2 rounded-[10px] text-lg font-low text-gray-900 w-fit">
          Support Bot
        </div>

        {/* Right cell: search + avatar */}
        <div className=" items-center gap-4 justify-end w-full hidden">
          {/* Search */}
          <div className="relative w-full max-w-md md:max-w-none">
            <InputBox
              placeholder={searchPlaceholder}
              variant="primary"
              onChange={onSearchChange}
              value={searchValue}
              icon={
                <svg
                  className="h-5 w-5 text-gray-500"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <circle cx="11" cy="11" r="7" />
                  <line x1="21" y1="21" x2="16.65" y2="16.65" />
                </svg>
              }
              backgroundColor="fff"
              className="border-0 border-b-2 border-gray-400 hover:border-gray-400 focus:border-gray-400 rounded-[5px]"
            />
          </div>

          <div className="w-10 h-10 bg-gray-400 rounded-full flex items-center justify-center flex-shrink-0">
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              className="text-white"
            >
              <path
                d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"
                stroke="currentColor"
                strokeWidth="2"
              />
              <circle
                cx="12"
                cy="7"
                r="4"
                stroke="currentColor"
                strokeWidth="2"
              />
            </svg>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsNavbar;