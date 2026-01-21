import gearIcon from "../assets/Settings.svg";
import { fuzzyMatch } from "../utils/search";
import { useSidebarContext } from "../hooks/useSidebarContext";
import sidebarImg from "../assets/sidebar.svg";
import searchIcon from "../assets/SearchIcon.svg";
import logoutImg from "../assets/logout.svg";
import threeDotsIcon from "../assets/ThreeDots.svg";
import archiveIcon from "../assets/ArchiveIcon.svg";
import editPencilIcon from "../assets/EditPencilIcon.svg";
import { Link, useNavigate } from "react-router-dom";
import InputBox from "./ui/InputBox";
import { useEffect, useState, useRef, useCallback } from "react";
import { useAuthContext } from "../hooks/useAuthContext";
import { archiveChatById, renameChatById, getAllMyChats } from "../handlers/chatHandler";
import { SkeletonChatList } from "./ui/Skeleton";
import { LoadMoreButton } from "./ui/Pagination";
import { useDelayedLoading } from "../hooks/useDelayedLoading";

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
    triggerRefreshChats
  } = useSidebarContext();
  const [searchInput, setSearchInput] = useState("");
  const { user, logout } = useAuthContext();
  const [activeMenu, setActiveMenu] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const [editingChatId, setEditingChatId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState<string>("");
  const editingInputRef = useRef<HTMLInputElement | null>(null);
  const navigate = useNavigate();

  // Pagination state
  const [hasMore, setHasMore] = useState(false);
  const [totalChats, setTotalChats] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);

  // Delayed loading - only show skeleton after 150ms
  const showSidebarLoading = useDelayedLoading(isSidebarLoading);

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
          setHasMore(response.has_more);
          setTotalChats(response.total);
        } else {
          setChats([]);
          setHasMore(false);
          setTotalChats(0);
        }
      } catch (err) {
        console.error("Failed to fetch chats:", err);
        setChats([]);
        setHasMore(false);
        setTotalChats(0);
      } finally {
        setIsSidebarLoading(false);
      }
    };
    fetchChats();
  }, [user, refreshChatsTick, setChats, setIsSidebarLoading]);

  // Load more chats handler
  const loadMoreChats = useCallback(async () => {
    if (!user || loadingMore || !hasMore) return;

    setLoadingMore(true);
    try {
      const token = localStorage.getItem("token");
      if (!token) return;
      const response = await getAllMyChats(token, CHATS_PAGE_SIZE, chats.length);
      if (response && Array.isArray(response.chats)) {
        const newChats = response.chats.map(
          (chat: { id: string; title: string; updated_at: string }) => ({
            chatId: chat.id,
            chatTitle: chat.title,
            date: chat.updated_at,
          })
        );
        setChats([...chats, ...newChats]);
        setHasMore(response.has_more);
      }
    } catch (err) {
      console.error("Failed to load more chats:", err);
    } finally {
      setLoadingMore(false);
    }
  }, [user, loadingMore, hasMore, chats, setChats]);

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
      className={`left-0 top-0 z-[1000] h-screen bg-gray-50 flex flex-col transition-all duration-300 overflow-hidden ${
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
                backgroundColor="f9fafb"
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
            className="mx-3 mt-2 flex items-center p-1.5 gap-2 rounded-lg hover:bg-gray-200"
          >
            <p className="pb-1 text-2xl">+</p>
            <button className="font-medium " onClick={() => handleLinkClick()}>
              New Chat
            </button>
          </Link>
          <div className="flex-1 overflow-y-auto p-4">
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
                      className={`hover:bg-gray-200 block p-2 rounded-md group ${
                        currentChat?.chatId === chat.chatId && "bg-gray-200"
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
                          className="p-1 rounded-md hover:bg-gray-300 invisible group-hover:visible "
                        >
                          <img src={threeDotsIcon} alt="" className="w-5 max-w-5" />
                        </button>
                      </div>
                    </Link>
                    {activeMenu === chat.chatId && (
                      <div ref={menuRef} className="absolute right-0 top-full mt-1 bg-white border border-gray-200 rounded-md shadow-lg z-10">
                        <button
                          className="flex items-center gap-2 px-2 py-1 hover:bg-gray-100 w-full text-left"
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
                          className="flex items-center gap-2 px-4 py-2 hover:bg-gray-100 w-full text-left"
                          onClick={() => {
                            onArchiveChat(chat.chatId);
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
                {/* Load More button - only show when not searching */}
                {!searchInput && hasMore && (
                  <LoadMoreButton
                    onClick={loadMoreChats}
                    loading={loadingMore}
                    hasMore={hasMore}
                    loadedCount={chats.length}
                    totalCount={totalChats}
                  />
                )}
              </div>
            )}
          </div>
          <div className="flex bg-[#eaedef] mb-6 m-4 p-2 rounded-lg items-center justify-between ">
            <div className="flex items-center gap-2">
              <img
                src="https://t3.ftcdn.net/jpg/08/05/28/22/360_F_805282248_LHUxw7t2pnQ7x8lFEsS2IZgK8IGFXePS.jpg"
                className="w-8 rounded-full"
                alt=""
                title={user?.email || "Guest"}
              />
              <p>{user?.email.split("@")[0] || "Guest"}</p>
            </div>
            <div className="flex items-center gap-2">
              <Link to="/settings" className="hover:bg-gray-300 p-1 rounded">
                <img
                  src={gearIcon}
                  className="w-5 rounded-full cursor-pointer hover:opacity-80"
                  alt="Settings"
                  title="Settings"
                />
              </Link>
              <div className="hover:bg-gray-300 p-1 rounded">
              <img
                src={logoutImg}
                onClick={handleLogout}
                className="w-4 cursor-pointer "
                alt=""
                title="Logout"
              />
              </div>
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
              className="p-2 rounded-md hover:bg-gray-200"
              title="New Chat"
            >
              <p className="text-3xl">+</p>
            </Link>
          </div>
          <div >
            <Link
              to="/settings"
              className="p-2 rounded-md hover:bg-gray-200 block"
              title="Settings"
            >
              <img src={gearIcon} className="w-5 rounded-full" alt="Settings" />
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}

export default Sidebar;
