import { useState, useEffect, useCallback } from "react";

const STORAGE_KEY = "takeout-queue";
const CHANNEL_NAME = "takeout-queue-sync";

export function useQueue() {
  const [queue, setQueue] = useState<number[]>(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : [];
  });

  useEffect(() => {
    const channel = new BroadcastChannel(CHANNEL_NAME);
    channel.onmessage = (e) => {
      setQueue(e.data);
    };

    const handleStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY && e.newValue) {
        setQueue(JSON.parse(e.newValue));
      }
    };
    window.addEventListener("storage", handleStorage);

    return () => {
      channel.close();
      window.removeEventListener("storage", handleStorage);
    };
  }, []);

  const broadcast = useCallback((next: number[]) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    const channel = new BroadcastChannel(CHANNEL_NAME);
    channel.postMessage(next);
    channel.close();
  }, []);

  const addNumber = useCallback(
    (num: number) => {
      setQueue((prev) => {
        if (prev.includes(num)) return prev;
        const next = [...prev, num];
        broadcast(next);
        return next;
      });
    },
    [broadcast]
  );

  const removeNumber = useCallback(
    (num: number) => {
      setQueue((prev) => {
        const next = prev.filter((n) => n !== num);
        broadcast(next);
        return next;
      });
    },
    [broadcast]
  );

  const clearAll = useCallback(() => {
    setQueue([]);
    broadcast([]);
  }, [broadcast]);

  return { queue, addNumber, removeNumber, clearAll };
}
