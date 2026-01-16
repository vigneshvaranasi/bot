import { useState } from "react";
import { Outlet, useNavigate } from "react-router-dom";
import SettingsNav from "./SettingsNav";

const SettingsLayout = () => {
  const [navOpen, setNavOpen] = useState(false);
  const navigate = useNavigate();

  const pageTitle = "Settings";

  const closeNav = () => setNavOpen(false);
  const openNav = () => setNavOpen(true);

  return (
    <div className="min-h-screen bg-gray-50 w-full overflow-x-hidden">
      <div className="bg-white/95 backdrop-blur border-b border-gray-200 sticky top-0 z-30">
        <div className="mx-auto max-w-7xl px-4 py-3 sm:px-6 lg:px-8 flex items-center gap-3">
          <div
            className="bg-transparent hover:bg-gray-100 text-gray-900 px-1 md:px-2 py-2 rounded-md cursor-pointer"
            onClick={() => navigate("/")}
          >
            ← <span className="hidden md:inline">Back</span>
          </div>
          <h1 className="text-base sm:text-lg font-semibold text-gray-900 flex-1 truncate">
            {pageTitle}
          </h1>
          <div
            className="md:hidden text-black px-3 py-2 flex items-center gap-2"
            onClick={openNav}
            aria-label="Open settings menu"
            title="Open settings menu"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="w-5 h-5"
            >
              <line x1="3" y1="6" x2="21" y2="6" />
              <line x1="3" y1="12" x2="21" y2="12" />
              <line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8 flex gap-6">
        <aside className="w-64 shrink-0 hidden md:block">
          <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm sticky top-20">
            <SettingsNav />
          </div>
        </aside>
        <main className="flex-1 min-w-0">
          <div className="bg-white border border-gray-200 rounded-lg p-4 sm:p-6 shadow-sm">
            <Outlet />
          </div>
        </main>
      </div>

      {navOpen ? (
        <div className="fixed inset-0 z-50 bg-white flex flex-col">
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
            <div className="flex flex-row items-center gap-3">
              <div
                className="bg-transparent hover:bg-gray-100 text-gray-900 px-1 md:px-2 py-2 rounded-md cursor-pointer"
                onClick={() => navigate("/")}
              >
                ← <span className="hidden md:inline">Back</span>
              </div>
              <h2 className="text-md font-semibold text-gray-900">Settings</h2>
            </div>
            <div
              className="bg-transparent hover:bg-gray-100 text-gray-500 p-2 rounded-full cursor-pointer"
              onClick={closeNav}
              aria-label="Close menu"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="w-6 h-6"
              >
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            <SettingsNav onNavigate={closeNav} />
          </div>
        </div>
      ) : null}
    </div>
  );
};

export default SettingsLayout;
