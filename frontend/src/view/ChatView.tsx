import Navbar from "../components/Navbar";
import Bubble from "../components/ui/Bubble";

const ChatView = () => {
  return (
    <div className="flex flex-col max-h-screen">
      <Navbar />
      <div className={`p-4 overflow-y-auto`}>
        <div className={`space-y-4`}>
          <Bubble variant="bot" content="Hello, how can I help you today?" />
          <Bubble variant="user" content="I am getting a status code 499 when connecting to PayU Service, how to solve it?" />
          <Bubble
            variant="bot"
            content="The HTTP 499 error indicates that the client closed the connection before the server could respond. It commonly occurs when:

- The server takes longer to respond than the client's timeout threshold
- Network latency causes a delay in response reception
- The client forcibly disconnects or retries before server reply

## Solution Strategy:

### Plan A: Adjust Client Timeout Settings

Step 1: Identify current timeout threshold in the client system

Step 2: Increase it to a recommended value (e.g., 6–8 seconds)

Step 3: Re-test the request cycle

**Fallback:**

- Use exponential backoff for retries

- Enable async background processing for non-critical API calls

### Plan B: Investigate Backend Latency

Step 1: Trace request lifecycle in API gateway logs

Step 2: Correlate timestamp with downstream service metrics (e.g., Banking API)

Step 3: Identify if third-party latency contributed to delay

Fallback:

- Optimize response time of backend services

- Consider caching frequent responses

### Plan C: Detect Premature Client Disconnects

Step 1: Check for app/browser-triggered disconnects

Step 2: Review user agents or platforms with abnormal patterns

Step 3: Apply client-level patch or browser compatibility workaround

Would you like to:

- View related incidents
- Log this as a new case
- Save this strategy to ticket"
          />
        </div>
      </div>
      <div className={`flex p-4 border-t border-gray-200`}>
        <input
          type="text"
          placeholder="Type your message..."
          className={`w-full p-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500`}
        />
        <button
          className={`ml-2 px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500`}
        >
          Send
        </button>
      </div>
    </div>
  );
};

export default ChatView;
