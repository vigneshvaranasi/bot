import gearIcon from "../assets/Settings.svg";

type SidebarProps = {
  isOpen: boolean;
  onClose: () => void;
};

const pastChats = [
  {
    id: 1,
    title: "499 Issue with PayU",
    date: "2025-08-01",
    description: "Customer reported an issue with PayU payment gateway.",
  },
  {
    id: 2,
    title: "500 Service Unavailable",
    date: "2025-08-02",
    description: "Service was unavailable for 30 minutes.",
  },
  {
    id: 3,
    title: "502 Bad Gateway",
    date: "2025-08-03",
    description: "Received a 502 error from the payment service.",
  },
  {
    id: 4,
    title: "503 Service Unavailable",
    date: "2025-08-04",
    description: "Service was down for maintenance.",
  },
  {
    id: 5,
    title: "504 Gateway Timeout",
    date: "2025-08-05",
    description: "Payment gateway timed out after 60 seconds.",
  },
  {
    id: 6,
    title: "505 HTTP Version Not Supported",
    date: "2025-08-06",
    description: "Payment service does not support HTTP/2.",
  },
  {
    id: 7,
    title: "506 Variant Also Negotiates",
    date: "2025-08-07",
    description: "Payment service returned a 506 error.",
  },
  {
    id: 8,
    title: "507 Insufficient Storage",
    date: "2025-08-08",
    description: "Payment service ran out of storage space.",
  },
  {
    id: 9,
    title: "508 Loop Detected",
    date: "2025-08-09",
    description: "Payment service detected an infinite loop.",
  },
  {
    id: 10,
    title: "509 Bandwidth Limit Exceeded",
    date: "2025-08-10",
    description: "Payment service exceeded its bandwidth limit.",
  },
  {
    id: 11,
    title: "510 Not Extended",
    date: "2025-08-11",
    description: "Payment service requires further extensions.",
  },
  {
    id: 12,
    title: "511 Network Authentication Required",
    date: "2025-08-12",
    description: "Payment service requires network authentication.",
  },
  {
    id: 13,
    title: "512 Custom Error",
    date: "2025-08-13",
    description: "Custom error message from the payment service.",
  },
  {
    id: 14,
    title: "513 Custom Error",
    date: "2025-08-14",
    description: "Another custom error message from the payment service.",
  }
];

function Sidebar({ isOpen, onClose }: SidebarProps) {
  return (
    <div
      className={`left-0 top-0 z-[1000] h-screen bg-gray-50 flex flex-col transition-all duration-300 overflow-hidden ${
        isOpen ? "w-72" : "w-0"
      }`}
    >
      <div className="flex items-center justify-between pt-2 px-4">
        {/* Implement Search Box to search the past chats */}
        <div className="relative">
          <input
            type="text"
            placeholder="Search..."
            className="border-b border-gray-300 rounded-md py-2 px-3 w-full foucus:outline-none focus:ring-0 "
          />
        </div>
        <button
          onClick={onClose}
          className="text-2xl font-bold text-gray-500 hover:text-gray-700 focus:outline-none"
          aria-label="Close Sidebar"
        >
          &times;
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        {pastChats.length === 0 ? (
          <div className="text-gray-400 text-center mt-8">No chats found.</div>
        ) : (
          <ul className="space-y-4">
            {pastChats.map((chat) => (
              <li key={chat.id} className="">
                <div className="text-xs text-[#5c5c5c]">{chat.date}</div>
                <div className="font-medium text-base">{chat.title}</div>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="flex bg-[#eaedef] m-4 p-2 rounded-lg items-center justify-between">
        <div className="flex items-center gap-2">
          <img
            src="https://t3.ftcdn.net/jpg/08/05/28/22/360_F_805282248_LHUxw7t2pnQ7x8lFEsS2IZgK8IGFXePS.jpg"
            className="w-8 rounded-full"
            alt=""
          />
          <p>Username</p>
        </div>
        <img src={gearIcon} className="w-5 rounded-full" alt="" />
      </div>
    </div>
  );
}

export default Sidebar;
