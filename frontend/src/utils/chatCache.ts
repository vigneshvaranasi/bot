export type CachedChatMessage = {
  id: string;
  userMessage: string;
  botMessage: string;
};

type CachedChat = {
  chatId: string;
  messages: CachedChatMessage[];
  updatedAt: number;
};

const DB_NAME = "chat-db";
const DB_VERSION = 1;
const STORE_CHATS = "chats";

function keyFor(userKey: string | undefined, chatId: string) {
  const uk = (userKey || "").trim();
  return uk ? `${uk}::${chatId}` : chatId;
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE_CHATS)) {
        const store = db.createObjectStore(STORE_CHATS, { keyPath: "chatId" });
        store.createIndex("updatedAt", "updatedAt", { unique: false });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function loadChatFromCache(chatId: string, userKey?: string): Promise<CachedChatMessage[] | null> {
  try {
    const db = await openDb();
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_CHATS, "readonly");
      const store = tx.objectStore(STORE_CHATS);
      const getReq = store.get(keyFor(userKey, chatId));
      getReq.onsuccess = () => {
        const result = getReq.result as CachedChat | undefined;
        resolve(result ? result.messages : null);
      };
      getReq.onerror = () => reject(getReq.error);
    });
  } catch (e) {
    console.warn("loadChatFromCache failed", e);
    return null;
  }
}

export async function saveChatToCache(
  chatId: string,
  messages: CachedChatMessage[],
  keepMostRecent = 20,
  userKey?: string
): Promise<void> {
  try {
    const db = await openDb();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE_CHATS, "readwrite");
      const store = tx.objectStore(STORE_CHATS);
      const putReq = store.put({ chatId: keyFor(userKey, chatId), messages, updatedAt: Date.now() } as CachedChat);
      putReq.onerror = () => reject(putReq.error);
      putReq.onsuccess = () => resolve();
    });

    await pruneCache(db, keepMostRecent, userKey);
  } catch (e) {
    console.warn("saveChatToCache failed", e);
  }
}

export async function deleteChatFromCache(chatId: string, userKey?: string): Promise<void> {
  try {
    const db = await openDb();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE_CHATS, "readwrite");
      const store = tx.objectStore(STORE_CHATS);
      const delReq = store.delete(keyFor(userKey, chatId));
      delReq.onerror = () => reject(delReq.error);
      delReq.onsuccess = () => resolve();
    });
  } catch (e) {
    console.warn("deleteChatFromCache failed", e);
  }
}

async function pruneCache(db: IDBDatabase, keepMostRecent: number, userKey?: string) {
  if (keepMostRecent <= 0) return;
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE_CHATS, "readwrite");
    const store = tx.objectStore(STORE_CHATS);
    const index = store.index("updatedAt");

    const keys: { key: IDBValidKey; updatedAt: number; chatId: string }[] = [];
    const cursorReq = index.openCursor();
    cursorReq.onsuccess = () => {
      const cursor = cursorReq.result as IDBCursorWithValue | null;
      if (cursor) {
        const val = cursor.value as CachedChat;
        const compositeId = val.chatId || "";
        const hasUser = (userKey || "").trim().length > 0;
        if (!hasUser || compositeId.startsWith(`${(userKey || "").trim()}::`)) {
          keys.push({ key: cursor.primaryKey, updatedAt: val.updatedAt, chatId: compositeId });
        }
        cursor.continue();
      } else {
        const toDelete = Math.max(0, keys.length - keepMostRecent);
        if (toDelete === 0) return resolve();
        let remaining = toDelete;
        for (let i = 0; i < toDelete; i++) {
          const del = store.delete(keys[i].key);
          del.onerror = () => {
            remaining--;
            if (remaining <= 0) resolve();
          };
          del.onsuccess = () => {
            remaining--;
            if (remaining <= 0) resolve();
          };
        }
        if (toDelete > 0 && keys.length === 0) resolve();
      }
    };
    cursorReq.onerror = () => reject(cursorReq.error);
  });
}

export function messagesEqual(a: CachedChatMessage[], b: CachedChatMessage[]) {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    const x = a[i];
    const y = b[i];
    if (x.id !== y.id) return false;
    if (x.userMessage !== y.userMessage) return false;
    if (x.botMessage !== y.botMessage) return false;
  }
  return true;
}

export async function removeAllChatCache(): Promise<void> {
  try {
    const db = await openDb();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE_CHATS, "readwrite");
      const store = tx.objectStore(STORE_CHATS);
      const clearReq = store.clear();
      clearReq.onsuccess = () => resolve();
      clearReq.onerror = () => reject(clearReq.error);
    });
  } catch (e) {
    console.warn("clearChatCache failed", e);
  }
}