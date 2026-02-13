import { fuzzyMatch } from "../utils/search";
import { useSidebarContext } from "../hooks/useSidebarContext";
import sidebarImg from "../assets/sidebar.svg";
import searchIcon from "../assets/SearchIcon.svg";
import threeDotsIcon from "../assets/ThreeDots.svg";
import archiveIcon from "../assets/ArchiveIcon.svg";
import editPencilIcon from "../assets/EditPencilIcon.svg";
import { Link, useNavigate } from "react-router-dom";
import InputBox from "./ui/InputBox";
import { useEffect, useState, useRef } from "react";
import { useAuthContext } from "../hooks/useAuthContext";
import { archiveChatById, renameChatById, getAllMyChats } from "../handlers/chatHandler";
import { ConfirmModal } from "./ui/Modal";
import { SkeletonChatList } from "./ui/Skeleton";
import { useDelayedLoading } from "../hooks/useDelayedLoading";
import { usePaginatedChats } from "../hooks/usePaginatedChats";

const CHATS_PAGE_SIZE = 20;

function Sidebar() {
  const {
    isSidebarOpen,
    toggleSidebar,
    chats,
    setChats,
    currentChat,
    isSidebarLoading,
    setIsSidebarLoading,
    refreshChatsTick,
    triggerRefreshChats,
    chatsPagination,
    setChatsPagination,
    appendChats,
    setIsLoadingMoreChats,
  } = useSidebarContext();
  const [searchInput, setSearchInput] = useState("");
  const { user, logout } = useAuthContext();
  const [activeMenu, setActiveMenu] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const [editingChatId, setEditingChatId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState<string>("");
  const [archiveModalChatId, setArchiveModalChatId] = useState<string | null>(null);
  const editingInputRef = useRef<HTMLInputElement | null>(null);
  const navigate = useNavigate();

  // Refs for infinite scroll
  const bottomSentinelRef = useRef<HTMLDivElement>(null);
  const sidebarListRef = useRef<HTMLDivElement>(null);
  const loadingMoreRef = useRef(false);

  // Delayed loading - only show skeleton after 150ms
  const showSidebarLoading = useDelayedLoading(isSidebarLoading);

  // Use the paginated chats hook
  const { loadMoreChats } = usePaginatedChats({
    currentChats: chats,
    hasMore: chatsPagination.hasMore,
    isLoadingMore: chatsPagination.isLoadingMore,
    setIsLoadingMore: setIsLoadingMoreChats,
    appendChats,
  });

  // All hooks must be called unconditionally at the top (React Rules of Hooks)
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setActiveMenu(null);
      }
    };
    if (activeMenu) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [activeMenu]);

  // Focus the input when entering edit mode
  useEffect(() => {
    if (editingChatId && editingInputRef.current) {
      // Small timeout to ensure the input is mounted
      setTimeout(() => editingInputRef.current && editingInputRef.current.focus(), 0);
    }
  }, [editingChatId]);

  // Fetch chats when user or refresh tick changes
  useEffect(() => {
    if (!user) return;

    const fetchChats = async () => {
      setIsSidebarLoading(true);
      try {
        const token = localStorage.getItem("token");
        if (!token) return;
        const response = await getAllMyChats(token, CHATS_PAGE_SIZE, 0);
        if (response && Array.isArray(response.chats)) {
          setChats(
            response.chats.map((chat: { id: string; title: string; updated_at: string }) => ({
              chatId: chat.id,
              chatTitle: chat.title,
              date: chat.updated_at,
            }))
          );
          // Update pagination state in context
          setChatsPagination({
            hasMore: response.has_more,
            total: response.total,
            offset: response.chats.length,
            isLoadingMore: false,
          });
        } else {
          setChats([]);
          setChatsPagination({
            hasMore: false,
            total: 0,
            offset: 0,
            isLoadingMore: false,
          });
        }
      } catch (err) {
        console.error("Failed to fetch chats:", err);
        setChats([]);
        setChatsPagination({
          hasMore: false,
          total: 0,
          offset: 0,
          isLoadingMore: false,
        });
      } finally {
        setIsSidebarLoading(false);
      }
    };
    fetchChats();
  }, [user, refreshChatsTick, setChats, setIsSidebarLoading, setChatsPagination]);

  // IntersectionObserver for infinite scroll on sidebar chat list
  useEffect(() => {
    const sentinel = bottomSentinelRef.current;
    const container = sidebarListRef.current;

    if (!sentinel || !container || !chatsPagination.hasMore || searchInput) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const [entry] = entries;
        if (
          entry.isIntersecting &&
          chatsPagination.hasMore &&
          !chatsPagination.isLoadingMore &&
          !loadingMoreRef.current
        ) {
          loadingMoreRef.current = true;
          loadMoreChats().finally(() => {
            loadingMoreRef.current = false;
          });
        }
      },
      {
        root: container,
        rootMargin: "0px 0px 100px 0px", // Trigger 100px before reaching the bottom
        threshold: 0.1,
      }
    );

    observer.observe(sentinel);

    return () => {
      observer.disconnect();
    };
  }, [chatsPagination.hasMore, chatsPagination.isLoadingMore, loadMoreChats, searchInput]);

  const handleLogout = () => {
    logout();
  };

  // Early return AFTER all hooks have been called
  if (!user) {
    return (
      <div className="flex justify-center items-center h-screen">
        <p className="text-gray-500">Please log in to view chats.</p>
      </div>
    );
  }

  const onArchiveChat = async (chatId: string) => {
    try {
      const token = localStorage.getItem("token");
      if (!token) {
        console.error("User token is missing");
        return;
      }
      await archiveChatById(token, chatId);
      triggerRefreshChats();
      // If the chat is currently open, close it after archiving
      if (currentChat?.chatId === chatId) {
        navigate("/");
      }
    } catch (error) {
      console.error("Failed to archive chat:", error);
    }
  };

  const onRenameChat = async (chatId: string, title: string) => {
    try {
      const token = localStorage.getItem("token");
      if (!token) {
        console.error("User token is missing");
        return;
      }
      if (!title || title.trim().length === 0) {
        console.error("Title cannot be empty");
        return;
      }
      await renameChatById(token, chatId, title.trim());
      triggerRefreshChats();
    } catch (error) {
      console.error("Failed to rename chat:", error);
    }
  };

  const handleLinkClick = () => {
    if (window.innerWidth < 768) {
      toggleSidebar();
    }
  };

  const filteredChats = searchInput
    ? chats.filter(
        (chat) =>
          fuzzyMatch(chat.chatTitle, searchInput) ||
          (chat.date && fuzzyMatch(chat.date, searchInput))
      )
    : chats;

  return (
    <div
      className={`left-0 top-0 z-[1000] h-screen  flex flex-col transition-all duration-300 overflow-hidden ${
        isSidebarOpen ? "w-full md:w-72" : "w-0 md:w-12"
      }`}
    >
      {isSidebarOpen ? (
        <div className="flex flex-col h-full">
          <div className="flex items-center justify-between pt-2 px-4 gap-2">
            <div className="relative flex-1">
              <InputBox
                placeholder="Search..."
                variant="primary"
                onChange={(value) => {
                  setSearchInput(value);
                }}
                value={searchInput}
                icon={searchIcon}
                backgroundColor="surface-secondary"
              />
            </div>
            <button
              className="p-2 rounded-md hover:bg-gray-200"
              onClick={() => toggleSidebar()}
              title="Close Sidebar"
            >
              <img
                src={sidebarImg}
                alt="Close Sidebar"
                className="w-7 mt-3 md:mt-0 md:w-6"
              />
            </button>
          </div>
          <Link
            onClick={() => handleLinkClick()}
            to={"/"}
            className="mx-3 mt-2 flex items-center p-1.5 py-2 gap-2 rounded-md border border-border-default hover:bg-surface-tertiary transition-colors"
          >
            <svg className="w-5 h-5 text-text-secondary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            <span className="font-medium">New Chat</span>
          </Link>
          <div ref={sidebarListRef} className="flex-1 overflow-y-auto p-4">
            {showSidebarLoading && chats.length === 0 ? (
              <SkeletonChatList count={6} />
            ) : filteredChats.length === 0 ? (
              <div className="text-gray-400 text-center mt-8">
                No chats found.
              </div>
            ) : (
              <div className="space-y-1">
                {filteredChats.map((chat) => (
                  <div key={chat.chatId} className="relative cursor-pointer">
                    <Link
                      className={`block p-2 rounded-md group transition-colors ${
                        currentChat?.chatId === chat.chatId
                          ? "bg-surface-primary shadow-sm border border-transparent"
                          : "hover:bg-surface-tertiary border border-transparent"
                      }`}
                      to={`/${chat.chatId}`}
                      onClick={() => {
                        handleLinkClick();
                      }}
                    >
                      <div className="text-xs text-[#5c5c5c]">
                        {chat.date
                          ? new Date(chat.date).toLocaleDateString("en-US", {
                              year: "numeric",
                              month: "short",
                              day: "numeric",
                            })
                          : ""}
                      </div>
                      <div className="flex justify-between items-start font-medium text-base">
                        {editingChatId === chat.chatId ? (
                          <input
                            ref={editingInputRef}
                            className="truncate bg-white border border-gray-300 rounded px-1"
                            value={editingTitle}
                            onClick={(e) => {
                              e.stopPropagation();
                            }}
                            onMouseDown={(e) => {
                              e.stopPropagation();
                            }}
                            onChange={(e) => setEditingTitle(e.target.value)}
                            onBlur={() => {
                              setEditingChatId(null);
                            }}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") {
                                e.preventDefault();
                                e.stopPropagation();
                                onRenameChat(chat.chatId, editingTitle);
                                setEditingChatId(null);
                              } else if (e.key === "Escape") {
                                setEditingChatId(null);
                              }
                            }}
                          />
                        ) : (
                          <p className="truncate">{chat.chatTitle}</p>
                        )}
                        <button
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            setActiveMenu(activeMenu === chat.chatId ? null : chat.chatId);
                          }}
                          className={`p-1 rounded-md hover:bg-gray-300 transition-opacity ${
                            currentChat?.chatId === chat.chatId
                              ? "opacity-70"
                              : "opacity-0 group-hover:opacity-100"
                          }`}
                        >
                          <img src={threeDotsIcon} alt="" className="w-5 max-w-5" />
                        </button>
                      </div>
                    </Link>
                    {activeMenu === chat.chatId && (
                      <div ref={menuRef} className="absolute right-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-dropdown p-1 min-w-[140px] z-10">
                        <button
                          className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-gray-100 w-full text-left rounded-md rounded-tl-md rounded-tr-md"
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            // start editing this chat title
                            setEditingTitle(chat.chatTitle || "");
                            setEditingChatId(chat.chatId);
                            setActiveMenu(null);
                          }}
                        >
                          <img
                            src={editPencilIcon}
                            alt="Edit"
                            className="w-4"
                          />
                          Rename
                        </button>
                        <button
                          className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-gray-100 w-full text-left rounded-md rounded-bl-md rounded-br-md"
                          onClick={() => {
                            setArchiveModalChatId(chat.chatId);
                            setActiveMenu(null);
                          }}
                        >
                          <img
                            src={archiveIcon}
                            alt="Archive"
                            className="w-4"
                          />
                          Archive
                        </button>
                      </div>
                    )}
                  </div>
                ))}

                {/* Bottom sentinel for infinite scroll - only show when not searching */}
                {!searchInput && chatsPagination.hasMore && (
                  <div ref={bottomSentinelRef} className="h-1" data-bottom-sentinel />
                )}

                {/* Loading indicator for loading more chats */}
                {!searchInput && chatsPagination.isLoadingMore && (
                  <div className="flex justify-center py-3">
                    <div className="flex items-center gap-2 text-gray-500 text-sm">
                      <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      <span>Loading...</span>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
          <div className="flex bg-surface-tertiary border border-border-subtle mb-6 m-4 p-2 rounded-lg items-center justify-between ">
            <div className="flex items-center gap-2">
              <div
                className="w-8 h-8 rounded-full bg-gray-600 text-text-inverse flex items-center justify-center text-xs font-semibold select-none"
                title={user?.email || "Guest"}
              >
                {(user?.email || "GU").slice(0, 2).toUpperCase()}
              </div>
              <p>{user?.email.split("@")[0] || "Guest"}</p>
            </div>
            <div className="flex items-center gap-2">
              <Link to="/settings" className="hover:bg-gray-300 p-1.5 rounded cursor-pointer" title="Settings">
                <svg className="w-5 h-5 text-gray-700" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="3" />
                  <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z" />
                </svg>
              </Link>
              <button onClick={handleLogout} className="hover:bg-gray-300 p-1.5 rounded cursor-pointer" title="Logout">
                <svg className="w-5 h-5 text-gray-700" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" />
                  <polyline points="16 17 21 12 16 7" />
                  <line x1="21" y1="12" x2="9" y2="12" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="flex flex-1 flex-col justify-between items-center gap-2 py-2 pb-6">
          <div className="flex items-center flex-col">
            <button
              className="p-2 rounded-md hover:bg-gray-200 cursor-pointer"
              onClick={() => toggleSidebar()}
              title={isSidebarOpen ? "Close Sidebar" : "Open Sidebar"}
            >
              <img src={sidebarImg} alt="Close Sidebar" className="w-6" />
            </button>
            <Link
              to={"/"}
              className="p-2 rounded-md hover:bg-surface-tertiary transition-colors"
              title="New Chat"
            >
              <svg className="w-6 h-6 text-text-secondary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
            </Link>
          </div>
          <div >
            <Link
              to="/settings"
              className="p-2 rounded-md hover:bg-gray-200 block"
              title="Settings"
            >
              <svg className="w-5 h-5 text-gray-700" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="3" />
                <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z" />
              </svg>
            </Link>
          </div>
        </div>
      )}

      <ConfirmModal
        isOpen={archiveModalChatId !== null}
        onClose={() => setArchiveModalChatId(null)}
        onConfirm={() => {
          if (archiveModalChatId) {
            onArchiveChat(archiveModalChatId);
          }
          setArchiveModalChatId(null);
        }}
        title="Archive Chat"
        message="Are you sure you want to archive this chat? You can find it in your archived chats later."
        confirmLabel="Archive"
        cancelLabel="Cancel"
        confirmVariant="danger"
      />
    </div>
  );
}

export default Sidebar;
